"""Real-image artifact-robustness tests for ``LegalMoveFilter``.

Loads the committed fixture board images and injects synthetic visual
artifacts — a cursor cross, a highlight tint on the last-moved squares —
then verifies the filter rejects corrupted frames while still accepting
every genuine move in the opening.  Skipped when numpy, Pillow, or
python-chess are absent.
"""

import os
import unittest

try:
    import numpy as np
    from PIL import Image
    import chess as _chess
    _HAVE_DEPS = True
except ImportError:
    _HAVE_DEPS = False

from chesscheat import board
from chesscheat.recognition import (TemplateBoardRecognizer,
                                    NumpyImageBackend, LegalMoveFilter)

BOARDS_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "boards")

SEQUENCE = ["start", "e4", "c5", "nf3"]
EXPECTED_FEN = {
    "start": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
    "e4":    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR",
    "c5":    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR",
    "nf3":   "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R",
}


def _load(piece_set, name):
    """Load a board fixture as an RGB numpy array.

    Args:
        piece_set: One of ``'wikipedia'``, ``'alpha'``, or ``'merida'``.
        name: Frame name without extension (e.g. ``'start'``).

    Returns:
        An ``(H, W, 3)`` uint8 numpy array.
    """
    path = os.path.join(BOARDS_DIR, piece_set, f"{name}.png")
    return np.array(Image.open(path).convert("RGB"))


