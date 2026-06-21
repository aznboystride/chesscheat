# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A small Python toolkit that reads a chessboard off the screen. It captures a
screen region, splits it into an 8x8 grid, identifies each square by template
matching, and prints the live board state as text (with a canonical FEN).

## Commands

```bash
# Run the live reader (needs a real display + the deps below)
python3 chessboard_state.py

# Run the unit tests
python3 -m unittest test_chessboard_state -v

# Run a single test case / method
python3 -m unittest test_chessboard_state.FenTests
python3 -m unittest test_chessboard_state.FenTests.test_after_e4
```

There is no build step, linter config, or requirements file. Runtime
dependencies (`opencv-python`, `mss`, `numpy`) must be installed manually:
`pip install opencv-python mss numpy`.

## Architecture

Three modules, layered capture → recognition → presentation:

- `screenshot.py` — fast screen capture. Holds a single module-level
  `mss()` instance (`_sct`) reused across calls; `screenshot(x1,y1,x2,y2)`
  returns a BGRA numpy array. Reusing the one `mss` instance is the main
  speed lever — do not recreate it per call.

- `chessboard_state.py` — the application. Prompts for the board's bounding
  box and which side the user plays, then loops: screenshot → classify 64
  squares → render. Key design points:
  - **Calibration from the starting position.** There are no bundled piece
    images. On startup the board must be in the standard starting position;
    `build_templates` captures one template per square and labels it using
    `start_label`, so every piece type (and empty light/dark squares) gets a
    reference. `classify` then matches later frames against these templates
    with `cv2.matchTemplate` (`TM_CCOEFF_NORMED`). Consequence: templates are
    tied to the current board theme/size/position — recalibrate if any change.
  - **Two coordinate spaces.** Screen grid cells are `(row, col)` with
    `row 0` at the top; chess coordinates are `(file_idx 0=a, rank 1..8)`.
    `square_coord` converts between them and is the single place board
    orientation (white vs black perspective) is handled. `to_fen` always
    emits the canonical white-view FEN regardless of perspective, so it is
    the orientation-independent source of truth.

- `test_chessboard_state.py` — unit tests for the pure logic only
  (`square_coord`, `start_label`, `render`, `to_fen`). The capture/vision
  functions (`prep`, `classify`, `read_board`) are not unit-tested.

### Import boundary (important)

`chessboard_state.py` deliberately imports `cv2` (inside `prep`/`classify`)
and `screenshot` (inside `main`) **lazily**, so the pure board logic imports
and tests cleanly without the vision/capture stack installed. Keep new
heavy/IO dependencies behind the same lazy boundary; only the
coordinate/label/render/FEN code should be importable dependency-free.
