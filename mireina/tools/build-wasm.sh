#!/usr/bin/env bash
# Builds SDL3 for Emscripten once (libs/), then the game into build-wasm/ (pete.js, pete.wasm, pete.data).
# Usage: bash mireina/tools/build-wasm.sh    (needs: brew install emscripten cmake)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SDL_VER=3.2.2
LIBS="$ROOT/libs"
SDL_SRC="$LIBS/SDL3-$SDL_VER"
SDL_INSTALL="$LIBS/SDL3-$SDL_VER-wasm-install"
JOBS="$(sysctl -n hw.ncpu 2>/dev/null || nproc)"

command -v emcmake >/dev/null || { echo "emcmake not found: brew install emscripten" >&2; exit 1; }
command -v cmake >/dev/null || { echo "cmake not found: brew install cmake" >&2; exit 1; }

if [ ! -f "$SDL_INSTALL/lib/cmake/SDL3/SDL3Config.cmake" ]; then
  mkdir -p "$LIBS"
  if [ ! -d "$SDL_SRC" ]; then
    # extract into a temporary tree and move it into place only once tar succeeded, so a failed
    # download never leaves a half tree that the [ ! -d "$SDL_SRC" ] guard above would accept
    SDL_TMP="$(mktemp -d "$LIBS/SDL3-$SDL_VER.tmp.XXXXXX")"
    trap 'rm -rf "$SDL_TMP"' EXIT
    curl -fsSL "https://libsdl.org/release/SDL3-$SDL_VER.tar.gz" | tar xz -C "$SDL_TMP"
    mv "$SDL_TMP/SDL3-$SDL_VER" "$SDL_SRC"
    rm -rf "$SDL_TMP"
    trap - EXIT
  fi
  emcmake cmake -S "$SDL_SRC" -B "$SDL_SRC/build-wasm" \
    -DCMAKE_BUILD_TYPE=Release -DSDL_SHARED=OFF -DSDL_STATIC=ON -DSDL_TEST_LIBRARY=OFF \
    -DCMAKE_INSTALL_PREFIX="$SDL_INSTALL"
  cmake --build "$SDL_SRC/build-wasm" -j"$JOBS"
  cmake --install "$SDL_SRC/build-wasm"
fi

emcmake cmake -S "$ROOT" -B "$ROOT/build-wasm" -DCMAKE_BUILD_TYPE=Release \
  -DSDL3_DIR="$SDL_INSTALL/lib/cmake/SDL3"
cmake --build "$ROOT/build-wasm" -j"$JOBS"
ls -la "$ROOT/build-wasm/pete.js" "$ROOT/build-wasm/pete.wasm" "$ROOT/build-wasm/pete.data"
