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
python3 chessboard_state.py
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

The whole suite runs with **no** third-party dependencies installed: the board
logic is pure, and recognition is tested end-to-end through mock
implementations of the interfaces (synthetic board images fed through the real
matching algorithm), so no GUI, screen, or numpy is required.

```bash
# Run the full suite
python3 -m unittest discover -p 'test_*.py' -v

# Run a single module / case / method
python3 -m unittest test_recognition
python3 -m unittest test_board.FenTests
python3 -m unittest test_board.FenTests.test_after_e4
```

## Design

The code is programmed to interfaces (`interfaces.py`) so implementations are
swappable: how setup is obtained (`GuiSetupProvider`, `PromptSetupProvider`,
`MockSetupProvider`), how frames are supplied (`ScreenFrameSource`,
`MockFrameSource`), and how images are matched (`NumpyImageBackend`,
`MockImageBackend`). This is what lets the program be verified against
generated positions evolving over time without any GUI or screenshotting.
