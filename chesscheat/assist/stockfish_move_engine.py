"""The ``StockfishMoveEngine`` move engine."""

import atexit
import os
import shutil

from chesscheat.interfaces import MoveEngine


def limit_strength_options(elo, lowest, highest):
    """Build the UCI options that make Stockfish play at a rating.

    Pure: clamps ``elo`` to the range the engine supports and returns the
    option map to send it, or the map that restores full strength.

    Args:
        elo: Target Elo rating, or None for full strength.
        lowest: The engine's minimum supported ``UCI_Elo``.
        highest: The engine's maximum supported ``UCI_Elo``.

    Returns:
        A dict of UCI option names to values: ``UCI_LimitStrength`` plus the
        clamped ``UCI_Elo``, or ``{"UCI_LimitStrength": False}`` when
        ``elo`` is None (so a process that was limited earlier is restored).
    """
    if elo is None:
        return {"UCI_LimitStrength": False}
    return {"UCI_LimitStrength": True,
            "UCI_Elo": max(lowest, min(highest, int(elo)))}


class StockfishMoveEngine(MoveEngine):
    """A ``MoveEngine`` backed by a UCI engine binary (Stockfish by default).

    Talks to the engine via python-chess's UCI client. The binary is located
    at construction from, in order: an explicit ``path``, the
    ``STOCKFISH_PATH`` environment variable, or ``stockfish`` on ``PATH``.
    **One engine process is kept alive** across calls (opened on first use,
    closed by ``close`` or at interpreter exit): starting Stockfish costs
    tens of milliseconds plus loading its network, which would otherwise be
    paid on every move and every evaluation. The strength setting is sent
    with every search as per-call options, and every analysis asks for full
    strength, so the shared process never carries stale state between the
    two. If the process dies the next call reopens it. python-chess's
    ``SimpleEngine`` serialises commands from several threads, so a search
    on a worker thread and an evaluation elsewhere simply queue.

    Attributes:
        path: Absolute path to the engine binary.
        think_time: Seconds the engine is allowed to search per move.
        eval_time: Seconds the engine analyses a position for ``evaluate``.
        elo: Target rating from ``set_strength``, or None for full strength.
    """

    def __init__(self, path=None, think_time=0.3, eval_time=0.1):
        """Locate the engine binary.

        Args:
            path: Explicit path to a UCI engine binary (a string, or a
                command list such as ``["python3", "engine.py"]``); if None,
                falls back to ``STOCKFISH_PATH`` then
                ``shutil.which("stockfish")``.
            think_time: Seconds to let the engine search per move.
            eval_time: Seconds to analyse a position for ``evaluate``; kept
                short since it runs after every move.

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
        self.eval_time = eval_time
        self.elo = None
        self._process = None
        self._exit_hook = False

    def set_think_time(self, seconds):
        """Change the search time for subsequent ``best_move`` calls.

        Args:
            seconds: Search time in seconds (anything below 0.01 counts as
                0.01 so the engine always gets a real search).
        """
        self.think_time = max(0.01, float(seconds))

    def set_strength(self, elo):
        """Play at about ``elo`` (Stockfish's ``UCI_LimitStrength`` mode).

        Args:
            elo: Target Elo rating, clamped to the engine's supported range
                on use, or None to restore full strength.
        """
        self.elo = elo

    @property
    def running(self):
        """True while an engine process is open."""
        return self._process is not None

    def _engine(self):
        """Return the live engine process, opening it on first use.

        Returns:
            A ``chess.engine.SimpleEngine``.
        """
        import chess.engine

        if self._process is None:
            self._process = chess.engine.SimpleEngine.popen_uci(self.path)
            if not self._exit_hook:
                atexit.register(self.close)
                self._exit_hook = True
        return self._process

    def close(self):
        """Quit the engine process, if one is open (safe to call twice)."""
        process, self._process = self._process, None
        if process is not None:
            try:
                process.quit()
            except Exception:   # already gone: nothing to tidy
                pass

    def _run(self, action):
        """Run ``action(engine)``; drop a dead process so the next call
        reopens it.

        Args:
            action: Callable taking the ``SimpleEngine``.

        Returns:
            Whatever ``action`` returns.

        Raises:
            chess.engine.EngineError: If the engine misbehaves or has died
                (after the process has been discarded).
        """
        import chess.engine

        try:
            return action(self._engine())
        except chess.engine.EngineError:
            self.close()
            raise

    def _strength_options(self, engine):
        """The per-search options for the current strength setting.

        Args:
            engine: The live ``SimpleEngine`` (to read its ``UCI_Elo`` range).

        Returns:
            The options map, or ``{}`` if the engine cannot limit strength.
        """
        elo_option = engine.options.get("UCI_Elo")
        if elo_option is None:
            return {}
        return limit_strength_options(self.elo, elo_option.min,
                                      elo_option.max)

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

        def play(engine):
            return engine.play(position,
                               chess.engine.Limit(time=self.think_time),
                               options=self._strength_options(engine))

        result = self._run(play)
        return result.move.uci() if result.move else None

    def evaluate(self, fen):
        """Analyse ``fen`` briefly at full strength and return its score.

        The strength limit from ``set_strength`` is deliberately not
        applied: the bar should show the true evaluation even when the
        engine plays weakened moves.

        Args:
            fen: A full FEN string including the side to move.

        Returns:
            ``{"cp": n}`` or ``{"mate": n}`` from white's perspective, or
            None for a finished or invalid position.
        """
        import chess
        import chess.engine

        position = chess.Board(fen)
        if not position.is_valid() or position.is_game_over():
            return None

        def analyse(engine):
            full = ({"UCI_LimitStrength": False}
                    if "UCI_LimitStrength" in engine.options else {})
            return engine.analyse(position,
                                  chess.engine.Limit(time=self.eval_time),
                                  options=full)

        score = self._run(analyse).get("score")
        if score is None:
            return None
        white = score.white()
        return ({"mate": white.mate()} if white.is_mate()
                else {"cp": white.score()})