def _cursor_over_square(image, row, col):
    """Paint a white cross cursor over a square to simulate mouse-over noise.

    Args:
        image: An ``(H, W, 3)`` uint8 numpy board image.
        row: Screen grid row (0 = top).
        col: Screen grid column (0 = left).

    Returns:
        A copy of ``image`` with the cursor drawn on it.
    """
    img = image.copy()
    h, w = img.shape[:2]
    sq_h, sq_w = h // 8, w // 8
    cy = row * sq_h + sq_h // 2
    cx = col * sq_w + sq_w // 2
    arm = max(6, sq_h // 4)
    thick = max(2, sq_h // 12)
    img[cy - arm: cy + arm, cx - thick: cx + thick] = 255  # vertical
    img[cy - thick: cy + thick, cx - arm: cx + arm] = 255  # horizontal
    return img


def _highlight_squares(image, squares_rowcol, color=(255, 255, 100)):
    """Tint a set of squares to simulate a last-move highlight.

    Args:
        image: An ``(H, W, 3)`` uint8 numpy board image.
        squares_rowcol: Iterable of ``(row, col)`` screen-grid pairs to tint.
        color: RGB tint to blend in.

    Returns:
        A copy of ``image`` with a 50 % tint applied to the given squares.
    """
    img = image.copy().astype(np.int32)
    h, w = img.shape[:2]
    sq_h, sq_w = h // 8, w // 8
    tint = np.array(color, dtype=np.int32)
    for row, col in squares_rowcol:
        y0, y1 = row * sq_h, (row + 1) * sq_h
        x0, x1 = col * sq_w, (col + 1) * sq_w
        img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] // 2 + tint // 2)
    return np.clip(img, 0, 255).astype(np.uint8)


@unittest.skipUnless(_HAVE_DEPS, "requires numpy, Pillow, and python-chess")
class FilterRealImagesTests(unittest.TestCase):
    """``LegalMoveFilter`` over real fixture images: moves accepted, artifacts
    rejected, across all three piece sets."""

    def _make_and_calibrate(self, piece_set):
        """Return a calibrated ``LegalMoveFilter`` for ``piece_set``.

        Args:
            piece_set: Name of the piece set directory.

        Returns:
            A ``LegalMoveFilter`` calibrated on the starting-position fixture.
        """
        rec = LegalMoveFilter(TemplateBoardRecognizer(NumpyImageBackend()))
        rec.calibrate(_load(piece_set, "start"), playing_white=True)
        return rec

    def test_opening_sequence_accepted(self):
        """Every genuine move in the fixture opening is accepted by the filter."""
        for piece_set in ["wikipedia", "alpha", "merida"]:
            with self.subTest(piece_set=piece_set):
                rec = self._make_and_calibrate(piece_set)
                for name in SEQUENCE[1:]:   # start already used for calibration
                    image = _load(piece_set, name)
                    result = rec.read(image)
                    self.assertEqual(
                        board.to_fen(result), EXPECTED_FEN[name],
                        f"{piece_set}/{name}: FEN mismatch",
                    )

    def test_cursor_artifact_on_clean_frame_rejected(self):
        """A cursor drawn over a square on an otherwise-correct frame is rejected.

        After calibrating from start, we feed the start image again with a
        cursor painted over a2 (where a white pawn sits).  This corrupts that
        square's appearance; the resulting board can't be explained by a legal
        move from start, so the filter must return the starting position.
        """
        for piece_set in ["wikipedia", "alpha", "merida"]:
            with self.subTest(piece_set=piece_set):
                rec = self._make_and_calibrate(piece_set)
                start_image = _load(piece_set, "start")
                # Row 6 = rank 2 (white pawn row), col 0 = a-file.
                corrupted = _cursor_over_square(start_image, row=6, col=0)
                result = rec.read(corrupted)
                self.assertEqual(
                    board.to_fen(result), EXPECTED_FEN["start"],
                    f"{piece_set}: cursor artifact was not rejected",
                )

    def test_cursor_artifact_between_moves_rejected(self):
        """A cursor artifact between two real moves is discarded; both moves land."""
        for piece_set in ["wikipedia", "alpha", "merida"]:
            with self.subTest(piece_set=piece_set):
                rec = self._make_and_calibrate(piece_set)

                # Accept 1.e4 normally.
                r1 = rec.read(_load(piece_set, "e4"))
                self.assertEqual(board.to_fen(r1), EXPECTED_FEN["e4"])

                # Inject cursor artifact on the e4 frame.
                corrupted = _cursor_over_square(
                    _load(piece_set, "e4"), row=4, col=4)   # centre of board
                r2 = rec.read(corrupted)
                self.assertEqual(board.to_fen(r2), EXPECTED_FEN["e4"],
                                 f"{piece_set}: artifact not rejected")

                # 1…c5 must still be accepted.
                r3 = rec.read(_load(piece_set, "c5"))
                self.assertEqual(board.to_fen(r3), EXPECTED_FEN["c5"])

    def test_highlight_artifact_between_moves_rejected(self):
        """A last-move yellow highlight on start→e4 squares is rejected if early.

        After calibration, we feed a start-position image with e2 and e4
        highlighted (mimicking a UI overlay before the e4 move is in the
        fixture).  The template matcher misreads the highlighted squares; the
        filter must reject the frame and return the starting-position FEN.
        """
        for piece_set in ["wikipedia", "alpha", "merida"]:
            with self.subTest(piece_set=piece_set):
                rec = self._make_and_calibrate(piece_set)

                # Tint e2 (row 6, col 4) and e4 (row 4, col 4) yellow on the
                # start image — this doesn't correspond to any legal move from
                # the starting position.
                start_image = _load(piece_set, "start")
                highlighted = _highlight_squares(
                    start_image, [(6, 4), (4, 4)], color=(220, 220, 60))
                result = rec.read(highlighted)
                self.assertEqual(
                    board.to_fen(result), EXPECTED_FEN["start"],
                    f"{piece_set}: highlight artifact was not rejected",
                )

    def test_multiple_artifacts_then_resume(self):
        """After several artifact frames, the game continues correctly."""
        piece_set = "wikipedia"
        rec = self._make_and_calibrate(piece_set)

        # Feed three artifact frames (cursor in different spots).
        start_image = _load(piece_set, "start")
        for row, col in [(0, 0), (3, 3), (7, 7)]:
            corrupted = _cursor_over_square(start_image, row, col)
            result = rec.read(corrupted)
            self.assertEqual(board.to_fen(result), EXPECTED_FEN["start"])

        # The game should resume normally.
        r = rec.read(_load(piece_set, "e4"))
        self.assertEqual(board.to_fen(r), EXPECTED_FEN["e4"])

        r = rec.read(_load(piece_set, "c5"))
        self.assertEqual(board.to_fen(r), EXPECTED_FEN["c5"])


if __name__ == "__main__":
    unittest.main()
