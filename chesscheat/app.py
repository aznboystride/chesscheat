"""Live chessboard reader -- application orchestration.

The ``run`` loop is programmed entirely against the interfaces in
``chesscheat.interfaces``: it asks a ``SetupProvider`` for the side and box,
builds a ``FrameSource`` for that box, calibrates a ``BoardRecognizer`` from the
first frame (the starting position) and then reports every subsequent frame.
``main`` wires the real GUI/screen/numpy implementations; tests wire mocks.
"""

import argparse
import collections
import os
import sys
import time

from chesscheat import board


def run(setup, make_frame_source, recognizer, *, on_board,
        on_frame=lambda image: None, before_calibrate=lambda: None,
        interval=0.0, sleeper=time.sleep, trigger=None,
        on_trigger=lambda board_map, playing_white, box: None):
    """Drive the read loop using injected interface implementations.

    Asks ``setup`` for the side and box, shows the user what the box captures
    (reselecting until it is confirmed), builds a frame source, calibrates the
    recognizer from the first frame (the starting position) and then reports
    every subsequent frame until the source is exhausted or interrupted. When
    a ``trigger`` fires (e.g. the user's keybind), ``on_trigger`` is invoked
    with the latest reading so an assistant can act on the current position.

    Args:
        setup: A ``SetupProvider`` for the side, bounding box, and capture
            confirmation.
        make_frame_source: A ``box -> FrameSource`` factory.
        recognizer: A ``BoardRecognizer`` to calibrate and read with.
        on_board: Callback invoked as ``(board_map, playing_white)`` for each
            read frame.
        on_frame: Callback invoked with each raw captured frame just after it
            is recognised (so a preview can annotate the frame with its own
            reading) and before ``on_board``.
        before_calibrate: Side-effect hook run just before calibration, e.g.
            to wait for the user to set up the starting position.
        interval: Seconds to sleep between frames; 0 disables sleeping.
        sleeper: Sleep function, injectable for testing.
        trigger: Optional ``MoveTrigger`` polled once per frame; started
            before the loop and stopped when it ends. None disables the
            assist path entirely.
        on_trigger: Callback invoked as ``(board_map, playing_white, box)``
            with the latest reading when ``trigger`` fires.

    Returns:
        The ``playing_white`` boolean chosen via ``setup``.
    """
    playing_white = setup.select_side()
    while True:
        box = setup.select_box()
        if setup.confirm_box(make_frame_source(box).grab(), playing_white):
            break
    frames = make_frame_source(box)

    before_calibrate()
    recognizer.calibrate(frames.grab(), playing_white)

    if trigger is not None:
        try:
            trigger.start()
        except Exception as exc:
            # A trigger that can't start (e.g. missing OS permission) disables
            # the assist -- it must never take down the reader.
            print(f"Move assist disabled: {exc}")
            trigger = None
    try:
        while True:
            try:
                image = frames.grab()
            except StopIteration:
                break
            reading = recognizer.read(image)
            on_frame(image)
            on_board(reading, playing_white)
            if trigger is not None and trigger.poll():
                on_trigger(reading, playing_white, box)
            if interval:
                sleeper(interval)
    except KeyboardInterrupt:
        pass
    finally:
        if trigger is not None:
            trigger.stop()
    return playing_white


