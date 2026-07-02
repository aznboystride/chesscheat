"""Tests for ``LegalMoveFilter``: legal-move inference and artifact rejection.

These tests exercise ``LegalMoveFilter`` end-to-end through the mock pipeline
(no numpy, no GUI, no screen required).  The filter is expected to:

- Accept readings that correspond to legal chess moves.
- Silently reject readings that do not (transient artifacts, cursor noise, etc.)
- Correctly handle special moves: castling, en passant, and promotion.

The python-chess package is required; the suite is skipped when absent.
"""

import unittest

try:
    import chess as _chess
    _HAVE_CHESS = True
except ImportError:
    _HAVE_CHESS = False

from chesscheat import board
from chesscheat.recognition import TemplateBoardRecognizer, LegalMoveFilter
from chesscheat.mocks import MockImageBackend, render_mock_image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recognizer():
    """Return a fresh LegalMoveFilter wrapping the mock pipeline."""
    return LegalMoveFilter(TemplateBoardRecognizer(MockImageBackend()))


def _calibrate(recognizer):
    """Calibrate ``recognizer`` from the standard starting position."""
    start = board.starting_board()
    recognizer.calibrate(render_mock_image(start, True), True)
    return start


def _read(recognizer, board_map):
    """Render ``board_map`` and feed it through ``recognizer.read``."""
    return recognizer.read(render_mock_image(board_map, True))


def _chess_to_map(chess_board):
    """Convert a python-chess ``Board`` to a chesscheat board map.

    Args:
        chess_board: A ``chess.Board`` instance.

    Returns:
        A ``{(file_idx, rank): label}`` map with all 64 squares, using ``'.'``
        for empty squares and the standard piece-letter convention for pieces
        (uppercase = white, lowercase = black).
    """
    result = {}
    for f in range(8):
        for r in range(1, 9):
            piece = chess_board.piece_at(_chess.square(f, r - 1))
            result[(f, r)] = piece.symbol() if piece else '.'
    return result


def _apply(chess_board, *uci_moves):
    """Push UCI move strings onto a copy of ``chess_board``.

    Args:
        chess_board: Starting ``chess.Board``.
        *uci_moves: UCI move strings to push in order.

    Returns:
        The resulting ``chess.Board`` after all moves.
    """
    b = chess_board.copy()
    for uci in uci_moves:
        b.push_uci(uci)
    return b


def _sequence(uci_moves):
    """Build a list of chesscheat board maps for a sequence of UCI moves.

    The first element is always the standard starting position.

    Args:
        uci_moves: An iterable of UCI move strings.

    Returns:
        A list of ``{(file_idx, rank): label}`` maps, one per position
        (including start).
    """
    b = _chess.Board()
    maps = [_chess_to_map(b)]
    for uci in uci_moves:
        b.push_uci(uci)
        maps.append(_chess_to_map(b))
    return maps


# ---------------------------------------------------------------------------
# Artifact rejection
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class ArtifactRejectionTests(unittest.TestCase):
    """Frames that are not one legal move away from the current state are
    discarded and the last good state is returned unchanged."""

    def setUp(self):
        self.rec = _make_recognizer()
        self.start = _calibrate(self.rec)

    def test_unchanged_frame_returned(self):
        """A frame identical to the current state is returned immediately."""
        result = _read(self.rec, self.start)
        self.assertEqual(result, self.start)

    def test_impossible_extra_piece_rejected(self):
        """An extra queen appearing in the middle of the board is rejected."""
        corrupted = dict(self.start)
        corrupted[(4, 4)] = 'Q'   # impossible from starting position
        result = _read(self.rec, corrupted)
        self.assertEqual(result, self.start)

    def test_piece_vanishing_mid_board_rejected(self):
        """A pawn silently disappearing (cursor covers it) is rejected."""
        corrupted = dict(self.start)
        corrupted[(4, 2)] = '.'   # e2 pawn gone, no corresponding arrival
        result = _read(self.rec, corrupted)
        self.assertEqual(result, self.start)

    def test_two_pieces_swapped_rejected(self):
        """Two pieces trading squares (impossible in one legal move) is rejected."""
        corrupted = dict(self.start)
        corrupted[(4, 2)], corrupted[(3, 2)] = 'P', 'P'  # e2↔d2, no legal explanation
        corrupted[(4, 1)] = 'K'   # put something on e1 to make it clearly wrong
        result = _read(self.rec, corrupted)
        self.assertEqual(result, self.start)

    def test_many_squares_changed_rejected(self):
        """A frame with many changed squares (drag animation) is rejected."""
        corrupted = dict(self.start)
        for f in range(4):
            corrupted[(f, 4)] = 'p'   # black pawns on rank 4, no legal path
        result = _read(self.rec, corrupted)
        self.assertEqual(result, self.start)

    def test_state_after_artifact_is_still_start(self):
        """After an artifact, the state is still the original starting position."""
        corrupted = dict(self.start)
        corrupted[(4, 4)] = 'Q'
        _read(self.rec, corrupted)
        self.assertEqual(_read(self.rec, self.start), self.start)


