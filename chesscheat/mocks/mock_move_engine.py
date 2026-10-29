"""The ``MockMoveEngine`` move engine."""

from chesscheat.interfaces import MoveEngine


class MockMoveEngine(MoveEngine):
    """Returns a canned move and records how it was used.

    Attributes:
        move: The UCI move (or None) returned by every ``best_move`` call.
        score: The score dict (or None) returned by every ``evaluate`` call.
        seen_fens: FENs passed to ``best_move``, in order.
        evaluated: FENs passed to ``evaluate``, in order.
        strengths: Values passed to ``set_strength``, in order.
    """

    def __init__(self, move="e2e4"):
        """Initialise the mock.

        Args:
            move: The UCI move ``best_move`` should return, or None.
        """
        self.move = move
        self.score = None
        self.seen_fens = []
        self.evaluated = []
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

    def evaluate(self, fen):
        """Record ``fen`` and return the canned score.

        Args:
            fen: The position FEN; appended to ``evaluated``.

        Returns:
            The configured ``score``.
        """
        self.evaluated.append(fen)
        return self.score

    def set_strength(self, elo):
        """Record a strength request.

        Args:
            elo: The requested rating (or None); appended to ``strengths``.
        """
        self.strengths.append(elo)
