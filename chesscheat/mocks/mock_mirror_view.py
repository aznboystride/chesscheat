"""The ``MockMirrorView`` mirror view."""

from chesscheat.interfaces import MirrorView


class MockMirrorView(MirrorView):
    """Records every redraw instead of drawing anything.

    Attributes:
        updates: A list of ``(board_map, last_move, status)`` tuples, one per
            ``update`` call, in order.
        ran: True once ``run`` has been called.
        positions: A ``{square_name: (x, y)}`` map ``square_position``
            answers from; empty by default (no positions known).
        evaluations: ``(white_share, label)`` pairs from
            ``update_evaluation``, in order.
        orientations: ``bottom_white`` values from ``set_orientation``.
    """

    def __init__(self, positions=None):
        """Initialise the mock with an empty record.

        Args:
            positions: Optional ``{square_name: (x, y)}`` screen positions
                to report from ``square_position``.
        """
        self.updates = []
        self.ran = False
        self.positions = dict(positions or {})
        self.evaluations = []
        self.orientations = []

    def update_evaluation(self, white_share, label):
        """Record an evaluation display request."""
        self.evaluations.append((white_share, label))

    def set_orientation(self, bottom_white):
        """Record an orientation change."""
        self.orientations.append(bottom_white)

    def square_position(self, name):
        """Return the configured position for ``name``, or None.

        Args:
            name: A square in algebraic notation.

        Returns:
            The ``(x, y)`` from ``positions``, or None if unknown.
        """
        return self.positions.get(name)

    def update(self, board_map, last_move, status):
        """Record a redraw request.

        Args:
            board_map: The position to show.
            last_move: The move to highlight, or None.
            status: The status message.
        """
        self.updates.append((board_map, last_move, status))

    def run(self):
        """Record that the view was shown; returns immediately."""
        self.ran = True
