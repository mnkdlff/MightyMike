#!/usr/bin/env python3
"""Reads and patches Pangea shape tables (Data/Shapes/*.shapes): the game's sprites.

File = packed container (int32 BE unpacked size, int32 BE pack type, payload: RLB byte runs, RLW word runs or
raw) around a shape table: int32 offset to the colour table, int32 offset to the shape list (int16 count +
int32 offsets); each shape header holds, at +2 and +6, offsets (relative to the header) to its frame list and
anim list. A frame header is width, height, x, y (int16) and the offsets of its pixels and mask (int32,
relative to the shape header), both width×height bytes: pixel = palette index, mask = 0x00 where the sprite
is opaque, 0xFF where the background shows (dest = dest & mask | pixel). An anim is a byte count followed by
(opcode, operand) int16 pairs; opcode 1 = show frame.

`patch` keeps the whole file as it is and appends the new pixel + mask blobs at the end, re-pointing the frame
headers to them (offsets are per shape header, so anywhere in the table is legal); the result is written
unpacked (pack type 2), which the loader accepts.

  .venv-tools/bin/python mireina/tools/shapes.py info main 5          # the frames and anims of shape 5
  .venv-tools/bin/python mireina/tools/shapes.py export main 5 DIR    # frames as PNG (in-game palette: the Mac CLUT of border2.tga)
"""
from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SHAPES_DIR = ROOT / "Data" / "Shapes"
IMAGES_DIR = ROOT / "Data" / "Images"
PACK_RLB, PACK_NONE, PACK_RLW = 0, 2, 6
OP_FRAME = 1


def unpack_rlb(src: bytes, size: int) -> bytes:
    out = bytearray()
    i = 0
    while len(out) < size:
        count = src[i]
        i += 1
        if count > 0x7F:
            out += bytes([src[i]]) * ((256 - count) + 1)
            i += 1
        else:
            out += src[i : i + count + 1]
            i += count + 1
    return bytes(out[:size])


def unpack_rlw(src: bytes, size: int) -> bytes:
    out = bytearray()
    i = 0
    while i < len(src) and len(out) < size:
        run = src[i]
        i += 1
        if run & 0x80:
            out += src[i : i + 2] * ((run & 0x7F) + 1)
            i += 2
        else:
            n = run + 1
            out += src[i : i + 2 * n]
            i += 2 * n
    return bytes(out[:size])


def load(path: Path) -> bytes:
    raw = path.read_bytes()
    size, kind = struct.unpack(">ii", raw[:8])
    payload = raw[8:]
    if kind == PACK_RLB:
        return unpack_rlb(payload, size)
    if kind == PACK_RLW:
        return unpack_rlw(payload, size)
    if kind == PACK_NONE:
        return payload[:size]
    raise SystemExit(f"{path.name}: unknown pack type {kind}")


def save(path: Path, table: bytes) -> None:
    path.write_bytes(struct.pack(">ii", len(table), PACK_NONE) + table)


@dataclass
class Frame:
    header_off: int  # absolute, in the table
    width: int
    height: int
    x: int
    y: int
    pixel_off: int  # relative to the shape header
    mask_off: int


@dataclass
class Shape:
    header_off: int
    frames: list[Frame] = field(default_factory=list)
    anims: list[list[tuple[int, int]]] = field(default_factory=list)

    def pixels(self, table: bytes, f: int) -> bytes:
        fr = self.frames[f]
        a = self.header_off + fr.pixel_off
        return table[a : a + fr.width * fr.height]

    def mask(self, table: bytes, f: int) -> bytes:
        fr = self.frames[f]
        a = self.header_off + fr.mask_off
        return table[a : a + fr.width * fr.height]


