"""Dependency-free mock implementations of the interfaces, for testing.

These need no GUI, screen, numpy or OpenCV. ``render_mock_image`` turns a board
map into a synthetic grayscale "image" (a list of lists of ints) where each
piece type has a distinct pixel pattern; ``MockImageBackend`` matches those
patterns with the same normalised-correlation logic as the real backend. Wiring
``MockSetupProvider`` + ``MockFrameSource`` + a ``TemplateBoardRecognizer`` over
these lets the whole pipeline be exercised on positions evolving over time.
"""

import math

import board
from interfaces import SetupProvider, FrameSource, ImageBackend

LABELS = ".PNBRQKpnbrqk"


class MockSetupProvider(SetupProvider):
    """Returns fixed setup values without any UI.

    Attributes:
        _playing_white: The side to report.
        _box: The bounding box to report.
    """

    def __init__(self, playing_white=True, box=(0, 0, 8, 8)):
        """Initialise the mock with canned answers.

        Args:
            playing_white: Value ``select_side`` should return.
            box: Value ``select_box`` should return.
        """
        self._playing_white = playing_white
        self._box = box

    def select_side(self):
        """Return the configured side.

        Returns:
            The ``playing_white`` value passed at construction.
        """
        return self._playing_white

    def select_box(self):
        """Return the configured bounding box.

        Returns:
            The ``box`` tuple passed at construction.
        """
        return self._box


class MockFrameSource(FrameSource):
    """Yields a fixed sequence of frames, then signals exhaustion."""

    def __init__(self, frames):
        """Initialise the source.

        Args:
            frames: An iterable of frames to yield in order.
        """
        self._frames = iter(frames)

    def grab(self):
        """Return the next scripted frame.

        Returns:
            The next frame in the sequence.

        Raises:
            StopIteration: When the sequence is exhausted.
        """
        return next(self._frames)


def _pattern_value(label_index, i, j):
    """Compute a deterministic, label-specific pixel value.

    Pseudo-random per piece so that distinct pieces yield low-correlation
    patterns while identical pieces match exactly.

    Args:
        label_index: Index of the piece label in ``LABELS``.
        i: Row offset within the square.
        j: Column offset within the square.

    Returns:
        An integer pixel value in ``[0, 250]``.
    """
    mixed = (label_index + 1) * 1009 + i * 97 + j * 53 + i * j * (label_index + 1) * 13
    return (mixed * 2654435761) % 251


def render_mock_image(board_map, playing_white, cell=8):
    """Render a board map to a synthetic grayscale image.

    Each square is a ``cell`` x ``cell`` block carrying its piece's pattern,
    plus a small constant tint for the square colour. Because matching is
    brightness-invariant, the tint is ignored -- mirroring how a real piece is
    recognised regardless of the light/dark square it sits on.

    Args:
        board_map: A ``{(file_idx, rank): label}`` map to render.
        playing_white: True to lay the board out from white's perspective,
            False for black's.
        cell: Side length, in pixels, of each square.

    Returns:
        An ``8*cell`` x ``8*cell`` grayscale image as a list of lists of ints.
    """
    n = 8 * cell
    image = [[0] * n for _ in range(n)]
    for row in range(8):
        for col in range(8):
            file_rank = board.square_coord(row, col, playing_white)
            label = board_map.get(file_rank, ".")
            k = LABELS.index(label)
            tint = 6 if board.is_light(*file_rank) else -6
            for i in range(cell):
                for j in range(cell):
                    image[row * cell + i][col * cell + j] = _pattern_value(k, i, j) + tint
    return image


class MockImageBackend(ImageBackend):
    """Pure-Python backend matching synthetic images by normalised correlation.

    Mirrors ``NumpyImageBackend``'s maths on plain lists of ints, so the same
    ``TemplateBoardRecognizer`` algorithm can be tested without numpy.

    Attributes:
        margin: Fraction trimmed from each side of a square before matching.
    """

    def __init__(self, margin=0.0):
        """Initialise the backend.

        Args:
            margin: Fraction trimmed from each side of a square; 0 keeps the
                whole square (synthetic squares have no borders to drop).
        """
        self.margin = margin

    def get_square(self, image, row, col):
        """Crop one square from a synthetic image.

        Args:
            image: A board image as a list of lists of ints.
            row: Screen grid row, 0 at the top.
            col: Screen grid column, 0 at the left.

        Returns:
            The cropped square as a list of lists of ints.
        """
        cell = len(image) // 8
        m = int(cell * self.margin)
        return [r[col * cell + m:(col + 1) * cell - m]
                for r in image[row * cell + m:(row + 1) * cell - m]]

    def feature(self, patch):
        """Reduce a square to a mean-subtracted, unit-normalised vector.

        Args:
            patch: A square crop as a list of lists of ints.

        Returns:
            A tuple of floats; normalising makes ``similarity`` a correlation
            coefficient. A flat patch yields an all-zero tuple.
        """
        flat = [v for r in patch for v in r]
        mean = sum(flat) / len(flat)
        centered = [v - mean for v in flat]
        norm = math.sqrt(sum(v * v for v in centered))
        return tuple(v / norm for v in centered) if norm else tuple(centered)

    def similarity(self, feature_a, feature_b):
        """Return the normalised cross-correlation of two features.

        Args:
            feature_a: A tuple from ``feature``.
            feature_b: Another tuple from ``feature``.

        Returns:
            The dot product as a float; in ``[-1, 1]`` for unit-normalised
            features.
        """
        return sum(x * y for x, y in zip(feature_a, feature_b))
