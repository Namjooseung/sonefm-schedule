"""pywebview 진입점.

    python app/main.py          빌드된 화면(frontend/dist/index.html)을 연다
    python app/main.py --dev    Vite 개발 서버(http://localhost:5173)를 연다
"""
from __future__ import annotations

import argparse
import ctypes
import time
import sys
from pathlib import Path

# `python app/main.py`로 실행해도 `app` 패키지를 import할 수 있게 저장소 루트를 경로에 넣는다
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import webview  # noqa: E402

from app import APP_NAME  # noqa: E402
from app.api import Api  # noqa: E402
from app.config import frontend_index  # noqa: E402
from app.logging_setup import setup_logging  # noqa: E402
from app.startup import prepare  # noqa: E402

DEV_URL = "http://localhost:5173"


def show_error(message: str) -> None:
    """창을 띄우기 전 오류를 윈도우 메시지 상자로 알린다."""
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    else:
        print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--dev", action="store_true", help="Vite 개발 서버를 로드")
    args = parser.parse_args(argv)

    log = setup_logging()
    try:
        started = prepare()
    except Exception:
        log.exception("시작 준비 실패")
        show_error("프로그램을 시작하지 못했습니다.\n"
                   "자세한 내용은 문서\\SoneFM\\logs\\app.log 를 확인해 주세요.")
        return 1

    if args.dev:
        url = DEV_URL
    else:
        index = frontend_index()
        if not index.exists():
            log.error("화면 파일 없음: %s", index)
            show_error("화면 파일을 찾지 못했습니다. 프로그램을 다시 설치해 주세요.\n"
                       "(개발 중이라면 frontend 폴더에서 npm run build 를 실행하세요.)")
            return 1
        url = index.as_uri()

    window = webview.create_window(
        APP_NAME, url, js_api=Api(started.config),
        width=1440, height=900, min_size=(1100, 700),
    )

    def on_loaded() -> None:
        # 문제 해결용: 화면이 열렸는지, 내부 연결(pywebview)이 준비됐는지 로그에 남긴다
        try:
            time.sleep(2)   # 화면이 첫 데이터를 불러올 시간 (이 처리기는 별도 스레드에서 돈다)
            state = window.evaluate_js(
                "JSON.stringify({"
                " bridge: !!(window.pywebview && window.pywebview.api),"
                " title: document.querySelector('h1')?.innerText,"
                " weeks: document.querySelectorAll('.weekrow').length,"
                " error: document.querySelector('.callout-danger')?.innerText || null})")
            log.info("화면 열림: %s", state)
        except Exception:
            log.exception("화면 상태 확인 실패")

    window.events.loaded += on_loaded
    webview.start(debug=args.dev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
