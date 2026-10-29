"""The ``MockMoveEngine`` move engine."""

from chesscheat.interfaces import MoveEngine


class MockMoveEngine(MoveEngine):
    """Returns a canned move and records how it was used.

    Attributes:
        move: The UCI move (or None) returned by every ``best_move`` call.
        seen_fens: FENs passed to ``best_move``, in order.
        strengths: Values passed to ``set_strength``, in order.
    """

    def __init__(self, move="e2e4"):
        """Initialise the mock.

        Args:
            move: The UCI move ``best_move`` should return, or None.
        """
        self.move = move
        self.seen_fens = []
        self.strengths = []

    def best_move(self, fen):
        """Record ``fen`` and return the canned move.

        Args:
            fen: The position FEN; appended to ``seen_fens``.

        Returns:
            The configured ``move``.
        """
        self.seen_fens.append(fen)
        return self.move

    def set_strength(self, elo):
        """Record a strength request.

        Args:
            elo: The requested rating (or None); appended to ``strengths``.
        """
        self.strengths.append(elo)
