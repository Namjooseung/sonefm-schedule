"""엑셀 편성표 칸 글자 ↔ 편성 정보 (순수 함수).

칸 글자 형식 (기존 엑셀 편성표)
- 본방: `프로그램명_23화`        재방: `프로그램명_23화(재)`
- 회차를 안 붙이는 프로그램: `963 음악쌀롱`, 재방이면 `[미디어 동아리_ESG](재)`
- 이름 안의 줄바꿈·연속 공백은 공백 하나로 본다.
- `#REF!` 같은 엑셀 오류 값은 가져오지 않고 알린다.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

_RERUN = re.compile(r"\s*\((재|재방)\)\s*$")
_EPISODE = re.compile(r"_\s*(\d+)\s*화\s*$")


@dataclass(frozen=True)
class ParsedCell:
    name: str = ""
    kind: str = "본방"
    episode: int | None = None
    error: str | None = None      # 엑셀 오류 값이면 그 글자


def normalize_name(text: str) -> str:
    return " ".join(str(text).split())


def parse_cell_text(value: object) -> ParsedCell | None:
    """빈칸이면 None."""
    if value is None:
        return None
    text = normalize_name(str(value))
    if not text:
        return None
    if text.startswith("#"):
        return ParsedCell(error=text)
    kind = "본방"
    m = _RERUN.search(text)
    if m:
        kind = "재방"
        text = text[: m.start()].strip()
    episode = None
    m = _EPISODE.search(text)
    if m:
        episode = int(m.group(1))
        text = text[: m.start()].strip()
    return ParsedCell(name=text, kind=kind, episode=episode)


def format_cell_text(name: str, kind: str, episode: int | None, show_episode: bool) -> str:
    text = name
    if show_episode and episode is not None:
        text += f"_{episode}화"
    if kind == "재방":
        text += "(재)"
    return text


# ── 이름 매칭 ─────────────────────────────────────

def _squash(s: str) -> str:
    return "".join(s.split())


def match_names(names: Iterable[str], index: list[tuple[str, str, list[str]]]
                ) -> dict[str, tuple[str, str | None]]:
    """엑셀 이름 → (상태, 프로그램 id). 상태: matched(이름·별칭과 같음) | suggested(띄어쓰기만 다름) | unmatched.

    index: (프로그램 id, 이름, 별칭 목록)
    """
    exact: dict[str, str] = {}
    squashed: dict[str, set[str]] = defaultdict(set)
    for pid, name, aliases in index:
        for n in (name, *aliases):
            exact.setdefault(normalize_name(n), pid)
            squashed[_squash(n)].add(pid)
    out: dict[str, tuple[str, str | None]] = {}
    for raw in names:
        n = normalize_name(raw)
        if n in exact:
            out[raw] = ("matched", exact[n])
        elif len(squashed.get(_squash(n), ())) == 1:
            out[raw] = ("suggested", next(iter(squashed[_squash(n)])))
        else:
            out[raw] = ("unmatched", None)
    return out


# ── 편성 자리 추정 (새로 등록하는 프로그램용) ─────

@dataclass(frozen=True)
class InferredSlot:
    weekday: int
    hour: int
    role: str


@dataclass
class Inferred:
    cycle_type: str = "weekly"
    anchor: date | None = None
    slots: list[InferredSlot] = field(default_factory=list)


def infer_cycle(on_dates: Iterable[date]) -> tuple[str, date | None]:
    """본방 날짜들의 간격으로 주기 판정. (주기, 격주 기준일)

    - 본방이 한 주에 여러 번(간격 7일 미만이 가장 많음) → 매주 (예: 회차 없는 음악 프로그램)
    - 7일 간격이 절반 이상 → 매주,  14일 간격이 절반 이상 → 격주(기준일 = 마지막 본방)
    - 그 밖, 또는 본방이 1번뿐 → 비정기.  본방이 없으면 매주(재방만 나가는 프로그램)
    """
    ons = sorted(set(on_dates))
    if not ons:
        return "weekly", None
    if len(ons) < 2:
        return "irregular", None
    gaps = Counter((b - a).days for a, b in zip(ons, ons[1:]))
    mode, n = gaps.most_common(1)[0]
    share = n / sum(gaps.values())
    if mode < 7:
        return "weekly", None
    if mode == 7 and share >= 0.5:
        return "weekly", None
    if mode == 14 and share >= 0.5:
        return "biweekly", ons[-1]
    return "irregular", None


def infer_slots(cells: Iterable[tuple[date, int, str, str]], mondays: list[date],
                history: Iterable[tuple[date, int, str, str]] | None = None) -> dict[str, Inferred]:
    """프로그램별 편성 자리와 주기 추정.

    - 편성 자리: mondays 주들(보통 마지막 4주)에서 같은 요일·시각에 두 주 이상 나온 자리.
    - 자리 역할: history(가져온 전체 기간)에 그 자리 본방이 한 번이라도 있으면 본방 자리, 아니면 재방 자리.
      (휴방 기간처럼 마지막 몇 주에 재방만 있어도 본방 자리를 잃지 않게)
    - 주기: history 전체의 본방 간격으로 infer_cycle.
    cells·history 항목: (날짜, 시, 프로그램 id, 본방/재방). history가 없으면 cells를 쓴다.
    """
    cells = list(cells)
    history = list(history) if history is not None else cells
    week_set = set(mondays)
    by_pos: dict[str, dict[tuple[int, int], set[date]]] = defaultdict(lambda: defaultdict(set))
    for d, h, pid, _kind in cells:
        mon = d - timedelta(days=d.weekday())
        if mon in week_set:
            by_pos[pid][(d.weekday(), h)].add(mon)
    on_pos: dict[str, set[tuple[int, int]]] = defaultdict(set)
    on_dates: dict[str, list[date]] = defaultdict(list)
    for d, h, pid, kind in history:
        if kind == "본방":
            on_pos[pid].add((d.weekday(), h))
            on_dates[pid].append(d)

    out: dict[str, Inferred] = {}
    for pid, positions in by_pos.items():
        slots = [InferredSlot(wd, h, "본방" if (wd, h) in on_pos[pid] else "재방")
                 for (wd, h), weeks in sorted(positions.items()) if len(weeks) >= 2]
        if not slots:
            continue
        cycle, anchor = infer_cycle(on_dates[pid])
        out[pid] = Inferred(cycle_type=cycle, anchor=anchor, slots=slots)
    return out
