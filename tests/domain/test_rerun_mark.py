"""재방 표시: 본방 자리에 나가는 재방(격주 쉬는 주 등)에는 표시를 붙이지 않는다."""
from app.domain.rerun_mark import rerun_marks

from .helpers import D, cell


def test_본방_자리에서_나온_재방은_표시없음():
    cells = [cell("2026-11-03", 10, "p", "본방", slot_id="main"),
             cell("2026-11-10", 10, "p", "재방", slot_id="main"),      # 격주 쉬는 주
             cell("2026-11-08", 15, "p", "재방", slot_id="rerun")]     # 재방 자리
    marks = rerun_marks(cells, {"main": "본방", "rerun": "재방"})
    assert marks == {(D("2026-11-10"), 10): False, (D("2026-11-08"), 15): True}


def test_자리_정보가_없으면_직전_본방_자리로_판정():
    cells = [cell("2026-10-27", 10, "p", "본방", source="import"),
             cell("2026-11-03", 10, "p", "재방", source="import"),      # 직전 본방과 같은 자리 → 표시 없음
             cell("2026-11-05", 10, "p", "재방", source="import"),      # 다른 요일 → 표시
             cell("2026-12-29", 10, "p", "재방", source="import"),      # 휴방으로 몇 주 지나도 같은 자리 → 표시 없음
             cell("2026-11-03", 11, "q", "재방", source="import")]      # 본방 이력 없는 프로그램 → 표시
    marks = rerun_marks(cells, {})
    assert marks[(D("2026-11-03"), 10)] is False
    assert marks[(D("2026-11-05"), 10)] is True
    assert marks[(D("2026-12-29"), 10)] is False
    assert marks[(D("2026-11-03"), 11)] is True


def test_첫_본방_전이면_다음_3주_안_같은_자리_본방():
    cells = [cell("2026-11-03", 10, "p", "재방", source="import"),
             cell("2026-11-10", 10, "p", "본방", source="import"),
             cell("2026-10-01", 9, "p", "재방", source="import")]
    marks = rerun_marks(cells, {})
    assert marks[(D("2026-11-03"), 10)] is False
    assert marks[(D("2026-10-01"), 9)] is True


def test_본방은_대상_아님():
    assert rerun_marks([cell("2026-11-03", 10, "p", "본방")], {}) == {}
