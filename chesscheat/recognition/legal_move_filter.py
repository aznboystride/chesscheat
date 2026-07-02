"""The ``LegalMoveFilter`` board-recognizer decorator."""

from chesscheat import board
from chesscheat.interfaces import BoardRecognizer


class LegalMoveFilter(BoardRecognizer):
    """Wraps a ``BoardRecognizer``; accepts new readings only on legal moves.

    On each call to ``read``:

    1. The inner recognizer classifies all 64 squares from the raw image.
    2. If the reading is identical to the current state, return it immediately.
    3. Otherwise check whether the piece-placement FEN of the candidate matches
       the result of pushing any one legal move from the current position.
    4. On a match, advance the internal game clock and accept the new board.
       If no legal move explains the diff — the frame was corrupted by a mouse
       cursor, a highlight, a drag animation, or any other transient artifact —
       discard the frame and return the last accepted state unchanged.

    This makes the reader resilient to transient visual noise: a corrupted
    frame is silently ignored and the position does not change.

    The legality check uses *python-chess* (``chess`` package), which is
    imported lazily so the rest of the package remains dependency-free when
    the filter is not in use.

    Attributes:
        inner: The wrapped ``BoardRecognizer``.
        on_event: Optional ``(kind, detail)`` callback reporting filter
            decisions.
    """

    def __init__(self, inner, on_event=None):
        """Initialise the filter around an inner recognizer.

        Args:
            inner: A ``BoardRecognizer`` whose raw output this class filters.
            on_event: Optional callable invoked as ``on_event(kind, detail)``
                when the filter makes a decision worth surfacing: ``("move",
                san)`` when a reading is accepted as a legal move, and
                ``("dropped", reason)`` when a changed reading matches no
                legal move and is discarded. Unchanged frames report nothing.
        """
        self.inner = inner
        self.on_event = on_event
        self._state = None        # last accepted {(file_idx, rank): label}
        self._chess_board = None  # python-chess Board for legality checks

    def calibrate(self, image, playing_white):
        """Calibrate the inner recognizer and reset game state to start.

        Delegates template learning to the inner recognizer and initialises
        a *python-chess* ``Board`` at the standard starting position.

        Args:
            image: A board image showing the standard starting position.
            playing_white: True if white is at the bottom of the image.
        """
        import chess  # lazy: only required when the filter is actually used
        self.inner.calibrate(image, playing_white)
        self._state = board.starting_board()
        self._chess_board = chess.Board()

    def read(self, image):
        """Read the board, accepting only a reading that is a legal move away.

        Args:
            image: A board image to recognise.

        Returns:
            The last accepted ``{(file_idx, rank): label}`` board map.
            Returns the previous state unchanged when the inner reading does
            not correspond to a legal chess move from the current position.
        """
        report = self.on_event or (lambda kind, detail: None)
        candidate = self.inner.read(image)
        if candidate == self._state:
            return self._state
        move = self._matching_legal_move(candidate)
        if move is not None:
            report("move", self._chess_board.san(move))
            self._chess_board.push(move)
            self._state = candidate
        else:
            changed = sum(1 for square, label in candidate.items()
                          if self._state.get(square, ".") != label)
            report("dropped",
                   f"{changed} square(s) changed but no legal move matches")
        return self._state

    def _matching_legal_move(self, candidate):
        """Return the legal move whose result matches ``candidate``, or ``None``.

        Converts ``candidate`` to a piece-placement FEN and tests it against
        every legal continuation from the current position.

        Args:
            candidate: A ``{(file_idx, rank): label}`` board map from the
                inner recognizer.

        Returns:
            A ``chess.Move`` if one legal move produces a board matching
            ``candidate``; ``None`` if no legal move does.
        """
        candidate_fen = board.to_fen(candidate)
        for move in self._chess_board.legal_moves:
            test = self._chess_board.copy()
            test.push(move)
            if test.board_fen() == candidate_fen:
                return move
        return None
