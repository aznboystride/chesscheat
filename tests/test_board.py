"""Unit tests for the pure board logic in ``chesscheat.board``."""

import unittest

from chesscheat import board

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


class SquareCoordTests(unittest.TestCase):
    def test_white_corners(self):
        self.assertEqual(board.square_coord(0, 0, True), (0, 8))
        self.assertEqual(board.square_coord(7, 7, True), (7, 1))

    def test_black_corners(self):
        self.assertEqual(board.square_coord(0, 0, False), (7, 1))
        self.assertEqual(board.square_coord(7, 7, False), (0, 8))

    def test_every_cell_maps_uniquely(self):
        for playing_white in (True, False):
            seen = {board.square_coord(r, c, playing_white)
                    for r in range(8) for c in range(8)}
            self.assertEqual(len(seen), 64)


class StartLabelTests(unittest.TestCase):
    def test_back_ranks(self):
        self.assertEqual([board.start_label(f, 1) for f in range(8)],
                         list("RNBQKBNR"))
        self.assertEqual([board.start_label(f, 8) for f in range(8)],
                         list("rnbqkbnr"))

    def test_pawn_ranks(self):
        self.assertTrue(all(board.start_label(f, 2) == "P" for f in range(8)))
        self.assertTrue(all(board.start_label(f, 7) == "p" for f in range(8)))

    def test_empty_middle(self):
        for rank in (3, 4, 5, 6):
            self.assertTrue(all(board.start_label(f, rank) == "."
                                for f in range(8)))


class IsLightTests(unittest.TestCase):
    def test_known_squares(self):
        self.assertTrue(board.is_light(0, 8))    # a8 light
        self.assertTrue(board.is_light(7, 1))    # h1 light
        self.assertFalse(board.is_light(0, 1))   # a1 dark
        self.assertFalse(board.is_light(7, 8))   # h8 dark


class FenTests(unittest.TestCase):
    def test_starting_position(self):
        self.assertEqual(board.to_fen(board.starting_board()), START_FEN)

    def test_empty_board(self):
        self.assertEqual(board.to_fen({}), "8/8/8/8/8/8/8/8")

    def test_after_e4(self):
        position = dict(board.starting_board())
        position[(4, 2)] = "."
        position[(4, 4)] = "P"
        self.assertEqual(board.to_fen(position),
                         "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR")

    def test_single_piece_run_counts(self):
        self.assertEqual(board.to_fen({(4, 1): "K"}), "8/8/8/8/8/8/8/4K3")


class RenderTests(unittest.TestCase):
    def test_white_perspective_layout(self):
        lines = board.render(board.starting_board(), True).splitlines()
        self.assertEqual(lines[0].split(), list("abcdefgh"))
        self.assertEqual(lines[1].split(), ["8"] + list("rnbqkbnr") + ["8"])
        self.assertEqual(lines[8].split(), ["1"] + list("RNBQKBNR") + ["1"])

    def test_black_perspective_is_flipped(self):
        lines = board.render(board.starting_board(), False).splitlines()
        self.assertEqual(lines[0].split(), list("hgfedcba"))
        self.assertEqual(lines[1].split()[0], "1")
        self.assertEqual(lines[8].split()[0], "8")

    def test_render_has_border_rows(self):
        out = board.render(board.starting_board(), True).splitlines()
        self.assertEqual(out[0], out[-1])
        self.assertEqual(len(out), 10)


if __name__ == "__main__":
    unittest.main()
