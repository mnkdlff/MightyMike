#!/usr/bin/env python3
"""Redraws Pete's speech balloons (main.shapes, shape 5) with the lines of mireina/texts.json ("voice").

The engine shows a balloon sprite above Pete while the voice plays (MakeMikeMessage): nine frames, one per
line, drawn in the Mac system palette (0 white, 255 black, greys 43/86/129/172 and 245–254). Each new balloon
is cut from an original one: its lettering is erased (black pixels well inside the body), the body is
stretched to the width of the new text by repeating one clean column, then the text is written in black with
a comic font, upper case, no anti-aliasing. The frame's anchor keeps the original rule (x = -(width-3),
y = -(height+76)) so the tail still points at Pete. The food balloon has no line in texts.json and keeps its
original; DeathScream has a voice but no balloon.

  .venv-tools/bin/python mireina/tools/balloons.py preview DIR    # PNGs + a sheet, nothing written to Data/
  .venv-tools/bin/python mireina/tools/balloons.py apply          # patches Data/Shapes/main.shapes
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shapes  # noqa: E402

TEXTS = shapes.ROOT / "mireina" / "texts.json"
SHAPE = 5  # ObjType_Message in GROUP_MAIN
# messageNum (= frame) per voice name; "food" (4) is not a voice line and keeps its balloon.
FRAME = {"IllSaveYou": 0, "ComeHereRodent": 1, "TakeThat": 2, "EatMyDust": 3, "FreeDude": 5, "Ouch": 6, "NoMoreNiceGuy": 7, "FireInTheHole": 8}
TEMPLATE = {1: 6, 2: 8}  # lines → original frame used as the blank balloon ("OUCH!", "FIRE IN THE HOLE!")
FONT_FILES = ["/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf", "/Library/Fonts/Comic Sans MS Bold.ttf"]
FONT_SIZE = 14
BLACK, RED = 255, 216
LIGHT = {0, 245, 246, 247, 248, 249, 250}  # the balloon body: white and the light end of the grey ramp
MARGIN_X, MIN_WIDTH, MAX_WIDTH = 7, 56, 118
LEFT_SLICE = 12


def lines() -> dict[str, str]:
    raw = json.loads(TEXTS.read_text("utf8"))["voice"]
    out = {}
    for line in raw.splitlines():
        m = re.match(r"\s*(.*?)\s*\((\w+)\.aiff\)\s*$", line)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def font() -> ImageFont.FreeTypeFont:
    for f in FONT_FILES:
        if Path(f).exists():
            return ImageFont.truetype(f, FONT_SIZE)
    raise SystemExit("Comic Sans MS Bold not found")


class Template:
    """A blank balloon cut from an original frame: left cap, one clean middle column, right cap with the tail."""

    def __init__(self, table: bytes, shape: shapes.Shape, f: int):
        fr = shape.frames[f]
        self.w, self.h = fr.width, fr.height
        px = bytearray(shape.pixels(table, f))
        mk = bytes(shape.mask(table, f))
        w, h = self.w, self.h
        opaque = [[mk[r * w + c] == 0 for c in range(w)] for r in range(h)]
        counts = [sum(row) for row in opaque]
        self.body_bottom = max(r for r in range(h) if counts[r] >= 0.6 * w)
        self.tail_left = min(c for r in range(self.body_bottom + 1, h) for c in range(w) if opaque[r][c])
        # Erase the lettering: inside the body, away from the outline and the bevel (right and bottom bands),
        # the fill is one value per row; anything else there is text, its anti-aliasing included.
        for r in range(3, self.body_bottom - 4):
            inner = [c for c in range(w) if opaque[r][c]]
            lo, hi = inner[0] + 3, inner[-1] - 6
            zone = [px[r * w + c] for c in range(lo, hi + 1)]
            light = [v for v in zone if v in LIGHT] or zone  # a row through thick letters is mostly black
            fill = Counter(light).most_common(1)[0][0]
            for c in range(lo, hi + 1):
                px[r * w + c] = fill
        self.px, self.mk = bytes(px), mk
        self.right_slice = max(self.tail_left - 4, LEFT_SLICE + 1)
        self.mid = (LEFT_SLICE + self.right_slice) // 2

    def stretch(self, width: int) -> tuple[bytearray, bytearray]:
        w, h = self.w, self.h
        extra = width - w
        px, mk = bytearray(), bytearray()
        for r in range(h):
            row_px, row_mk = self.px[r * w : (r + 1) * w], self.mk[r * w : (r + 1) * w]
            cut = self.right_slice
            if extra >= 0:
                px += row_px[:cut] + bytes([row_px[self.mid]]) * extra + row_px[cut:]
                mk += row_mk[:cut] + bytes([row_mk[self.mid]]) * extra + row_mk[cut:]
            else:
                # Narrower than the original: drop columns around the middle.
                keep = w + extra
                a = LEFT_SLICE + (keep - LEFT_SLICE - (w - cut)) // 2
                px += row_px[:a] + row_px[a - extra :]
                mk += row_mk[:a] + row_mk[a - extra :]
        return px, mk


def layout(text: str, fnt: ImageFont.FreeTypeFont) -> list[str]:
    """One line when it is short, else two balanced lines (the originals never go past two)."""
    words = text.upper().split()
    if len(words) == 1 or fnt.getlength(" ".join(words)) <= 48:
        return [" ".join(words)]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wide = max(fnt.getlength(a), fnt.getlength(b))
        if best is None or wide < best[0]:
            best = (wide, [a, b])
    return best[1]


def render_text(rows: list[str], fnt: ImageFont.FreeTypeFont) -> Image.Image:
    """1-bit image of the lines, centred, tight."""
    asc, desc = fnt.getmetrics()
    line_h = asc + desc - 2
    widths = [int(fnt.getlength(r)) + 4 for r in rows]
    im = Image.new("1", (max(widths), line_h * len(rows)), 0)
    d = ImageDraw.Draw(im)
    for i, r in enumerate(rows):
        d.text(((im.width - widths[i]) // 2 + 1, i * line_h), r, font=fnt, fill=1)
    return im.crop(im.getbbox()) if im.getbbox() else im


def build(table: bytes, shape: shapes.Shape, templates: dict[int, Template], text: str, colour: int, fnt) -> tuple[int, int, int, int, bytes, bytes]:
    rows = layout(text, fnt)
    tpl = templates[len(rows)]
    txt = render_text(rows, fnt)
    width = max(MIN_WIDTH, min(MAX_WIDTH, txt.width + 2 * MARGIN_X + (tpl.w - tpl.right_slice - 6)))
    px, mk = tpl.stretch(width)
    x0 = max(3, (width - 3 - txt.width) // 2)  # the body spans the width; the tail hangs below it
    y0 = max(3, (tpl.body_bottom + 1 - txt.height) // 2)
    for ty in range(txt.height):
        for tx in range(txt.width):
            if txt.getpixel((tx, ty)):
                i = (y0 + ty) * width + x0 + tx
                if mk[i] == 0:
                    px[i] = colour
    return width, tpl.h, -(width - 3), -(tpl.h + 76), bytes(px), bytes(mk)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("preview", "apply"):
        raise SystemExit(__doc__)
    path = shapes.SHAPES_DIR / "main.shapes"
    table = shapes.load(path)
    shape = shapes.parse(table)[SHAPE]
    templates = {n: Template(table, shape, f) for n, f in TEMPLATE.items()}
    fnt = font()
    phrases = lines()
    new = {}
    for name, f in FRAME.items():
        if name not in phrases:
            print(f"-- · {name}: no line in texts.json, original kept")
            continue
        new[f] = build(table, shape, templates, phrases[name], RED if name == "FreeDude" else BLACK, fnt)
        print(f"{name:15} frame {f}: {new[f][0]}×{new[f][1]} — {phrases[name]}")
    if sys.argv[1] == "preview":
        out = Path(sys.argv[2])
        out.mkdir(parents=True, exist_ok=True)
        pal = shapes.palette()
        tiles = []
        for f in range(len(shape.frames)):
            if f in new:
                w, h, _, _, px, mk = new[f]
            else:
                fr = shape.frames[f]
                w, h, px, mk = fr.width, fr.height, shape.pixels(table, f), shape.mask(table, f)
            im = Image.frombytes("P", (w, h), px)
            im.putpalette(pal)
            im.save(out / f"balloon-{f}.png")
            rgb = Image.composite(Image.new("RGB", (w, h), (255, 0, 255)), im.convert("RGB"), Image.frombytes("L", (w, h), mk))
            tiles.append(rgb.resize((w * 3, h * 3), Image.NEAREST))
        tw, th = max(t.width for t in tiles), max(t.height for t in tiles)
        sheet = Image.new("RGB", (3 * (tw + 10), 3 * (th + 10)), (40, 40, 40))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 3) * (tw + 10), (i // 3) * (th + 10)))
        sheet.save(out / "sheet.png")
        print(f"preview · {out / 'sheet.png'}")
    else:
        patched = shapes.patch(table, shape, new)
        shapes.save(path, patched)
        check = shapes.parse(shapes.load(path))[SHAPE]
        for f, (w, h, x, y, px, mk) in new.items():
            fr = check.frames[f]
            assert (fr.width, fr.height, fr.x, fr.y) == (w, h, x, y) and check.pixels(patched, f) == px and check.mask(patched, f) == mk, f
        print(f"wrote · Data/Shapes/main.shapes ({len(patched)} bytes unpacked, {len(new)} balloons replaced, verified)")


if __name__ == "__main__":
    main()
