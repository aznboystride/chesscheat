"""Live chessboard reader -- application orchestration.

The ``run`` loop is programmed entirely against the interfaces in
``chesscheat.interfaces``: it asks a ``SetupProvider`` for the side and box,
builds a ``FrameSource`` for that box, calibrates a ``BoardRecognizer`` from the
first frame (the starting position) and then reports every subsequent frame.
``main`` wires the real GUI/screen/numpy implementations; tests wire mocks.
"""

import collections
import sys
import time

from chesscheat import board


def run(setup, make_frame_source, recognizer, *, on_board,
        on_frame=lambda image: None, before_calibrate=lambda: None,
        interval=0.0, sleeper=time.sleep):
    """Drive the read loop using injected interface implementations.

    Asks ``setup`` for the side and box, shows the user what the box captures
    (reselecting until it is confirmed), builds a frame source, calibrates the
    recognizer from the first frame (the starting position) and then reports
    every subsequent frame until the source is exhausted or interrupted.

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

    try:
        while True:
            try:
                image = frames.grab()
            except StopIteration:
                break
            reading = recognizer.read(image)
            on_frame(image)
            on_board(reading, playing_white)
            if interval:
                sleeper(interval)
    except KeyboardInterrupt:
        pass
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


def main():
    """Wire the real implementations and run the live reader."""
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

    run(setup, ScreenFrameSource, recognizer,
        on_board=on_board, on_frame=on_frame,
        before_calibrate=lambda: print(
            "\nCapture confirmed -- calibrating from the starting position..."),
        interval=0.3)


if __name__ == "__main__":
    main()
