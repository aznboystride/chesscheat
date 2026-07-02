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
`numpy`, `chess`) live in `requirements.txt`; `setup.sh` builds a `venv/` and
installs them (honors a `PYTHON` env var override). Installing manually works
too: `pip install -r requirements.txt`. The entire test suite still *runs*
with **no** third-party deps installed: the dep-free tests exercise the mock
implementations, and the dep-requiring tests are `skipUnless`-guarded. Wrapper
scripts: `./run.sh` (live reader), `./test.sh` (`--fast` dep-free only,
`--real` dep-requiring only, or a dotted test path), `./generate-fixtures.sh`.
See `README.md` for end-user install/run instructions.

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
  interfaces/       SetupProvider, FrameSource, ImageBackend, BoardRecognizer
  recognition/      TemplateBoardRecognizer, NumpyImageBackend, LegalMoveFilter
  providers/        Gui/Prompt/Fallback SetupProvider, ScreenFrameSource
  mocks/            Mock{SetupProvider,FrameSource,ImageBackend}, synthetic_image
  capture/          screenshot
  gui/              dialogs (select_side, select_box)
tests/              test_board, test_recognition, test_legal_move_filter, ...
```

### Interfaces (`chesscheat/interfaces/`)

- `SetupProvider` — `select_side()`, `select_box()` (the user's config).
- `FrameSource` — `grab()` returns the next board image; may raise
  `StopIteration` when a finite source is exhausted.
- `ImageBackend` — `get_square` / `feature` / `similarity` / `recolor`.
  Abstracts the image representation so the recognition *algorithm* is shared
  by a real numpy backend and a pure-Python mock backend. `recolor` repaints a
  square's empty background from one colour to another (for template synthesis).
- `BoardRecognizer` — `calibrate(image, playing_white)`, `read(image)`.

### Core logic (`chesscheat/board.py`) — dependency-free, the source of truth

`square_coord`, `start_label`, `is_light`, `starting_board`, `render`,
`to_fen`. **Two coordinate spaces**: screen cells are `(row, col)` with row 0
at the top; chess coords are `(file_idx 0=a, rank 1..8)`. `square_coord` is the
single place orientation (white vs black) is handled. `to_fen` always emits the
canonical white-view FEN regardless of perspective.

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
  colour. The same algorithm runs with the real and the mock backend.
- `NumpyImageBackend` — real backend. `feature` is a `(shape, mean)` pair:
  `shape` is a mean-subtracted, unit-normalised grayscale vector (so its dot
  product is the normalised cross-correlation coefficient, OpenCV's
  `TM_CCOEFF_NORMED`, but numpy-only — **no `cv2`**), and `mean` is brightness,
  which keeps *flat* (empty) squares distinguishable (mean-subtraction alone
  zeroes them). `recolor` swaps a piece's background colour using the average
  empty colours. Templates are tied to the current board theme/size/position;
  recalibrate if any change.
- `LegalMoveFilter(inner)` — a `BoardRecognizer` decorator that makes the
  reader robust to transient visual noise (mouse cursor, move highlights,
  drag animations). It tracks the game with **python-chess** (`chess`,
  imported lazily inside `calibrate`) and accepts an inner reading only when
  it equals the current state or matches the result of exactly one legal move
  (castling, en passant and promotion included); anything else is discarded
  and the last accepted board is returned. `main` wraps the real recognizer
  in this filter.

### Real I/O implementations

- `chesscheat/capture/screenshot.py` — fast capture; one reused module-level
  `mss()` instance (`_sct`). Do not recreate it per call.
- `chesscheat/gui/dialogs.py` — tkinter setup UI: White/Black buttons and a
  crosshair overlay to click the two corners. tkinter imported lazily.
- `chesscheat/providers/` — `GuiSetupProvider`, `PromptSetupProvider`,
  `FallbackSetupProvider` (GUI → prompt on error; a GUI *cancel* raises
  `SystemExit`, which propagates and quits), and `ScreenFrameSource`.

### Mocks (`chesscheat/mocks/`) — dependency-free, test the whole pipeline

`MockSetupProvider`, `MockFrameSource` (scripted frames), `render_mock_image`
(board map → synthetic grayscale image with a distinct per-piece pattern, plus
a square-colour tint that matching ignores), and `MockImageBackend` (same
normalised-correlation logic as the real backend, in pure Python).

### App loop (`chesscheat/app.py`)

`run(setup, make_frame_source, recognizer, *, on_board, before_calibrate, ...)`
is the heart, wired only to interfaces: get side+box → build frame source →
calibrate from first frame → report each subsequent frame via `on_board`.
`main` injects the real implementations; `tests/test_recognition.py` injects
mocks to verify positions evolving over time are recognised exactly.

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

Note `NumpyImageBackend`'s feature is a `(shape, mean)` pair: mean-subtracted
correlation discriminates pieces across square colours, while the brightness
`mean` keeps *flat* (empty) squares distinguishable — without it, empty squares
correlate with nothing and get misread. The synthetic mock images never exposed
this because their empty squares carry a pattern; the real-image test does.

### Import boundary (important)

Keep heavy/IO deps (`numpy`, `mss`, `chess`, tkinter, `chesscheat.capture`)
imported **lazily** inside the methods/functions that use them (see
`recognition/numpy_image_backend.py`, `recognition/legal_move_filter.py`,
`providers/`, `gui/dialogs.py`). The
`board`, `interfaces`, `mocks` packages and the `run` loop must stay importable
dependency-free so the suite runs anywhere. Subpackage `__init__.py` files must
likewise avoid eager heavy imports (e.g. `capture/__init__.py` pulls in numpy,
so depend on it only behind a lazy import).
