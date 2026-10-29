"""The ``MirrorGame`` controller."""

import time

from chesscheat import board


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
      program's reply. The engine thinks immediately; the reply is held back
      until the delay has elapsed, without blocking the view (``schedule``),
      and is cancelled if the position changes or auto is paused meanwhile.
    - strength -- forwarded to ``engine.set_strength`` for the next reply.

    ``undo`` takes back the last opponent move together with whatever was
    played after it (the engine's reply or a manual move), for correcting a
    mis-entered move; only the mirror board is reverted.

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
        delay: Minimum seconds from the opponent's move to the reply.
        elo: The strength last requested from the engine, or None.
    """

    def __init__(self, playing_white, box, engine, actuator, view,
                 on_event=lambda kind, detail: None, auto=True, delay=0.0,
                 clock=time.time, schedule=None):
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
            delay: Initial minimum reply delay in seconds.
            clock: Time source (seconds), injectable for testing.
            schedule: ``schedule(seconds, fn)`` deferring ``fn`` without
                blocking (e.g. Tk's ``after``). None runs ``fn`` at once,
                which makes the delay a blocking no-op -- fine for tests,
                not for a GUI.
        """
        import chess

        self.playing_white = playing_white
        self.box = box
        self.last_move = None
        self.auto = auto
        self.delay = max(0.0, float(delay))
        self.elo = None
        self._engine = engine
        self._actuator = actuator
        self._view = view
        self._on_event = on_event
        self._clock = clock
        self._schedule = schedule or (lambda seconds, fn: fn())
        self._game = chess.Board()
        self._opponent_time = clock()
        # Bumped whenever the opponent's move history changes (a new opponent
        # move, an undo) so a reply scheduled for an earlier state can never
        # land -- even if the user re-enters the very same move.
        self._epoch = 0

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
        """Set the minimum delay before the program replies.

        Applies to the next reply; a pending reply that has not fired yet is
        held until the new delay has elapsed too.

        Args:
            seconds: Minimum seconds between the opponent's move and the
                program's reply (negative values count as zero).
        """
        self.delay = max(0.0, float(seconds))
        self._on_event("delay", f"{self.delay:g}s")

    def set_strength(self, elo):
        """Change the engine's playing strength for subsequent replies.

        Args:
            elo: Target Elo rating, or None for full strength.
        """
        self.elo = elo
        self._engine.set_strength(elo)
        self._on_event("strength", "full" if elo is None else f"{elo} Elo")

    # -- play --------------------------------------------------------------

    def start(self):
        """Show the opening position and, if it is the program's turn, move.

        When the program plays white (and auto-play is on) it moves first;
        otherwise the view waits for the user.
        """
        self._opponent_time = self._clock()
        if self.auto and self._program_to_move():
            self._reply()
        else:
            self._refresh(self._turn_status())

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
        self._epoch += 1
        self._on_event("opponent", move.uci())
        if self.auto and not self._game.is_game_over():
            return self._reply()
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
        self._refresh(f"Undid {' and '.join(undone)} on this board (the real "
                      f"app is not changed). {self._turn_status()}")
        return undone

    def _reply(self):
        """Ask the engine for the program's move and play it after the delay.

        The engine thinks immediately; the move is committed once ``delay``
        seconds have passed since the opponent moved, via ``schedule`` so the
        view stays responsive. A deferred commit is dropped if the position
        changed or auto-play was paused in the meantime.

        Returns:
            The UCI move if it was played immediately, else None.
        """
        import chess

        self._refresh("Thinking...")
        try:
            uci = self._engine.best_move(self._game.fen())
        except Exception as exc:  # engine problems must not kill the GUI
            self._on_event("engine", f"failed: {exc}")
            self._refresh(f"Engine error: {exc}")
            return None
        if not uci:
            self._refresh("The engine has no move (game over?).")
            return None
        if chess.Move.from_uci(uci) not in self._game.legal_moves:
            self._on_event("engine", f"illegal reply {uci}")
            self._refresh(f"Engine proposed an illegal move: {uci}")
            return None

        return self._commit_after_delay(uci, self._game.fen(), self._epoch)

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
        remaining = self.delay - (self._clock() - self._opponent_time)
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
            return uci
        self._refresh(f"Played {uci}. {self._turn_status()}")
        return uci
