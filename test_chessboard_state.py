"""Unit tests for the pure board logic in chessboard_state.

These cover coordinate mapping, starting-position labels, text rendering and
FEN generation. They do not require cv2/mss, since those are imported lazily
only inside the screen-capture / vision functions.
"""

import unittest

import chessboard_state as cs

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


def starting_board(playing_white):
    """Build the {(file, rank): label} dict for the starting position."""
    board = {}
    for row in range(8):
        for col in range(8):
            file_idx, rank = cs.square_coord(row, col, playing_white)
            board[(file_idx, rank)] = cs.start_label(file_idx, rank)
    return board


class SquareCoordTests(unittest.TestCase):
    def test_white_corners(self):
        # Top-left is a8, bottom-right is h1 from white's perspective.
        self.assertEqual(cs.square_coord(0, 0, True), (0, 8))
        self.assertEqual(cs.square_coord(7, 7, True), (7, 1))

    def test_black_corners(self):
        # Board is flipped: top-left is h1, bottom-right is a8.
        self.assertEqual(cs.square_coord(0, 0, False), (7, 1))
        self.assertEqual(cs.square_coord(7, 7, False), (0, 8))

    def test_every_cell_maps_uniquely(self):
        for playing_white in (True, False):
            seen = set()
            for row in range(8):
                for col in range(8):
                    coord = cs.square_coord(row, col, playing_white)
                    self.assertNotIn(coord, seen)
                    seen.add(coord)
            self.assertEqual(len(seen), 64)


class StartLabelTests(unittest.TestCase):
    def test_back_ranks(self):
        self.assertEqual([cs.start_label(f, 1) for f in range(8)],
                         list("RNBQKBNR"))
        self.assertEqual([cs.start_label(f, 8) for f in range(8)],
                         list("rnbqkbnr"))

    def test_pawn_ranks(self):
        self.assertTrue(all(cs.start_label(f, 2) == "P" for f in range(8)))
        self.assertTrue(all(cs.start_label(f, 7) == "p" for f in range(8)))

    def test_empty_middle(self):
        for rank in (3, 4, 5, 6):
            self.assertTrue(all(cs.start_label(f, rank) == "." for f in range(8)))


class FenTests(unittest.TestCase):
    def test_starting_position_both_views(self):
        # Orientation must not affect the canonical FEN.
        self.assertEqual(cs.to_fen(starting_board(True)), START_FEN)
        self.assertEqual(cs.to_fen(starting_board(False)), START_FEN)

    def test_empty_board(self):
        self.assertEqual(cs.to_fen({}), "8/8/8/8/8/8/8/8")

    def test_after_e4(self):
        board = starting_board(True)
        board[(4, 2)] = "."   # e2 vacated
        board[(4, 4)] = "P"   # pawn to e4
        self.assertEqual(cs.to_fen(board),
                         "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR")

    def test_single_piece_run_counts(self):
        # A lone white king on e1 -> rank1 is "4K3".
        self.assertEqual(cs.to_fen({(4, 1): "K"}), "8/8/8/8/8/8/8/4K3")


class RenderTests(unittest.TestCase):
    def test_white_perspective_layout(self):
        lines = cs.render(starting_board(True), True).splitlines()
        self.assertEqual(lines[0].split(), list("abcdefgh"))
        self.assertEqual(lines[1].split(), ["8"] + list("rnbqkbnr") + ["8"])
        self.assertEqual(lines[8].split(), ["1"] + list("RNBQKBNR") + ["1"])

    def test_black_perspective_is_flipped(self):
        lines = cs.render(starting_board(False), False).splitlines()
        # Files run h..a and the player's own (black) back rank is on top.
        self.assertEqual(lines[0].split(), list("hgfedcba"))
        self.assertEqual(lines[1].split()[0], "1")
        self.assertEqual(lines[8].split()[0], "8")

    def test_render_has_border_rows(self):
        out = cs.render(starting_board(True), True).splitlines()
        self.assertEqual(out[0], out[-1])  # header repeated top and bottom
        self.assertEqual(len(out), 10)     # header + 8 ranks + header


if __name__ == "__main__":
    unittest.main()
