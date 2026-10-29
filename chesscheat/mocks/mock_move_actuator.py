"""The ``MockMoveActuator`` move actuator."""

from chesscheat.interfaces import MoveActuator


class MockMoveActuator(MoveActuator):
    """Records the moves it was asked to play instead of driving the mouse.

    Attributes:
        applied: A list of ``(uci, box, playing_white)`` tuples, one per
            ``apply`` call, in order.
        pointed: A list of ``(x, y)`` positions passed to ``point_to``.
    """

    def __init__(self):
        """Initialise the mock with an empty record."""
        self.applied = []
        self.pointed = []

    def apply(self, uci, box, playing_white):
        """Record the requested move without any side effect.

        Args:
            uci: The move in UCI notation.
            box: The board's bounding box.
            playing_white: The board orientation.
        """
        self.applied.append((uci, box, playing_white))

    def point_to(self, x, y):
        """Record a pointer move.

        Args:
            x: Screen x coordinate.
            y: Screen y coordinate.
        """
        self.pointed.append((x, y))
