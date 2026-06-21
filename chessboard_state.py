"""Live chessboard reader -- application entry point.

The ``run`` loop is programmed entirely against the interfaces in
``interfaces.py``: it asks a ``SetupProvider`` for the side and box, builds a
``FrameSource`` for that box, calibrates a ``BoardRecognizer`` from the first
frame (the starting position) and then reports every subsequent frame. ``main``
wires the real GUI/screen/numpy implementations; tests wire mocks instead.
"""

import time

import board


def run(setup, make_frame_source, recognizer, *, on_board,
        before_calibrate=lambda: None, interval=0.0, sleeper=time.sleep):
    """Drive the read loop using injected interface implementations.

    Asks ``setup`` for the side and box, builds a frame source, calibrates the
    recognizer from the first frame (the starting position) and then reports
    every subsequent frame until the source is exhausted or interrupted.

    Args:
        setup: A ``SetupProvider`` for the side and bounding box.
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
    box = setup.select_box()
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


def _console_printer():
    """Build a de-duplicating ``on_board`` callback that prints board + FEN.

    Returns:
        A ``(board_map, playing_white)`` callback that clears the screen and
        reprints only when the position changes from the previous frame.
    """
    last = [None]

    def show(board_map, playing_white):
        if board_map != last[0]:
            print("\033[H\033[J", end="")  # clear screen
            print(board.render(board_map, playing_white))
            print("\nFEN:", board.to_fen(board_map))
            last[0] = board_map

    return show


def main():
    """Wire the real implementations and run the live reader."""
    from providers import (GuiSetupProvider, PromptSetupProvider,
                           FallbackSetupProvider, ScreenFrameSource)
    from recognition import TemplateBoardRecognizer, NumpyImageBackend

    print("=== Live Chessboard Reader ===")
    print("Make sure the board is in the standard starting position.\n")

    setup = FallbackSetupProvider(GuiSetupProvider(), PromptSetupProvider())
    recognizer = TemplateBoardRecognizer(NumpyImageBackend())

    def gate():
        input("\nPosition the board in the starting position, then press Enter "
              "to calibrate...")
        print("Calibrated. Reading board... (press Ctrl+C to stop)\n")

    run(setup, ScreenFrameSource, recognizer,
        on_board=_console_printer(), before_calibrate=gate, interval=0.3)


if __name__ == "__main__":
    main()
