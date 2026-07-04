"""The ``MockMoveActuator`` move actuator."""

from chesscheat.interfaces import MoveActuator


class MockMoveActuator(MoveActuator):
    """Records the moves it was asked to play instead of driving the mouse.

    Attributes:
        applied: A list of ``(uci, box, playing_white)`` tuples, one per
            ``apply`` call, in order.
    """

    def __init__(self):
        """Initialise the mock with an empty record."""
        self.applied = []

    def apply(self, uci, box, playing_white):
        """Record the requested move without any side effect.

        Args:
            uci: The move in UCI notation.
            box: The board's bounding box.
            playing_white: The board orientation.
        """
        self.applied.append((uci, box, playing_white))