def _console_ui(header="", clock=time.time):
    """Build the live terminal display: board, FEN, activity log, capture rate.

    The display clears the screen on each repaint, which erases everything
    printed earlier -- so all state the user should keep seeing (the header,
    the recent activity, the capture rate) is part of every repaint. A full
    repaint happens when the position changes or an event is logged; between
    repaints the capture-rate line (the last line on screen) is rewritten in
    place for every frame, so the terminal always shows the reader is alive.

    Args:
        header: Status line shown above the board on every repaint.
        clock: Time source used for the frame-rate estimate, injectable for
            testing.

    Returns:
        An ``(on_board, on_frame, on_event)`` triple of callbacks sharing the
        display: ``on_board(board_map, playing_white)`` repaints when the
        position changes; ``on_frame(image)`` records a capture timestamp and
        refreshes the rate line; ``on_event(kind, detail)`` appends a
        timestamped activity line (e.g. a move or a dropped frame) and
        repaints.
    """
    state = {"board": None, "white": True}
    events = collections.deque(maxlen=6)
    times = collections.deque(maxlen=20)

    def rate_text():
        if len(times) < 2 or times[-1] <= times[0]:
            return "capturing..."
        return (f"capturing at "
                f"{(len(times) - 1) / (times[-1] - times[0]):.1f} fps")

    def repaint():
        print("\033[H\033[J", end="")  # clear screen
        if header:
            print(header + "\n")
        if state["board"] is not None:
            print(board.render(state["board"], state["white"]))
            print("\nFEN:", board.to_fen(state["board"]))
        if events:
            print("\nRecent activity:")
            print("\n".join(f"  {line}" for line in events))
        print("\n" + rate_text().ljust(40), end="", flush=True)

    def on_board(board_map, playing_white):
        if board_map != state["board"]:
            state["board"] = board_map
            state["white"] = playing_white
            repaint()

    def on_frame(_image):
        times.append(clock())
        print("\r" + rate_text().ljust(40), end="", flush=True)

    def on_event(kind, detail):
        stamp = time.strftime("%H:%M:%S")
        label = "frame dropped" if kind == "dropped" else kind
        events.append(f"[{stamp}] {label}: {detail}")
        repaint()

    return on_board, on_frame, on_event


def _calibration_progress(done, total):
    """Render a single-line terminal progress bar for calibration.

    Overwrites the same line as squares are learned and, on completion,
    announces that the reader is live -- so it is always visible in the
    terminal whether calibration is running, finished, or stuck.

    Args:
        done: Squares learned so far.
        total: Total squares to learn.
    """
    width = 32
    filled = width * done // total
    print(f"\r  Calibrating [{'#' * filled}{'.' * (width - filled)}] "
          f"{done}/{total} squares", end="", flush=True)
    if done == total:
        print("\nCalibration complete. Watching the board... "
              "(press Ctrl+C to stop)\n", flush=True)


# Best matches scoring below this SSIM are shown as "unknown". Genuine
# matches score near 1.0 and the best wrong template stays under ~0.5 on the
# fixture sets, so 0.6 separates them with margin on both sides.
SSIM_THRESHOLD = 0.6

# Key the user presses when it is their turn and they want the assistant to
# compute and play the best move.
ASSIST_KEY = "a"


def build_engine(engine_url=None):
    """Pick the decision maker behind the ``MoveEngine`` interface.

    Args:
        engine_url: URL of a remote best-move service; falls back to the
            ``CHESSCHEAT_ENGINE_URL`` environment variable. When neither is
            set, a local Stockfish binary is used.

    Returns:
        A ``RemoteMoveEngine`` for a URL, else a ``StockfishMoveEngine``.

    Raises:
        FileNotFoundError: If no URL is given and no Stockfish binary is
            found.
    """
    from chesscheat.assist import StockfishMoveEngine, RemoteMoveEngine

    url = engine_url or os.environ.get("CHESSCHEAT_ENGINE_URL")
    return RemoteMoveEngine(url) if url else StockfishMoveEngine()


