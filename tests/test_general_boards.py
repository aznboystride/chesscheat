"""Recognition on arbitrary boards with non-traditional pieces.

This is the generality test: a made-up colour theme and pieces that look
nothing like chess pieces (just consistent coloured patterns composited over
the square), exercised through positions where kings and queens move onto the
opposite-coloured square -- the case the starting position never shows, handled
by template synthesis. The recognizer should still recover every position
exactly, from the starting-position image alone.

Skipped automatically when numpy is unavailable.
"""

import unittest

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:
    _HAVE_NUMPY = False

from chesscheat import board, app
from chesscheat.recognition import TemplateBoardRecognizer, NumpyImageBackend
from chesscheat.mocks import MockSetupProvider, MockFrameSource

LABELS = ".PNBRQKpnbrqk"

# A deliberately non-chess theme: unusual square colours...
LIGHT = (120, 170, 90)
DARK = (35, 55, 110)
CELL = 24
BORDER = 4               # square colour shows in a border around each piece
CENTER = CELL - 2 * BORDER


def _piece_pattern(label):
    """A distinct, consistent RGB pattern per piece (not chess-like)."""
    k = LABELS.index(label)
    yy, xx = np.mgrid[0:CENTER, 0:CENTER]
    r = (k * 43 + yy * 9 + xx * 3) % 180 + 40
    g = (k * 71 + yy * 4 + xx * 14) % 180 + 40
    b = (k * 97 + xx * 8 + yy * 16) % 180 + 40
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


# ...precompute once; pieces look identical wherever they are placed.
_PATTERNS = {label: _piece_pattern(label) for label in LABELS if label != "."}


def render(board_map, playing_white):
    """Render a board map to an RGB numpy image in the chosen perspective."""
    image = np.zeros((8 * CELL, 8 * CELL, 3), dtype=np.uint8)
    for row in range(8):
        for col in range(8):
            file_rank = board.square_coord(row, col, playing_white)
            colour = LIGHT if board.is_light(*file_rank) else DARK
            y, x = row * CELL, col * CELL
            image[y:y + CELL, x:x + CELL] = colour
            label = board_map.get(file_rank, ".")
            if label != ".":
                image[y + BORDER:y + CELL - BORDER,
                      x + BORDER:x + CELL - BORDER] = _PATTERNS[label]
    return image


def move(position, *changes):
    """Return a copy of ``position`` with ``(square, label)`` changes applied."""
    updated = dict(position)
    updated.update(changes)
    return updated


def cross_colour_sequence():
    """Positions moving kings/queens onto the opposite-coloured square.

    Squares: d1 is light, d4 dark (white queen light->dark); e8 light, a3 dark
    (black king light->dark); e1 dark, h5 light (white king dark->light); d8
    dark, d5 light (black queen dark->light). Each lands a royal piece on the
    colour the start position never shows it on.
    """
    start = board.starting_board()
    p1 = move(start, ((3, 1), "."), ((3, 4), "Q"))
    p2 = move(p1, ((4, 8), "."), ((0, 3), "k"))
    p3 = move(p2, ((4, 1), "."), ((7, 5), "K"), ((3, 8), "."), ((3, 5), "q"))
    return [start, p1, p2, p3]


def recognise(positions, playing_white):
    """Run the full pipeline over rendered ``positions``; return read maps."""
    frames = [render(p, playing_white) for p in positions]
    seen = []
    app.run(
        MockSetupProvider(playing_white),
        lambda box: MockFrameSource(frames),
        TemplateBoardRecognizer(NumpyImageBackend()),
        on_board=lambda board_map, _white: seen.append(board_map),
    )
    return seen


@unittest.skipUnless(_HAVE_NUMPY, "requires numpy")
class GeneralBoardTests(unittest.TestCase):
    def test_non_traditional_pieces_white(self):
        positions = cross_colour_sequence()
        self.assertEqual(recognise(positions, True), positions[1:])

    def test_non_traditional_pieces_black(self):
        positions = cross_colour_sequence()
        self.assertEqual(recognise(positions, False), positions[1:])

    def test_kings_and_queens_cross_colours(self):
        # Explicitly assert the royal pieces are read on their new colours.
        positions = cross_colour_sequence()
        seen = recognise(positions, True)
        self.assertEqual(seen[0][(3, 4)], "Q")   # white queen on a dark square
        self.assertEqual(seen[1][(0, 3)], "k")   # black king on a dark square
        self.assertEqual(seen[2][(7, 5)], "K")   # white king on a light square
        self.assertEqual(seen[2][(3, 5)], "q")   # black queen on a light square


if __name__ == "__main__":
    unittest.main()
