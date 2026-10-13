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
- **`src/Heart/Cinema.c`** (`MR_HoldScreen`): the still screens La Reina must have time to see stay longer
  on the web — the lose picture at least 9 s, the world sign at least 6 s, the confetti screen at least 10 s
  (longer while their music plays), and a tap skips them only after a grace period (2 s, 1 s, 2 s) so a tap
  left over from the game does not blow through them; Karim's win text scrolls a third slower
  (`DoScrollingTextScreen` takes the line period, so the spacing stays the same). The legal screen keeps its 6 s.
- **`src/Boot.cpp`**: the data folder is the preloaded `Data`; no `gamecontrollerdb.txt` (SDL's
  built-in gamepad mappings are used); SDL canvas/keyboard hints; no message box on a fatal error.

## Known fixes

- **`CMakeLists.txt`, Emscripten block**: `--preload-file` packs `Data/` at link time, but CMake
  did not know the link depended on those files, so a build after an image/text/voice change
  reused the old `pete.data` (same build hash as before: the giveaway). The target now lists every
  file under `Data/` as a `LINK_DEPENDS`, so any change there relinks and repacks.

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

- **`src/Heart/SettingsScreen.c`, `"playfield size"`**: the row is wrapped in `#if !MR_WEB` — the
  page hard-codes the 832×480 canvas, so letting a player cycle `gGamePrefs.pfSize` would resize
  the playfield under a canvas that cannot follow. That left `OnChangePlayfieldSizeViaSettings`
  unused on the web (its only other caller, the `"windowed zoom"` row, is already web-hidden), so
  its declaration and definition are wrapped in `#if !MR_WEB` too, the same way
  `OnChangeFullscreenMode` and `OnChangeDebugInfoInTitleBar` were; native behavior is unchanged.

- **`src/Heart/Cinema.c`, `ChoosePlayerMode`**: the `#if MR_WEB` shortcut that jumps straight to
  `restore_chosen` when the vestíbulo already chose a slot skips the save-game dialog loop, and
  with it the `gLoadOldGameFlag = false;` that loop performed before polling. It now sets
  `gLoadOldGameFlag = false;` explicitly before the `goto`, so a web run can never inherit a stale
  true from an earlier game; native behavior is unchanged.

Otherwise none. The unmodified engine and Pomme compiled under Emscripten 6.0.10 without a single
source fix beyond the six guarded patches listed above.

- **Music toggled before the first song crashed the web build.** The page pushes its audio flags right after
  `boot` (`audioDirty`), and `MR_Tick` applies them through `OnToggleMusic` → `StartMusic`, which read the song
  handle while `SoundHand_Music` was still nil (the legal screen has no song): `GetHandleSize(nil)` trapped with
  « memory access out of bounds ». `StartMusic` now returns when no song is loaded; the next `PlaySong` honours
  the preference. The link also keeps function names (`--profiling-funcs`) so a trap in the page names its frames.
- **Tab title.** SDL set `document.title` to the native name; the web edition titles its window Power Reina
  (`MR_WINDOW_TITLE` in `version.h.in`, used by `Boot.cpp` and `SettingsScreen.c`).
- **No local path in the wasm.** `-ffile-prefix-map` on the game and on SDL: `strings pete.wasm | grep -c /Users/` is 0.
  SDL's install is keyed on `.prefix-mapped`, so a cached SDL built without the flag is rebuilt once.

- **Top 8 table under the new title.** `scores.tga` now carries « Top Scores de la Reina » on two lines down to
  y=222; on the web the table starts at `TOP_SCORE_VTAB` 228 with a 30 px line gap (native: 190 / 32).

## Notes

- The `pause` hooks in `src/Heart/Infobar.c:ShowPaused` are **dead code**: `ShowPaused`'s only
  upstream caller is commented out, so the function never runs. The live emitter of the `pause`
  event is `AskIfQuit` in the same file — that is what the page actually sees when a player presses
  Esc.
- The `alert` kind (non-fatal `DoAlert`) is distinct from `fatal` (`DoAssert`, `DoFatalAlert`,
  `DoFatalAlert2`): an `alert` is informational and the engine keeps running, so the page only logs
  it (`console.warn`) instead of tearing the stage down.
- The `"playfield size"` row of Settings > Video is hidden on the web (see Known fixes above); the
  page owns the 832×480 canvas size.

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

## Persistence (MiReina)

MiReina mirrors the game files in Supabase. On every `file` event the page reads the named file from
`/home/web_user/.config/MightyMike/` through `Module.FS.readFile` (the page never calls into the engine)
and stores it base64 in `level_answers` as `file:<name>`; before the next boot it writes every stored file
back in `preRun`, so Prefs, HighScores and the save travel across devices. Only names matching
`Prefs | HighScores | PowerPeteSavedGameData[1-4] | PowerPeteSavedGameData2x<p><g> | PeteP[12]Swap.data`
are accepted, each at most 64 KiB. The web build saves into slot 1 only; the page offers « Continuar »
when `PowerPeteSavedGameData1` exists and asks for that slot through `loadSlot`. The counters of the
vestíbulo (sessions, bunnies, deaths, areas, worlds, weapons, best score, play time) are reduced from the
events table above; nothing here changes the engine.