# ---------------------------------------------------------------------------
# State recovery: artifact between valid moves
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class RecoveryTests(unittest.TestCase):
    """Artifacts between valid moves do not corrupt the state; subsequent
    legal moves are still accepted correctly."""

    def test_artifact_between_moves_is_dropped(self):
        """Corrupted frame between 1.e4 and 1…c5 is dropped; c5 is accepted."""
        positions = _sequence(["e2e4", "c7c5"])
        start_map, e4_map, c5_map = positions

        rec = _make_recognizer()
        rec.calibrate(render_mock_image(start_map, True), True)

        r1 = _read(rec, e4_map)
        self.assertEqual(r1, e4_map)

        # Inject artifact: cursor over d5 makes it look like a pawn appeared.
        artifact = dict(e4_map)
        artifact[(3, 5)] = 'p'
        r2 = _read(rec, artifact)
        self.assertEqual(r2, e4_map)   # artifact rejected — still e4

        r3 = _read(rec, c5_map)
        self.assertEqual(r3, c5_map)   # c5 accepted

    def test_multiple_consecutive_artifacts_all_rejected(self):
        """A run of artifact frames leaves the state unchanged."""
        positions = _sequence(["e2e4"])
        start_map, e4_map = positions

        rec = _make_recognizer()
        rec.calibrate(render_mock_image(start_map, True), True)
        _read(rec, e4_map)

        for _ in range(5):
            corrupted = dict(e4_map)
            corrupted[(3, 4)] = 'Q'
            result = _read(rec, corrupted)
            self.assertEqual(result, e4_map)

    def test_same_frame_twice_is_not_an_artifact(self):
        """Re-reading an already-accepted state returns it without rejecting."""
        positions = _sequence(["e2e4"])
        start_map, e4_map = positions

        rec = _make_recognizer()
        rec.calibrate(render_mock_image(start_map, True), True)
        _read(rec, e4_map)

        # Reading the same e4 frame again must return e4, not drop it.
        result = _read(rec, e4_map)
        self.assertEqual(result, e4_map)


# ---------------------------------------------------------------------------
# Normal opening sequences
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class OpeningSequenceTests(unittest.TestCase):
    """A legal opening is read back move by move."""

    def _run(self, uci_moves):
        positions = _sequence(uci_moves)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions[0], True), True)
        return [_read(rec, p) for p in positions[1:]]

    def test_sicilian_defence(self):
        """1.e4 c5 2.Nf3 is recovered move by move."""
        uci = ["e2e4", "c7c5", "g1f3"]
        positions = _sequence(uci)
        seen = self._run(uci)
        self.assertEqual(seen, positions[1:])

    def test_ruy_lopez(self):
        """1.e4 e5 2.Nf3 Nc6 3.Bb5 is recovered move by move."""
        uci = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]
        positions = _sequence(uci)
        seen = self._run(uci)
        self.assertEqual(seen, positions[1:])

    def test_fens_are_canonical(self):
        """FENs from the filter match expected FENs regardless of orientation."""
        uci = ["e2e4", "c7c5", "g1f3"]
        expected_fens = [
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR",
            "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR",
            "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R",
        ]
        positions = _sequence(uci)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions[0], True), True)
        for i, (p, expected) in enumerate(zip(positions[1:], expected_fens)):
            with self.subTest(move=i + 1):
                result = _read(rec, p)
                self.assertEqual(board.to_fen(result), expected)


