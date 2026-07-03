"""The ``MoveActuator`` interface."""

from abc import ABC, abstractmethod


class MoveActuator(ABC):
    """Plays a move on the physical board by driving the mouse."""

    @abstractmethod
    def apply(self, uci, box, playing_white):
        """Perform a move by dragging from its origin square to its target.

        Args:
            uci: The move in UCI notation (e.g. ``"e2e4"``); only the origin
                and destination squares (the first four characters) are used
                for the drag, any promotion suffix is ignored.
            box: The board's ``(x1, y1, x2, y2)`` bounding box in absolute
                screen coordinates, used to locate each square's centre.
            playing_white: True if the board is oriented from white's
                perspective, which determines where each square sits.
        """
