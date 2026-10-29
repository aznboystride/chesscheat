"""The ``MoveEngine`` interface."""

from abc import ABC, abstractmethod


class MoveEngine(ABC):
    """Computes a best move for a position given as a FEN.

    The decision maker behind the program's moves. Implementations may run
    anything anywhere -- a local engine binary, a remote service, a lookup
    table. ``set_strength`` is optional to honour: the base implementation
    is a no-op, so engines that cannot vary their strength simply play as
    they are.
    """

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

    def set_style(self, style, margin=None):
        """Ask the engine to play with a character, not just its best move.

        Optional: the default ignores it. See
        ``chesscheat.assist.style.STYLES`` for the names (``"best"`` means
        no style).

        Args:
            style: The style name.
            margin: How far below its best line, in pawns, the engine may
                stray to express the style; None keeps the engine's
                default.
        """
        return None

    def set_think_time(self, seconds):
        """Set how long the engine may search for the next ``best_move``.

        Optional: the default ignores it (engines with a fixed or external
        time budget). Takes effect for subsequent calls, so a controller may
        vary it per move -- e.g. to think for as long as it would otherwise
        wait before replying.

        Args:
            seconds: Search time budget in seconds.
        """
        return None

    def evaluate(self, fen):
        """Score a position, for an evaluation display.

        Optional: the default knows nothing and returns None, which a view
        shows as an unknown (level) evaluation.

        Args:
            fen: A full FEN string including the side to move.

        Returns:
            ``{"cp": n}`` (centipawns) or ``{"mate": n}`` (moves to mate,
            negative when black mates), both from **white's** perspective,
            or None if the position cannot be scored.
        """
        return None

    def set_strength(self, elo):
        """Ask the engine to play at roughly a given rating.

        Takes effect for subsequent ``best_move`` calls, so it may be
        changed at any time. The default ignores the request.

        Args:
            elo: Target playing strength as an Elo rating, or None for the
                engine's full strength.
        """
        return None
