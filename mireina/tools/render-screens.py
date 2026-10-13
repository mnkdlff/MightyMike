#!/usr/bin/env python3
"""Renders the text screens of La Reina's edition from mireina/texts.json and writes the TGAs.

legal (420×251, free palette) — Karim's lines in the original's two colours plus the attribution.
charging (640×480, free) — « Amor Cargando ... » in rainbow letters where « CHARGING BATTERIES » was.
head (640×480, free) — the easter egg, six styles of « Karim was here ».
bonus (640×480, KEPT palette) — « BONUS DE LA REINA » in the red of the original, top band.
credits1 (640×480, KEPT palette) — « REINA CREDITS » in the magenta of the original, top band.
Run: .venv-tools/bin/python mireina/tools/render-screens.py [name ...] [--preview DIR]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import images  # noqa: E402

FONTS = Path("/System/Library/Fonts/Supplemental")
TEXTS = json.loads((images.ROOT / "mireina" / "texts.json").read_text("utf8"))
BLACK = (0, 0, 0)
# The original legal screen: light blue title and links, white body (sampled from legal.tga).
BLUE, BLUE_DARK, WHITE, GREY = (45, 201, 251), (23, 117, 148), (255, 255, 255), (156, 158, 155)
ATTRIBUTION = ["Basado en Mighty Mike © 1995-2000 Pangea Software", "Versión moderna de Iliyas Jorio, CC BY-NC-SA 4.0"]


def font(file: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    path = FONTS / file
    if not path.exists():
        raise FileNotFoundError(f"font missing: {path}")
    return ImageFont.truetype(str(path), size, index=index)


def text_of(item: str) -> str:
    t = TEXTS.get(item)
    if not isinstance(t, str) or not t.strip():
        raise ValueError(f"texts.json has no {item!r}: export the artifact first")
    return t.strip()


def centred(draw: ImageDraw.ImageDraw, y: int, text: str, f: ImageFont.FreeTypeFont, fill, width: int, stroke=0, stroke_fill=None, shadow=None):
    """One centred line; `shadow` = (dx, dy, colour) drawn first."""
    x = width // 2
    if shadow:
        draw.text((x + shadow[0], y + shadow[1]), text, font=f, fill=shadow[2], anchor="mt")
    draw.text((x, y), text, font=f, fill=fill, anchor="mt", stroke_width=stroke, stroke_fill=stroke_fill)


def gradient_text(canvas: Image.Image, y: int, text: str, f: ImageFont.FreeTypeFont, top, bottom, outline, outline_w=3):
    """A heavy title with a vertical gradient fill and a dark outline (the Bonus / Credits look)."""
    w, h = canvas.size
    draw = ImageDraw.Draw(canvas)
    draw.text((w // 2, y), text, font=f, fill=outline, anchor="mt", stroke_width=outline_w, stroke_fill=outline)
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text((w // 2, y), text, font=f, fill=255, anchor="mt")
    x0, y0, x1, y1 = mask.getbbox()
    grad = Image.new("RGB", canvas.size, top)
    gd = ImageDraw.Draw(grad)
    for yy in range(y0, y1 + 1):
        t = (yy - y0) / max(1, y1 - y0)
        c = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        gd.line([(x0, yy), (x1, yy)], fill=c)
    canvas.paste(grad, mask=mask)


def render_legal() -> Image.Image:
    im = Image.new("RGB", images.SIZES["legal"], BLACK)
    d = ImageDraw.Draw(im)
    lines = text_of("legal").split("\n")
    title, body = lines[0], lines[1:]
    centred(d, 18, title, font("Arial Rounded Bold.ttf", 46), BLUE, im.width, shadow=(2, 3, BLUE_DARK))
    y = 86
    for line in body:
        if not line.strip():
            y += 10
            continue
        is_link = "." in line and " " not in line.strip() or line.strip().lower().startswith("hecho")
        centred(d, y, line.strip(), font("Arial Rounded Bold.ttf", 21), BLUE if is_link else WHITE, im.width)
        y += 27
    small = font("Arial Rounded Bold.ttf", 11)
    for i, line in enumerate(ATTRIBUTION):
        centred(d, im.height - 32 + i * 14, line, small, GREY, im.width)
    return im


RAINBOW = [(255, 60, 60), (255, 150, 40), (255, 230, 60), (90, 220, 90), (60, 200, 255), (90, 120, 255), (200, 90, 255)]


def render_charging() -> Image.Image:
    im = Image.new("RGB", images.SIZES["charging"], BLACK)
    d = ImageDraw.Draw(im)
    text = text_of("charging")
    f = font("ChalkboardSE.ttc", 40, index=1)  # ChalkboardSE Bold
    widths = [f.getlength(ch) for ch in text]
    x = (im.width - sum(widths)) / 2
    y = 160  # the original's band
    for i, (ch, wch) in enumerate(zip(text, widths)):
        if ch.strip():
            d.text((x + 3, y + 3), ch, font=f, fill=(40, 10, 60))
            d.text((x, y), ch, font=f, fill=RAINBOW[i % len(RAINBOW)])
        x += wch
    return im


def render_head() -> Image.Image:
    """Six styles, laid out like the original (which had « Brian was here » six times)."""
    im = Image.new("RGB", images.SIZES["head"], BLACK)
    d = ImageDraw.Draw(im)
    raw = text_of("head").split("(")[0].strip()  # "Karim WAS HERE  (× 6 styles)" → "Karim WAS HERE"
    who = raw.split()[0]
    styles = [
        ((36, 40), f"{who.upper()} WAS HERE", font("Herculanum.ttf", 40), (214, 190, 205)),
        ((120, 140), f"{who.upper()} WAS HERE", font("Copperplate.ttc", 20, index=1), (230, 230, 230)),
        ((455, 180), f"{who} was here", font("Arial Rounded Bold.ttf", 15), (170, 150, 220)),
        ((148, 232), f"{who} was here", font("SnellRoundhand.ttc", 24, index=1), (200, 80, 70)),
        ((352, 278), f"{who.upper()} WAS HERE", font("Trattatello.ttf", 20), (150, 160, 190)),
        ((190, 388), f"{who} was here!", font("Luminari.ttf", 36), (190, 150, 60)),
    ]
    for (x, y), text, f, colour in styles:
        d.text((x, y), text, font=f, fill=colour)
    return im


def render_bonus() -> Image.Image:
    im = Image.new("RGB", images.SIZES["bonus"], BLACK)
    gradient_text(im, 14, text_of("bonus"), font("Impact.ttf", 60), (250, 80, 140), (190, 20, 60), (70, 0, 30))
    return im


def render_credits1() -> Image.Image:
    im = Image.new("RGB", images.SIZES["credits1"], BLACK)
    gradient_text(im, 6, text_of("credits-image"), font("Impact.ttf", 72), (255, 90, 230), (170, 20, 90), (60, 0, 40))
    return im


RENDERS = {"legal": render_legal, "charging": render_charging, "head": render_head, "bonus": render_bonus, "credits1": render_credits1}


if __name__ == "__main__":
    args = sys.argv[1:]
    preview = None
    if "--preview" in args:
        i = args.index("--preview")
        preview = Path(args[i + 1])
        args = args[:i] + args[i + 2 :]
    names = args or list(RENDERS)
    for name in names:
        im = RENDERS[name]()
        out = images.to_tga(im, name)
        print(f"wrote · {out.relative_to(images.ROOT)}")
        if preview:
            preview.mkdir(parents=True, exist_ok=True)
            Image.open(out).convert("RGB").save(preview / f"{name}.png")
