"""Template-matching board recognition.

``TemplateBoardRecognizer`` implements the recognition algorithm against an
``ImageBackend``; it works identically with the real ``NumpyImageBackend`` and
the pure-Python mock backend used in tests. Calibration captures one template
per square from the starting position (so every piece type and empty square
gets a reference); ``read`` then classifies each square by nearest template.
"""

import board
from interfaces import BoardRecognizer, ImageBackend


class TemplateBoardRecognizer(BoardRecognizer):
    def __init__(self, backend):
        self.backend = backend
        self.playing_white = True
        self.templates = []  # list of (label, feature)

    def calibrate(self, image, playing_white):
        self.playing_white = playing_white
        self.templates = [
            (board.start_label(*board.square_coord(row, col, playing_white)),
             self.backend.feature(self.backend.get_square(image, row, col)))
            for row in range(8) for col in range(8)
        ]

    def read(self, image):
        def classify(row, col):
            feat = self.backend.feature(self.backend.get_square(image, row, col))
            label, _ = max(
                self.templates,
                key=lambda t: self.backend.similarity(feat, t[1]),
            )
            return board.square_coord(row, col, self.playing_white), label

        return dict(classify(row, col)
                    for row in range(8) for col in range(8))


def _resize_nearest(arr, size):
    """Nearest-neighbour resize of a 2-D array to ``size`` x ``size``."""
    import numpy as np

    h, w = arr.shape[:2]
    ys = (np.arange(size) * h) // size
    xs = (np.arange(size) * w) // size
    return arr[ys][:, xs]


class NumpyImageBackend(ImageBackend):
    """Real backend: crops numpy frames and matches by normalised correlation.

    ``feature`` produces a mean-subtracted, unit-normalised grayscale vector,
    so ``similarity`` (a dot product) is the normalised cross-correlation
    coefficient -- equivalent to OpenCV's ``TM_CCOEFF_NORMED`` but numpy-only.
    """

    def __init__(self, size=48, margin=0.12):
        self.size = size
        self.margin = margin

    def get_square(self, image, row, col):
        h, w = image.shape[:2]
        sy, ey = int(row * h / 8), int((row + 1) * h / 8)
        sx, ex = int(col * w / 8), int((col + 1) * w / 8)
        cell = image[sy:ey, sx:ex]
        ch, cw = cell.shape[:2]
        my, mx = int(ch * self.margin), int(cw * self.margin)
        inner = cell[my:ch - my, mx:cw - mx]
        return inner if inner.size else cell

    def feature(self, patch):
        import numpy as np

        arr = np.asarray(patch, dtype=np.float64)
        if arr.ndim == 3:
            arr = arr[..., :3].mean(axis=2)
        arr = _resize_nearest(arr, self.size)
        vec = arr.ravel()
        vec = vec - vec.mean()
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def similarity(self, feature_a, feature_b):
        import numpy as np

        return float(np.dot(feature_a, feature_b))
