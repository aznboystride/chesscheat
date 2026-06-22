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
