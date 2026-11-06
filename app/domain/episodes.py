"""회차 계산. 회차는 저장하지 않고 칸 목록에서 매번 계산한다.

규칙
- 본방 회차 = 시작 회차 + 그 시점 이전까지 실제로 나간 본방 횟수.
  결방은 칸이 없으니 세지 않는다 → 다음 본방이 그 회차를 이어받는다.
- 본방 회차를 수동 지정하면 그 칸이 그 회차가 되고, 다음 본방은 거기서 1씩 이어진다.
- 재방 회차 = 수동 지정이 있으면 그 값(그 칸만), 없으면 그 시점 직전 본방의 회차.
- 앱 안에 아직 본방이 없을 때의 재방:
  - 시작 회차 N > 1 이면 앱 이전에 N-1화까지 나간 것으로 보고 N-1화.
  - 시작 회차 1(신규)이면 회차 없음 → '본방 대기'.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.domain.models import Cell


@dataclass(frozen=True)
class EpisodeInfo:
    episode: int | None
    waiting: bool = False      # 본방 대기


def compute_episodes(cells: Iterable[Cell], start_episode: int) -> list[EpisodeInfo]:
    """한 프로그램의 칸들(전체 이력)을 시간순으로 정렬해 칸마다 회차를 돌려준다.

    돌려주는 목록은 시간순 정렬 결과와 같은 순서다.
    """
    ordered = sorted(cells, key=lambda c: c.key)
    next_ep = start_episode
    last: int | None = start_episode - 1 if start_episode > 1 else None
    out: list[EpisodeInfo] = []
    for c in ordered:
        if c.kind == "본방":
            ep = c.rerun_episode_override if c.rerun_episode_override is not None else next_ep
            next_ep = ep + 1
            last = ep
            out.append(EpisodeInfo(ep))
        elif c.rerun_episode_override is not None:
            out.append(EpisodeInfo(c.rerun_episode_override))
        else:
            out.append(EpisodeInfo(last, waiting=last is None))
    return out


def previous_episode(cells: Iterable[Cell], start_episode: int, key: tuple[date, int]) -> int:
    """key 칸 직전까지 나간 마지막 본방 회차. 없으면 시작 회차 - 1 (신규면 0)."""
    before = sorted((c for c in cells if c.key < key), key=lambda c: c.key)
    last = start_episode - 1
    for c, info in zip(before, compute_episodes(before, start_episode)):
        if c.kind == "본방" and info.episode is not None:
            last = info.episode
    return last


def plan_episode_change(value: int, previous: int, in_main_slot: bool) -> tuple[str, int | None]:
    """회차 − / + 버튼의 결과: (칸 종류, 수동 지정 회차).

    본방 자리 칸은 직전 회차와 비교해 칸 종류까지 정한다 (비정기도 같다).
    - 직전보다 크면 새 회차 = 본방. 직전+1이면 자동 계산과 같으므로 지정하지 않는다.
    - 직전과 같으면 그날은 새 회차 없음 = 재방. 다음 본방이 이 회차를 이어받는다.
    - 직전보다 작으면 예전 회차를 다시 내는 재방 (그 칸만).
    재방 자리 칸은 언제나 재방이고 그 칸만 바뀐다.
    """
    if not in_main_slot:
        return "재방", value
    if value > previous:
        return "본방", None if value == previous + 1 else value
    if value == previous:
        return "재방", None
    return "재방", value


def episodes_by_program(
    cells: Iterable[Cell], start_episodes: dict[str, int]
) -> dict[tuple[date, int], EpisodeInfo]:
    """여러 프로그램이 섞인 칸 목록 → 칸 위치별 회차. 화면 표시용."""
    groups: dict[str, list[Cell]] = {}
    for c in cells:
        groups.setdefault(c.program_id, []).append(c)
    out: dict[tuple[date, int], EpisodeInfo] = {}
    for pid, group in groups.items():
        ordered = sorted(group, key=lambda c: c.key)
        for c, info in zip(ordered, compute_episodes(ordered, start_episodes.get(pid, 1))):
            out[c.key] = info
    return out
