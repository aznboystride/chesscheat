"""The ``MoveEngine`` interface."""

from abc import ABC, abstractmethod


class MoveEngine(ABC):
    """Computes a best move for a position given as a FEN."""

    @abstractmethod
    def best_move(self, fen):
        """Return the engine's best move for a position.

        Args:
            fen: A full FEN string describing the position, including the
                side to move (e.g. ``"rnbq.../... w KQkq - 0 1"``).

        Returns:
            The best move in UCI notation (e.g. ``"e2e4"`` or ``"e7e8q"``),
            or None if there is no move to make (game over or invalid
            position).
        """