## Images (La Reina's edition)

Every screen is an 8-bit colormapped TGA (`src/Drivers/TGA.c`: type 1 or 9, no id field, 24-bit
palette, ≤ 256 colours) and installs its own palette while shown. `mireina/tools/images.py` turns
a PNG into that format (run it with the Pillow venv: `python3 -m venv .venv-tools && .venv-tools/bin/pip
install pillow`, then `.venv-tools/bin/python mireina/tools/images.py`):

- **free palette** (nothing drawn over): legal 420×251, charging, head, lose, the five scenes.
- **kept palette** (sprites drawn over are indexed in it): titlepagepp, diff, playerchoose, scores,
  bonus, win, credits1, winbw, overheadmap — the new picture is quantized onto the original palette,
  so keep the original colour scheme or the sprites will look wrong.

Drop Gemini outputs as `mireina/images/<name>.png` (exact size) and run the script; the originals of
the artwork screens are exported to `mireina/images/orig/` (`images.py export`). The text screens
(legal, charging, head, bonus, credits1) are rendered from `mireina/texts.json` by
`mireina/tools/render-screens.py`. Rebuild afterwards: the images live in `pete.data`.

## Voices (La Reina's edition)

The nine spoken effects (`Data/Audio/Default/{IllSaveYou,ComeHereRodent,TakeThat,EatMyDust,NoMoreNiceGuy,FireInTheHole,Ouch,FreeDude,DeathScream}.aiff`)
are loaded at boot by `InitSound`; a file Pomme cannot read ends in a `fatal` event in the page.
`mireina/tools/voices.sh` converts recordings from `mireina/voices/` with `afconvert` into AIFF 16-bit
big-endian PCM at 22 050 Hz mono (Pomme's AIFF reader: `extern/Pomme/src/SoundFormats/AIFF.cpp`,
'NONE' compression). The recording guide is `mireina/voices/README.md`. Rebuild afterwards.
Without recordings, `.venv-tools/bin/python mireina/tools/gemini-voices.py --voice Fenrir --out mireina/voices`
speaks the nine lines of `texts.json` (`voice`) with the Gemini TTS API (key as for `gemini-images.py`; the style
is a short prefix of the prompt, these models refuse system instructions; `--check gemini-3.8-flash` transcribes
each file back) as WAVs that `voices.sh` then converts.

## Balloons (La Reina's edition)

The same nine lines are speech balloons drawn above Pete while the voice plays (`MakeMikeMessage`,
`src/Misc/MiscAnims.c`): `Data/Shapes/main.shapes`, shape 5 (`ObjType_Message`), one frame and one anim per
line in `messageNum` order (IllSaveYou, ComeHereRodent, TakeThat, EatMyDust, food, FreeDude, Ouch,
NoMoreNiceGuy, FireInTheHole; DeathScream has no balloon). `mireina/tools/shapes.py` reads and patches
Pangea's shape tables (packed container RLB/RLW/raw, big-endian offsets, per frame w/h/x/y + pixel and mask
blobs relative to the shape header; `patch` appends the new blobs and saves the table unpacked, which
`LoadPackedFile` accepts). `mireina/tools/balloons.py preview DIR` renders the balloons from the `voice`
lines of `texts.json` (an original balloon with its lettering erased, stretched, Comic Sans MS Bold 14 px
upper case, FreeDude in red) and `balloons.py apply` writes them into `main.shapes`. Sprites use the Mac
system palette in play (`border2.tga`): 0 white, 255 black, greys 43/86/129/172 and 245–254. Rebuild
afterwards: the file lives in `pete.data`.

## Texts (La Reina's edition)

- `mireina/texts.json` is an export of the « Power Pete Textos » artifact (`{ itemId: text }`).
- `node mireina/tools/texts.mjs` writes `Data/System/credits.txt`, `win1.txt` and (when present) `win3.txt` from it,
  then validates every scrolling text against the font: A-Z, a-z, 0-9, `! ? . : @ ,` (the hyphen is tolerated,
  the original credits carry `1995-2000`), 32 columns, a single closing `~`. `node mireina/tools/check-texts.mjs`
  runs the validation alone; `node mireina/tools/test-texts.mjs` tests it.
- Strings that live in the C sources use `MR_TXT(web, native)` from `src/Web/MRBridge.h`: the web build shows
  La Reina's text, the native build the original. Today: the `SCORE DE LA REINA` label (`ShowLastScore`, centred
  for its 17 letters) and the settings captions (`teclado / gamepad / video / audio de la reina`, `power reina`).
