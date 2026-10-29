"""The ``MirrorGame`` controller."""

import random
import time

from chesscheat import board
from chesscheat.mirror.evaluation import score_label, white_share


def _describe(error):
    """Name an exception for a status line, even one with no message.

    Args:
        error: The exception.

    Returns:
        Its message, or its type name when the message is empty (a
        cancelled future, for instance, says nothing by itself).
    """
    return str(error) or type(error).__name__


def _run_now(fn, done):
    """The default worker: run ``fn`` here and report to ``done`` at once.

    Args:
        fn: No-argument callable to run.
        done: ``done(result, error)`` callback; ``error`` is the exception
            ``fn`` raised, else None.
    """
    try:
        result = fn()
    except Exception as exc:
        done(None, exc)
        return
    done(result, None)


def position_map(game):
    """Convert a python-chess board to the project's board-map form.

    Args:
        game: A ``chess.Board``.

    Returns:
        A ``{(file_idx, rank): label}`` map of all 64 squares, ``'.'`` for
        empty, piece letters otherwise (uppercase white, lowercase black).
    """
    import chess

    def label(file_idx, rank):
        piece = game.piece_at(chess.square(file_idx, rank - 1))
        return piece.symbol() if piece else "."

    return {(f, r): label(f, r) for f in range(8) for r in range(1, 9)}


