# chesscheat

A small Python toolkit that reads a chessboard off your screen. It captures a
screen region, splits it into an 8x8 grid, identifies each square by template
matching, and prints the live board state as text along with a canonical FEN.

## How it works

There are no bundled piece images. On startup the board must be in the
standard starting position — from that single image the program learns how
each piece and each empty square looks, then extrapolates to any later
configuration. Because the templates are tied to the current board theme, size,
and position, you should recalibrate (restart) if any of those change.

It works on **any** board, not just a particular site or piece set, as long as:

- the squares are evenly spaced;
- each colour's squares look identical everywhere on the board;
- each piece looks identical on every square it occupies.

The pieces need not look like traditional chess pieces — only be consistent.
Matching considers **only the shape and colour of the pieces, never the
square colour**: every square is first canonicalised against its own
background (estimated from the square's border), so the tints chess UIs
paint on squares — a selection highlight, the persistent last-move
highlight — do not throw off tracking. Moves onto highlighted squares are
recognised just like moves onto clean ones.

### Evaluation and confidence

Every screenshot is evaluated **purely from the image**: each of the 64
squares is compared against the templates learned from the starting
position using **SSIM** (structural similarity), computed per colour channel
over the background-canonicalised square — so both the shape and the colour
of a piece must match. No chess-rules filtering is applied; what you see is
what the image says.

Each square's best match carries its SSIM score. If the best score falls
below the confidence threshold, the square is shown as **unknown** with the
score, rather than silently guessing — a mouse cursor or a piece mid-drag
shows up as an unknown square for a frame instead of corrupting the reading.

(A `LegalMoveFilter` decorator that additionally validates readings against
legal chess moves is available in `chesscheat.recognition` for stricter
game tracking, but the live reader does not use it.)

## Requirements

- Python 3.8+
- A real display (the tool captures the screen and cannot run headless)
- Python modules: `mss`, `numpy`, `chess` (see `requirements.txt`)

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
   `Escape` at any time to cancel. The overlay disappears completely once the
   corners are chosen — it never blocks the board while the reader runs, so
   you can click and move pieces normally.
3. **Confirm the capture** — a window shows exactly what was captured from
   the selected region, which must be the board **in the starting position**.
   The capture is annotated with the expected starting layout: every piece
   outlined and named, every empty square labelled with its colour — if the
   labels don't sit on the pieces, the selection is misaligned. Click
   **Looks good** to proceed, or **Reselect** to pick the corners again.

(If no display or Tk is available, it falls back to text prompts for the side,
the corner coordinates, and a y/n capture confirmation.)

Confirming closes the window and calibration starts immediately — a progress
bar in the terminal tracks the 64 squares being learned:

```
Capture confirmed -- calibrating from the starting position...
  Calibrating [########################........] 48/64 squares
```

Then it loops: screenshotting the board, classifying all 64 squares, and
reprinting the position whenever it changes. While it runs:

- a small always-on-top **live capture window** shows exactly what is being
  screenshotted in real time, with the measured frame rate in its title bar
  (close the window to dismiss it — the reader keeps going). Every square is
  annotated with that frame's evaluation: **detected pieces** are outlined
  with a chip naming the piece (white chips for white pieces, black chips
  for black), **empty squares** carry a chip naming the square's colour
  ("white"/"black"), and squares whose best match scored below the SSIM
  threshold are marked **unknown** with the score, e.g. `unknown (0.42)`;
- the terminal shows a timestamped **recent activity** log — each position
  change (as a FEN) and each frame with unknown squares;
- the last terminal line shows the live **capture rate**, updated on every
  frame, so a stall is immediately visible.

For example:

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

Recent activity:
  [21:03:12] position: rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR
  [21:03:19] unknown: 1 square(s) below SSIM 0.6

capturing at 3.3 fps
```

Press `Ctrl+C` to stop.

## Troubleshooting

**The capture shows only my desktop wallpaper (macOS).** macOS hides all
window content from screen capture until the capturing app has **Screen
Recording** permission. Grant it to whatever runs the program (Terminal,
iTerm2, your IDE) under *System Settings → Privacy & Security → Screen
Recording*, then **fully quit and reopen** that app — the permission only
takes effect on restart. The confirmation dialog will show the real board
once it's granted; until then, click **Reselect** after fixing it.

**The selection overlay hides the window with the board (macOS).** Fixed by
using a translucent borderless window instead of Tk fullscreen (which moves
into its own black Space). If the overlay ever misbehaves, press `Escape` or
right-click to cancel it, and the text-prompt fallback can be used by
entering the corner coordinates by hand.

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

The legal-move filter has its own suites (both skipped automatically when
their deps are absent): `tests/test_legal_move_filter.py` (needs
python-chess) covers legal openings, castling, en passant, promotion, and a
battery of simulated artifacts — cursor over a square, pieces vanishing
mid-drag, highlight misreads — through the mock pipeline;
`tests/test_filter_real_images.py` (needs numpy, Pillow, and python-chess)
paints cursor crosses and highlight tints directly onto the real fixture
images and verifies corrupted frames are rejected while genuine moves still
land.

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
