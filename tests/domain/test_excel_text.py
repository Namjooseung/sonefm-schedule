from app.domain.excel_text import (
    format_cell_text,
    infer_slots,
    match_names,
    normalize_name,
    parse_cell_text,
)

from .helpers import D


# ── 칸 글자 해석 ──────────────────────────────────

def test_본방_회차():
    p = parse_cell_text("마을살이정류장_23화")
    assert (p.name, p.kind, p.episode) == ("마을살이정류장", "본방", 23)


def test_재방_표시():
    p = parse_cell_text("러너스 해피에코_26화(재)")
    assert (p.name, p.kind, p.episode) == ("러너스 해피에코", "재방", 26)
    p = parse_cell_text("[미디어 동아리_ESG](재)")
    assert (p.name, p.kind, p.episode) == ("[미디어 동아리_ESG]", "재방", None)


def test_회차_없는_프로그램과_대괄호_이름():
    p = parse_cell_text("963 음악쌀롱")
    assert (p.name, p.kind, p.episode) == ("963 음악쌀롱", "본방", None)
    p = parse_cell_text("[우리동네안테나](광주FM)_40화")
    assert p.name == "[우리동네안테나](광주FM)" and p.episode == 40


def test_줄바꿈과_공백은_한칸으로():
    p = parse_cell_text("[우리동네안테나](단원FM) \n지구는 오늘도_12화")
    assert p.name == "[우리동네안테나](단원FM) 지구는 오늘도" and p.episode == 12
    assert normalize_name("  그 사이   음악 ") == "그 사이 음악"


def test_빈칸과_오류값():
    assert parse_cell_text(None) is None
    assert parse_cell_text("   ") is None
    assert parse_cell_text("#REF!").error
    assert parse_cell_text("#N/A").error


# ── 칸 글자 만들기 (내보내기) ─────────────────────

def test_글자_만들기():
    assert format_cell_text("마을살이정류장", "본방", 23, True) == "마을살이정류장_23화"
    assert format_cell_text("러너스 해피에코", "재방", 26, True) == "러너스 해피에코_26화(재)"
    assert format_cell_text("963 음악쌀롱", "본방", 3, False) == "963 음악쌀롱"
    assert format_cell_text("[미디어 동아리_ESG]", "재방", 5, False) == "[미디어 동아리_ESG](재)"
    assert format_cell_text("새 프로그램", "재방", None, True) == "새 프로그램(재)"   # 본방 대기


def test_해석과_만들기는_서로_되돌림():
    for text in ("마을살이정류장_23화", "러너스 해피에코_26화(재)", "963 음악쌀롱", "[미디어 동아리_ESG](재)"):
        p = parse_cell_text(text)
        assert format_cell_text(p.name, p.kind, p.episode, p.episode is not None) == text


# ── 이름 매칭 ─────────────────────────────────────

def test_이름_매칭():
    index = [("p1", "마을살이 정류장", ["마을살이"]), ("p2", "그 사이 음악", []), ("p3", "그삶이다", [])]
    m = match_names(["마을살이", "그 사이 음악", "마을살이정류장", "그 삶이다", "모르는 이름"], index)
    assert m["마을살이"] == ("matched", "p1")
    assert m["그 사이 음악"] == ("matched", "p2")
    assert m["마을살이정류장"] == ("suggested", "p1")      # 띄어쓰기만 다름 → 추천
    assert m["그 삶이다"] == ("suggested", "p3")
    assert m["모르는 이름"] == ("unmatched", None)


def test_띄어쓰기_무시해도_여러개면_추천하지_않음():
    index = [("a", "그 사이", []), ("b", "그사이", [])]
    assert match_names(["그  사이 "], index)["그  사이 "] == ("matched", "a")
    assert match_names(["그사 이"], index)["그사 이"] == ("unmatched", None)


# ── 편성 자리 추정 ────────────────────────────────

def _cells(weeks, weekday, hour, kinds, pid="p"):
    """weeks: 월요일 목록, kinds: 주마다 '본방'/'재방'/None"""
    from datetime import timedelta
    return [(w + timedelta(days=weekday), hour, pid, k) for w, k in zip(weeks, kinds) if k]


NOV = [D("2026-11-02"), D("2026-11-09"), D("2026-11-16"), D("2026-11-23"), D("2026-11-30")]


def test_매주_본방_자리():
    r = infer_slots(_cells(NOV, 0, 9, ["본방"] * 5), NOV)
    assert r["p"].cycle_type == "weekly"
    assert [(s.weekday, s.hour, s.role) for s in r["p"].slots] == [(0, 9, "본방")]


def test_본방_재방_번갈아면_격주():
    r = infer_slots(_cells(NOV, 1, 10, ["본방", "재방", "본방", "재방", "본방"]), NOV)
    assert r["p"].cycle_type == "biweekly" and r["p"].anchor == D("2026-11-03")
    assert [(s.weekday, s.hour, s.role) for s in r["p"].slots] == [(1, 10, "본방")]


def test_재방_자리와_한번만_나온_칸은_제외():
    cells = _cells(NOV, 0, 9, ["본방"] * 5) + _cells(NOV, 5, 18, ["재방"] * 5) + _cells(NOV, 3, 20, ["재방", None, None, None, None])
    r = infer_slots(cells, NOV)
    assert sorted((s.weekday, s.hour, s.role) for s in r["p"].slots) == [(0, 9, "본방"), (5, 18, "재방")]


def test_재방만_나오면_매주_재방_자리():
    r = infer_slots(_cells(NOV, 2, 11, ["재방"] * 4), NOV)
    assert r["p"].cycle_type == "weekly" and r["p"].slots[0].role == "재방"


def test_본방이_드문드문이면_부정기():
    r = infer_slots(_cells(NOV, 2, 11, ["재방", "재방", "본방", "재방", "재방"]), NOV)
    assert r["p"].cycle_type == "irregular" and r["p"].slots[0].role == "본방"
