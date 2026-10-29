"""The ``MirrorGame`` controller."""

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
    """Mirror mode: the user enters the opponent's moves, the engine answers.

    The real game happens in a chess app on screen; nothing is detected from
    it. Instead the user mimics each opponent move on a mirror board (the
    ``MirrorView``), and this controller plays the program's reply in two
    places at once: on the mirror board, and in the real app by dragging the
    mouse there (via the ``MoveActuator``, over the app's bounding box).

    The user's side in the real game is ``playing_white``; the program plays
    that side, and the user enters the *other* side's moves. Which decision
    maker picks the reply is up to the injected ``MoveEngine`` (local
    Stockfish, a remote service, anything).

    Game rules (legality, castling, en passant, promotion) come from
    **python-chess**, imported lazily so this module stays importable
    dependency-free.

    Attributes:
        playing_white: True if the program (and the user, in the real app)
            plays white.
        box: The real app board's ``(x1, y1, x2, y2)`` screen bounding box.
        last_move: The most recent move in UCI, or None.
    """

    def __init__(self, playing_white, box, engine, actuator, view,
                 on_event=lambda kind, detail: None):
        """Initialise a fresh game from the starting position.

        Args:
            playing_white: True if the program's side is white.
            box: The real app board's screen bounding box for the actuator.
            engine: A ``MoveEngine`` deciding the program's replies.
            actuator: A ``MoveActuator`` playing replies in the real app.
            view: A ``MirrorView`` to draw the board on; it reports the
                user's picks back through ``submit_opponent_move``.
            on_event: Optional ``(kind, detail)`` callback for logging.
        """
        import chess

        self.playing_white = playing_white
        self.box = box
        self.last_move = None
        self._engine = engine
        self._actuator = actuator
        self._view = view
        self._on_event = on_event
        self._game = chess.Board()

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

    def _opponent_name(self):
        """The opponent's colour, for status messages."""
        return "black" if self.playing_white else "white"

    def _refresh(self, status):
        """Redraw the view with the current position.

        Args:
            status: The status message to show.
        """
        self._view.update(self.board_map(), self.last_move, status)

    def start(self):
        """Show the opening position and, if it is the program's turn, move.

        When the program plays white it moves first; otherwise the view
        waits for the user to enter white's opening move.
        """
        if self._program_to_move():
            self._refresh("Thinking...")
            self._play_reply()
        else:
            self._refresh(f"Enter the opponent's move ({self._opponent_name()}).")

    def submit_opponent_move(self, from_name, to_name):
        """Enter the opponent's move, then answer with the engine's reply.

        A pawn reaching the last rank promotes to a queen. An illegal move,
        or a move entered when it is not the opponent's turn, is rejected
        with a status message and the position is left unchanged.

        Args:
            from_name: The origin square in algebraic notation, e.g. ``"e7"``.
            to_name: The destination square, e.g. ``"e5"``.

        Returns:
            The program's reply in UCI if one was played, else None.
        """
        import chess

        if self._program_to_move():
            self._refresh("It is the program's turn; wait for its move.")
            return None
        move = chess.Move.from_uci(from_name + to_name)
        if move not in self._game.legal_moves:
            promotion = chess.Move.from_uci(from_name + to_name + "q")
            if promotion in self._game.legal_moves:
                move = promotion
            else:
                self._refresh(f"{from_name}{to_name} is not a legal move "
                              f"for {self._opponent_name()}.")
                return None

        self._game.push(move)
        self.last_move = move.uci()
        self._on_event("opponent", move.uci())
        if self._game.is_game_over():
            self._refresh(f"Game over: {self._game.result()}")
            return None
        self._refresh("Thinking...")
        return self._play_reply()

    def _play_reply(self):
        """Ask the engine for the program's move and play it in both places.

        Returns:
            The UCI move played, or None if the engine offered none or failed.
        """
        import chess

        try:
            uci = self._engine.best_move(self._game.fen())
        except Exception as exc:  # engine problems must not kill the GUI
            self._on_event("engine", f"failed: {exc}")
            self._refresh(f"Engine error: {exc}")
            return None
        if not uci:
            self._refresh("The engine has no move (game over?).")
            return None

        move = chess.Move.from_uci(uci)
        if move not in self._game.legal_moves:
            self._on_event("engine", f"illegal reply {uci}")
            self._refresh(f"Engine proposed an illegal move: {uci}")
            return None

        self._game.push(move)
        self.last_move = uci
        self._on_event("program", uci)
        try:
            self._actuator.apply(uci, self.box, self.playing_white)
        except Exception as exc:  # mouse failures must not desync the board
            self._on_event("actuator", f"failed: {exc}")
            self._refresh(f"Played {uci} here, but could not move the mouse: "
                          f"{exc}")
            return uci

        if self._game.is_game_over():
            self._refresh(f"Played {uci}. Game over: {self._game.result()}")
        else:
            self._refresh(f"Played {uci}. Enter the opponent's move "
                          f"({self._opponent_name()}).")
        return uci
