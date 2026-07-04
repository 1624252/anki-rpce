#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Derive every app icon from one master logo image.

The previous logo was portrait art padded onto a square canvas, so it rendered
as a stretched-looking pill inside square containers and launcher masks. This
tool crops the master to its content, centers it on a true square, and writes
the full set of assets below.

In-app banner + desktop window icons:

- ``mobile/app/app/src/main/assets/rpce_logo.png``  - in-app banner (512, square)
- ``qt/aqt/data/qt/icons/rpce_logo.png``            - window/taskbar icon (256)
- ``qt/aqt/data/qt/icons/rpce_logo_small.png``      - desktop home banner (96)

Desktop installer icons (Briefcase packages these into the app + the Windows
MSI / macOS bundle; ``icon = "resources/anki"`` in the installer pyproject):

- ``qt/installer/app/resources/anki.png``   - installer/app icon (176, square)
- ``qt/installer/app/resources/anki.ico``   - Windows icon (multi-size ICO)
- ``qt/installer/app/resources/anki.icns``  - macOS icon (1024 ICNS)

Android launcher icons at every density (mdpi 48 / hdpi 72 / xhdpi 96 /
xxhdpi 144 / xxxhdpi 192), under ``mobile/app/app/src/main/res/``:

- ``mipmap-<d>/ic_launcher.png``             - rounded-square (legacy, API < 26)
- ``mipmap-<d>/ic_launcher_round.png``       - circular (legacy, API < 26)
- ``mipmap-<d>/ic_launcher_foreground.png``  - adaptive foreground (padded gavel)

Android adaptive icon (API 26+), so the launcher mask never distorts it:

- ``mipmap-anydpi-v26/ic_launcher.xml`` / ``ic_launcher_round.xml``
- ``values/ic_launcher_background.xml``      - solid white background color

Usage (from the repo root):

    python pylib/tools/rpce_make_icons.py [master.png]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

WHITE_THRESHOLD = 245  # pixels at/above this in all channels count as background

RES = "mobile/app/app/src/main/res"

# Launcher icon edge (px) per density bucket.
LAUNCHER_PX = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# Adaptive foreground is a 108dp layer (2.25x the launcher size).
FOREGROUND_PX = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
# White keeps the navy gavel readable and matches the app's white theme.
BACKGROUND_COLOR = "#FFFFFF"

_ADAPTIVE_XML = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
"""

_BACKGROUND_XML = f"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">{BACKGROUND_COLOR}</color>
</resources>
"""


def content_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    """Bounding box of the non-white artwork."""
    gray = img.convert("L").point(lambda v: 0 if v >= WHITE_THRESHOLD else 255)
    bbox = gray.getbbox()
    return bbox or (0, 0, img.width, img.height)


def squared(
    master: Image.Image, art_fraction: float, transparent: bool = False
) -> Image.Image:
    """Artwork centered on a square, filling ``art_fraction`` of it.

    Padding is white, or transparent for adaptive foregrounds (the launcher
    paints its own background layer behind them).
    """
    art = master.crop(content_bbox(master))
    side = round(max(art.size) / art_fraction)
    if transparent:
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        art = art.convert("RGBA")
    else:
        canvas = Image.new("RGB", (side, side), "white")
    canvas.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return canvas


def rounded(img: Image.Image, radius_frac: float) -> Image.Image:
    """Apply a rounded-rect (or circle at 0.5) alpha mask."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, img.width - 1, img.height - 1),
        radius=round(img.width * radius_frac),
        fill=255,
    )
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def save(img: Image.Image, size: int, path: str) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.resize((size, size), Image.LANCZOS).save(dest)
    print(f"wrote {dest} ({size}x{size})")


# ICO sizes Windows picks between (taskbar, Explorer, ARP, shortcut).
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def save_ico(img: Image.Image, path: str) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    base = img.resize((256, 256), Image.LANCZOS).convert("RGBA")
    base.save(dest, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    print(f"wrote {dest} (ICO {ICO_SIZES})")


def save_icns(img: Image.Image, path: str) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 1024 master; Pillow derives the smaller icns variants from it.
    base = img.resize((1024, 1024), Image.LANCZOS).convert("RGBA")
    base.save(dest, format="ICNS")
    print(f"wrote {dest} (ICNS 1024)")


def save_text(text: str, path: str) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {dest}")


def main() -> None:
    master_path = sys.argv[1] if len(sys.argv) > 1 else "docs/rpce/rpce_logo_master.png"
    master = Image.open(master_path).convert("RGB")

    square = squared(master, art_fraction=0.82)
    square_safe = squared(master, art_fraction=0.68)  # margin for a circular crop
    foreground = squared(master, art_fraction=0.68, transparent=True)  # adaptive

    tile = rounded(square, radius_frac=0.18)
    circle = rounded(square_safe, radius_frac=0.5)

    # In-app banner + desktop window icons.
    save(square, 512, "mobile/app/app/src/main/assets/rpce_logo.png")
    save(tile, 256, "qt/aqt/data/qt/icons/rpce_logo.png")
    save(square, 96, "qt/aqt/data/qt/icons/rpce_logo_small.png")

    # Desktop installer icons (rounded tile, matching the window icon).
    installer = "qt/installer/app/resources"
    save(tile, 176, f"{installer}/anki.png")
    save_ico(tile, f"{installer}/anki.ico")
    save_icns(tile, f"{installer}/anki.icns")

    # Legacy launcher icons (API < 26) at every density.
    for density, px in LAUNCHER_PX.items():
        save(tile, px, f"{RES}/mipmap-{density}/ic_launcher.png")
        save(circle, px, f"{RES}/mipmap-{density}/ic_launcher_round.png")

    # Adaptive icon (API 26+): white background layer + padded gavel foreground.
    for density, px in FOREGROUND_PX.items():
        save(foreground, px, f"{RES}/mipmap-{density}/ic_launcher_foreground.png")
    save_text(_ADAPTIVE_XML, f"{RES}/mipmap-anydpi-v26/ic_launcher.xml")
    save_text(_ADAPTIVE_XML, f"{RES}/mipmap-anydpi-v26/ic_launcher_round.xml")
    save_text(_BACKGROUND_XML, f"{RES}/values/ic_launcher_background.xml")


if __name__ == "__main__":
    main()