def parse(table: bytes) -> list[Shape]:
    (shape_list_off,) = struct.unpack(">i", table[4:8])
    (n,) = struct.unpack(">h", table[shape_list_off : shape_list_off + 2])
    offs = struct.unpack(f">{n}i", table[shape_list_off + 2 : shape_list_off + 2 + 4 * n])
    shapes = []
    for so in offs:
        sh = Shape(so)
        frame_list_off, anim_list_off = struct.unpack(">ii", table[so + 2 : so + 10])
        fl = so + frame_list_off
        (nf,) = struct.unpack(">h", table[fl : fl + 2])
        for fo in struct.unpack(f">{nf}i", table[fl + 2 : fl + 2 + 4 * nf]):
            h = so + fo
            w, ht, x, y, po, mo = struct.unpack(">hhhhii", table[h : h + 16])
            sh.frames.append(Frame(h, w, ht, x, y, po, mo))
        al = so + anim_list_off
        (na,) = struct.unpack(">h", table[al : al + 2])
        for ao in struct.unpack(f">{na}i", table[al + 2 : al + 2 + 4 * na]):
            a = so + ao
            cnt = table[a]
            sh.anims.append([struct.unpack(">hh", table[a + 1 + 4 * c : a + 5 + 4 * c]) for c in range(cnt)])
        shapes.append(sh)
    return shapes


def frame_of_anim(shape: Shape, anim: int) -> int | None:
    """The first frame an anim shows (opcode 1)."""
    for op, operand in shape.anims[anim]:
        if op == OP_FRAME:
            return operand
    return None


def palette(name: str = "border2") -> list[int]:
    im = Image.open(IMAGES_DIR / f"{name}.tga")
    pal = im.getpalette()
    if not pal:
        raise SystemExit(f"{name}.tga has no palette")
    return (pal + [0] * 768)[:768]


def frame_image(table: bytes, shape: Shape, f: int, pal: list[int]) -> Image.Image:
    """The frame as a P image; transparent pixels (mask 0xFF) are index 0 wherever the sprite is see-through."""
    fr = shape.frames[f]
    im = Image.frombytes("P", (fr.width, fr.height), shape.pixels(table, f))
    im.putpalette(pal)
    return im


def mask_image(table: bytes, shape: Shape, f: int) -> Image.Image:
    fr = shape.frames[f]
    return Image.frombytes("L", (fr.width, fr.height), shape.mask(table, f))


def patch(table: bytes, shape: Shape, frames: dict[int, tuple[int, int, int, int, bytes, bytes]]) -> bytes:
    """New (width, height, x, y, pixels, mask) per frame index, appended; the headers are rewritten in place."""
    out = bytearray(table)
    for f, (w, h, x, y, pixels, mask) in frames.items():
        if len(pixels) != w * h or len(mask) != w * h:
            raise ValueError(f"frame {f}: {w}×{h} needs {w * h} bytes, got {len(pixels)} / {len(mask)}")
        po = len(out) - shape.header_off
        out += pixels
        mo = len(out) - shape.header_off
        out += mask
        if len(out) % 2:
            out += b"\0"
        hdr = shape.frames[f].header_off
        out[hdr : hdr + 16] = struct.pack(">hhhhii", w, h, x, y, po, mo)
    return bytes(out)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cmd, name = sys.argv[1], sys.argv[2]
    path = SHAPES_DIR / f"{name}.shapes"
    table = load(path)
    shapes = parse(table)
    if cmd == "list":
        print(f"{name}.shapes · {len(table)} bytes unpacked · {len(shapes)} shapes")
        for i, s in enumerate(shapes):
            print(f"  shape {i:2}: {len(s.frames):3} frames, {len(s.anims):3} anims")
        return
    idx = int(sys.argv[3])
    s = shapes[idx]
    if cmd == "info":
        for a, cmds in enumerate(s.anims):
            print(f"anim {a}: frame {frame_of_anim(s, a)} · {cmds}")
        for f, fr in enumerate(s.frames):
            used = sorted(set(s.pixels(table, f)))
            masks = sorted(set(s.mask(table, f)))
            print(f"frame {f}: {fr.width}×{fr.height} at ({fr.x},{fr.y}) · indices {used} · mask values {masks}")
        return
    if cmd == "export":
        out = Path(sys.argv[4])
        out.mkdir(parents=True, exist_ok=True)
        pal = palette()
        for f in range(len(s.frames)):
            frame_image(table, s, f, pal).save(out / f"{name}-{idx}-{f}.png")
            mask_image(table, s, f).save(out / f"{name}-{idx}-{f}.mask.png")
        print(f"wrote {len(s.frames)} frames to {out}")
        return
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