def _build_assist(on_event, engine_url=None):
    """Try to wire the move-assist (engine + mouse + keybind).

    The assist needs a decision maker (local Stockfish, or a remote service
    via ``engine_url``) plus ``pyautogui`` and ``pynput``. If any is missing
    this returns no-op wiring and prints why, so the reader still runs
    without the assist.

    Args:
        on_event: The console activity callback, used to log assist actions.
        engine_url: Optional remote engine URL (see ``build_engine``).

    Returns:
        A ``(trigger, on_trigger)`` pair for ``run``; ``trigger`` is None
        when the assist is unavailable.
    """
    noop = lambda board_map, playing_white, box: None

    if os.environ.get("CHESSCHEAT_NO_ASSIST"):
        print("Move assist disabled (CHESSCHEAT_NO_ASSIST set).\n")
        return None, noop

    from chesscheat.assist import PyAutoGuiActuator, KeyTrigger, assist_move
    try:
        import pyautogui  # noqa: F401  -- probe availability early
        import pynput  # noqa: F401
        engine = build_engine(engine_url)
        actuator = PyAutoGuiActuator()
        trigger = KeyTrigger(ASSIST_KEY)
    except (ImportError, FileNotFoundError) as exc:
        print(f"Move assist disabled ({exc}).\n")
        return None, noop

    # On macOS the global keybind needs Input Monitoring permission; without
    # it, starting the listener aborts the process (a "trace trap"). Check up
    # front and disable the assist gracefully instead of crashing later.
    if not trigger.permission_ok():
        print(f"Move assist disabled: grant your terminal Input Monitoring "
              "(and Accessibility) in System Settings -> Privacy & Security, "
              f"then restart to use the '{ASSIST_KEY.upper()}' keybind.\n")
        return None, noop

    print(f"Move assist ready: press '{ASSIST_KEY.upper()}' on your turn to "
          "play the engine's best move.\n")

    def on_trigger(board_map, playing_white, box):
        on_event("assist", "computing best move...")
        try:
            uci = assist_move(board_map, playing_white, box, engine, actuator)
        except Exception as exc:  # keep the read loop alive on engine errors
            on_event("assist", f"failed: {exc}")
            return
        on_event("assist", f"played {uci}" if uci
                 else "no move (game over or unreadable position)")

    return trigger, on_trigger


def reader_main(engine_url=None):
    """Wire the real implementations and run the live reader.

    Args:
        engine_url: Optional remote engine URL for the move assist.
    """
    from chesscheat.providers import (GuiSetupProvider, PromptSetupProvider,
                                      FallbackSetupProvider, ScreenFrameSource)
    from chesscheat.recognition import (TemplateBoardRecognizer,
                                        NumpyImageBackend)

    print("=== Live Chessboard Reader ===")
    print("Make sure the board is in the standard starting position.\n")
    if sys.platform == "darwin":
        print("Note (macOS): the app running this (Terminal, iTerm, ...) "
              "needs Screen Recording\npermission -- System Settings → "
              "Privacy & Security → Screen Recording -- or every\ncapture "
              "will show only the desktop wallpaper. Grant it and restart "
              "the terminal.\n")

    from chesscheat.gui import LivePreview

    setup = FallbackSetupProvider(GuiSetupProvider(), PromptSetupProvider())

    console_board, console_frame, on_event = _console_ui(
        "Calibrated 64 squares -- watching the board. Press Ctrl+C to stop.")
    # Each frame is evaluated purely from the image, matching every square
    # (SSIM) against the templates learned from the starting position; no
    # move-legality filtering. Low-scoring squares surface as "unknown".
    recognizer = TemplateBoardRecognizer(NumpyImageBackend(),
                                         on_progress=_calibration_progress,
                                         match_threshold=SSIM_THRESHOLD)
    preview = LivePreview()
    seen = {"board": None, "unknown": None}

    def on_board(board_map, playing_white):
        if board_map != seen["board"] and seen["board"] is not None:
            on_event("position", board.to_fen(board_map))
        seen["board"] = board_map
        console_board(board_map, playing_white)

    def on_frame(image):
        # recognizer.read has just run for this frame, so last_scored is the
        # scored reading of exactly this capture.
        preview.show(image, recognizer.last_scored, recognizer.playing_white)
        unknown = sorted(sq for sq, (label, _score)
                         in recognizer.last_scored.items() if label == "?")
        if unknown != seen["unknown"] and unknown:
            on_event("unknown", f"{len(unknown)} square(s) below "
                                f"SSIM {SSIM_THRESHOLD}")
        seen["unknown"] = unknown
        console_frame(image)

    trigger, on_trigger = _build_assist(on_event, engine_url)

    run(setup, ScreenFrameSource, recognizer,
        on_board=on_board, on_frame=on_frame,
        before_calibrate=lambda: print(
            "\nCapture confirmed -- calibrating from the starting position..."),
        interval=0.3, trigger=trigger, on_trigger=on_trigger)


