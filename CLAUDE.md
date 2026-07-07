# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A small Python toolkit that reads a chessboard off the screen. It captures a
screen region, splits it into an 8x8 grid, identifies each square by template
matching, and prints the live board state as text (with a canonical FEN).

## Commands

```bash
# One-time setup: create ./venv and install deps from requirements.txt
./setup.sh
source venv/bin/activate

# Run the live reader (needs a real display)
python3 -m chesscheat

# Run the whole test suite (pure logic + mock pipeline; needs no deps)
python3 -m unittest discover -s tests -t . -v

# Run a single test module / case / method
python3 -m unittest tests.test_recognition
python3 -m unittest tests.test_board.FenTests
python3 -m unittest tests.test_board.FenTests.test_after_e4
```

There is no build step or linter config. Runtime dependencies (`mss`,
`numpy`, `chess`, `pyautogui`, `pynput`) live in `requirements.txt`; `setup.sh`
builds a `venv/`, installs them (honors a `PYTHON` env var override), and then
downloads a **Stockfish** binary matching the host into `venv/bin` via
`scripts/install_stockfish.py` (Apple Silicon → `macos-m1-apple-silicon`
build; skip with `SKIP_STOCKFISH=1`, pin with `STOCKFISH_VERSION`). That step
is non-fatal — the reader still runs without the move assist. Installing
manually works too: `pip install -r requirements.txt`. The entire test suite
still *runs* with **no** third-party deps installed: the dep-free tests
exercise the mock implementations, and the dep-requiring tests are
`skipUnless`-guarded. Wrapper scripts: `./run.sh` (live reader; also puts
`venv/bin` on PATH so the installed `stockfish` is found without activation),
`./test.sh` (`--fast` dep-free only, `--real` dep-requiring only, or a dotted
test path), `./generate-fixtures.sh`. See `README.md` for end-user install/run
instructions.

## Coding preferences

- Prefer a functional style: functions should avoid mutating state or causing
  side effects, returning new values instead of modifying their inputs or
  globals. Keep unavoidable side effects (screen capture, `input`/`print`,
  the loop in `main`) isolated at the edges, away from the pure board logic.
- Use functional constructs — `map`, `filter`, `lambda`, comprehensions,
  generators, `functools`/`itertools` — and other Python features that
  support this style, in preference to imperative accumulation where it reads
  clearly.
