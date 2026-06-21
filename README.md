# chesscheat

A small Python toolkit that reads a chessboard off your screen. It captures a
screen region, splits it into an 8x8 grid, identifies each square by template
matching, and prints the live board state as text along with a canonical FEN.

## How it works

There are no bundled piece images. On startup the board must be in the
standard starting position — the program captures one reference template per
square (so every piece type and empty square gets a reference), then matches
later frames against those templates. Because the templates are tied to the
current board theme, size, and position, you should recalibrate (restart) if
any of those change.

## Requirements

- Python 3.8+
- A real display (the tool captures the screen and cannot run headless)
- Python modules: `mss`, `numpy` (see `requirements.txt`)

## Installation

Use the setup script to create a virtual environment and install everything:

```bash
./setup.sh
source venv/bin/activate
```

Or do it manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

With the virtual environment activated and a chessboard visible on screen in
the **starting position**:

```bash
python3 -m chesscheat
```

The program opens a small GUI to configure itself:

1. **Pick your side** — a window with **White** / **Black** buttons sets the
   board orientation.
2. **Select the board area** — the screen dims into a fullscreen overlay with
   a crosshair that tracks your cursor and shows live coordinates. Click the
   board's **top-left** corner, then its **bottom-right** corner. Press
   `Escape` at any time to cancel.

(If no display or Tk is available, it falls back to text prompts for the side
and the corner coordinates.)

After you confirm calibration, it loops: screenshotting the board, classifying
all 64 squares, and reprinting the position whenever it changes, for example:

```
   a  b  c  d  e  f  g  h
8  r  n  b  q  k  b  n  r  8
7  p  p  p  p  p  p  p  p  7
6  .  .  .  .  .  .  .  .  6
5  .  .  .  .  .  .  .  .  5
4  .  .  .  .  P  .  .  .  4
3  .  .  .  .  .  .  .  .  3
2  P  P  P  P  .  P  P  P  2
1  R  N  B  Q  K  B  N  R  1
   a  b  c  d  e  f  g  h

FEN: rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR
```

Press `Ctrl+C` to stop.

## Tests

Most of the suite runs with **no** third-party dependencies installed: the
board logic is pure, and recognition is tested end-to-end through mock
implementations of the interfaces (synthetic board images fed through the real
matching algorithm), so no GUI, screen, or numpy is required.

```bash
# Run the full suite (from the repo root)
python3 -m unittest discover -s tests -t . -v

# Run a single module / case / method
python3 -m unittest tests.test_recognition
python3 -m unittest tests.test_board.FenTests
python3 -m unittest tests.test_board.FenTests.test_after_e4
```

In addition, `tests/test_real_images.py` runs the **real** `NumpyImageBackend`
over real board images (the committed `tests/fixtures/boards/` PNGs, built from
the Wikipedia piece set) for the opening 1.e4 c5 2.Nf3, verifying each evolving
position is recovered. It needs numpy and Pillow and is skipped automatically
when they are absent:

```bash
pip install -r requirements-dev.txt
python3 -m unittest tests.test_real_images
```

## Layout

Source lives in the `chesscheat/` package and tests in `tests/`. The code is
programmed to the interfaces in `chesscheat/interfaces/` so implementations are
swappable: how setup is obtained (`GuiSetupProvider`, `PromptSetupProvider`,
`MockSetupProvider`), how frames are supplied (`ScreenFrameSource`,
`MockFrameSource`), and how images are matched (`NumpyImageBackend`,
`MockImageBackend`). This is what lets the program be verified against
generated positions evolving over time without any GUI or screenshotting.

```
chesscheat/
  app.py            board.py        __main__.py
  interfaces/   recognition/   providers/   mocks/   capture/   gui/
tests/
```
