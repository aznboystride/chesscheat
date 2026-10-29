"""Pure-logic tests for reading the opponent's move off a highlight.

``chesscheat.mirror.move_inference`` works on plain per-square scans and a
legality predicate, so everything here runs without numpy or python-chess.
"""

import unittest

from chesscheat import board
from chesscheat.mirror import (highlighted_squares, piece_colours,
                               infer_opponent_move)

LIGHT, DARK = (235.0, 236.0, 208.0), (119.0, 149.0, 86.0)
TINT = (20.0, 20.0, -90.0)          # a yellowish last-move highlight
OWN_BRIGHT, OPP_BRIGHT = 225.0, 60.0


def _scans(board_map, bottom_white=True, highlighted=(), playing_white=True,
           pieces=None):
    """Build a synthetic scan of ``board_map`` as a chess app would show it.

    Args:
        board_map: ``{(file_idx, rank): label}`` position to depict.
        bottom_white: Orientation of the depicted board.
        highlighted: Square names whose background is tinted.
        playing_white: Which side is "ours" (sets piece brightness).
        pieces: Optional ``{square_name: (fraction, brightness)}``
            overrides for what the image shows on a square.

    Returns:
        A ``{(row, col): (background, fraction, brightness)}`` dict.
    """
    pieces = pieces or {}
    scans = {}
    for row in range(8):
        for col in range(8):
            file_rank = board.square_coord(row, col, bottom_white)
            name = board.square_name(*file_rank)
            base = LIGHT if (row + col) % 2 == 0 else DARK
            background = (tuple(b + t for b, t in zip(base, TINT))
                          if name in highlighted else base)
            if name in pieces:
                fraction, brightness = pieces[name]
            else:
                label = board_map.get(file_rank, ".")
                if label == ".":
                    fraction, brightness = 0.0, None
                else:
                    ours = label.isupper() == playing_white
                    fraction = 0.3
                    brightness = OWN_BRIGHT if ours else OPP_BRIGHT
            scans[(row, col)] = (background, fraction, brightness)
    return scans


def _after(*uci_moves):
    """Apply simple (non-capturing, non-special) UCI moves to the start."""
    position = dict(board.starting_board())
    for uci in uci_moves:
        origin, dest = board.parse_square(uci[:2]), board.parse_square(uci[2:4])
        position[dest] = position.pop(origin)
        position[origin] = "."
    return position


class HighlightTests(unittest.TestCase):
    """Tinted squares stand out from the rest of their colour class."""

    def test_no_highlight_on_a_clean_board(self):
        self.assertEqual(highlighted_squares(_scans(_after()), True),
                         frozenset())

    def test_both_squares_of_a_move_are_found(self):
        scans = _scans(_after("c7c5"), highlighted=("c7", "c5"))
        self.assertEqual(highlighted_squares(scans, True),
                         frozenset({"c7", "c5"}))

    def test_orientation_is_honoured(self):
        scans = _scans(_after("e2e4"), bottom_white=False,
                       highlighted=("e2", "e4"))
        self.assertEqual(highlighted_squares(scans, False),
                         frozenset({"e2", "e4"}))

    def test_small_noise_is_not_a_highlight(self):
        scans = _scans(_after())
        bg, f, b = scans[(3, 3)]
        scans[(3, 3)] = (tuple(c + 5 for c in bg), f, b)
        self.assertEqual(highlighted_squares(scans, True), frozenset())


class PieceColourTests(unittest.TestCase):
    """Occupancy from piece pixels, colour from brightness vs the model."""

    def test_start_position_is_classified_from_the_model(self):
        colours = piece_colours(_scans(_after()), True, _after(), True)
        self.assertEqual(colours["e1"], "own")
        self.assertEqual(colours["e8"], "opponent")
        self.assertIsNone(colours["e4"])

    def test_sides_swap_when_we_play_black(self):
        scans = _scans(_after(), bottom_white=False, playing_white=False)
        colours = piece_colours(scans, False, _after(), False)
        self.assertEqual(colours["e8"], "own")
        self.assertEqual(colours["e1"], "opponent")

    def test_a_moved_piece_is_classified_by_its_brightness_not_the_model(self):
        # The model still has the pawn on c7; the image shows it on c5.
        scans = _scans(_after("c7c5"), highlighted=("c7", "c5"))
        colours = piece_colours(scans, True, _after(), True)
        self.assertIsNone(colours["c7"])
        self.assertEqual(colours["c5"], "opponent")

    def test_a_captured_square_shows_the_capturer(self):
        scans = _scans(_after(), pieces={"e4": (0.3, OPP_BRIGHT)})
        colours = piece_colours(scans, True, _after(), True)
        self.assertEqual(colours["e4"], "opponent")

    def test_a_few_stray_pixels_are_not_a_piece(self):
        scans = _scans(_after(), pieces={"e4": (0.02, OPP_BRIGHT)})
        self.assertIsNone(piece_colours(scans, True, _after(), True)["e4"])

    def test_without_a_reference_everything_occupied_reads_opponent(self):
        # Only black pieces in the model: no "own" reference exists.
        only_black = {sq: (lbl if lbl.islower() else ".")
                      for sq, lbl in _after().items()}
        scans = _scans(only_black, pieces={"e4": (0.3, OWN_BRIGHT)})
        self.assertEqual(piece_colours(scans, True, only_black, True)["e4"],
                         "opponent")


