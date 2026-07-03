"""Recognition tests over real chessboard images.

The fixtures in ``fixtures/boards/<set>/`` are real board renderings built from
several real chess piece sets pulled from the web (Wikipedia and alpha PNGs from
chessboard.js, and lichess's merida set rasterised from SVG -- see
``fixtures/generate_boards.py`` and the fixtures README). Each set uses its own
colour theme. This exercises the real ``NumpyImageBackend`` end-to-end --
calibrating from the starting position and then reading each later frame -- over
the opening 1.e4 c5 2.Nf3 for every set.

Skipped automatically when numpy or Pillow is unavailable.
"""

import os
import unittest

try:
    import numpy as np
    from PIL import Image
    _HAVE_DEPS = True
except ImportError:
    _HAVE_DEPS = False

from chesscheat import board, app
from chesscheat.recognition import TemplateBoardRecognizer, NumpyImageBackend
from chesscheat.mocks import MockSetupProvider, MockFrameSource

BOARDS_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "boards")

# Each piece set has its own subdirectory of board images.
PIECE_SETS = ["wikipedia", "alpha", "merida"]

# The opening 1.e4 c5 2.Nf3, as canonical (white-view) placement FENs.
SEQUENCE = ["start", "e4", "c5", "nf3"]
EXPECTED_FEN = {
    "start": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
    "e4": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR",
    "c5": "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR",
    "nf3": "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R",
}


def _load(piece_set, name):
    """Load a board fixture as an RGB numpy array."""
    path = os.path.join(BOARDS_DIR, piece_set, f"{name}.png")
    return np.array(Image.open(path).convert("RGB"))


@unittest.skipUnless(_HAVE_DEPS, "requires numpy and Pillow")
class SsimMatchingTests(unittest.TestCase):
    """Properties of the SSIM square comparison on real piece imagery."""

    def _features(self, piece_set="wikipedia"):
        """Return (backend, {name: feature}) for a few start-frame squares."""
        backend = NumpyImageBackend()
        image = _load(piece_set, "start")
        crops = {
            "wP_light": (6, 4),   # e2 pawn on a light square
            "wP_dark": (6, 3),    # d2 pawn on a dark square
            "bP_dark": (1, 4),    # e7 pawn on a dark square
            "empty_light": (4, 3),
            "empty_dark": (4, 4),
        }
        return backend, {
            name: backend.feature(backend.get_square(image, row, col))
            for name, (row, col) in crops.items()
        }

    def test_identical_squares_score_one(self):
        backend, feats = self._features()
        self.assertAlmostEqual(
            backend.similarity(feats["wP_light"], feats["wP_light"]), 1.0)

    def test_same_piece_across_square_colours_scores_high(self):
        backend, feats = self._features()
        self.assertGreater(
            backend.similarity(feats["wP_light"], feats["wP_dark"]), 0.8)

    def test_piece_colour_is_part_of_the_match(self):
        # Same silhouette, opposite piece colour: must score low.
        backend, feats = self._features()
        self.assertLess(
            backend.similarity(feats["wP_light"], feats["bP_dark"]), 0.6)

    def test_empty_squares_score_one_regardless_of_colour(self):
        backend, feats = self._features()
        self.assertAlmostEqual(
            backend.similarity(feats["empty_light"], feats["empty_dark"]),
            1.0, places=2)

    def test_piece_vs_empty_scores_low(self):
        backend, feats = self._features()
        self.assertLess(
            backend.similarity(feats["wP_light"], feats["empty_light"]), 0.6)

    def test_unknown_scoring_on_a_corrupted_square(self):
        recognizer = TemplateBoardRecognizer(NumpyImageBackend(),
                                             match_threshold=0.6)
        start = _load("wikipedia", "start")
        recognizer.calibrate(start, playing_white=True)

        corrupted = start.copy()
        h = corrupted.shape[0] // 8
        cy, cx = 3 * h + h // 2, 4 * h + h // 2   # centre of e5 (empty)
        corrupted[cy - 16:cy + 16, cx - 3:cx + 3] = 255
        corrupted[cy - 3:cy + 3, cx - 16:cx + 16] = 255

        recognizer.read(corrupted)
        label, score = recognizer.last_scored[(4, 5)]
        self.assertEqual(label, "?")
        self.assertLess(score, 0.6)
        # Every untouched square is confidently identified.
        others = [entry for square, entry in recognizer.last_scored.items()
                  if square != (4, 5)]
        self.assertTrue(all(label != "?" and score >= 0.6
                            for label, score in others))


@unittest.skipUnless(_HAVE_DEPS, "requires numpy and Pillow")
class RealImageRecognitionTests(unittest.TestCase):
    def test_starting_position_round_trips(self):
        for piece_set in PIECE_SETS:
            with self.subTest(piece_set=piece_set):
                recognizer = TemplateBoardRecognizer(NumpyImageBackend())
                start = _load(piece_set, "start")
                recognizer.calibrate(start, playing_white=True)
                self.assertEqual(board.to_fen(recognizer.read(start)),
                                 EXPECTED_FEN["start"])

    def test_evolving_game_is_recognised(self):
        for piece_set in PIECE_SETS:
            with self.subTest(piece_set=piece_set):
                frames = [_load(piece_set, name) for name in SEQUENCE]
                seen = []
                app.run(
                    MockSetupProvider(playing_white=True),
                    lambda box, frames=frames: MockFrameSource(frames),
                    TemplateBoardRecognizer(NumpyImageBackend()),
                    on_board=lambda board_map, _white: seen.append(board_map),
                )
                # The first frame calibrates; the rest are read back.
                got = [board.to_fen(board_map) for board_map in seen]
                self.assertEqual(got,
                                 [EXPECTED_FEN[name] for name in SEQUENCE[1:]])


if __name__ == "__main__":
    unittest.main()
