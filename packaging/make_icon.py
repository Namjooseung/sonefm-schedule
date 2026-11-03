"""로고(design/SONE_로고_96.3MHz_고화질.png)로 윈도우 아이콘(packaging/icon.ico)을 만든다.

로고 전체를 정사각형 투명 바탕 가운데에 맞춰 넣는다 (2026-11-03 합의: 3안).
실행: python packaging/make_icon.py   (Pillow 필요 — requirements.txt에 포함)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "design" / "SONE_로고_96.3MHz_고화질.png"
OUT_ICO = ROOT / "packaging" / "icon.ico"
OUT_PREVIEW = ROOT / "packaging" / "icon_preview.png"
SIZES = [16, 24, 32, 48, 64, 128, 256]
MARGIN = 0.04   # 가장자리 여백 비율


def square_logo(size: int = 1024) -> Image.Image:
    logo = Image.open(LOGO).convert("RGBA")
    bbox = logo.getbbox()                 # 투명 여백 잘라내기
    if bbox:
        logo = logo.crop(bbox)
    inner = int(size * (1 - 2 * MARGIN))
    scale = inner / max(logo.width, logo.height)
    logo = logo.resize((max(1, round(logo.width * scale)), max(1, round(logo.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(logo, ((size - logo.width) // 2, (size - logo.height) // 2), logo)
    return canvas


def main() -> None:
    big = square_logo()
    big.save(OUT_ICO, sizes=[(s, s) for s in SIZES])
    # 미리보기: 실제 크기별로 나란히
    pad = 12
    width = sum(SIZES) + pad * (len(SIZES) + 1)
    preview = Image.new("RGBA", (width, 256 + pad * 2), (255, 255, 255, 255))
    x = pad
    for s in SIZES:
        img = big.resize((s, s), Image.LANCZOS)
        preview.paste(img, (x, pad + 256 - s), img)
        x += s + pad
    preview.save(OUT_PREVIEW)
    print(f"아이콘: {OUT_ICO}\n미리보기: {OUT_PREVIEW}")


if __name__ == "__main__":
    main()
