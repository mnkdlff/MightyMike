#!/usr/bin/env python3
"""Generates La Reina's artwork screens with the Gemini API: original + prompt in, 640×480 PNG out.

The prompts are the pack in MiReina (docs/prompts/2026-10-13-power-reina-gemini.md): one section per
screen, the prompt in its fenced block. Each original (Data/Images/<name>.tga) is sent with its prompt to
an image model; the returned picture is fitted to 640×480 and written to mireina/images/<name>.png, where
images.py converts it into the game's TGA (kept palette where sprites are drawn over).

Key: GEMINI_API_KEY in the environment, else read from ../MiReina/.env.local (never printed).
Run with the project venv:
  .venv-tools/bin/python mireina/tools/gemini-images.py                 # every screen of the pack
  .venv-tools/bin/python mireina/tools/gemini-images.py scores win      # a subset
  .venv-tools/bin/python mireina/tools/gemini-images.py --list-models   # what the key can use
Options: --model NAME, --suffix "extra instruction" (appended to every prompt), --convert (run images.py after),
         --out DIR (default mireina/images), --pack PATH (the markdown pack).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import images  # noqa: E402

API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_PACK = images.ROOT.parent / "MiReina" / "docs" / "prompts" / "2026-10-13-power-reina-gemini.md"
KEY_FILE = images.ROOT.parent / "MiReina" / ".env.local"
# Preference order when the key lists several image models: the Pro ones render text far better.
PREFER = ["gemini-3.1-pro-image", "gemini-3-pro-image", "pro-image", "flash-image", "image"]
SIZE = (640, 480)


def api_key() -> str:
    import os

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        for line in KEY_FILE.read_text("utf8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit(f"GEMINI_API_KEY missing: export it or add it to {KEY_FILE}")
    return key


def request(method: str, path: str, key: str, body: dict | None = None, tries: int = 3) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}/{path}", data=data, method=method, headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf8", "replace")
            if e.code in (429, 500, 503) and attempt < tries - 1:
                wait = 10 * (attempt + 1)
                print(f"   HTTP {e.code}, retrying in {wait}s")
                time.sleep(wait)
                continue
            raise SystemExit(f"HTTP {e.code} on {path}: {payload[:600]}")
    raise SystemExit("unreachable")


def list_models(key: str) -> list[str]:
    out, token = [], None
    while True:
        page = request("GET", "models?pageSize=200" + (f"&pageToken={token}" if token else ""), key)
        out += [m["name"].split("/", 1)[1] for m in page.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        token = page.get("nextPageToken")
        if not token:
            return out


def pick_model(available: list[str]) -> str:
    candidates = [m for m in available if "image" in m and "embedding" not in m]
    for pref in PREFER:
        matches = sorted((m for m in candidates if pref in m), reverse=True)
        if matches:
            return matches[0]
    raise SystemExit(f"no image model on this key; models seen: {', '.join(sorted(available))[:800]}")


def parse_pack(path: Path) -> dict[str, str]:
    """{name: prompt} from the markdown pack (## N. `name` — … then a fenced block)."""
    text = path.read_text("utf8")
    out = {}
    for section in re.split(r"\n## ", text)[1:]:
        head, _, rest = section.partition("\n")
        m = re.match(r"\d+\. `(\w+)`", head)
        block = re.search(r"```\n(.*?)```", rest, re.S)
        if m and block:
            out[m.group(1)] = " ".join(block.group(1).split())
    return out


def png_bytes(name: str) -> bytes:
    buf = io.BytesIO()
    Image.open(images.DATA_IMAGES / f"{name}.tga").convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def generate(key: str, model: str, name: str, prompt: str) -> Image.Image:
    body = {
        "contents": [{"parts": [{"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png_bytes(name)).decode()}}, {"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"], "imageConfig": {"aspectRatio": "4:3"}},
    }
    try:
        res = request("POST", f"models/{model}:generateContent", key, body)
    except SystemExit as e:
        if "imageConfig" not in str(e) and "aspectRatio" not in str(e):
            raise
        del body["generationConfig"]["imageConfig"]  # older image models refuse the field
        res = request("POST", f"models/{model}:generateContent", key, body)
    cands = res.get("candidates") or []
    if not cands:
        raise SystemExit(f"{name}: no candidate — {json.dumps(res)[:500]}")
    parts = cands[0].get("content", {}).get("parts", [])
    for p in parts:
        blob = p.get("inlineData") or p.get("inline_data")
        if blob and str(blob.get("mimeType") or blob.get("mime_type", "")).startswith("image/"):
            return Image.open(io.BytesIO(base64.b64decode(blob["data"]))).convert("RGB")
    texts = [p.get("text", "") for p in parts if p.get("text")]
    raise SystemExit(f"{name}: no image in the answer (finishReason {cands[0].get('finishReason')}) — {' '.join(texts)[:400]}")


def fit(im: Image.Image) -> Image.Image:
    """Centre-crop to 4:3 then resize to 640×480 (the model picks its own output size)."""
    w, h = im.size
    target = SIZE[0] / SIZE[1]
    if abs(w / h - target) > 0.01:
        if w / h > target:
            nw = round(h * target)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w / target)
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize(SIZE, Image.Resampling.LANCZOS) if im.size != SIZE else im


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--model")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--convert", action="store_true")
    ap.add_argument("--out", type=Path, default=images.DROP_DIR)
    ap.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    ap.add_argument("--list-models", action="store_true")
    a = ap.parse_args()
    key = api_key()
    if a.list_models:
        for m in sorted(list_models(key)):
            print(m)
        return
    prompts = parse_pack(a.pack)
    names = a.names or [n for n in images.GEMINI if n in prompts]
    unknown = [n for n in names if n not in prompts]
    if unknown:
        raise SystemExit(f"no prompt in the pack for: {', '.join(unknown)}")
    model = a.model or pick_model(list_models(key))
    print(f"model · {model}")
    a.out.mkdir(parents=True, exist_ok=True)
    for name in names:
        prompt = prompts[name] + (" " + a.suffix.strip() if a.suffix.strip() else "")
        print(f"→ {name}")
        im = fit(generate(key, model, name, prompt))
        dst = a.out / f"{name}.png"
        im.save(dst)
        print(f"wrote · {dst.relative_to(images.ROOT) if dst.is_relative_to(images.ROOT) else dst}")
    if a.convert:
        for name in names:
            out = images.to_tga(Image.open(a.out / f"{name}.png"), name)
            print(f"wrote · {out.relative_to(images.ROOT)} ({'kept palette' if name in images.KEEP else 'free palette'})")


if __name__ == "__main__":
    main()
