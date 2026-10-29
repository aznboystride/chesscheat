"""The ``PyAutoGuiActuator`` move actuator and its pixel-geometry helper."""

from chesscheat import board
from chesscheat.interfaces import MoveActuator


def move_pixels(uci, box, playing_white):
    """Map a UCI move to its origin and destination pixel centres.

    Pure geometry: locates the centre of the move's from- and to-squares in
    absolute screen coordinates, given the board's bounding box and
    orientation.

    Args:
        uci: A move in UCI notation; only the first four characters (the
            origin and destination squares) are used.
        box: The board's ``(x1, y1, x2, y2)`` bounding box in absolute
            screen coordinates.
        playing_white: True if the board is oriented from white's
            perspective.

    Returns:
        A ``((from_x, from_y), (to_x, to_y))`` pair of float pixel centres.
    """
    x1, y1, x2, y2 = box
    cell_w, cell_h = (x2 - x1) / 8, (y2 - y1) / 8

    def centre(name):
        row, col = board.cell_of(*board.parse_square(name), playing_white)
        return x1 + (col + 0.5) * cell_w, y1 + (row + 0.5) * cell_h

    return centre(uci[0:2]), centre(uci[2:4])


class PyAutoGuiActuator(MoveActuator):
    """Plays a move by dragging the mouse with ``pyautogui``.

    First **clicks the piece** on its origin square to bring the chess app's
    window to the front -- on macOS the first click on an inactive window
    only activates it and is otherwise swallowed, so a drag started cold
    could be lost -- pauses briefly, then drags: presses the left button on
    the same square, moves to the destination and releases. The piece thus
    receives two presses (focus click, then the drag's mouse-down), the
    click-drag gesture most web boards expect. A promotion suffix in the
    move is ignored; the site's own promotion prompt (if any) is not
    handled.

    Attributes:
        duration: Seconds the cursor takes to travel between squares.
        focus_pause: Seconds to wait after the focusing click before the
            drag begins, giving the window time to come to the front.
    """

    def __init__(self, duration=0.25, focus_pause=0.15):
        """Initialise the actuator.

        Args:
            duration: Seconds the drag from origin to destination takes;
                a short travel time makes the motion look natural and gives
                web boards time to register the drag.
            focus_pause: Seconds between the focusing click on the piece
                and the start of the drag.
        """
        self.duration = duration
        self.focus_pause = focus_pause

    def apply(self, uci, box, playing_white):
        """Click the piece to focus the app, then drag it to play ``uci``.

        Args:
            uci: The move in UCI notation.
            box: The board's ``(x1, y1, x2, y2)`` screen bounding box.
            playing_white: True if the board is from white's perspective.
        """
        import time

        import pyautogui

        (from_x, from_y), (to_x, to_y) = move_pixels(uci, box, playing_white)
        pyautogui.moveTo(from_x, from_y)
        pyautogui.click()                     # activate the chess app window
        time.sleep(self.focus_pause)
        pyautogui.mouseDown(button="left")    # second press: start the drag
        pyautogui.moveTo(to_x, to_y, duration=self.duration)
        pyautogui.mouseUp(button="left")

    def point_to(self, x, y):
        """Move the pointer to ``(x, y)`` without clicking.

        Args:
            x: Absolute screen x coordinate.
            y: Absolute screen y coordinate.
        """
        import pyautogui

        pyautogui.moveTo(x, y)
