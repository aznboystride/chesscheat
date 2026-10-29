"""Reading highlights off real piece-set images (numpy + Pillow + chess).

Composes the fixture piece sets onto their themes with last-move tints
under the pieces, as a chess app draws them, and checks the mirror mode's
screen scan + inference reads the opponent's move -- and only the
opponent's -- for every set and both orientations.
"""

import unittest

try:
    import numpy as np
    from PIL import Image  # noqa: F401
    import chess
    _HAVE_DEPS = True
except ImportError:
    _HAVE_DEPS = False

from chesscheat.mirror import (highlighted_squares, piece_colours,
                               infer_opponent_move)
from tests.test_filter_real_images import THEMES, _render_highlighted

SETS = tuple(THEMES)
CHECK_TINT = (235, 97, 80)   # a red "king in check" square


def _position(*uci_moves):
    game = chess.Board()
    for uci in uci_moves:
        game.push_uci(uci)
    board_map = {(f, r): (game.piece_at(chess.square(f, r - 1)).symbol()
                          if game.piece_at(chess.square(f, r - 1)) else ".")
                 for f in range(8) for r in range(1, 9)}
    return game, board_map


def _fr(name):
    return ord(name[0]) - 97, int(name[1])


@unittest.skipUnless(_HAVE_DEPS, "requires numpy, Pillow and python-chess")
class WatchRealImageTests(unittest.TestCase):
    """Highlight reading on real piece artwork."""

    def _infer(self, piece_set, model_moves, shown_moves, highlighted,
               playing_white=True, extra_tints=()):
        """Scan a composed frame and infer against a model position."""
        from chesscheat.recognition import scan_squares

        model, model_map = _position(*model_moves)
        _shown, shown_map = _position(*shown_moves)
        image = _render_highlighted(piece_set, shown_map,
                                    [_fr(n) for n in highlighted])
        for name in extra_tints:
            f, r = _fr(name)
            col, row = f, 8 - r
            cell = image[row * 64:(row + 1) * 64, col * 64:(col + 1) * 64]
            is_bg = np.abs(cell.astype(int)
                           - cell[2, 2].astype(int)).sum(axis=-1) < 40
            cell[is_bg] = CHECK_TINT
        if not playing_white:
            image = image[::-1, ::-1]      # black at the bottom
        scans = scan_squares(image)
        colours = piece_colours(scans, playing_white, model_map,
                                playing_white)
        return infer_opponent_move(
            highlighted_squares(scans, playing_white), colours,
            lambda a, b: (chess.Move.from_uci(a + b) in model.legal_moves
                          or chess.Move.from_uci(a + b + "q")
                          in model.legal_moves))

    def test_opponent_pawn_move_is_read(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                self.assertEqual(
                    self._infer(piece_set, ["e2e4"], ["e2e4", "c7c5"],
                                ("c7", "c5")), ("c7", "c5"))

    def test_our_own_highlight_is_ignored(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                self.assertIsNone(self._infer(piece_set, ["e2e4"], ["e2e4"],
                                              ("e2", "e4")))

    def test_clean_board_gives_nothing(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                self.assertIsNone(self._infer(piece_set, ["e2e4"], ["e2e4"],
                                              ()))

    def test_stale_highlight_after_our_reply_is_rejected(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                self.assertIsNone(self._infer(
                    piece_set, ["e2e4", "g8f6", "b1c3"],
                    ["e2e4", "g8f6", "b1c3"], ("g8", "f6")))

    def test_capture_is_read_once_the_piece_has_landed(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                model = ["e2e4", "d7d5", "g1f3"]
                self.assertEqual(self._infer(
                    piece_set, model, model + ["d5e4"], ("d5", "e4")),
                    ("d5", "e4"))

    def test_check_tint_on_our_king_does_not_block_detection(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                model = ["d2d4", "e7e6", "c2c4"]
                self.assertEqual(self._infer(
                    piece_set, model, model + ["f8b4"], ("f8", "b4"),
                    extra_tints=("e1",)), ("f8", "b4"))

    def test_black_orientation_reads_whites_move(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                self.assertEqual(self._infer(
                    piece_set, [], ["e2e4"], ("e2", "e4"),
                    playing_white=False), ("e2", "e4"))

    def test_knight_move_is_read(self):
        for piece_set in SETS:
            with self.subTest(piece_set=piece_set):
                model = ["e2e4", "c7c5", "g1f3"]
                self.assertEqual(self._infer(
                    piece_set, model, model + ["b8c6"], ("b8", "c6")),
                    ("b8", "c6"))