- Document code with [Google Style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
  Every module, public class, and public function/method gets a docstring with
  a one-line summary; use `Args:`, `Returns:`, `Raises:`, and `Attributes:`
  sections where they apply. Omit a section when it adds nothing (e.g. no
  `Args:` for a no-argument function, no `Returns:` for `None`). Document
  abstract methods on the interface so implementations inherit the contract.

## Architecture

Source lives in the `chesscheat/` package; tests in `tests/`. The code is
**programmed to interfaces** (`chesscheat/interfaces/`, ABCs) so real and mock
parts are interchangeable. The app loop depends only on the abstractions;
concrete implementations are injected. **One class per file**, grouped into
subpackages whose `__init__.py` re-exports the public names (so
`from chesscheat.providers import GuiSetupProvider` works). Function-only
modules (`board`, `app`, `gui/dialogs`, `capture/screenshot`,
`mocks/synthetic_image`) are kept whole rather than split.

### Package map

```
chesscheat/
  app.py            run() loop + main() wiring (functions)
  board.py          pure logic (functions, no classes)
  __main__.py       `python3 -m chesscheat` entry point
  interfaces/       SetupProvider, FrameSource, ImageBackend, BoardRecognizer,
                    MoveEngine, MoveActuator, MoveTrigger
  recognition/      TemplateBoardRecognizer, NumpyImageBackend, LegalMoveFilter
  providers/        Gui/Prompt/Fallback SetupProvider, ScreenFrameSource
  assist/           StockfishMoveEngine, PyAutoGuiActuator, KeyTrigger,
                    assist_move (move_pixels)
  mocks/            Mock{SetupProvider,FrameSource,ImageBackend,MoveEngine,
                    MoveActuator,MoveTrigger}, synthetic_image
  capture/          screenshot
  gui/              dialogs, overlays (annotations/draw), LivePreview
tests/              test_board, test_recognition, test_legal_move_filter, ...
```

### Interfaces (`chesscheat/interfaces/`)

- `SetupProvider` — `select_side()`, `select_box()`, `confirm_box(image)`
  (the user's config; `confirm_box` shows what the selected region captured
  and returns False to trigger reselection).
- `FrameSource` — `grab()` returns the next board image; may raise
  `StopIteration` when a finite source is exhausted.
- `ImageBackend` — `get_square` / `feature` / `similarity` / `recolor`.
  Abstracts the image representation so the recognition *algorithm* is shared
  by a real numpy backend and a pure-Python mock backend. `recolor` repaints a
  square's empty background from one colour to another (for template synthesis).
- `BoardRecognizer` — `calibrate(image, playing_white)`, `read(image)`.
- `MoveEngine` — `best_move(fen)` returns the best move (UCI) for a full FEN,
  or None. `MoveActuator` — `apply(uci, box, playing_white)` plays a move by
  dragging the mouse. `MoveTrigger` — `start()`/`poll()`/`stop()`; `poll`
  edge-consumes one activation (the read loop polls it once per frame).

### Core logic (`chesscheat/board.py`) — dependency-free, the source of truth

`square_coord`, `cell_of` (its inverse), `square_name`/`parse_square`,
`start_label`, `is_light`, `piece_name`, `starting_board`, `render`, `to_fen`,
`castling_field`, `to_full_fen`. **Two coordinate spaces**: screen cells are
`(row, col)` with row 0 at the top; chess coords are `(file_idx 0=a, rank
1..8)`. `square_coord`/`cell_of` are the single place orientation (white vs
black) is handled. `to_fen` always emits the canonical white-view FEN
regardless of perspective; `to_full_fen(board_map, white_to_move)` appends the
side-to-move plus castling rights inferred by `castling_field` (king+rook on
home squares) for feeding an engine.

### Recognition (`chesscheat/recognition/`)

Works on **any** board (any theme, any pieces — they need not look like chess
pieces) given the assumptions: squares evenly spaced; each colour's squares
look identical everywhere; each piece looks identical wherever it is placed.

- `TemplateBoardRecognizer(backend)` — the algorithm: **calibrate from the
  starting position.** There are no bundled piece images; the first frame must
  be the standard start position, from which it learns how each piece and each
  empty square looks. Matching is **colour-aware**: a square's colour is known
  from its coordinates, so a square is only compared against templates for that
  colour (no cross-colour confusion). Because the start position shows kings
  and queens on a single colour, the missing piece-on-opposite-colour templates
  are **synthesised** (via the backend's `recolor`, repainting the empty
  background to the other colour) so every piece is recognisable on either
  colour. The same algorithm runs with the real and the mock backend. Takes
  an optional ``on_progress(done, total)`` callback reporting each of the 64
  squares learned during calibration (`main` wires a terminal progress bar),
  and an optional ``match_threshold``: `read` returns the best-guess map (so
  FEN stays valid) while ``last_scored`` holds the per-square
  ``(label, score)`` detail with sub-threshold squares marked ``'?'`` — the
  UI renders those as "unknown (score)".
- `NumpyImageBackend` — real backend. Matches **only the shape and colour of
  pieces, never the square colour**: chess UIs tint squares (selection /
  last-move highlights, which persist until the next move), so each patch is
  first **canonicalised against its own background** — the background colour
  is estimated per patch as the median of the patch's border ring, and pixels
  within `background_tol` of it are repainted to a constant grey while piece
  pixels keep their true colours. `similarity` is **SSIM** (structural
  similarity, numpy-only — **no `cv2`/skimage**): the global-window SSIM per
  RGB channel of the canonical patches, averaged — so piece colour is part
  of the match (white vs black pawn scores low), two empties score 1.0, and
  scores live in `[-1, 1]` giving thresholds a meaningful scale. `feature`
  precomputes `(canonical, mean, variance)`. `recolor` swaps a piece's
  background colour using the average empty colours (post-canonicalisation
  it barely changes the feature; kept so every piece has a template under
  both colour keys). Templates are tied to the current board
  theme/size/position; recalibrate if any change.
- `LegalMoveFilter(inner)` — a `BoardRecognizer` decorator that makes the
  reader robust to transient visual noise (mouse cursor, move highlights,
  drag animations). It tracks the game with **python-chess** (`chess`,
  imported lazily inside `calibrate`) and accepts an inner reading only when
  it equals the current state or matches the result of exactly one legal move
  (castling, en passant and promotion included); anything else is discarded
  and the last accepted board is returned. Takes an optional
  ``on_event(kind, detail)`` callback: ``("move", san)`` on acceptance,
  ``("dropped", reason)`` on rejection, nothing for unchanged frames.
  **Not wired into `main`**: the live reader evaluates each frame purely
  from the image (per user requirement), surfacing low-confidence squares
  as "unknown" instead of filtering by move legality. The filter remains
  available (and tested) for stricter game tracking.

### Real I/O implementations

- `chesscheat/capture/screenshot.py` — fast capture; one reused module-level
  `mss()` instance (`_sct`). Do not recreate it per call.
- `chesscheat/gui/dialogs.py` — tkinter setup UI: White/Black buttons, a
  crosshair overlay to click the two corners, and a capture-confirmation
  dialog (`confirm_box`, image shown via a PPM-encoded `tk.PhotoImage` —
  `_image_to_ppm`, no Pillow). Every dialog is torn down via `_dismiss`
  (unmap + flush the event queue **before** destroy; the overlay also sleeps
  briefly for a repaint) so no dead window lingers on screen — beachballing,
  blocking the user's clicks, or polluting the first capture — while the
  program blocks on calibration or stdin. On macOS the overlay is a translucent **borderless window**
  (`overrideredirect` + screen-sized geometry), *not* Tk `-fullscreen`, which
  would move into its own black Space and hide the board; right-click cancels
  alongside Escape since borderless windows may not get key events. macOS
  also needs Screen Recording permission or captures show only the wallpaper
  (hinted in `main()`, the confirm dialog, and README troubleshooting).
  tkinter imported lazily.
- `chesscheat/providers/` — `GuiSetupProvider`, `PromptSetupProvider`,
  `FallbackSetupProvider` (GUI → prompt on error; a GUI *cancel* raises
  `SystemExit`, which propagates and quits), and `ScreenFrameSource`.

### Move assist (`chesscheat/assist/`)

Plays the engine's best move on the user's turn. `assist_move(board_map,
playing_white, box, engine, actuator)` (in `coordinator.py`) is pure
orchestration: `board.to_full_fen` → `engine.best_move(fen)` → (if a move)
`actuator.apply(uci, box, playing_white)`, returning the UCI played.
- `StockfishMoveEngine` — locates a binary (explicit path / `STOCKFISH_PATH` /
  `shutil.which("stockfish")`) at construction; `best_move` opens a UCI engine
  per call via **python-chess** (`chess.engine`, lazy), returns None for an
  invalid/finished position. The binary is normally supplied by
  `scripts/install_stockfish.py` (run from `setup.sh`), which picks the
  release asset for the host — `asset_candidates`/`select_asset` map
  system/machine to the right `.tar` (Apple Silicon M1–M4 → the single
  `macos-m1-apple-silicon` build) — downloads it from the official Stockfish
  GitHub releases, installs it as `venv/bin/stockfish` and clears the macOS
  quarantine flag. Stdlib-only; the selection logic is pure and tested in
  `test_install_stockfish.py` (no network).
- `PyAutoGuiActuator` — `move_pixels(uci, box, playing_white)` (pure: maps the
  from/to squares to screen-pixel centres via `board.parse_square`/`cell_of`)
  then `pyautogui` (lazy) moveTo → mouseDown → moveTo(duration) → mouseUp.
  Promotion suffix ignored (site prompt not handled).
- `KeyTrigger(key="a")` — a global `pynput` (lazy) keyboard listener in a
  thread; a matching press sets a `threading.Event` that `poll` edge-consumes.
  On macOS a global listener needs **Input Monitoring** permission; without it
  the native event-tap creation aborts the whole process with a *trace trap*
  that Python can't catch. `has_input_monitoring()` preflights via
  `Quartz.CGPreflightListenEventAccess` (True off-macOS / when the API is
  absent) and `start` raises `PermissionError` rather than creating the tap
  unpermitted.
- `main` builds the assist via `_build_assist`, which honours a
  `CHESSCHEAT_NO_ASSIST` opt-out, probes for Stockfish + `pyautogui` +
  `pynput` (on any `ImportError`/`FileNotFoundError` prints why and returns a
  no-op trigger), and gates on `trigger.permission_ok()` so a missing macOS
  permission disables the assist with a message up front instead of crashing.
  `run` additionally wraps `trigger.start()` so any start failure disables the
  assist rather than taking down the reader. `on_trigger` calls `assist_move`
  and logs `("assist", …)` events; engine exceptions are caught so the loop
  survives.

### Mocks (`chesscheat/mocks/`) — dependency-free, test the whole pipeline

`MockSetupProvider`, `MockFrameSource` (scripted frames), `render_mock_image`
(board map → synthetic grayscale image with a distinct per-piece pattern, plus
a square-colour tint that matching ignores), `MockImageBackend` (same
normalised-correlation logic as the real backend, in pure Python), and the
assist mocks: `MockMoveEngine` (canned move, records FENs), `MockMoveActuator`
(records `(uci, box, playing_white)`), `MockMoveTrigger` (`fire()` queues an
activation `poll` consumes).

### App loop (`chesscheat/app.py`)

`run(setup, make_frame_source, recognizer, *, on_board, on_frame,
before_calibrate, ...)` is the heart, wired only to interfaces: get side →
loop { get box → grab a preview frame → `confirm_box` } until confirmed →
build a fresh frame source (so scripted mock sources restart; the preview
grab never consumes the calibration frame) → calibrate from first frame →
for each subsequent frame, surface it raw via `on_frame` then report the
reading via `on_board`.
`run` reads each frame *before* `on_frame` so a preview can annotate the
frame with its own scored reading. It also accepts an optional `trigger`
(`MoveTrigger`, started before the loop / stopped in `finally`) polled once
per frame; on activation it calls `on_trigger(board_map, playing_white, box)`
with the latest reading — this is the move-assist entry point. `main` injects the real implementations
(recognizer with `match_threshold=SSIM_THRESHOLD`, no legal-move filter) and
wires the terminal UI (`_console_ui` returns `(on_board, on_frame,
on_event)` sharing one display: board + FEN, a timestamped recent-activity
log — position changes, unknown-square notices, and assist actions — and a
capture-rate line refreshed every frame) plus a `LivePreview` window
(`gui/live_preview.py`)
showing each raw capture with the fps in its title and **every square
annotated** from `recognizer.last_scored`: pieces outlined with a name chip
("knight" etc., white/black chip per side), empty squares chip-labelled by
their square colour ("white"/"black"), sub-threshold squares marked
"unknown (score)". The pure `annotations()` spec builder and the Tk `draw`
helper live in `gui/overlays.py` (shared with the confirmation dialog, which
overlays the expected starting layout so a misaligned selection is obvious);
the preview self-disables on any Tk failure rather than break the loop.
`board.piece_name` maps a piece letter to its name. Pressing `ASSIST_KEY`
(`"a"`) fires `on_trigger` → `assist_move`, playing the engine's best move.
`tests/test_recognition.py` injects mocks to verify positions evolving over
time are recognised exactly.

### Tests (`tests/`)

- `test_board.py` — pure logic.
- `test_recognition.py` — the real `TemplateBoardRecognizer` over synthetic
  images via `MockImageBackend`, driven through `run`. Both run with no
  third-party deps installed.
- `test_real_images.py` — the real `NumpyImageBackend` over real board images
  for several piece sets (`fixtures/boards/<set>/`: Wikipedia + alpha PNGs from
  chessboard.js, and lichess's merida rasterised from SVG; each on its own
  colour theme), composed by `fixtures/generate_boards.py` for the opening
  1.e4 c5 2.Nf3. Needs numpy + Pillow (`requirements-dev.txt`);
  `skipUnless`-guarded so it skips when those are absent.
- `test_general_boards.py` — the generality guarantee: an arbitrary colour
  theme with non-chess-looking pieces, through positions where kings/queens
  cross onto the opposite-coloured square (the synthesis path). Renders boards
  with numpy directly; `skipUnless(numpy)`-guarded.
- `test_legal_move_filter.py` — `LegalMoveFilter` through the mock pipeline:
  legal openings, castling (both sides), en passant, promotion and
  underpromotion accepted; simulated artifacts (cursor over a square, piece
  vanishing mid-drag, highlight misreads, impossible extra pieces, multi-square
  corruption) rejected while the state stays intact and later legal moves still
  land. `skipUnless(chess)`-guarded.
- `test_filter_real_images.py` — the same filter over the real fixture images:
  paints cursor crosses and 50 % highlight tints directly onto the PNGs and
  checks corrupted frames are dropped and genuine moves accepted, for all
  three piece sets. `skipUnless(numpy + Pillow + chess)`-guarded.
- `test_setup_confirmation.py` — the capture-confirmation step: rejection
  loops back to reselection, the preview never consumes the calibration
  frame, prompt y/n and fallback forwarding, and `_image_to_ppm` encoding
  (grayscale lists dep-free; BGRA/RGB/gray arrays `skipUnless(numpy)`).
- `test_install_stockfish.py` — the Stockfish installer's pure
  platform/asset selection (`asset_candidates`/`select_asset`): M1–M4 Mac →
  `macos-m1-apple-silicon.tar`, Intel-Mac/Linux ordering and fallbacks,
  `.tar`-only, unsupported platforms → None. Loads `scripts/install_stockfish.py`
  by path; dep-free, no network.
- `test_assist.py` — the move assist, dep-free via mocks: `cell_of`/
  `parse_square`/`castling_field`/`to_full_fen` helpers, `move_pixels`
  geometry (white/black orientation, promotion suffix ignored), `assist_move`
  (builds a side-to-move FEN, plays the move, skips the actuator on None),
  and `run`'s trigger loop (start/stop, fired vs unfired, end-to-end through
  engine+actuator). A `skipUnless(shutil.which("stockfish"))` case runs the
  real `StockfishMoveEngine` (legal opening move; None at game over).

Note `NumpyImageBackend`'s SSIM feature is `(canonical, mean, variance)` over
the background-canonicalised colour patch: SSIM (per RGB channel, averaged)
makes both piece shape and piece colour part of the score, and two empty
squares canonicalise to identical flat grey (score 1.0). The mock backend
keeps its plain full-patch correlation (features are opaque to the
recognizer), so SSIM/background canonicalisation is exercised by the
real-image tests, including the highlighted-squares cases in
`test_filter_real_images`.

### Import boundary (important)

Keep heavy/IO deps (`numpy`, `mss`, `chess`/`chess.engine`, `pyautogui`,
`pynput`, tkinter, `chesscheat.capture`) imported **lazily** inside the
methods/functions that use them (see `recognition/numpy_image_backend.py`,
`recognition/legal_move_filter.py`, `assist/` (engine/actuator/trigger),
`providers/`, `gui/dialogs.py`). The `board`, `interfaces`, `mocks` and
`assist` packages and the `run` loop must stay importable dependency-free so
the suite runs anywhere (the `assist/__init__` re-exports only lazily-importing
classes). Subpackage `__init__.py` files must likewise avoid eager heavy
imports (e.g. `capture/__init__.py` pulls in numpy, so depend on it only
behind a lazy import).
