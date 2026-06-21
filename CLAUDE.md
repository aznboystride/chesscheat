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
python3 chessboard_state.py

# Run the whole test suite (pure logic + mock pipeline; needs no deps)
python3 -m unittest discover -p 'test_*.py' -v

# Run a single test module / case / method
python3 -m unittest test_recognition
python3 -m unittest test_board.FenTests
python3 -m unittest test_board.FenTests.test_after_e4
```

There is no build step or linter config. Runtime dependencies (`mss`,
`numpy`) live in `requirements.txt`; `setup.sh` builds a `venv/` and installs
them (honors a `PYTHON` env var override). Installing manually works too:
`pip install -r requirements.txt`. The entire test suite runs with **no**
third-party deps installed, because it exercises the mock implementations.
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

The code is **programmed to interfaces** (`interfaces.py`, ABCs) so real and
mock parts are interchangeable. The app loop depends only on the abstractions;
concrete implementations are injected.

### Interfaces (`interfaces.py`)

- `SetupProvider` — `select_side()`, `select_box()` (the user's config).
- `FrameSource` — `grab()` returns the next board image; may raise
  `StopIteration` when a finite source is exhausted.
- `ImageBackend` — `get_square` / `feature` / `similarity`. Abstracts the image
  representation so the recognition *algorithm* is shared by a real numpy
  backend and a pure-Python mock backend.
- `BoardRecognizer` — `calibrate(image, playing_white)`, `read(image)`.

### Core logic (`board.py`) — dependency-free, the source of truth

`square_coord`, `start_label`, `is_light`, `starting_board`, `render`,
`to_fen`. **Two coordinate spaces**: screen cells are `(row, col)` with row 0
at the top; chess coords are `(file_idx 0=a, rank 1..8)`. `square_coord` is the
single place orientation (white vs black) is handled. `to_fen` always emits the
canonical white-view FEN regardless of perspective.

### Recognition (`recognition.py`)

- `TemplateBoardRecognizer(backend)` — the algorithm: **calibrate from the
  starting position.** There are no bundled piece images; the first frame must
  be the standard start position, from which one template per square is
  captured (so every piece type and empty square gets a reference). `read`
  classifies each later square by nearest template. The same algorithm runs
  with the real and the mock backend.
- `NumpyImageBackend` — real backend. `feature` is a mean-subtracted,
  unit-normalised grayscale vector, so `similarity` (a dot product) equals the
  normalised cross-correlation coefficient (OpenCV's `TM_CCOEFF_NORMED`, but
  numpy-only — there is **no `cv2` dependency**). Templates are tied to the
  current board theme/size/position; recalibrate if any change.

### Real I/O implementations

- `screenshot.py` — fast capture; one reused module-level `mss()` instance
  (`_sct`). Do not recreate it per call.
- `gui.py` — tkinter setup UI: White/Black buttons and a crosshair overlay to
  click the two corners. tkinter imported lazily.
- `providers.py` — `GuiSetupProvider`, `PromptSetupProvider`,
  `FallbackSetupProvider` (GUI → prompt on error; a GUI *cancel* raises
  `SystemExit`, which propagates and quits), and `ScreenFrameSource`.

### Mocks (`mocks.py`) — dependency-free, enable testing the whole pipeline

`MockSetupProvider`, `MockFrameSource` (scripted frames), `render_mock_image`
(board map → synthetic grayscale image with a distinct per-piece pattern, plus
a square-colour tint that matching ignores), and `MockImageBackend` (same
normalised-correlation logic as the real backend, in pure Python).

### App loop (`chessboard_state.py`)

`run(setup, make_frame_source, recognizer, *, on_board, before_calibrate, ...)`
is the entry point's heart, wired only to interfaces: get side+box → build
frame source → calibrate from first frame → report each subsequent frame via
`on_board`. `main` injects the real implementations; `test_recognition.py`
injects mocks to verify positions evolving over time are recognised exactly.

### Tests

- `test_board.py` — pure logic.
- `test_recognition.py` — the real `TemplateBoardRecognizer` over synthetic
  images via `MockImageBackend`, driven through `run`. Both run with no
  third-party deps installed.

### Import boundary (important)

Keep heavy/IO deps (`numpy`, `mss`, tkinter, `screenshot`) imported **lazily**
inside the methods/functions that use them (see `recognition.NumpyImageBackend`,
`providers`, `gui`). `board.py`, `interfaces.py`, `mocks.py` and the `run` loop
must stay importable dependency-free so the suite runs anywhere.
