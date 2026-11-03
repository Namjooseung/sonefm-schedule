"""회차 계산. 회차는 저장하지 않고 칸 목록에서 매번 계산한다.

규칙
- 본방 회차 = 시작 회차 + 그 시점 이전까지 실제로 나간 본방 횟수.
  결방은 칸이 없으니 세지 않는다 → 다음 본방이 그 회차를 이어받는다.
- 재방 회차 = 수동 지정이 있으면 그 값, 없으면 그 시점 직전 본방의 회차.
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
    aired = 0
    last: int | None = start_episode - 1 if start_episode > 1 else None
    out: list[EpisodeInfo] = []
    for c in ordered:
        if c.kind == "본방":
            ep = start_episode + aired
            aired += 1
            last = ep
            out.append(EpisodeInfo(ep))
        elif c.rerun_episode_override is not None:
            out.append(EpisodeInfo(c.rerun_episode_override))
        else:
            out.append(EpisodeInfo(last, waiting=last is None))
    return out


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
