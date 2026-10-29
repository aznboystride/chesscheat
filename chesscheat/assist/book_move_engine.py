"""The ``BookMoveEngine`` move engine decorator."""

import random

from chesscheat.interfaces import MoveEngine


class BookMoveEngine(MoveEngine):
    """Plays from a Polyglot opening book, then hands over to another engine.

    While the position is in the book, a book move is played: chosen at
    random in proportion to the book's weights, or -- with the
    ``"unusual"`` style -- the *least* weighted line, for offbeat openings.
    Out of book, every call goes to the wrapped engine. Settings
    (``set_strength``, ``set_think_time``, ``set_style``) and ``evaluate``
    are forwarded. The book is opened lazily (``chess.polyglot``).

    Attributes:
        path: The ``.bin`` Polyglot book.
        style: The current style (``set_style``).
    """

    def __init__(self, inner, path, rng=None):
        """Wrap an engine with a book.

        Args:
            inner: The ``MoveEngine`` to use out of book.
            path: Path to a Polyglot ``.bin`` book.
            rng: Optional ``random.Random`` for the weighted choice
                (injectable for tests).
        """
        self._inner = inner
        self.path = path
        self.style = "best"
        self._rng = rng or random.Random()
        self._reader = None

    def _book(self):
        """Return the opened book reader (opened on first use)."""
        import chess.polyglot

        if self._reader is None:
            self._reader = chess.polyglot.open_reader(self.path)
        return self._reader

    def best_move(self, fen):
        """Return a book move for ``fen`` if there is one, else the engine's.

        Args:
            fen: A full FEN string including the side to move.

        Returns:
            The move in UCI notation, or None (from the engine) if there is
            no move to make.
        """
        import chess

        board = chess.Board(fen)
        entries = list(self._book().find_all(board))
        if not entries:
            return self._inner.best_move(fen)
        if self.style == "unusual":
            return min(entries, key=lambda e: e.weight).move.uci()
        return self._book().weighted_choice(board, random=self._rng).move.uci()

    def set_style(self, style, margin=None):
        """Record the style (for the book choice) and forward it.

        Args:
            style: One of ``chesscheat.assist.style.STYLES``.
            margin: Pawns below the best line the engine may stray; passed on.
        """
        self.style = style
        self._inner.set_style(style, margin)

    def set_strength(self, elo):
        """Forward to the wrapped engine."""
        self._inner.set_strength(elo)

    def set_think_time(self, seconds):
        """Forward to the wrapped engine."""
        self._inner.set_think_time(seconds)

    def evaluate(self, fen):
        """Forward to the wrapped engine."""
        return self._inner.evaluate(fen)

    def close(self):
        """Close the book and the wrapped engine, if it can be closed."""
        reader, self._reader = self._reader, None
        if reader is not None:
            reader.close()
        close = getattr(self._inner, "close", None)
        if close:
            close()