class MirrorGame:
    """Mirror mode: the user enters the opponent's moves, the program answers.

    The real game happens in a chess app on screen; nothing is detected from
    it. Instead the user mimics each opponent move on a mirror board (the
    ``MirrorView``), and this controller plays the program's side's move in
    two places at once: on the mirror board, and in the real app by dragging
    the mouse there (via the ``MoveActuator``, over the app's bounding box).

    The user's side in the real game is ``playing_white``; the program plays
    that side, and the user enters the *other* side's moves. Three settings
    can be changed at any time:

    - ``auto`` -- when on, the engine chooses and plays the program's moves;
      when off, the user plays the program's side manually on the mirror
      board, and those moves are still played in the real app. Turning it on
      mid-turn makes the program reply at once.
    - ``delay`` -- the minimum seconds between the opponent's move and the
      program's reply, drawn afresh for every reply from ``delay_range``
      (a fixed value when the range's ends are equal, otherwise uniform
      random jitter within it). The engine thinks immediately; the reply is
      held back until the delay has elapsed, without blocking the view
      (``schedule``), and is cancelled if the position changes or auto is
      paused meanwhile.
    - strength -- forwarded to ``engine.set_strength`` for the next reply.
    - ``think_time`` -- the engine's search budget per reply, and
      ``think_in_delay``: when on, a reply that will wait anyway thinks for
      as long as it would wait (capped by ``max_think``), so the delay is
      spent searching rather than idling and the move is still ready on
      time.

    The engine is consulted through an injectable ``worker(fn, done)`` so a
    GUI can run the search on a background thread and keep its window
    responsive (``done(result, error)`` must be called back on the GUI
    thread); the default runs it synchronously. A result arriving after the
    position has changed (undo, new game, another opponent move) is dropped.

    After the program's move has been played in the real app, the mouse
    pointer is returned to the mirror board, onto the square the opponent's
    last move ended on (where the user last clicked), if the view can say
    where that is on screen.

    ``undo`` takes back the last opponent move together with whatever was
    played after it (the engine's reply or a manual move), for correcting a
    mis-entered move; only the mirror board is reverted. ``new_game`` starts
    over as either colour on the same real board (the box is kept).

    After every change of position the engine's ``evaluate`` is consulted
    and the result handed to ``view.update_evaluation`` as a bar share and
    a label (``chesscheat.mirror.evaluation``); a finished game shows its
    result instead.

    Which decision maker picks the reply is up to the injected
    ``MoveEngine`` (local Stockfish, a remote service, anything). Game rules
    come from **python-chess**, imported lazily so this module stays
    importable dependency-free.

    Attributes:
        playing_white: True if the program (and the user, in the real app)
            plays white.
        box: The real app board's ``(x1, y1, x2, y2)`` screen bounding box.
        last_move: The most recent move in UCI, or None.
        auto: Whether the engine plays the program's side automatically.
        delay_range: ``(min, max)`` seconds the per-reply delay is drawn from.
        delay: The delay in force for the current/next reply (read-only).
        elo: The strength last requested from the engine, or None.
        style: The playing style last requested from the engine.
        think_time: Base engine search time per reply, in seconds.
        think_in_delay: Whether a waiting reply may think for the wait.
        max_think: Cap on the search time when thinking in the delay.
        think_margin: Seconds of the delay kept free of searching, so the
            move is ready (engine start-up, actuation) when the delay ends.
    """

    def __init__(self, playing_white, box, engine, actuator, view,
                 on_event=lambda kind, detail: None, auto=True, delay=0.0,
                 clock=time.time, schedule=None, rng=random.uniform,
                 think_time=0.3, think_in_delay=True, max_think=10.0,
                 think_margin=0.1, worker=None):
        """Initialise a fresh game from the starting position.

        Args:
            playing_white: True if the program's side is white.
            box: The real app board's screen bounding box for the actuator.
            engine: A ``MoveEngine`` deciding the program's replies.
            actuator: A ``MoveActuator`` playing moves in the real app.
            view: A ``MirrorView`` to draw the board on; it reports the
                user's picks back through ``submit_move``.
            on_event: Optional ``(kind, detail)`` callback for logging.
            auto: Initial automatic-play setting.
            delay: Initial reply delay: a number of seconds (fixed), or a
                ``(min, max)`` pair to jitter within.
            clock: Time source (seconds), injectable for testing.
            schedule: ``schedule(seconds, fn)`` deferring ``fn`` without
                blocking (e.g. Tk's ``after``). None runs ``fn`` at once,
                which makes the delay a blocking no-op -- fine for tests,
                not for a GUI.
            rng: ``rng(lo, hi)`` returning a float in ``[lo, hi]``, used to
                draw each reply's delay; defaults to ``random.uniform``.
            think_time: Base engine search seconds per reply (applied to
                the engine through ``set_think_time`` before each search).
            think_in_delay: Initial setting for thinking during the delay.
            max_think: Cap on the search seconds when thinking in the delay.
            think_margin: Seconds of the delay left unused by the search.
            worker: ``worker(fn, done)`` running ``fn()`` and then calling
                ``done(result, error)`` -- on a background thread with the
                callback marshalled to the GUI thread (the view's
                ``run_in_background``), or None to run synchronously.
        """
        import chess

        self.playing_white = playing_white
        self.box = box
        self.last_move = None
        self.auto = auto
        self.elo = None
        self.style = "best"
        self._engine = engine
        self._actuator = actuator
        self._view = view
        self._on_event = on_event
        self._clock = clock
        self._schedule = schedule or (lambda seconds, fn: fn())
        self._rng = rng
        self.think_time = max(0.05, float(think_time))
        self.think_in_delay = bool(think_in_delay)
        self.max_think = float(max_think)
        self.think_margin = float(think_margin)
        self._worker = worker or _run_now
        self._thinking = None   # (fen, epoch) a search is under way for
        self._game = chess.Board()
        self._opponent_time = clock()
        self._last_opponent_to = None
        # Bumped whenever the opponent's move history changes (a new opponent
        # move, an undo) so a reply scheduled for an earlier state can never
        # land -- even if the user re-enters the very same move.
        self._epoch = 0
        lo, hi = delay if isinstance(delay, (tuple, list)) else (delay, delay)
        self.delay_range = self._clamped_range(lo, hi)
        self._current_delay = self._draw_delay()

    @staticmethod
    def _clamped_range(lo, hi):
        """Normalise a delay range: no negatives, max never below min.

        Args:
            lo: Requested minimum seconds.
            hi: Requested maximum seconds.

        Returns:
            A ``(min, max)`` pair of floats.
        """
        lo = max(0.0, float(lo))
        return lo, max(lo, float(hi))

    def _draw_delay(self):
        """Draw the delay for one reply from ``delay_range``.

        Returns:
            The range's single value when its ends coincide, else a sample
            from ``rng`` within it.
        """
        lo, hi = self.delay_range
        return lo if hi <= lo else float(self._rng(lo, hi))

    @property
    def delay(self):
        """The delay in force for the current or next reply, in seconds."""
        return self._current_delay

    # -- queries -----------------------------------------------------------

    @property
    def fen(self):
        """The current position as a full FEN string."""
        return self._game.fen()

    def board_map(self):
        """Return the current position as a ``{(file_idx, rank): label}`` map."""
        return position_map(self._game)

    def _program_to_move(self):
        """Whether it is the program's (not the opponent's) turn."""
        import chess

        return self._game.turn == (chess.WHITE if self.playing_white
                                   else chess.BLACK)

    @property
    def opponent_to_move(self):
        """True while the game is on and it is the opponent's turn."""
        return not self._game.is_game_over() and not self._program_to_move()

    def is_legal(self, from_name, to_name):
        """Whether two squares form a legal move for the side to move.

        A pawn reaching the last rank counts (as a queen promotion).

        Args:
            from_name: Origin square, e.g. ``"e7"``.
            to_name: Destination square, e.g. ``"e5"``.

        Returns:
            True if the move is legal in the current position.
        """
        return self._legal(from_name, to_name) is not None

    def _colour(self, program_side):
        """Name a side's colour for status messages.

        Args:
            program_side: True for the program's colour, False for the
                opponent's.

        Returns:
            ``"white"`` or ``"black"``.
        """
        return ("white" if self.playing_white == program_side else "black")

    def _refresh(self, status):
        """Redraw the view with the current position.

        Args:
            status: The status message to show.
        """
        self._view.update(self.board_map(), self.last_move, status)

    def _turn_status(self):
        """The idle status for whoever is to move now.

        Returns:
            A message telling the user what to enter next.
        """
        if self._game.is_game_over():
            return f"Game over: {self._game.result()}"
        if not self._program_to_move():
            return f"Enter the opponent's move ({self._colour(False)})."
        return (f"Auto-play is paused: play {self._colour(True)}'s move "
                "yourself.")

    # -- settings ----------------------------------------------------------

    def set_auto(self, enabled):
        """Turn automatic engine play on or off.

        Args:
            enabled: True to let the engine play the program's side; False
                to pause it and play that side manually.
        """
        self.auto = bool(enabled)
        self._on_event("auto", "on" if self.auto else "off")
        if self.auto and self._program_to_move():
            self._reply()
        else:
            self._refresh(self._turn_status())

    def set_delay(self, seconds):
        """Set a fixed reply delay (shorthand for a range of one value).

        Args:
            seconds: Minimum seconds between the opponent's move and the
                program's reply (negative values count as zero).
        """
        self.set_delay_range(seconds, seconds)

    def set_delay_range(self, lo, hi):
        """Set the range each reply's delay is drawn from.

        Equal ends give a fixed delay; otherwise every reply gets its own
        uniformly random delay within the range (jitter). Applies to the
        next reply and to a reply that is still waiting: its delay is drawn
        again from the new range and the wait is held until that has
        elapsed too.

        Args:
            lo: Minimum seconds (negative counts as zero).
            hi: Maximum seconds (raised to ``lo`` if below it).
        """
        self.delay_range = self._clamped_range(lo, hi)
        self._current_delay = self._draw_delay()
        lo, hi = self.delay_range
        self._on_event("delay", f"{lo:g}s" if hi <= lo
                       else f"{lo:g}s to {hi:g}s (random)")

    def set_think_time(self, seconds):
        """Set the engine's base search time per reply.

        Args:
            seconds: Search seconds (anything below 0.05 counts as 0.05).
        """
        self.think_time = max(0.05, float(seconds))
        self._on_event("think", f"{self.think_time:g}s")

    def set_think_in_delay(self, enabled):
        """Let a reply that will wait anyway spend the wait thinking.

        Args:
            enabled: True to extend the search to the reply delay (capped
                by ``max_think``); False for the fixed ``think_time``.
        """
        self.think_in_delay = bool(enabled)
        self._on_event("think", "uses the reply delay" if self.think_in_delay
                       else "fixed")

    def _think_budget(self):
        """Seconds the next search may take.

        Returns:
            ``think_time``, raised to whatever is left of the current delay
            (less ``think_margin``, at most ``max_think``) when
            ``think_in_delay`` is on.
        """
        budget = self.think_time
        if self.think_in_delay:
            elapsed = self._clock() - self._opponent_time
            available = self._current_delay - elapsed - self.think_margin
            budget = max(budget, min(self.max_think, available))
        return budget

    def set_strength(self, elo):
        """Change the engine's playing strength for subsequent replies.

        Args:
            elo: Target Elo rating, or None for full strength.
        """
        self.elo = elo
        self._engine.set_strength(elo)
        self._on_event("strength", "full" if elo is None else f"{elo} Elo")

    def set_style(self, style, margin=None):
        """Change the engine's playing style for subsequent replies.

        Args:
            style: One of ``chesscheat.assist.style.STYLES`` (``"best"`` =
                plain best move).
            margin: Pawns below its best line the engine may stray to
                express the style, or None to keep the engine's current.
        """
        self.style = style
        self._engine.set_style(style, margin)
        self._on_event("style", style if margin is None
                       else f"{style} (within {margin:g} pawns)")

    # -- play --------------------------------------------------------------

    def start(self):
        """Show the opening position and, if it is the program's turn, move.

        When the program plays white (and auto-play is on) it moves first;
        otherwise the view waits for the user.
        """
        self._opponent_time = self._clock()
        if self.auto and self._program_to_move():
            if self._reply() is None:          # not answered on the spot
                self._refresh_evaluation()
        else:
            self._refresh_evaluation()
            self._refresh(self._turn_status())

    def new_game(self, playing_white):
        """Start over from the initial position, as the given colour.

        The real board's box is kept, so only the side needs choosing. The
        view is re-oriented to the new side (the user's side at the bottom),
        any reply still waiting is cancelled, and the program opens at once
        if it plays white with auto-play on.

        Args:
            playing_white: True if the program (the user) now plays white.
        """
        import chess

        self.playing_white = playing_white
        self._game = chess.Board()
        self.last_move = None
        self._last_opponent_to = None
        self._epoch += 1
        self._on_event("new_game", f"you play {self._colour(True)}")
        self._view.set_orientation(playing_white)
        self.start()

    def _refresh_evaluation(self):
        """Score the current position and show it on the view's bar.

        The engine is asked through the ``worker``, off the critical path:
        it is dispatched only after a reply search has been started (or a
        move actuated), so the bar never delays the program's move. A score
        arriving for a position that has since changed is dropped. A
        finished game shows its result at once; an engine that cannot
        evaluate (or fails) shows a level, unlabelled bar and logs the
        failure.
        """
        if self._game.is_game_over():
            result = self._game.result()
            share = {"1-0": 1.0, "0-1": 0.0}.get(result, 0.5)
            self._view.update_evaluation(share, result)
            return
        fen = self.fen

        def done(score, error):
            if self.fen != fen:
                return
            if error is not None:
                self._on_event("engine",
                               f"evaluation failed: {_describe(error)}")
                score = None
            self._view.update_evaluation(white_share(score),
                                         score_label(score))

        self._worker(lambda: self._engine.evaluate(fen), done)

    def _legal(self, from_name, to_name):
        """Resolve two squares to a legal move, auto-queening promotions.

        Args:
            from_name: Origin square, e.g. ``"e7"``.
            to_name: Destination square, e.g. ``"e8"``.

        Returns:
            The legal ``chess.Move``, or None if no legal move matches.
        """
        import chess

        plain = chess.Move.from_uci(from_name + to_name)
        promotion = chess.Move.from_uci(from_name + to_name + "q")
        return next((m for m in (plain, promotion)
                     if m in self._game.legal_moves), None)

    def submit_move(self, from_name, to_name):
        """Enter a move from the mirror board.

        On the opponent's turn this records the opponent's move and (if
        auto-play is on) triggers the program's reply. On the program's turn
        it is accepted only while auto-play is paused, as the user playing
        the program's side by hand -- and is then played in the real app as
        well. Illegal or out-of-turn entries are rejected with a status.

        Args:
            from_name: The origin square in algebraic notation.
            to_name: The destination square in algebraic notation.

        Returns:
            The UCI of a program move played synchronously (a manual move,
            or an undelayed automatic reply), else None.
        """
        if self._program_to_move() and self.auto:
            self._refresh("It is the program's turn; wait for its move "
                          "(or pause auto-play to move yourself).")
            return None
        move = self._legal(from_name, to_name)
        if move is None:
            self._refresh(f"{from_name}{to_name} is not a legal move for "
                          f"{self._colour(self._program_to_move())}.")
            return None

        if self._program_to_move():
            return self._play_program_move(move.uci(), "manual")

        self._game.push(move)
        self.last_move = move.uci()
        self._opponent_time = self._clock()
        self._last_opponent_to = to_name
        self._current_delay = self._draw_delay()   # fresh jitter per reply
        self._epoch += 1
        self._on_event("opponent", move.uci())
        if self.auto and not self._game.is_game_over():
            played = self._reply()             # search first, then the bar
            if played is None:
                self._refresh_evaluation()
            return played
        self._refresh_evaluation()
        self._refresh(self._turn_status())
        return None

    def _has_opponent_move(self):
        """Whether the move history contains a move by the opponent.

        Returns:
            True if an undo has something to revert. The program moves first
            when it plays white, so then at least two plies are needed.
        """
        return len(self._game.move_stack) >= (2 if self.playing_white else 1)

    def undo(self):
        """Take back the last opponent move and everything played after it.

        Pops the program's reply (or the user's manual move for the program's
        side), if any, and then the opponent's move, so the board is back on
        the opponent's turn ready for the corrected entry. Any reply still
        waiting out the delay is cancelled. Only this board is reverted: the
        real app keeps whatever was already dragged there.

        Returns:
            The undone moves in UCI, most recent first; empty if there was no
            opponent move to take back.
        """
        if not self._has_opponent_move():
            self._refresh("Nothing to undo.")
            return []
        import chess

        opponent = chess.BLACK if self.playing_white else chess.WHITE
        undone = []
        while self._game.move_stack:
            undone.append(self._game.pop().uci())
            if self._game.turn == opponent:   # that ply was the opponent's
                break
        self._epoch += 1
        self.last_move = (self._game.move_stack[-1].uci()
                          if self._game.move_stack else None)
        self._on_event("undo", " ".join(undone))
        self._refresh_evaluation()
        self._refresh(f"Undid {' and '.join(undone)} on this board (the real "
                      f"app is not changed). {self._turn_status()}")
        return undone

    def _reply(self):
        """Ask the engine for the program's move and play it after the delay.

        The engine starts thinking immediately, through the ``worker`` so
        the view stays responsive, for ``_think_budget`` seconds; the move
        is committed once ``delay`` seconds have passed since the opponent
        moved, via ``schedule``. A result for a position that has since
        changed is dropped, as is a deferred commit if the position changed
        or auto-play was paused in the meantime. A second request for the
        same position while a search is under way is ignored.

        Returns:
            The UCI move if it was played immediately (synchronous worker,
            no delay left), else None.
        """
        import chess

        fen, epoch = self._game.fen(), self._epoch
        if self._thinking == (fen, epoch):
            return None
        budget = self._think_budget()
        self._thinking = (fen, epoch)
        self._refresh(f"Thinking ({budget:.1f}s)...")
        played = []

        def think():
            self._engine.set_think_time(budget)
            return self._engine.best_move(fen)

        def done(uci, error):
            if self._thinking == (fen, epoch):
                self._thinking = None
            if epoch != self._epoch or self._game.fen() != fen:
                self._on_event("engine", "stale reply dropped")
                return
            if error is not None:   # engine problems must not kill the GUI
                detail = _describe(error)
                self._on_event("engine", f"failed: {detail}")
                self._refresh(f"Engine error: {detail}")
                return
            if not uci:
                self._refresh("The engine has no move (game over?).")
                return
            if chess.Move.from_uci(uci) not in self._game.legal_moves:
                self._on_event("engine", f"illegal reply {uci}")
                self._refresh(f"Engine proposed an illegal move: {uci}")
                return
            played.append(self._commit_after_delay(uci, fen, epoch))

        self._worker(think, done)
        return played[0] if played else None

    def _commit_after_delay(self, uci, fen, epoch):
        """Play ``uci`` once the delay has elapsed, if still applicable.

        Args:
            uci: The engine's chosen move.
            fen: The position it was chosen for; the commit is dropped if
                the game has moved on.
            epoch: The opponent-history epoch it was chosen in; the commit
                is dropped if an opponent move or an undo happened since.

        Returns:
            The UCI if played now, else None (deferred or dropped).
        """
        if (not self.auto or epoch != self._epoch
                or self._game.fen() != fen):
            return None
        remaining = self._current_delay - (self._clock() - self._opponent_time)
        if remaining <= 0:
            return self._play_program_move(uci, "program")
        self._refresh(f"Waiting {remaining:.1f}s before replying...")
        self._schedule(remaining,
                       lambda: self._commit_after_delay(uci, fen, epoch))
        return None

    def _play_program_move(self, uci, source):
        """Push the program's move and play it in the real app.

        Args:
            uci: The move to play.
            source: ``"program"`` (engine) or ``"manual"`` (user), for the
                event log.

        Returns:
            The UCI played.
        """
        import chess

        self._game.push(chess.Move.from_uci(uci))
        self.last_move = uci
        self._on_event(source, uci)
        try:
            self._actuator.apply(uci, self.box, self.playing_white)
        except Exception as exc:  # mouse failures must not desync the board
            self._on_event("actuator", f"failed: {exc}")
            self._refresh(f"Played {uci} here, but could not move the mouse: "
                          f"{exc}")
            self._refresh_evaluation()
            return uci
        self._return_pointer()
        self._refresh(f"Played {uci}. {self._turn_status()}")
        self._refresh_evaluation()             # after the drag, not before
        return uci

    def _return_pointer(self):
        """Park the mouse on the mirror board after a move in the real app.

        Targets the square the opponent's last move ended on -- where the
        user last clicked -- so their hand is back where the next entry
        starts. Silently skipped when there is no opponent move yet or the
        view cannot locate the square on screen; pointer errors are logged.
        """
        if self._last_opponent_to is None:
            return
        position = self._view.square_position(self._last_opponent_to)
        if position is None:
            return
        try:
            self._actuator.point_to(*position)
        except Exception as exc:
            self._on_event("actuator", f"pointer return failed: {exc}")