# ---------------------------------------------------------------------------
# Special moves
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class SpecialMoveTests(unittest.TestCase):
    """Castling, en passant, and promotion are accepted as legal moves."""

    def _run_sequence(self, uci_moves):
        """Calibrate and read through all moves; return list of read maps."""
        positions = _sequence(uci_moves)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions[0], True), True)
        return [_read(rec, p) for p in positions[1:]]

    def test_kingside_castling_white(self):
        """White kingside castling (O-O) is accepted.

        Sequence: 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.O-O
        After O-O the white king lands on g1 and the h1 rook moves to f1.
        """
        uci = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1"]
        positions = _sequence(uci)
        results = self._run_sequence(uci)
        after_castling = results[-1]
        self.assertEqual(after_castling[(6, 1)], 'K')  # king on g1
        self.assertEqual(after_castling[(5, 1)], 'R')  # rook on f1
        self.assertEqual(after_castling.get((4, 1), '.'), '.')  # e1 empty
        self.assertEqual(after_castling.get((7, 1), '.'), '.')  # h1 empty

    def test_queenside_castling_black(self):
        """Black queenside castling (O-O-O) is accepted.

        Sequence: 1.e4 Nc6 2.Nf3 d5 3.d3 Bf5 4.Be2 Qd6 5.O-O O-O-O
        After black O-O-O the black king lands on c8 and the a8 rook moves to d8.
        """
        uci = ["e2e4", "b8c6", "g1f3", "d7d5", "d2d3", "c8f5",
               "f1e2", "d8d6", "e1g1", "e8c8"]
        positions = _sequence(uci)
        results = self._run_sequence(uci)
        after_castling = results[-1]
        self.assertEqual(after_castling[(2, 8)], 'k')  # king on c8
        self.assertEqual(after_castling[(3, 8)], 'r')  # rook on d8
        self.assertEqual(after_castling.get((4, 8), '.'), '.')  # e8 empty
        self.assertEqual(after_castling.get((0, 8), '.'), '.')  # a8 empty

    def test_en_passant(self):
        """En passant capture is accepted as a legal move.

        Sequence: 1.e4 c5 2.e5 d5 3.exd6
        After exd6 the white pawn is on d6 and the black d5 pawn is gone.
        """
        uci = ["e2e4", "c7c5", "e4e5", "d7d5", "e5d6"]
        positions = _sequence(uci)
        results = self._run_sequence(uci)
        after_ep = results[-1]
        self.assertEqual(after_ep[(3, 6)], 'P')          # white pawn on d6
        self.assertEqual(after_ep.get((4, 5), '.'), '.')  # e5 empty
        self.assertEqual(after_ep.get((3, 5), '.'), '.')  # d5 pawn captured

    def test_pawn_promotion_to_queen(self):
        """A pawn promoting to a queen (capturing on g8) is accepted."""
        # Build a minimal sequence using python-chess: push pawns until
        # promotion so the filter's internal game tracks it correctly.
        # Sequence: 1.e4 d5 2.e5 d4 3.e6 d3 4.exf7+ Kd7 5.fxg8=Q
        uci = ["e2e4", "d7d5", "e4e5", "d5d4", "e5e6", "d4d3",
               "e6f7", "e8d7", "f7g8q"]
        positions = _sequence(uci)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions[0], True), True)
        results = [_read(rec, p) for p in positions[1:]]
        after_promo = results[-1]
        self.assertEqual(after_promo[(6, 8)], 'Q')   # white queen on g8
        self.assertEqual(after_promo.get((5, 7), '.'), '.')  # f7 empty

    def test_underpromotion_to_rook(self):
        """Underpromotion (pawn → rook) is accepted as a legal move."""
        # Same sequence as above but promote to rook
        uci = ["e2e4", "d7d5", "e4e5", "d5d4", "e5e6", "d4d3",
               "e6f7", "e8d7", "f7g8r"]
        positions = _sequence(uci)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions[0], True), True)
        results = [_read(rec, p) for p in positions[1:]]
        after_promo = results[-1]
        self.assertEqual(after_promo[(6, 8)], 'R')   # white rook on g8

    def test_promotion_of_wrong_piece_rejected(self):
        """A frame showing a promoted piece on the wrong square is rejected."""
        # Play up to f7, then present the wrong promotion square.
        uci_up_to_capture = ["e2e4", "d7d5", "e4e5", "d5d4", "e5e6", "d4d3",
                              "e6f7", "e8d7"]
        positions_so_far = _sequence(uci_up_to_capture)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions_so_far[0], True), True)
        for p in positions_so_far[1:]:
            _read(rec, p)

        # Now present a wrong state: queen on e8 instead of g8
        last = positions_so_far[-1]
        wrong = dict(last)
        wrong[(4, 8)] = 'Q'   # queen on e8 — no legal promotion lands there
        result = _read(rec, wrong)
        self.assertEqual(result, positions_so_far[-1])  # rejected


