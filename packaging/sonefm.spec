# -*- mode: python ; coding: utf-8 -*-
# SoneFM 편성표 — PyInstaller onedir 빌드 (onefile보다 백신 오탐이 적다)
# 실행 (저장소 루트에서):  pyinstaller packaging/sonefm.spec --noconfirm
# 먼저 화면 빌드:          cd frontend && npm run build
# 결과: dist/SoneFM/SoneFM.exe  (데이터는 exe 안이 아니라 문서\SoneFM 에 저장)
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
INDEX = ROOT / "frontend" / "dist" / "index.html"
if not INDEX.exists():
    raise SystemExit("frontend/dist/index.html 이 없습니다. 먼저 frontend 폴더에서 npm run build 를 실행하세요.")

datas = [
    (str(INDEX), "frontend/dist"),
    (str(ROOT / "app" / "db" / "migrations" / "*.sql"), "app/db/migrations"),
]
datas += collect_data_files("holidays")          # 공휴일 이름 번역(ko) 파일

hiddenimports = collect_submodules("holidays") + collect_submodules("app")

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "PIL", "PyInstaller", "cryptography", "pdfplumber", "pdfminer", "pypdfium2"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SoneFM",
    icon=str(ROOT / "packaging" / "icon.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="SoneFM", upx=False)
