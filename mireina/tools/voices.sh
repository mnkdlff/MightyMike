#!/usr/bin/env bash
# Converts Karim's recordings into the effect files the game loads at boot.
# Input:  mireina/voices/<Name>.m4a (or .wav, .mp3, .aiff, .caf) for the nine names below.
# Output: Data/Audio/Default/<Name>.aiff — AIFF, 16-bit big-endian PCM, 22 050 Hz, mono.
# Usage: bash mireina/tools/voices.sh        (macOS: uses afconvert / afinfo)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IN="$ROOT/mireina/voices"
OUT="$ROOT/Data/Audio/Default"
NAMES=(IllSaveYou ComeHereRodent TakeThat EatMyDust NoMoreNiceGuy FireInTheHole Ouch FreeDude DeathScream)

command -v afconvert >/dev/null || { echo "afconvert not found (macOS only)" >&2; exit 1; }
done=0
for name in "${NAMES[@]}"; do
  src=""
  for ext in m4a wav mp3 aiff caf; do
    [ -f "$IN/$name.$ext" ] && { src="$IN/$name.$ext"; break; }
  done
  if [ -z "$src" ]; then
    echo "-- · $name (no recording in mireina/voices/, original kept)"
    continue
  fi
  afconvert -f AIFF -d BEI16@22050 -c 1 "$src" "$OUT/$name.aiff"
  afinfo "$OUT/$name.aiff" | grep -q "16-bit" || { echo "$name: conversion did not produce 16-bit PCM" >&2; exit 1; }
  dur="$(afinfo "$OUT/$name.aiff" | sed -n 's/.*estimated duration: \([0-9.]*\) sec.*/\1/p')"
  echo "wrote · Data/Audio/Default/$name.aiff (${dur}s)"
  done=$((done + 1))
done
echo "$done voice(s) converted; rebuild the web build to ship them (they live in pete.data)"
