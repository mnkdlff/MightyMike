#!/usr/bin/env python3
"""PNG → TGA for Power Reina's screens, in the exact format the engine's loader accepts.

The loader (src/Drivers/TGA.c) wants an 8-bit colormapped TGA (type 1 raw or 9 RLE), no id field,
a 24-bit palette, at most 256 colours; every image installs its own palette while shown. Screens
the engine draws sprites over (title icons, bonus counters, credits text…) must therefore keep their
ORIGINAL palette (mode "keep": the new picture is quantized onto it); the others take a free
256-colour palette (mode "free").

CLI:  images.py            convert every mireina/images/<name>.png into Data/Images/<name>.tga
      images.py export     write the originals of the Gemini targets to mireina/images/orig/
      images.py check F    print the header of a TGA and verify it
Run with the project venv: .venv-tools/bin/python mireina/tools/images.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA_IMAGES = ROOT / "Data" / "Images"
DROP_DIR = ROOT / "mireina" / "images"
ORIG_DIR = DROP_DIR / "orig"

# Every screen the edition may replace, with its exact size.
SIZES: dict[str, tuple[int, int]] = {
    "legal": (420, 251),
    **{n: (640, 480) for n in ["charging", "head", "bonus", "credits1", "titlepagepp", "scores", "win", "lose", "diff", "playerchoose", "winbw", "overheadmap", "dinoscene", "candyscene", "fairyscene", "clownscene", "bargainscene"]},
}
# Sprites are drawn over these: their palette is part of the game, keep it.
KEEP = frozenset(["titlepagepp", "diff", "playerchoose", "scores", "bonus", "win", "credits1", "winbw", "overheadmap"])
# Artwork screens Karim redraws with Gemini (the text screens are rendered by render-screens.py).
GEMINI = ["titlepagepp", "scores", "win", "dinoscene", "candyscene", "fairyscene", "clownscene", "bargainscene"]

TGA_RAW_CMAP, TGA_RLE_CMAP = 1, 9


def palette_of(name: str) -> Image.Image:
    """The committed original, mode P: its palette is the one the engine's sprites expect."""
    im = Image.open(DATA_IMAGES / f"{name}.tga")
    if im.mode != "P":
        raise ValueError(f"{name}.tga is not colormapped")
    im.load()
    return im


def to_tga(image: Image.Image, name: str, dst: Path | None = None) -> Path:
    """Converts any image into the TGA of `name` (size enforced, palette per mode) and verifies it."""
    if name not in SIZES:
        raise ValueError(f"unknown image {name!r}")
    if image.size != SIZES[name]:
        raise ValueError(f"{name}: {image.size[0]}×{image.size[1]}, the game wants {SIZES[name][0]}×{SIZES[name][1]}")
    rgb = image.convert("RGB")
    if name in KEEP:
        p = rgb.quantize(palette=palette_of(name), dither=Image.Dither.NONE)
    else:
        p = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = dst or (DATA_IMAGES / f"{name}.tga")
    out.parent.mkdir(parents=True, exist_ok=True)
    # orientation=1 → top-left origin (the loader accepts both and flips the other).
    p.save(out, format="TGA", orientation=1)
    check_tga(out)
    return out


def check_tga(path: Path) -> dict:
    """Parses the 18-byte header and asserts everything LoadTGA asserts."""
    with open(path, "rb") as f:
        raw = f.read(18)
    if len(raw) < 18:
        raise AssertionError(f"{path}: truncated header")
    idlen, cmaptype, imgtype, cmapstart, cmaplen, cmapbits, _x, _y, w, h, bpp, desc = struct.unpack("<BBBHHBHHHHBB", raw)
    assert imgtype in (TGA_RAW_CMAP, TGA_RLE_CMAP), f"{path}: image type {imgtype}, must be colormapped (1 or 9)"
    assert idlen == 0, f"{path}: id field length {idlen}, must be 0"
    assert cmaptype == 1 and cmapstart == 0 and cmaplen <= 256 and cmapbits == 24, f"{path}: palette {cmaptype}/{cmapstart}/{cmaplen}/{cmapbits}"
    assert bpp == 8, f"{path}: {bpp} bpp, must be 8"
    return {"type": imgtype, "size": (w, h), "colours": cmaplen, "top_left": bool(desc & 0x20)}


def export_originals(dst_dir: Path) -> list[Path]:
    """PNG copies of the Gemini targets, for the prompt pack and for Karim's reference."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for name in GEMINI:
        p = dst_dir / f"{name}.png"
        Image.open(DATA_IMAGES / f"{name}.tga").convert("RGB").save(p)
        out.append(p)
    return out


def convert_drops() -> list[Path]:
    """Every mireina/images/<name>.png whose name is a known screen → Data/Images/<name>.tga."""
    done = []
    for png in sorted(DROP_DIR.glob("*.png")):
        if png.stem not in SIZES:
            print(f"-- · {png.name} (not a game screen, ignored)")
            continue
        out = to_tga(Image.open(png), png.stem)
        print(f"wrote · {out.relative_to(ROOT)} ({'kept palette' if png.stem in KEEP else 'free palette'})")
        done.append(out)
    return done


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["export"]:
        for p in export_originals(ORIG_DIR):
            print(f"wrote · {p.relative_to(ROOT)}")
    elif args[:1] == ["check"]:
        for a in args[1:]:
            print(a, check_tga(Path(a)))
    else:
        if not convert_drops():
            print(f"nothing to convert: drop PNGs into {DROP_DIR.relative_to(ROOT)}/ (names: {', '.join(sorted(SIZES))})")
