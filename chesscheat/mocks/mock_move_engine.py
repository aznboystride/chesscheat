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
        think_times: Values passed to ``set_think_time``, in order.
        styles: ``(style, margin)`` pairs passed to ``set_style``, in order.
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
        self.think_times = []
        self.styles = []

    def set_style(self, style, margin=None):
        """Record a style request.

        Args:
            style: The style name; appended with ``margin`` to ``styles``.
            margin: The margin in pawns, or None.
        """
        self.styles.append((style, margin))

    def set_think_time(self, seconds):
        """Record a search-time request.

        Args:
            seconds: The requested search time; appended to ``think_times``.
        """
        self.think_times.append(seconds)

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
