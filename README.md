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
- Python modules: `mss`, `numpy`, `opencv-python` (see `requirements.txt`)

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

The program will prompt you for:

1. **The bounding box of the board** — the top-left and bottom-right screen
   coordinates (`x y`) of the board area. Tip: hover your mouse over a corner
   and note its pixel coordinates.
2. **Which side you are playing** — `w` (white) or `b` (black). This sets the
   board orientation.

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

The pure board logic (coordinate mapping, labels, rendering, FEN) is unit
tested and does not require the vision dependencies:

```bash
# Run the full suite
python3 -m unittest test_chessboard_state -v

# Run a single test case or method
python3 -m unittest test_chessboard_state.FenTests
python3 -m unittest test_chessboard_state.FenTests.test_after_e4
```
