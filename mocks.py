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
    def __init__(self, playing_white=True, box=(0, 0, 8, 8)):
        self._playing_white = playing_white
        self._box = box

    def select_side(self):
        return self._playing_white

    def select_box(self):
        return self._box


class MockFrameSource(FrameSource):
    """Yields a fixed sequence of frames, then raises ``StopIteration``."""

    def __init__(self, frames):
        self._frames = iter(frames)

    def grab(self):
        return next(self._frames)


def _pattern_value(label_index, i, j):
    """A deterministic, label-specific pixel value (pseudo-random per piece)."""
    mixed = (label_index + 1) * 1009 + i * 97 + j * 53 + i * j * (label_index + 1) * 13
    return (mixed * 2654435761) % 251


def render_mock_image(board_map, playing_white, cell=8):
    """Render a board map to a synthetic grayscale image.

    Each square is a ``cell`` x ``cell`` block carrying its piece's pattern,
    plus a small constant tint for the square colour. Because matching is
    brightness-invariant, the tint is ignored -- mirroring how a real piece is
    recognised regardless of the light/dark square it sits on.
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
    """Pure-Python backend matching synthetic images by normalised correlation."""

    def __init__(self, margin=0.0):
        self.margin = margin

    def get_square(self, image, row, col):
        cell = len(image) // 8
        m = int(cell * self.margin)
        return [r[col * cell + m:(col + 1) * cell - m]
                for r in image[row * cell + m:(row + 1) * cell - m]]

    def feature(self, patch):
        flat = [v for r in patch for v in r]
        mean = sum(flat) / len(flat)
        centered = [v - mean for v in flat]
        norm = math.sqrt(sum(v * v for v in centered))
        return tuple(v / norm for v in centered) if norm else tuple(centered)

    def similarity(self, feature_a, feature_b):
        return sum(x * y for x, y in zip(feature_a, feature_b))
