"""The ``MockMirrorView`` mirror view."""

from chesscheat.interfaces import MirrorView


class MockMirrorView(MirrorView):
    """Records every redraw instead of drawing anything.

    Attributes:
        updates: A list of ``(board_map, last_move, status)`` tuples, one per
            ``update`` call, in order.
        ran: True once ``run`` has been called.
    """

    def __init__(self):
        """Initialise the mock with an empty record."""
        self.updates = []
        self.ran = False

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
