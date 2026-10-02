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

- **`src/Heart/Main.c`, `InitDefaultPrefs`**: the web defaults (Task 4) also set
  `gGamePrefs.displayMode = kDisplayMode_Windowed`. Left at its native default of
  `kDisplayMode_FullscreenStretched`, `ApplyPrefs()` → `SetFullscreenMode(true)` calls
  `SDL_SetWindowFullscreen(gSDLWindow, true)` on boot, which on the Emscripten/SDL3 web backend
  stretches the canvas to the screen's resolution as soon as the deferred fullscreen request
  resolves on the player's first gesture (click or key press) — breaking the fixed 832×480 canvas
  the page relies on. Forcing windowed mode on the web keeps `SetFullscreenMode` from ever calling
  `SDL_SetWindowFullscreen`; native behavior is unchanged.

- **`src/Heart/SettingsScreen.c`, `OnMenuEntered`**: hiding the `"windowed zoom"` and `"monitor"`
  cycler entries from `gVideoMenu` on the web (Task 4) left `OnMenuEntered`'s
  `GAME_ASSERT(row >= 0)` calls with nothing to find — `FindRowControlling` returns `-1` for
  `gGamePrefs.windowedZoom` and `gGamePrefs.displayNum` once those rows don't exist, firing a fatal
  assertion (and exiting the app) the moment a player opened Settings > Video on the web build.
  Wrapped the whole `if (gMenu == gVideoMenu) { ... }` body in `#if !MR_WEB`, since those
  `numChoices` recalculations are meaningless on the web anyway; native behavior is unchanged.

Otherwise none. The unmodified engine and Pomme compiled under Emscripten 6.0.10 without a single
source fix beyond the six guarded patches listed above.

Notes on the toolchain, for the record:

- Emscripten 6.0.10-git, CMake 4.4.3, SDL 3.2.2, macOS arm64.
- The `--exclude-file=<glob>` form (with `=`) is accepted by this emcc; the space-separated form
  was not needed. `gamecontrollerdb.txt`, `view68k.tga` and `viewppc.tga` are absent from the
  preload package, as intended.
- Before the CMake patch, the web build failed at link with `undefined symbol: glOrtho` (and the
  rest of the fixed-function GL calls in `src/Drivers/GLRender.c`) — that is what turning
  `GLRENDER` off on the web fixes.

## Events (MiReina bridge)

The engine notifies the page by dispatching a `CustomEvent("powerpete")` on `window`, whose
`detail` is `{ kind, a, b }` for `MR_EMIT(kind, a, b)` or `{ kind, s }` for
`MR_EMIT_STR(kind, s)` (`src/Web/MRBridge.c`, `src/Web/MRBridge.h`). 34 distinct kinds are
emitted, grouped below in the order they appear in the Task 5 brief's "Produces" list:

| Kind | a | b / s | Emitted by |
|---|---|---|---|
| `title` | 0 | 0 | `src/Heart/Cinema.c:DoTitleScreen` |
| `settings` | 0 | 0 | `src/Heart/SettingsScreen.c:DoSettingsScreen` |
| `difficulty` | difficulty mode | 0 | `src/Heart/Cinema.c:DoDifficultyScreen` |
| `players` | 1 or 2 | 0 | `src/Heart/Cinema.c:ChoosePlayerMode` |
| `game_start` | difficulty | restored (0/1) | `src/Heart/Main.c:InitGame` |
| `world_intro` | scene | 0 | `src/Heart/Cinema.c:DoSceneScreen` |
| `area_start` | scene | area | `src/Heart/Main.c:InitArea` |
| `attempt` | scene | area | `src/Heart/Main.c:PlayArea` |
| `bunny_freed` | bunnies left | bunnies total | `src/Misc/Bonus.c:DecBunnyCount` |
| `all_bunnies` | scene | area | `src/Misc/Bonus.c:DecBunnyCount` |
| `weapon` | weapon type | 0 | `src/MeAndMo/Weapon.c:GetAWeapon` |
| `key` | key index | 0 | `src/MeAndMo/MyGuy.c:MeHitBonusObject` |
| `heart` | health | 0 | `src/Heart/Infobar.c:GiveMeHealth` |
| `coins` | coins total | 0 | `src/Heart/Infobar.c:GetCoins` |
| `nuke` | 0 | 0 | `src/Misc/Bonus.c:StartNuke` |
| `life_lost` | lives left | 0 | `src/Heart/Main.c:Do1PlayerGame`, `src/Heart/Main.c:Do2PlayerGame` |
| `area_done` | scene | area | `src/MeAndMo/MyGuy.c:MoveMe_Liftoff` |
| `bonus` | bunnies | coins | `src/Heart/Cinema.c:ShowBonusScreen` |
| `saved` | slot | 0 | `src/Heart/Main.c:SaveGame` |
| `loaded` | slot | 0 | `src/Heart/Main.c:LoadGame` |
| `game_over` | score | 0 | `src/Heart/Cinema.c:DoLoseScreen` |
| `win` | difficulty | score | `src/Heart/Cinema.c:DoWinScreen` |
| `score_shown` | score | 0 | `src/Heart/Cinema.c:ShowLastScore` |
| `high_score` | rank | score | `src/Heart/Cinema.c:AddHighScore` |
| `name_entry` | 1 or 0 | 0 | `src/Heart/Cinema.c:DoEnterName` |
| `credits` | 0 | 0 | `src/Heart/Cinema.c:DoCredits` |
| `pause` | 1 or 0 | 0 | `src/Heart/Infobar.c:ShowPaused`, `src/Heart/Infobar.c:AskIfQuit` |
| `quit_game` | score | 0 | `src/Heart/Infobar.c:AskIfQuit` |
| `exit` | 0 | 0 | `src/Heart/Misc.c:CleanQuit` |
| `file` | — | `s` = file name | `src/Heart/Cinema.c:SaveHighScores`, `src/Heart/Main.c:SaveGame`, `src/Heart/Main.c:SavePrefs` |
| `scores` | — | `s` = JSON array | `src/Heart/Cinema.c:SaveHighScores` |
| `alert` | — | `s` = message | `src/Heart/Misc.c:DoAlert` |
| `fatal` | — | `s` = message | `src/Heart/Misc.c:DoAssert`, `src/Heart/Misc.c:DoFatalAlert`, `src/Heart/Misc.c:DoFatalAlert2` |
| `boot` | 0 | 0 | `src/Web/MRBridge.c:MR_Boot` |

Verified against the source with `grep -rho 'MR_EMIT\(_STR\)\?("[a-z_]*"' src | sort -u`: 34
distinct kinds, matching the list above.

## Game files

The game writes its files under `/home/web_user/.config/MightyMike/` (Emscripten's virtual
filesystem). The page learns about each write through the `file` event, whose `s` carries the
file name:

- `Prefs`
- `HighScores`
- `PowerPeteSavedGameData1` .. `PowerPeteSavedGameData4` (one-player save slots)
- `PowerPeteSavedGameData2x<p><g>` (two-player save slots, `<p>` = player, `<g>` = game number)
- `PeteP1Swap.data`, `PeteP2Swap.data`
