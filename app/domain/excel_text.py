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


def infer_slots(cells: Iterable[tuple[date, int, str, str]], mondays: list[date]) -> dict[str, Inferred]:
    """한 달치 칸 (날짜, 시, 프로그램 id, 본방/재방)으로 프로그램별 편성 자리와 주기를 추정한다.

    - 같은 요일·시각에 두 주 이상 나온 자리만 편성 자리로 본다.
    - 그 자리에 본방이 한 번이라도 있으면 본방 자리, 아니면 재방 자리.
    - 주기는 본방이 가장 많은 자리로 판정: 매주 본방이면 매주, 2주 간격이면 격주(기준일=첫 본방),
      그 밖에 본방이 있으면 부정기. 본방 자리가 없으면 매주(재방만 나가는 프로그램).
    """
    week_set = set(mondays)
    by_pos: dict[str, dict[tuple[int, int], list[tuple[date, str]]]] = defaultdict(lambda: defaultdict(list))
    for d, h, pid, kind in cells:
        if d - timedelta(days=d.weekday()) in week_set:
            by_pos[pid][(d.weekday(), h)].append((d, kind))

    out: dict[str, Inferred] = {}
    for pid, positions in by_pos.items():
        result = Inferred()
        main: tuple[int, list[date], int] | None = None    # (본방 수, 본방 날짜들, 나온 주 수)
        for (wd, h), seen in sorted(positions.items()):
            weeks = {d - timedelta(days=d.weekday()) for d, _ in seen}
            if len(weeks) < 2:
                continue
            ons = sorted(d for d, k in seen if k == "본방")
            result.slots.append(InferredSlot(wd, h, "본방" if ons else "재방"))
            if ons and (main is None or len(ons) > main[0]):
                main = (len(ons), ons, len(weeks))
        if main:
            n_on, ons, n_weeks = main
            gaps = Counter((b - a).days for a, b in zip(ons, ons[1:]))
            if n_on == n_weeks:
                result.cycle_type = "weekly"
            elif n_on >= 2 and set(gaps) == {14}:
                result.cycle_type, result.anchor = "biweekly", ons[0]
            else:
                result.cycle_type = "irregular"
        if result.slots:
            out[pid] = result
    return out
