# MiReina web build (Power Pete)

WebAssembly build of this fork for the private MiReina site. The native (macOS/Windows/Linux)
build is untouched: every change is guarded by `MR_WEB` or by `if(EMSCRIPTEN)` in CMake.

## Install the toolchain (once)

```bash
brew install emscripten cmake
```

## Build

```bash
bash mireina/tools/build-wasm.sh
```

The script builds SDL3 3.2.2 for Emscripten once into `libs/` (a few minutes, cached afterwards),
then the game into `build-wasm/`:

| File | Size (2026-10-02) | What it is |
|---|---|---|
| `build-wasm/pete.js` | ~227 KB | loader; defines the global `createPowerPete(moduleArg): Promise<Module>` |
| `build-wasm/pete.wasm` | ~1.9 MB | the engine |
| `build-wasm/pete.data` | ~13.9 MB | the `Data` folder, preloaded at `/Data` |

`Module.FS` and `Module.wasmMemory` are exported. `libs/` and `build-wasm/` are git-ignored.

## Dev harness

```bash
python3 -m http.server 8787      # from the repository root
# then open http://localhost:8787/mireina/tools/dev.html
```

The harness creates the `#pp-canvas` the game draws into, pipes stdout/stderr into a log div and
exposes the `mr.*` helpers that will drive the shared-memory input block (no effect until the
bridge of task 2 exists).

Note: Chrome throttles timers to about 1 Hz in a hidden or backgrounded tab, and the game's main
loop advances one frame per `emscripten_sleep`. A tab that is not visible therefore runs at ~1 fps.
This is a browser policy, not a build problem — keep the tab in the foreground (or let the game
play audio, which exempts the tab from throttling) when timing anything.

## What the web build changes

- **CMake** (`CMakeLists.txt`): `-fexceptions` and `MR_WEB=1` for the game *and* Pomme
  (wasm-native exceptions are incompatible with ASYNCIFY); no `find_package(OpenGL)`; `GLRENDER`
  off, so the SDL 2D renderer (WebGL2 / `opengles2`) is used instead of the fixed-function GL
  renderer; static SDL3; output named `pete.js`; `-sMODULARIZE=1 -sEXPORT_NAME=createPowerPete`,
  `-sASYNCIFY=1`, `-sEXIT_RUNTIME=1`, WebGL2, and `--preload-file Data@/Data`.
- **`src/Drivers/SDLRender.c`**: `emscripten_sleep(0)` after `SDL_RenderPresent`, so the blocking
  1995 game loop yields to the browser once per frame (paint + input delivery).
- **`src/Heart/FilterThreads.c`**: one filter thread on the web (web workers would need COOP/COEP).
- **`src/Boot.cpp`**: the data folder is the preloaded `Data`; no `gamecontrollerdb.txt` (SDL's
  built-in gamepad mappings are used); SDL canvas/keyboard hints; no message box on a fatal error.

## Known fixes

- **`src/Heart/Input.c`, `TryOpenGamepad`**: wrapping the `showMessage` message-box block in
  `#if !MR_WEB` (Task 3) left `showMessage` unused on the web, which `-Wunused-parameter` flagged.
  Added `(void) showMessage;` under `#if MR_WEB` at the top of the function to keep the build
  warning-free; native behavior is unchanged.

- **`src/Heart/SettingsScreen.c`**: hiding the `"display mode"` and `"titlebar debug"` cycler
  entries on the web (Task 4) left `OnChangeFullscreenMode` and `OnChangeDebugInfoInTitleBar`
  unused there, which `-Wunused-function` flagged. Wrapped both declarations and definitions in
  `#if !MR_WEB` to keep the build warning-free; native behavior is unchanged.

- **`src/Boot.cpp`, window creation**: `SDL_WINDOW_RESIZABLE` is dropped on the web (Task 4) so SDL
  stops stretching the canvas to the browser window — the page scales the fixed 832×480 canvas
  itself with CSS.
- **`src/Boot.cpp`, keyboard hint**: SDL 3.2.2 passes `SDL_HINT_EMSCRIPTEN_KEYBOARD_ELEMENT`
  straight through to Emscripten as an event target string, not a DOM id, so it is set to the CSS
  selector `"#pp-canvas"` (not `"#canvas"`).

Otherwise none. The unmodified engine and Pomme compiled under Emscripten 6.0.10 without a single
source fix beyond the four guarded patches listed above.

Notes on the toolchain, for the record:

- Emscripten 6.0.10-git, CMake 4.4.3, SDL 3.2.2, macOS arm64.
- The `--exclude-file=<glob>` form (with `=`) is accepted by this emcc; the space-separated form
  was not needed. `gamecontrollerdb.txt`, `view68k.tga` and `viewppc.tga` are absent from the
  preload package, as intended.
- Before the CMake patch, the web build failed at link with `undefined symbol: glOrtho` (and the
  rest of the fixed-function GL calls in `src/Drivers/GLRender.c`) — that is what turning
  `GLRENDER` off on the web fixes.
