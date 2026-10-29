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

### Move assist (optional)

When it's your turn, press the assist key (**`A`** by default) and the program
computes the best move with a chess engine and plays it for you by dragging
the mouse on the board:

1. the detected position is turned into a FEN (your side to move);
2. a `MoveEngine` returns the best move — the bundled `StockfishMoveEngine`
   drives a [Stockfish](https://stockfishchess.org/) binary via
   [python-chess](https://pypi.org/project/chess/);
3. a `MoveActuator` plays it — `PyAutoGuiActuator` moves the mouse to the
   origin square, **clicks the piece once to bring the chess app's window to
   the front** (on macOS the first click on an inactive window only
   activates it), pauses briefly, then presses on the same piece, drags to
   the destination and releases.

The engine is behind the `MoveEngine` interface (`best_move(fen) -> uci`), so
any engine can be dropped in. The assist is optional: if Stockfish, `pyautogui`
or `pynput` aren't available the reader prints why and runs without it. Set
`CHESSCHEAT_NO_ASSIST=1` to turn it off entirely.

> **macOS:** the global keybind needs **Input Monitoring** permission (and
> **Accessibility** to move the mouse). Grant them to your terminal under
> *System Settings → Privacy & Security*, then restart it. Without Input
> Monitoring, macOS would kill the process with a "trace trap" when the
> listener starts — the program now detects this up front and simply disables
> the assist with a message instead of crashing.

> **Heads up.** This automates mouse input to play moves on your behalf. Using
> engine assistance in online games violates the rules of every major chess
> site and will get accounts banned. Use it for analysis, bots, and local
> experimentation.

### Mirror mode (no piece recognition)

`python3 -m chesscheat --mode mirror` skips piece recognition entirely. You
pick your side and click the real board's corners, and a **mirror board**
opens next to it, oriented exactly like the real app (your side at the
bottom) so the two boards read identically. The opponent's moves reach the
mirror board in either of two ways — read off the real app automatically
(**Watch app**, below), or copied by you: click the origin square, then the
destination. Either way the program answers immediately in two places: on
the mirror board, and in the real chess app, by dragging the piece over the
region you selected. Illegal entries are refused with a message; a pawn
pushed to the last rank promotes to a queen. If you play white the program
opens with white's first move; if you play black it waits for white's move.

The mirror window is placed off the real board (right, left, below or above
it, whichever fits) so it never sits under the mouse drags.

A control bar under the board adjusts the behaviour at any time, mid-game:

- **Auto-play** (toggle) — on: the engine chooses and plays your side's moves.
  Off: auto-play pauses and *you* play your side on the mirror board by hand
  (click origin, click destination); those moves are still played in the
  real app for you. Switching it back on while it's your side's turn makes
  the program reply immediately.
- **Watch app** (toggle, on by default) — infers the opponent's moves from
  the real app so you don't have to enter them. While it is the opponent's
  turn the selected region is captured a few times a second and scanned for
  the app's **last-move highlight**: the two tinted squares. The move is
  accepted as soon as one tinted square is empty, the other holds a piece of
  the opponent's colour, and that move is legal — then it is entered for you
  and answered as usual. Your own moves are highlighted by the app too; they
  are never mistaken for the opponent's (no legal opponent move starts from
  your piece), nor is a highlight left over from a move already entered, a
  capture whose piece is still sliding, or a red "check" tint on your king.
  No piece images are needed: the two square colours and the piece
  brightness are learned from each frame itself, so any theme works. A
  promotion is read as a queen. Turn it off to enter moves by hand (you can
  still do that while it is on); if a mis-read move got in, Undo it and
  switch Watch app off before re-entering, or the same highlight is read
  again. On macOS the capture needs Screen Recording permission (see
  Troubleshooting).
- **Reply delay (s) min / max** — the minimum time between the opponent's
  move and the program's reply. Set both ends equal for a fixed delay, or
  apart to add **random jitter**: every reply draws its own delay uniformly
  from the range, so the timing doesn't look mechanical. The engine thinks
  straight away but the move is held back until the delay has elapsed (the
  window stays responsive, so you can pause during the wait). Changing the
  range while a reply is waiting redraws its delay from the new range.
- **Strength** — full strength or a target Elo (2800 down to 1400). With the
  local engine this sets Stockfish's `UCI_LimitStrength`/`UCI_Elo` (clamped
  to the engine's supported range); the remote engine receives it as `elo`
  in each request. Takes effect from the next reply.
- **Think (s)** — how long the engine searches per reply (default 0.3 s;
  `--think-seconds` sets the starting value). Stockfish at a tenth of a
  second is already far beyond human strength, so lower it freely for
  snappier replies. The remote engine receives it as `think` in each
  request.
- **Think in delay** (toggle, on by default) — when a reply is going to
  wait for the delay anyway, let the engine use the wait: it searches for
  whatever is left of the delay (less a small margin, at most 10 s) instead
  of the fixed think time, so the wait buys a stronger move and the reply
  is still ready on time. With it off, the engine always searches for the
  fixed think time and idles for the rest.

The engine searches on a background thread, so the window stays live
while it thinks: you can still pause auto-play, undo or start a new game
mid-search, and a result for a position that has since changed is thrown
away.
- **Undo** — takes back the last opponent move *and* whatever followed it
  (the engine's reply, or your own manual move), putting the board back on
  the opponent's turn so you can enter the correct move. A reply still
  waiting out the delay is cancelled. Only the mirror board is reverted:
  anything already dragged in the real app stays, so take it back there
  yourself if the app allows.
- **New game** — starts over on the same real board: you are asked only
  which colour you play now (Yes = white, No = black, Cancel keeps the
  current game); the board region you clicked out at the start is reused.
  The mirror board flips to put your new side at the bottom, any reply
  still waiting is cancelled, and if you are white the program opens at
  once.

An **evaluation bar** runs down the left of the mirror board and updates
after every move (yours, the opponent's, undos and new games): white's share
grows from white's side, and the score is printed on it — `+0.35` in pawns
from white's point of view, `M3` / `-M2` for a forced mate, the result
(`1-0`, `0-1`, `1/2-1/2`) once the game is over. With the local engine this
is a short Stockfish analysis at full strength regardless of the strength
setting; a remote engine can supply it too (below), and one that doesn't
leaves the bar level and blank.

After the program has dragged its move in the real app, the mouse pointer is
moved back onto the mirror board, to the square the opponent's last move
ended on (where you last clicked), so your hand is where the next entry
starts. The drag itself is quick: about 0.15 s of travel (just enough for
the app to see a drag rather than a jump), a few hundredths to let the
window take focus, and none of `pyautogui`'s default pauses between calls.

### Choosing the decision maker

The move chooser is the `MoveEngine` interface — `best_move(fen) -> uci`,
plus an optional `evaluate(fen)` for the evaluation bar — and both modes
take any implementation:

| Implementation | Where the engine runs | Select it with |
|---|---|---|
| `StockfishMoveEngine` (default) | locally, the binary `setup.sh` installed | nothing to do |
| `RemoteMoveEngine` | on another machine, behind an HTTP endpoint | `--engine-url URL` or `CHESSCHEAT_ENGINE_URL` |

The remote protocol is minimal JSON: `POST` `{"fen": "<full FEN>", "elo": N,
"think": S}` (`elo` is the requested strength, `null` for full; `think` the
requested search time in seconds, `null` for the service's default; a service
may ignore both) and reply `{"move": "e2e4"}` (or `{"move": null}` for no
move). For the
evaluation bar the client also `POST`s `{"fen": "<full FEN>", "evaluate":
true}` after every move and reads an optional `"score"` from the reply —
`{"cp": 35}` (centipawns) or `{"mate": 3}` (moves to mate, negative when
black mates), both from white's point of view; a service that doesn't
evaluate can answer such requests with `{"move": null}` straight away and
the bar stays blank. Any service that speaks this works — a Stockfish on a
beefier box, a cloud function, a different engine entirely. Implement
`MoveEngine` yourself for anything else; override its optional
`set_strength(elo)` if your engine can vary strength, `set_think_time(s)`
if it can vary its search time, and `evaluate(fen)` if it can score a
position.

## Requirements

- Python 3.8+
- A real display (the tool captures the screen and cannot run headless)
- Python modules: `mss`, `numpy`, `chess`, `pyautogui`, `pynput` (see
  `requirements.txt`)
- For the move assist: a **Stockfish** binary. `./setup.sh` downloads one
  matching your machine automatically (see below), so you normally don't need
  to install it yourself. To supply your own, put a `stockfish` binary on
  `PATH` or point `STOCKFISH_PATH` at it.

## Installation

Use the setup script to create a virtual environment, install the Python
dependencies, and download a Stockfish engine matching your machine — the
current Stockfish releases ship one *universal* build per platform (on any
Mac, Apple Silicon or Intel, that's `stockfish-macos-universal`), installed
into `venv/bin`, ready for the move assist and mirror mode:

```bash
./setup.sh
source venv/bin/activate
```

The Stockfish download is best-effort: if it fails (no network, unsupported
platform) setup still succeeds and only the move assist is disabled. Useful
knobs:

```bash
SKIP_STOCKFISH=1 ./setup.sh          # don't download Stockfish
STOCKFISH_VERSION=sf_17.1 ./setup.sh # pin a specific release tag
```

Or do it manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 scripts/install_stockfish.py --dest venv/bin   # optional: the engine
```

Launching with `./run.sh` puts `venv/bin` on `PATH`, so the engine installed
there is found even without activating the venv.

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
  frame, so a stall is immediately visible;
- pressing the **assist key** (`A`) on your turn plays the engine's best move
  for you (see [Move assist](#move-assist-optional)); each assist action is
  logged in the activity list.

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

**The GUI windows can't open: "No module named '_tkinter'" (macOS).**
Homebrew Python ships Tk as a separate *versioned* formula, and the version
must match the Python your venv was built on — a bare `brew install
python-tk` installs Tk for the newest Python, which may not be yours.
`setup.sh` warns and names the right one; mirror mode exits with the same
hint. Check the venv's version and install that:

```bash
venv/bin/python --version          # e.g. Python 3.14.x
brew install python-tk@3.14
venv/bin/python -c "import tkinter; print(tkinter.TkVersion)"
```

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

**It crashed with "zsh: trace trap" right after I confirmed the board
(macOS).** That was the global assist keybind: macOS kills the process when a
keyboard listener starts without **Input Monitoring** permission. Grant your
terminal Input Monitoring (and Accessibility, to move the mouse) under
*System Settings → Privacy & Security*, then restart it. The program now
checks this permission before starting the listener and, if it's missing,
prints a message and runs without the assist instead of crashing. You can
also disable the assist entirely with `CHESSCHEAT_NO_ASSIST=1`.

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

Mirror mode's **Watch app** reading is covered three ways:
`tests/test_move_inference.py` (dependency-free) checks the highlight,
occupancy/colour and move-inference logic on synthetic square scans;
`tests/test_opponent_watcher.py` (needs python-chess) drives the watcher
through the mocks — skips capture on your turn, submits and answers a
detected move, toggle, polling loop, capture errors logged; and
`tests/test_watch_real_images.py` (needs numpy, Pillow, python-chess)
composes the three real piece sets with last-move tints under the pieces
and checks the opponent's move — and only the opponent's — is read in both
orientations, including a capture, a knight move and a tinted king in check.

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
  interfaces/   recognition/   providers/   assist/   mirror/   mocks/
  capture/      gui/
tests/
```