def mirror_main(engine_url=None):
    """Run mirror mode: a GUI where the user plays the opponent's moves.

    Asks for the user's side and the real chess app's board box, then opens
    a mirror board oriented from the opponent's perspective. Each opponent
    move the user enters is answered by the engine, and the reply is played
    on the mirror board and -- by dragging the mouse over the box -- in the
    real app.

    Args:
        engine_url: Optional remote engine URL (see ``build_engine``).
    """
    from chesscheat.providers import (GuiSetupProvider, PromptSetupProvider,
                                      FallbackSetupProvider)
    from chesscheat.assist import PyAutoGuiActuator
    from chesscheat.mirror import MirrorGame
    from chesscheat.gui import MirrorBoardWindow

    print("=== Mirror Mode ===")
    print("Pick your side, then click the real board's corners. A mirror "
          "board opens from the\nopponent's perspective: enter each opponent "
          "move on it and the program answers\nthere and in the real app.\n")
    if sys.platform == "darwin":
        print("Note (macOS): moving the mouse needs Accessibility permission "
              "for your terminal\n(System Settings → Privacy & Security → "
              "Accessibility).\n")

    try:
        engine = build_engine(engine_url)
    except FileNotFoundError as exc:
        raise SystemExit(f"No decision maker available: {exc}")

    setup = FallbackSetupProvider(GuiSetupProvider(), PromptSetupProvider())
    playing_white = setup.select_side()
    box = setup.select_box()

    def log(kind, detail):
        print(f"[{time.strftime('%H:%M:%S')}] {kind}: {detail}", flush=True)

    def on_move(origin, destination):
        mirror.submit_move(origin, destination)   # bound below

    view = MirrorBoardWindow(
        on_move, bottom_white=not playing_white, avoid_box=box,
        on_auto=lambda enabled: mirror.set_auto(enabled),
        on_delay=lambda seconds: mirror.set_delay(seconds),
        on_strength=lambda elo: mirror.set_strength(elo))
    mirror = MirrorGame(playing_white, box, engine, PyAutoGuiActuator(),
                        view, on_event=log, schedule=view.schedule)
    log("mode", f"you play {'white' if playing_white else 'black'}; "
                f"enter {'black' if playing_white else 'white'}'s moves. "
                "Toggle Auto-play, the reply delay and the strength in the "
                "window at any time.")
    mirror.start()
    view.run()


def build_parser():
    """Build the command-line parser.

    Returns:
        An ``argparse.ArgumentParser`` with ``--mode`` and ``--engine-url``.
    """
    parser = argparse.ArgumentParser(
        prog="chesscheat",
        description="Read a chessboard off the screen, or mirror a game and "
                    "let an engine play your moves.")
    parser.add_argument(
        "--mode", choices=("reader", "mirror"), default="reader",
        help="'reader' (default) watches the screen and prints the position; "
             "'mirror' opens a board where you enter the opponent's moves and "
             "the engine plays yours, in the GUI and in the real app.")
    parser.add_argument(
        "--engine-url", default=None,
        help="URL of a remote best-move service (POST {fen} -> {move}); "
             "defaults to CHESSCHEAT_ENGINE_URL, else a local Stockfish.")
    return parser


def main(argv=None):
    """Parse the command line and run the chosen mode.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.
    """
    args = build_parser().parse_args(argv)
    if args.mode == "mirror":
        mirror_main(args.engine_url)
    else:
        reader_main(args.engine_url)


if __name__ == "__main__":
    main()
