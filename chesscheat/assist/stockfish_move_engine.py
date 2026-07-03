"""The ``StockfishMoveEngine`` move engine."""

import os
import shutil

from chesscheat.interfaces import MoveEngine


class StockfishMoveEngine(MoveEngine):
    """A ``MoveEngine`` backed by a UCI engine binary (Stockfish by default).

    Talks to the engine via python-chess's UCI client. The binary is located
    at construction from, in order: an explicit ``path``, the
    ``STOCKFISH_PATH`` environment variable, or ``stockfish`` on ``PATH``. A
    fresh engine process is opened and closed per query, which keeps the
    class stateless and avoids leaking a background process.

    Attributes:
        path: Absolute path to the engine binary.
        think_time: Seconds the engine is allowed to search per move.
    """

    def __init__(self, path=None, think_time=0.5):
        """Locate the engine binary.

        Args:
            path: Explicit path to a UCI engine binary; if None, falls back
                to ``STOCKFISH_PATH`` then ``shutil.which("stockfish")``.
            think_time: Seconds to let the engine search per move.

        Raises:
            FileNotFoundError: If no engine binary can be located.
        """
        self.path = (path or os.environ.get("STOCKFISH_PATH")
                     or shutil.which("stockfish"))
        if not self.path:
            raise FileNotFoundError(
                "No Stockfish binary found. Install Stockfish and put it on "
                "PATH, or set STOCKFISH_PATH to its location.")
        self.think_time = think_time

    def best_move(self, fen):
        """Return Stockfish's best move for ``fen`` in UCI notation.

        Args:
            fen: A full FEN string including the side to move.

        Returns:
            The best move in UCI notation, or None if the position is over
            or not a valid, playable position.
        """
        import chess
        import chess.engine

        position = chess.Board(fen)
        if not position.is_valid() or position.is_game_over():
            return None
        with chess.engine.SimpleEngine.popen_uci(self.path) as engine:
            result = engine.play(position,
                                 chess.engine.Limit(time=self.think_time))
        return result.move.uci() if result.move else None