class InferenceTests(unittest.TestCase):
    """Choosing the one candidate consistent with the image and the rules."""

    def _legal(self, *moves):
        allowed = set(moves)
        return lambda origin, dest: origin + dest in allowed

    def test_opponent_move_is_read_from_its_highlight(self):
        scans = _scans(_after("e2e4", "c7c5"), highlighted=("c7", "c5"))
        colours = piece_colours(scans, True, _after("e2e4"), True)
        move = infer_opponent_move(highlighted_squares(scans, True), colours,
                                   self._legal("c7c5", "c7c6", "e7e5"))
        self.assertEqual(move, ("c7", "c5"))

    def test_our_own_move_highlight_is_ignored(self):
        scans = _scans(_after("e2e4"), highlighted=("e2", "e4"))
        colours = piece_colours(scans, True, _after("e2e4"), True)
        # Nothing legal starts from a square of ours.
        self.assertIsNone(infer_opponent_move(
            highlighted_squares(scans, True), colours, self._legal("c7c5")))

    def test_stale_highlight_of_a_known_move_is_rejected(self):
        # Model already has Nf6 (and our reply); the app still shows g8/f6
        # tinted. f6->g8 would be legal, but the knight is on f6, not off it.
        model = _after("e2e4", "g8f6", "b1c3")
        scans = _scans(model, highlighted=("g8", "f6"))
        colours = piece_colours(scans, True, model, True)
        self.assertIsNone(infer_opponent_move(
            highlighted_squares(scans, True), colours, self._legal("f6g8")))

    def test_capture_still_animating_is_not_accepted_yet(self):
        model = _after("e2e4", "d7d5", "g1f3")
        # d5 already vacated, e4 still shows our pawn.
        scans = _scans(model, highlighted=("d5", "e4"),
                       pieces={"d5": (0.0, None)})
        colours = piece_colours(scans, True, model, True)
        self.assertIsNone(infer_opponent_move(
            highlighted_squares(scans, True), colours, self._legal("d5e4")))
        # Landed: the opponent's pawn is on e4 now.
        scans = _scans(model, highlighted=("d5", "e4"),
                       pieces={"d5": (0.0, None), "e4": (0.3, OPP_BRIGHT)})
        colours = piece_colours(scans, True, model, True)
        self.assertEqual(infer_opponent_move(
            highlighted_squares(scans, True), colours, self._legal("d5e4")),
            ("d5", "e4"))

    def test_extra_tinted_square_such_as_a_king_in_check_is_tolerated(self):
        model = _after("d2d4", "e7e6", "c2c4")
        scans = _scans(_after("d2d4", "e7e6", "c2c4", "f8b4"),
                       highlighted=("f8", "b4", "e1"))
        colours = piece_colours(scans, True, model, True)
        self.assertEqual(infer_opponent_move(
            highlighted_squares(scans, True), colours,
            self._legal("f8b4", "f8e7")), ("f8", "b4"))

    def test_ambiguous_or_incomplete_highlights_give_nothing(self):
        colours = {"a8": None, "h8": None, "f8": "opponent", "g8": "opponent"}
        self.assertIsNone(infer_opponent_move(
            {"a8", "f8", "h8", "g8"}, colours, self._legal("a8f8", "h8g8")))
        self.assertIsNone(infer_opponent_move({"c7"}, {"c7": None},
                                              lambda a, b: True))
        self.assertIsNone(infer_opponent_move(set(), {}, lambda a, b: True))
