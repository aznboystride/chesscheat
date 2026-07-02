"""Live chessboard reader -- application orchestration.

The ``run`` loop is programmed entirely against the interfaces in
``chesscheat.interfaces``: it asks a ``SetupProvider`` for the side and box,
builds a ``FrameSource`` for that box, calibrates a ``BoardRecognizer`` from the
first frame (the starting position) and then reports every subsequent frame.
``main`` wires the real GUI/screen/numpy implementations; tests wire mocks.
"""

import sys
import time

from chesscheat import board


def run(setup, make_frame_source, recognizer, *, on_board,
        before_calibrate=lambda: None, interval=0.0, sleeper=time.sleep):
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
        if setup.confirm_box(make_frame_source(box).grab()):
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
            on_board(recognizer.read(image), playing_white)
            if interval:
                sleeper(interval)
    except KeyboardInterrupt:
        pass
    return playing_white


def _console_printer(header=""):
    """Build a de-duplicating ``on_board`` callback that prints board + FEN.

    Args:
        header: Status line reprinted above the board on every repaint. The
            printer clears the screen each time the position changes, which
            erases everything printed before (including the calibration
            progress), so any state the user should keep seeing must be part
            of this header.

    Returns:
        A ``(board_map, playing_white)`` callback that clears the screen and
        reprints only when the position changes from the previous frame.
    """
    last = [None]

    def show(board_map, playing_white):
        if board_map != last[0]:
            print("\033[H\033[J", end="")  # clear screen
            if header:
                print(header + "\n")
            print(board.render(board_map, playing_white))
            print("\nFEN:", board.to_fen(board_map))
            last[0] = board_map

    return show


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


def main():
    """Wire the real implementations and run the live reader."""
    from chesscheat.providers import (GuiSetupProvider, PromptSetupProvider,
                                      FallbackSetupProvider, ScreenFrameSource)
    from chesscheat.recognition import (TemplateBoardRecognizer,
                                        NumpyImageBackend, LegalMoveFilter)

    print("=== Live Chessboard Reader ===")
    print("Make sure the board is in the standard starting position.\n")
    if sys.platform == "darwin":
        print("Note (macOS): the app running this (Terminal, iTerm, ...) "
              "needs Screen Recording\npermission -- System Settings → "
              "Privacy & Security → Screen Recording -- or every\ncapture "
              "will show only the desktop wallpaper. Grant it and restart "
              "the terminal.\n")

    setup = FallbackSetupProvider(GuiSetupProvider(), PromptSetupProvider())
    recognizer = LegalMoveFilter(TemplateBoardRecognizer(
        NumpyImageBackend(), on_progress=_calibration_progress))

    run(setup, ScreenFrameSource, recognizer,
        on_board=_console_printer(
            "Calibrated 64 squares -- watching the board. "
            "Press Ctrl+C to stop."),
        before_calibrate=lambda: print(
            "\nCapture confirmed -- calibrating from the starting position..."),
        interval=0.3)


if __name__ == "__main__":
    main()
