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
# Mirror mode: no detection; enter the opponent's moves on a GUI, the
# engine plays yours (in the GUI and, by mouse, in the real app)
python3 -m chesscheat --mode mirror
# Either mode with a remote decision maker instead of local Stockfish
python3 -m chesscheat --mode mirror --engine-url http://host:8000/best-move

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
`scripts/install_stockfish.py` (Stockfish 19+ universal builds, e.g.
`macos-universal` for any Mac; skip with `SKIP_STOCKFISH=1`, pin with
`STOCKFISH_VERSION`). That step
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
                    MoveEngine, MoveActuator, MoveTrigger, MirrorView
  recognition/      TemplateBoardRecognizer, NumpyImageBackend, LegalMoveFilter,
                    square_scan (scan_squares)
  providers/        Gui/Prompt/Fallback SetupProvider, ScreenFrameSource
  assist/           StockfishMoveEngine, RemoteMoveEngine, BookMoveEngine,
                    style (STYLES, choose_move, aggression, solidity),
                    PyAutoGuiActuator, KeyTrigger, assist_move (move_pixels)
  mirror/           MirrorGame (position_map), gui_placement, OpponentWatcher,
                    move_inference (highlighted_squares, piece_colours,
                    infer_opponent_move), evaluation (white_share,
                    score_label)
  mocks/            Mock{SetupProvider,FrameSource,ImageBackend,MoveEngine,
                    MoveActuator,MoveTrigger,MirrorView}, synthetic_image
  capture/          screenshot
  gui/              dialogs, overlays (annotations/draw), LivePreview,
                    MirrorBoardWindow, BackgroundRunner
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
  or None; plus **concrete, optional** `set_strength(elo)` (None = full
  strength; the base is a no-op so engines that can't vary strength ignore
  it), `set_think_time(seconds)` (search budget for subsequent calls; the
  base ignores it), `set_style(style, margin)` (a playing character, see
  `assist/style.py`; the base ignores it) and `evaluate(fen)` → `{"cp": n}` / `{"mate": n}` from
  **white's** perspective, or None (the base returns None: no evaluation
  bar). **This is the decision-maker interface**: `StockfishMoveEngine`
  (local binary) and `RemoteMoveEngine` (HTTP service) implement it, and
  `app.build_engine(engine_url)` picks one (`--engine-url` /
  `CHESSCHEAT_ENGINE_URL` → remote, else local). `MoveActuator` —
  `apply(uci, box, playing_white)` plays a move by dragging the mouse.
  `MoveTrigger` — `start()`/`poll()`/`stop()`; `poll` edge-consumes one
  activation (the read loop polls it once per frame). `MirrorView` —
  `update(board_map, last_move, status)` / `run()`: the mirror-mode board the
  user enters the opponent's moves on (it reports picks via the callback it
  was constructed with).

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
  `shutil.which("stockfish")`; `path` may also be a command list) at
  construction; **one UCI process is kept alive** across calls via
  **python-chess** (`chess.engine`, lazy): `_engine()` opens it on first
  use and registers `close` with `atexit`; `_run(action)` closes and
  re-raises on `chess.engine.EngineError` so a dead process is reopened by
  the next call; `running` tells; `SimpleEngine` serialises commands from
  several threads (a worker-thread search and an evaluation just queue).
  `best_move` returns None for an invalid/finished position; `think_time`
  (default **0.3 s**, settable via `set_think_time`, floor 0.01) is the
  `Limit(time=…)`. Strength is sent as **per-call `options`** on every
  `play` via the pure `limit_strength_options(elo, min, max)` →
  `{UCI_LimitStrength, UCI_Elo}` clamped to the engine's advertised range,
  or `{UCI_LimitStrength: False}` for None (restoring a process limited
  earlier); skipped if the engine has no `UCI_Elo` option. The binary is normally supplied by
  `scripts/install_stockfish.py` (run from `setup.sh`), which picks the
  release asset for the host — `asset_candidates`/`select_asset` map
  system/machine to the right tarball. Since **Stockfish 19** every platform
  ships one *universal* build (`stockfish-macos-universal.tar.gz`,
  `stockfish-linux-x86-64-universal.tar.gz`, …, gzip tarballs), tried first;
  the pre-19 per-CPU names (`macos-m1-apple-silicon.tar`,
  `ubuntu-x86-64-avx2.tar`, …) are fallbacks for a pinned older release.
  `.tar`/`.tar.gz`/`.tgz` accepted, `.zip` never. It downloads from the
  official Stockfish GitHub releases, extracts into a subfolder (so the
  largest-file search can't pick the archive itself), installs it as
  `venv/bin/stockfish` and clears the macOS quarantine flag. Stdlib-only;
  selection and extraction are tested in `test_install_stockfish.py`
  (no network).
- `RemoteMoveEngine(url)` — the second decision maker: ``POST {"fen": …,
  "elo": …}`` to an HTTP endpoint (``elo`` from `set_strength`, null = full),
  reads ``{"move": "e2e4"}`` (``null`` → None). `evaluate(fen)` posts
  ``{"fen": …, "evaluate": true}`` and returns the reply's ``score`` dict
  (``{"cp": n}`` / ``{"mate": n}``) or None when absent/not a dict;
  `set_think_time` is forwarded as ``"think"`` and `set_style` as
  ``"style"``/``"style_margin"`` in each best-move request (null =
  service default).
  Stdlib ``urllib`` only (shared `_post`); raises ``RuntimeError`` on an
  unreachable service, non-2xx status, malformed JSON or (for `best_move`)
  a reply without ``move``. Tested against a real local ``http.server`` in
  `test_mirror.py`. `StockfishMoveEngine.evaluate` runs `engine.analyse`
  for `eval_time` (0.1 s) on the shared process with per-call
  `{UCI_LimitStrength: False}` (the bar shows the true evaluation even
  while the engine plays weakened), converting `info["score"].white()` to
  the dict; None for finished/invalid positions. Both are exercised
  without Stockfish by `tests/fixtures/fake_uci_engine.py`, a minimal UCI
  engine (advertises `UCI_LimitStrength`/`UCI_Elo`, answers the first
  legal move with `score cp ±37` encoding whether it was limited, `crash`
  argument dies on `go`) run as `[sys.executable, path]`.
- **Playing style** (`assist/style.py`, function-only) — Stockfish has no
  style options, so style is applied *around* the engine. `STYLES =
  ("best", "aggressive", "solid", "unusual")`. `_features(fen, uci)`
  (python-chess, lazy) describes a move: capture/captured value, check,
  castling, piece, forward ranks, into the enemy half, `near_king` (lands
  within 4 squares of the enemy king, nearer than it started — a plain
  "distance reduced" test fired for almost every move), develops (minor
  piece off its home rank), king move. `aggression` = +3 check, +2
  capture, +1 enemy half, +1 near king, −2 castling, −1 retreat;
  `solidity` = +3 castling, +2 develops, +1 quiet, −2 king walk, −1
  capture, −1 queen move. `eligible_moves(candidates, margin_cp)` keeps
  the `[(uci, cp)]` lines (mover's perspective, best first) within the
  margin of the best; `choose_move(candidates, style, fen, margin_cp=30,
  rng)` picks: aggressive/solid = max by `(score, cp)` over the eligible
  set, unusual = a random eligible line *other than the first* when there
  is one, anything else = the first. `StockfishMoveEngine.set_style(style,
  margin)` (margin in pawns, default 0.3): with a style on, `best_move`
  runs `_styled_move` — `engine.analyse(..., multipv=STYLE_CANDIDATES=5,
  options=strength)` in the same `think_time`, candidates from each
  info's `pv[0]` and `score.pov(turn).score(mate_score=MATE_SCORE)`, then
  `choose_move`. Note Stockfish applies its Elo limit when *choosing* a
  move, so the MultiPV lines are its honest best lines regardless of the
  strength setting: with a style on, the margin is what makes it stray.
  `BookMoveEngine(inner, path, rng)` is a `MoveEngine` decorator over a
  Polyglot `.bin` book (`chess.polyglot`, lazy): in book it plays
  `weighted_choice` (or the *least* weighted entry for `"unusual"`), out
  of book it delegates; `set_style`/`set_strength`/`set_think_time`/
  `evaluate` forwarded, `close` closes both. `app.build_engine(engine_url,
  think_time, style, style_margin, book)` wraps the engine when `--book`
  is given (missing file → `FileNotFoundError`) and applies the style;
  `--style`/`--style-margin` are CLI flags for both modes.
- `PyAutoGuiActuator` — `move_pixels(uci, box, playing_white)` (pure: maps the
  from/to squares to screen-pixel centres via `board.parse_square`/`cell_of`)
  then `pyautogui` (lazy): moveTo(origin) → **click** (focuses the chess
  app's window; on macOS the first click on an inactive window only
  activates it, so a cold drag could be swallowed) → sleep(`focus_pause`)
  → mouseDown → moveTo(dest, `duration`) → mouseUp. The piece gets two
  presses (focus click + the drag's mouse-down). **Tuned for speed**:
  `_pyautogui()` imports the module with `pyautogui.PAUSE = 0` (its default
  0.1 s after *every* call would add ~0.5 s per move), `focus_pause` is
  0.05 s and `duration` 0.15 s — just above the floor, because `pyautogui`
  only animates a move *strictly longer* than `MINIMUM_DURATION` (0.1 s;
  shorter ones jump) and a web board needs the intermediate motion events
  to see a drag (0.15 s gives three steps at `MINIMUM_SLEEP`). The exact call
  sequence, the pause disabling and the defaults are pinned in
  `test_assist.py` with a fake `pyautogui` module. Promotion suffix ignored
  (site prompt not handled).
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

### Mirror mode (`chesscheat/mirror/`) — `--mode mirror`

No detection. The user mirrors each **opponent** move on a GUI board and the
program plays its own side's reply in two places at once: on the GUI and,
via the `MoveActuator`, in the real app (dragging the mouse over the box the
user clicked out). `MirrorGame(playing_white, box, engine, actuator, view,
on_event)` is the controller, programmed only against `MoveEngine` /
`MoveActuator` / `MirrorView`:
- holds a **python-chess** `Board` (lazy import; rules, legality, castling,
  en passant, promotion) — `position_map(board)` converts it to the project's
  board map; `fen` exposes the full FEN for the engine;
- `start()` plays first if the program is white (and auto is on), else waits;
  `submit_move(from, to)` is the single entry point from the view: on the
  opponent's turn it records their move (auto-queening a promotion) and, if
  auto is on, triggers `_reply`; on the program's turn it is accepted only
  while auto is **paused** -- the user playing the program's side by hand --
  and is then actuated in the real app too (`_play_program_move`, event
  `"manual"`). Out-of-turn/illegal entries are rejected with a status.
- Runtime settings, each changeable any time: `set_auto(enabled)` (turning
  on mid-turn replies at once), `set_delay_range(lo, hi)` (`set_delay(x)` =
  `[x, x]`), `set_strength(elo)` (forwarded to `engine.set_strength`). The
  **delay** is the minimum time from the opponent's move (`_opponent_time`,
  via an injectable `clock`) to the reply; each reply draws its own delay
  from `delay_range` via an injectable `rng(lo, hi)` (`random.uniform`;
  equal ends → fixed, no draw) -- redrawn on every opponent move and on a
  range change, so jitter is per reply and a pending wait follows the new
  range. `_reply` has the engine think immediately **through an injectable
  `worker(fn, done)`** (the view's `run_in_background` → a thread, with
  `done(result, error)` marshalled back onto the Tk loop; `_run_now`
  synchronous by default) so the window never freezes during a search: it
  captures `(fen, epoch)`, computes the budget, sets `_thinking` (a second
  request for the same position -- e.g. `set_auto(True)` mid-search -- is
  ignored), and `done` drops a stale result (epoch/fen changed: undo, new
  game, another opponent move), turns an exception into an `("engine",
  "failed: …")` event + status, rejects None/illegal replies, else calls
  `_commit_after_delay`, which either plays now or defers itself via the
  injectable `schedule(seconds, fn)` (Tk `after` in the GUI; immediate by
  default). A deferred commit is dropped if the position changed or auto
  was paused, and re-defers if the delay was raised meanwhile. The
  **search budget** (`_think_budget`) is `think_time` (base, default 0.3 s,
  floor 0.05, `set_think_time`), raised when `think_in_delay` is on
  (`set_think_in_delay`, default on) to `min(max_think=10, current_delay -
  elapsed - think_margin=0.1)` -- the wait is spent searching and the move
  is still ready when the delay ends; it is applied with
  `engine.set_think_time(budget)` inside the worker right before
  `best_move`. `_play_program_move` pushes → `actuator.apply(uci, box,
  playing_white)` (the **real app's** orientation = the user's side), then
  `_return_pointer()`: `view.square_position(last opponent destination)`
  → `actuator.point_to(x, y)` parks the mouse back on the mirror board
  where the user last clicked (skipped when there is no opponent move or the
  view reports no position; errors logged). Both `square_position` and
  `point_to` are optional concrete methods on their interfaces (default
  None / no-op). Engine
  and actuator exceptions become status/events, never crashes; an actuator
  failure leaves the GUI move standing so the boards stay in sync.
- **Evaluation bar**: `_refresh_evaluation()` runs after every position
  change — `start`, each opponent move, each program/manual move, `undo`,
  `new_game` — **off the critical path**: the engine is asked through the
  `worker` (so a persistent engine busy with the search just queues the
  analysis, and the GUI never waits), and it is dispatched only *after*
  `_reply` has started the search / after the actuator has dragged (with a
  synchronous worker an instantly-played reply skips the pre-reply score,
  since the post-reply one follows at once); a score for a position that
  changed meanwhile is dropped (fen check). It
  calls `view.update_evaluation(white_share, label)` (optional concrete
  `MirrorView` method, default no-op) from `engine.evaluate(fen)` via the
  pure `evaluation.py` helpers: `white_share(score)` = lichess's logistic
  cp→probability (mate → 1.0/0.0, None → 0.5), `score_label(score)` =
  `"+0.35"` / `"-M2"` / `""`. A finished game shows the result string with
  share 1.0/0.0/0.5 without asking the engine; an `evaluate` exception is
  logged as `("engine", "evaluation failed: …")` and shows a level blank
  bar.
- `new_game(playing_white)` — same box, new side: fresh `chess.Board`,
  `last_move`/`_last_opponent_to` cleared, `_epoch` bumped (a reply deferred
  from the old game can never land), event `("new_game", "you play …")`,
  `view.set_orientation(playing_white)` (optional concrete, default no-op)
  then `start()` (the program opens at once as white with auto on; the
  `OpponentWatcher` reads `game.playing_white` each poll so it follows).
- `undo()` pops plies until the last **opponent** ply is removed (so the
  reply or a manual program move goes too), back onto the opponent's turn;
  `[]`/"Nothing to undo" when no opponent ply exists (the program's opening
  move alone never undoes). An `_epoch` counter, bumped on every opponent
  move and every undo and captured by scheduled commits, guarantees a reply
  deferred for an earlier state can never land -- even if the user
  re-enters the same move (the FEN check alone couldn't tell). Only the
  mirror board reverts; the status says the real app is unchanged.
- `gui_placement(box, screen_w, screen_h, win_w, win_h)` (pure) positions the
  GUI right/left/below/above the real board — never on top of it, since the
  mouse drags land there. `view_bottom_white(playing_white)` (pure) fixes the
  orientation: **the same as the real app**, the user's side at the bottom
  (this requirement flipped once — it used to be the opponent's view — and
  is pinned by a test).
- `gui/mirror_board.py` `MirrorBoardWindow(on_move, bottom_white, avoid_box,
  on_auto, on_delay, on_strength, on_undo, on_watch, on_new_game, on_think,
  on_think_in_delay, on_style, …)` is the Tk `MirrorView`: drawn with
  `bottom_white = view_bottom_white(playing_white)`, unicode
  piece glyphs, click-origin then click-destination → `on_move`,
  last-move/selection highlights, status line, and a control bar (Auto-play
  checkbox, reply-delay **min/max** spinboxes → `on_delay(lo, hi)`,
  strength menu from `STRENGTHS` presets,
  Undo button → `on_undo`, **New game** button → `ask_side()` (a
  `messagebox.askyesnocancel`: Yes = white, No = black, Cancel = keep
  playing) → `on_new_game(playing_white)`)
  reporting each change through its callback; `schedule(seconds, fn)` wraps
  Tk `after` for the controller's non-blocking delay; `square_position(name)`
  maps a square to absolute screen coordinates (canvas `winfo_rootx/y` +
  cell centre, same logical pixels `pyautogui` uses) for the pointer
  return; a **Watch app** checkbox → `on_watch(enabled)`; an **evaluation
  bar** canvas (`EVAL_WIDTH` px, left of the board; `update_evaluation`
  stores `(share, label)` and `_draw_evaluation` fills white's share from
  white's side — bottom when `bottom_white` — with the label rotated along
  the bar at the leading side's end); `set_orientation(bottom_white)`
  flips the board and bar for a new game as the other colour; a second
  control row holds Strength, a **Think (s)** spinbox → `on_think(seconds)`
  and a **Think in delay** checkbox → `on_think_in_delay(enabled)`; a
  third row holds the **Style** menu (`STYLE_LABELS`) and a **within
  (pawns)** spinbox, either change → `on_style(style, margin)`;
  `run_in_background(fn, done)` delegates to `gui/background_runner.py`
  `BackgroundRunner(after)` -- a daemon thread per job, outcomes queued
  and drained on the Tk loop by polling `after(25, …)` only while jobs are
  pending, `done(result, error)` always on the loop thread (tested with
  real threads and a fake `after`); `run()` is the Tk mainloop (this mode
  has no reader loop; the watcher polls via `schedule`).
- **Watching the real app** (`OpponentWatcher`, `move_inference.py`,
  `recognition/square_scan.py`) — infers the opponent's move from the app's
  **last-move highlight** instead of the user entering it. No piece
  recognition: `scan_squares(image)` (numpy, lazy) summarises each screen
  cell as `(background, piece_fraction, piece_brightness)` — background =
  median of the margin-trimmed patch's four **corner blocks** (20 % of the
  side; a border ring gets polluted by big pieces on textured boards),
  piece pixels = those > `background_tol` (60, summed over channels) from
  it. The pure, dep-free `move_inference` functions then work on that dict:
  `highlighted_squares(scans, bottom_white, tol=40)` = squares whose
  background is > `tol` from the **median background of their chequerboard
  parity class** (the parity is orientation-independent); `piece_colours(
  scans, bottom_white, board_map, playing_white)` = `{name: "own" |
  "opponent" | None}` — occupied if `piece_fraction >= 0.06`, colour by
  brightness nearest to a per-side reference that is the median brightness
  of the squares the *model* says hold that side's pieces (recomputed every
  frame, so any theme works; with no reference for a side everything reads
  "opponent" and legality decides); `infer_opponent_move(highlighted,
  colours, is_legal)` keeps every ordered pair of highlighted squares whose
  origin is empty, destination holds an opponent piece and `is_legal(from,
  to)` holds, and returns the single candidate (None if 0 or ≥ 2). That one
  rule rejects our own move's highlight (no opponent piece on our squares),
  a stale highlight of a move already in the model (the piece is on the
  origin, not off it), a capture still animating (destination shows our
  piece) and tolerates extra tints (a red king-in-check square has no legal
  pairing). `OpponentWatcher(game, grab, schedule, interval=0.02, on_event,
  scan=None, enabled=True, threaded=True, idle_sleep=0.05)` **captures as
  fast as the screen can be read**: `start()` launches a daemon
  `_capture_loop` that grabs + scans back to back whenever `_wanted` is
  set and parks the newest scan in `_latest` (a one-slot mailbox; errors in
  `_latest_error`), sleeping `idle_sleep` otherwise; the GUI-side `_tick`
  on the view's `schedule` every `interval` refreshes `_wanted = enabled
  and game.opponent_to_move` (the thread never touches the game model —
  python-chess boards are not thread-safe) and `_consume()`s the mailbox:
  infer → `game.submit_move(*move)` with a `("detected", …)` event, on the
  GUI thread. `threaded=False` makes each tick a synchronous `poll()`
  (grab → scan → infer), the path the mock tests drive. Capture/scan
  exceptions are reported once per distinct message (`("watch", …)`) and
  watching continues. `stop()` clears the flags and ends the thread.
  `set_enabled()`. `MirrorGame`
  exposes `opponent_to_move` and `is_legal(from, to)` (auto-queen) for it.
  Manual entry keeps working alongside; after an Undo the same highlight is
  read again unless watching is switched off. Verified on real chess.com
  screenshots (default theme and a textured green one) and the three
  fixture piece sets.
- `app.mirror_main(engine_url)` wires it: `_require_tk()` first (mirror mode
  has no text fallback for its board, so a missing `tkinter` exits at once
  with a `brew install python-tk@X.Y` hint instead of prompting and then
  crashing), then side + box via the setup provider,
  `build_engine(engine_url, think_time)` (applies `set_think_time` when
  given), `PyAutoGuiActuator`, the window, `MirrorGame(…, think_time,
  worker=view.run_in_background)`, an `OpponentWatcher` over
  `ScreenFrameSource(box).grab` and `view.schedule` (started after
  `mirror.start()`), timestamped console events; `app.main(argv)`
  dispatches `--mode reader|mirror` via `build_parser()` and passes
  `--think-seconds` (default 0.3) to both modes.

### Mocks (`chesscheat/mocks/`) — dependency-free, test the whole pipeline

`MockSetupProvider`, `MockFrameSource` (scripted frames), `render_mock_image`
(board map → synthetic grayscale image with a distinct per-piece pattern, plus
a square-colour tint that matching ignores), `MockImageBackend` (same
normalised-correlation logic as the real backend, in pure Python), and the
assist mocks: `MockMoveEngine` (canned `move` and `score`, records FENs seen
by `best_move`/`evaluate`), `MockMoveActuator` (records `(uci, box,
playing_white)` and `point_to` calls), `MockMoveTrigger` (`fire()` queues an
activation `poll` consumes), and `MockMirrorView` (records every
`(board_map, last_move, status)` redraw, `evaluations` and `orientations`).

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
- `test_install_stockfish.py` — the Stockfish installer: pure
  platform/asset selection (`asset_candidates`/`select_asset`) against the
  real Stockfish 19 asset list (universal `.tar.gz` builds: M1–M4 and Intel
  Macs → `macos-universal`, Linux x86-64/arm64) and a pre-19 list (legacy
  per-CPU `.tar` fallbacks), `.zip` never, unsupported → None; plus archive
  handling with a self-built tarball (gzip and plain extraction, the binary
  found in the extracted tree and never the archive, path-escape refused).
  Loads `scripts/install_stockfish.py` by path; dep-free, no network.
- `test_mirror.py` — mirror mode: `gui_placement` (right/left/below/above
  fallbacks, never over the box; dep-free), `position_map`, and `MirrorGame`
  through the mocks (`skipUnless(chess)`): program-as-white moves first in
  both places with the app's orientation, program-as-black waits then
  answers, illegal/out-of-turn entries rejected without consulting the
  engine, promotion auto-queens, engine None/exception/illegal-reply and
  actuator failure all become statuses without desync; the runtime settings
  -- auto off lets the user play the program's side (actuated in the real
  app, no engine call) and rejects nothing but illegal moves, auto back on
  mid-turn replies at once; the delay (fake clock + recording scheduler):
  engine consulted immediately but the commit deferred, fired commit plays,
  cancelled by a pause or a position change, extended when raised; strength
  forwarded to the engine; undo (reverts reply+opponent move, keeps the
  program's opener, cancels a pending reply, a stale timer can't land after
  undo+re-entry thanks to the epoch, reverts a manual move too, re-entry
  gets a fresh reply); delay jitter (fixed delay never calls the rng, each
  reply draws within the range, clamping, a range change redraws a pending
  wait); pointer return (to the opponent's last destination, none before an
  opponent move or without view positions, after manual moves too, failure
  logged); evaluation bar (`white_share`/`score_label` mapping dep-free;
  bar updated at start, every move, manual moves and undo; engine without
  evaluation → level blank bar; evaluate exception logged; game over shows
  the result without asking the engine); new game (switch to black
  reorients and waits, as white opens on the same box, a reply pending
  from the old game cannot land); think time (base applied before each
  search, `set_think_time` floor and event, the delay extends the search
  when enabled, elapsed time and `max_think` shrink it, a short delay never
  shrinks below the base, off keeps the fixed time); background thinking
  with a fake `_Worker` (reply lands only when the job finishes, delayed
  commit after the wait, undo/new game during a search drop the stale
  result, pausing cancels it, a second request for the same position is
  ignored, an engine exception becomes a status); `BackgroundRunner` with
  real threads and a fake `after` (result and exception delivered on the
  loop, polling stops when idle, concurrent jobs share one poller).
  `RemoteMoveEngine` against a real local `http.server` (protocol incl.
  `think`, null move, 5xx, malformed, unreachable, `evaluate` posts the
  flag and reads `score` / None without one / raises on 5xx).
  `build_parser` modes/engine-url/think-seconds/style/style-margin/book;
  `MirrorGame.set_style` forwarded with its margin and logged.
- `test_style.py` — playing styles: `eligible_moves`/`choose_move`
  (dep-free: margin filtering, best/unknown styles take the top line,
  unusual avoids the top line via the injected rng and falls back when
  alone); the heuristics on real positions (`skipUnless(chess)`: captures
  and checks aggressive, Qh5/Bc4 towards the king, castling and
  development solid, styles pick by character within the margin and not
  outside it); `BookMoveEngine` over a Polyglot book written by the test
  (`struct ">QHHI"`, `zobrist_hash`): weighted choice in book, rarest line
  for unusual, engine consulted out of book, settings and evaluation
  forwarded; the styled search of `StockfishMoveEngine` against the fake
  UCI engine (now `MultiPV`-aware: first N legal moves, 10 cp apart):
  best = first line, unusual avoids it with a wide margin and not with a
  zero one, aggressive picks the capture among the lines.
- `test_move_inference.py` — dep-free: `highlighted_squares` (clean board,
  both squares of a move, orientation, small noise ignored), `piece_colours`
  (classified from the model's references, sides swap for black, a moved
  piece classified by brightness not the model, capture, stray pixels, no
  reference → "opponent"), `infer_opponent_move` (opponent move read, own
  highlight ignored, stale highlight rejected, capture mid-animation
  rejected then accepted once landed, extra check tint tolerated,
  ambiguous/incomplete → None) on synthetic scan dicts.
- `test_opponent_watcher.py` — `OpponentWatcher` through `MirrorGame` +
  mocks with scripted scans (`skipUnless(chess)`), synchronous
  (`threaded=False`): no capture on our turn or at game over, detected
  move submitted and answered, own highlight is not a move,
  program-as-black reads white's first move, toggle skips capture, the
  polling loop re-arms until stopped, capture errors logged once and
  survived; and threaded with a real capture thread: grabs back to back
  once a tick wants them and a tick submits the newest scan's move,
  nothing captured on our turn, a thread-side error reported once, `stop`
  ends the thread.
- `test_watch_real_images.py` — the real `scan_squares` over the three
  fixture piece sets composed with last-move tints under the pieces
  (`skipUnless(numpy + Pillow + chess)`): pawn/knight moves read, own
  highlight and clean board give nothing, stale highlight after our reply
  rejected, capture read once landed, a red check tint on our king does not
  block detection, black orientation reads white's move.
- `test_assist.py` — the move assist, dep-free via mocks: `cell_of`/
  `parse_square`/`castling_field`/`to_full_fen` helpers, `move_pixels`
  geometry (white/black orientation, promotion suffix ignored), `assist_move`
  (builds a side-to-move FEN, plays the move, skips the actuator on None),
  and `run`'s trigger loop (start/stop, fired vs unfired, end-to-end through
  engine+actuator), the actuator's call sequence with a fake `pyautogui`
  (focus click then drag, `PAUSE` zeroed, quick defaults, `point_to`).
  `PersistentEngineProcessTests` run `StockfishMoveEngine` against
  `fixtures/fake_uci_engine.py` (`skipUnless(chess)`): one process serves
  searches and evaluations and is reused, strength is per search while
  evaluation is always full, black-to-move scores are white-relative, a
  crashed process is dropped and reopened. A
  `skipUnless(shutil.which("stockfish"))` case runs the real
  `StockfishMoveEngine` (legal opening move; None at game over; `evaluate`
  signed from white's perspective).

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
`mirror/mirror_game.py`, `providers/`, `gui/dialogs.py`). The `board`,
`interfaces`, `mocks`, `assist` and `mirror` packages and the `run` loop must
stay importable dependency-free so the suite runs anywhere (the subpackage
`__init__`s re-export only lazily-importing modules). Subpackage `__init__.py` files must likewise avoid eager heavy
imports (e.g. `capture/__init__.py` pulls in numpy, so depend on it only
behind a lazy import).
