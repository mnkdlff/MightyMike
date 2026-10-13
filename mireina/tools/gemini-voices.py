#!/usr/bin/env python3
"""Speaks the nine voice lines of Power Reina with the Gemini TTS API: a WAV per line, ready for voices.sh.

The lines come from mireina/texts.json (key "voice", one "<phrase> (<Name>.aiff)" per line, as entered in the
« Power Pete Textos » artifact). Each phrase is spoken in the chosen prebuilt voice with a short style
instruction, trimmed of its silences and written to <out>/<Name>.wav (24 kHz, 16-bit, mono). Then
`bash mireina/tools/voices.sh` converts whatever sits in mireina/voices/ into the game's AIFF files.

Key: GEMINI_API_KEY in the environment, else read from ../MiReina/.env.local (never printed).
  .venv-tools/bin/python mireina/tools/gemini-voices.py                      # all nine, default voice
  .venv-tools/bin/python mireina/tools/gemini-voices.py EatMyDust Ouch       # a subset
  .venv-tools/bin/python mireina/tools/gemini-voices.py --voice Zephyr --out /tmp/preview
Options: --voice NAME (prebuilt Gemini voice, default Fenrir), --model NAME, --style TEXT, --out DIR.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import images  # noqa: E402  (ROOT)

# gemini-images.py has a dash in its name: load it by path for its key reader and HTTP helper.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("gemini_images", Path(__file__).resolve().parent / "gemini-images.py")
_gi = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_gi)
api_key, request = _gi.api_key, _gi.request

TEXTS = images.ROOT / "mireina" / "texts.json"
DEFAULT_OUT = images.ROOT / "mireina" / "voices"
DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Fenrir"
DEFAULT_STYLE = "Shout like an excited cartoon action hero, in Spanish, fast and punchy:"
NAMES = ["IllSaveYou", "ComeHereRodent", "TakeThat", "EatMyDust", "NoMoreNiceGuy", "FireInTheHole", "Ouch", "FreeDude", "DeathScream"]


def lines() -> dict[str, str]:
    """{Name: phrase} from texts.json's "voice" entry."""
    raw = json.loads(TEXTS.read_text("utf8"))["voice"]
    out = {}
    for line in raw.splitlines():
        m = re.match(r"\s*(.*?)\s*\((\w+)\.aiff\)\s*$", line)
        if m:
            out[m.group(2)] = m.group(1)
    missing = [n for n in NAMES if n not in out]
    if missing:
        raise SystemExit(f"texts.json voice entry lacks: {', '.join(missing)}")
    return out


def speak(key: str, model: str, voice: str, text: str, style: str) -> tuple[bytes, int]:
    """Raw 16-bit little-endian mono PCM and its sample rate. TTS models take the style as a short prefix
    in the prompt itself ("Say cheerfully: …"); they refuse system instructions."""
    body = {
        "contents": [{"parts": [{"text": f"{style} {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    res = request("POST", f"models/{model}:generateContent", key, body)
    cands = res.get("candidates") or []
    for p in (cands[0].get("content", {}).get("parts", []) if cands else []):
        blob = p.get("inlineData") or p.get("inline_data")
        if blob:
            mime = str(blob.get("mimeType") or blob.get("mime_type", ""))
            if not mime.startswith("audio/L16"):
                raise SystemExit(f"unexpected audio type {mime!r}: the converter expects raw 16-bit PCM")
            rate = int((re.search(r"rate=(\d+)", mime) or [0, 24000])[1])
            return base64.b64decode(blob["data"]), rate
    raise SystemExit(f"no audio in the answer: {json.dumps(res)[:400]}")


def trim(pcm: bytes, rate: int, threshold: int = 600, margin_ms: int = 60) -> bytes:
    """Cuts the leading and trailing silence (16-bit samples under `threshold`), keeping a short margin."""
    n = len(pcm) // 2
    samples = memoryview(pcm).cast("h")
    first = next((i for i in range(n) if abs(samples[i]) > threshold), 0)
    last = next((i for i in range(n - 1, -1, -1) if abs(samples[i]) > threshold), n - 1)
    margin = rate * margin_ms // 1000
    a, b = max(0, first - margin), min(n, last + 1 + margin)
    return bytes(samples[a:b].tobytes())


def transcribe(key: str, model: str, path: Path) -> str:
    """What a text model hears in the file: a cheap check that only the phrase was spoken."""
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(path.read_bytes()).decode()}},
            {"text": "Transcribe exactly what is said in this audio, nothing else."},
        ]}],
    }
    res = request("POST", f"models/{model}:generateContent", key, body)
    parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    return " ".join(p.get("text", "") for p in parts).strip()


def write_wav(path: Path, pcm: bytes, rate: int) -> float:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return len(pcm) / 2 / rate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--style", default=DEFAULT_STYLE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", metavar="MODEL", help="transcribe each file with this text model and print what it hears")
    a = ap.parse_args()
    phrases = lines()
    names = a.names or NAMES
    unknown = [n for n in names if n not in phrases]
    if unknown:
        raise SystemExit(f"unknown voice name(s): {', '.join(unknown)} (expected {', '.join(NAMES)})")
    key = api_key()
    a.out.mkdir(parents=True, exist_ok=True)
    print(f"model · {a.model} · voice {a.voice}")
    for name in names:
        pcm, rate = speak(key, a.model, a.voice, phrases[name], a.style.strip())
        dst = a.out / f"{name}.wav"
        dur = write_wav(dst, trim(pcm, rate), rate)
        heard = f" · heard: {transcribe(key, a.check, dst)!r}" if a.check else ""
        print(f"wrote · {dst} ({dur:.2f}s) — {phrases[name]}{heard}")


if __name__ == "__main__":
    main()
