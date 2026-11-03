"""공휴일: 오프라인 라이브러리(holidays, KR) + 앱에서 추가한 임시공휴일."""
from __future__ import annotations

import warnings
from datetime import date

with warnings.catch_warnings():
    # 0.x → 1.0 변경 예고 경고. requirements.txt에서 버전을 고정했으므로 숨긴다.
    warnings.simplefilter("ignore", DeprecationWarning)
    import holidays


def holidays_between(first: date, last: date, manual: dict[date, str] | None = None) -> dict[date, str]:
    lib = holidays.KR(years=range(first.year, last.year + 1), language="ko")
    out = {d: str(n) for d, n in lib.items() if first <= d <= last}
    for d, n in (manual or {}).items():   # 수동 추가가 우선
        if first <= d <= last:
            out[d] = n
    return out