# ---------------------------------------------------------------------------
# Cursor-over-square simulation
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class CursorArtifactTests(unittest.TestCase):
    """Simulates a mouse cursor visually corrupting a square."""

    def _corrupt_square(self, board_map, file_idx, rank, fake_label):
        """Return a board map with one square replaced by ``fake_label``."""
        corrupted = dict(board_map)
        corrupted[(file_idx, rank)] = fake_label
        return corrupted

    def test_cursor_over_empty_square_shows_wrong_piece(self):
        """A cursor that makes an empty square look like a piece is rejected."""
        rec = _make_recognizer()
        start = _calibrate(rec)
        # After 1.e4, e4 pawn is on (4,4); e5 is empty.
        # Cursor over e5 makes it look like a pawn is there.
        positions = _sequence(["e2e4"])
        _, e4_map = positions
        _read(rec, e4_map)

        corrupted = self._corrupt_square(e4_map, 4, 5, 'P')  # fake pawn on e5
        result = _read(rec, corrupted)
        self.assertEqual(result, e4_map)

    def test_cursor_over_piece_makes_it_vanish(self):
        """A cursor that obscures a piece making the square look empty is rejected."""
        rec = _make_recognizer()
        start = _calibrate(rec)
        positions = _sequence(["e2e4"])
        _, e4_map = positions
        _read(rec, e4_map)

        # The e4 pawn appears to have vanished (cursor rendered over it).
        corrupted = self._corrupt_square(e4_map, 4, 4, '.')
        result = _read(rec, corrupted)
        self.assertEqual(result, e4_map)

    def test_cursor_on_moving_piece_during_animation(self):
        """Mid-drag: piece missing from source but not yet on destination."""
        rec = _make_recognizer()
        _calibrate(rec)

        # Simulate a drag animation frame where e2 pawn has lifted off but
        # hasn't reached e4 yet — neither square shows the pawn.
        start = board.starting_board()
        mid_drag = dict(start)
        mid_drag[(4, 2)] = '.'  # lifted off e2
        # (4, 4) remains '.' — pawn not yet placed
        result = _read(rec, mid_drag)
        self.assertEqual(result, start)  # drag frame rejected

    def test_highlight_makes_piece_misidentified(self):
        """A last-move highlight changing square colour causes a misread → rejected."""
        rec = _make_recognizer()
        _calibrate(rec)
        positions = _sequence(["e2e4"])
        _, e4_map = positions
        _read(rec, e4_map)

        # Simulate: the highlight makes the e4 pawn look like a rook.
        corrupted = self._corrupt_square(e4_map, 4, 4, 'R')
        result = _read(rec, corrupted)
        self.assertEqual(result, e4_map)  # misread rejected


# ---------------------------------------------------------------------------
# Long game: many moves, no false positives
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class LongGameTests(unittest.TestCase):
    """Verify no false positives across a longer sequence of legal moves."""

    # The Italian Game, ~10 moves.
    ITALIAN = [
        "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6",
        "d2d3", "f8c5", "c2c3", "d7d6", "b2b4", "c5b6",
    ]

    def test_all_moves_accepted_no_artifact(self):
        """Every legal move in a 12-move sequence is accepted exactly."""
        positions = _sequence(self.ITALIAN)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions[0], True), True)
        for i, pos in enumerate(positions[1:], start=1):
            with self.subTest(move=i):
                result = _read(rec, pos)
                self.assertEqual(result, pos)

    def test_artifacts_scattered_throughout_long_game(self):
        """Artifacts scattered after every other move are all rejected."""
        positions = _sequence(self.ITALIAN)
        rec = _make_recognizer()
        rec.calibrate(render_mock_image(positions[0], True), True)

        for i, pos in enumerate(positions[1:], start=1):
            _read(rec, pos)
            # Inject a noisy frame: stick an extra queen somewhere.
            corrupted = dict(pos)
            corrupted[(3, 4)] = 'Q'
            artifact_result = _read(rec, corrupted)
            self.assertEqual(artifact_result, pos,
                             f"artifact after move {i} was not rejected")


if __name__ == "__main__":
    unittest.main()
