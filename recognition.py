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
    """Recognise a board by matching squares against calibrated templates.

    Attributes:
        backend: The ``ImageBackend`` used for cropping and matching.
        playing_white: Perspective captured at calibration time.
        templates: List of ``(label, feature)`` pairs, one per starting square.
    """

    def __init__(self, backend):
        """Initialise the recognizer.

        Args:
            backend: An ``ImageBackend`` implementation used to crop squares
                and score template similarity.
        """
        self.backend = backend
        self.playing_white = True
        self.templates = []  # list of (label, feature)

    def calibrate(self, image, playing_white):
        """Capture one template per square from the starting position.

        Every piece type and empty square appears in the starting position, so
        this yields a reference feature for each.

        Args:
            image: A board image showing the standard starting position.
            playing_white: True if the board is shown from white's
                perspective, False for black's.
        """
        self.playing_white = playing_white
        self.templates = [
            (board.start_label(*board.square_coord(row, col, playing_white)),
             self.backend.feature(self.backend.get_square(image, row, col)))
            for row in range(8) for col in range(8)
        ]

    def read(self, image):
        """Classify every square of an image by nearest calibrated template.

        Args:
            image: A board image to recognise.

        Returns:
            A ``{(file_idx, rank): label}`` map of all 64 squares.
        """
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
    """Resize a 2-D array to a square via nearest-neighbour sampling.

    Args:
        arr: A 2-D numpy array.
        size: Target side length, in pixels.

    Returns:
        A ``size`` x ``size`` numpy array sampled from ``arr``.
    """
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
        """Initialise the backend.

        Args:
            size: Side length each square is normalised to before matching.
            margin: Fraction trimmed from each side of a square to drop
                borders and coordinate labels.
        """
        self.size = size
        self.margin = margin

    def get_square(self, image, row, col):
        """Crop the inner region of one square from a numpy board image.

        Args:
            image: A full board image as an ``(H, W, ...)`` numpy array.
            row: Screen grid row, 0 at the top.
            col: Screen grid column, 0 at the left.

        Returns:
            The cropped, margin-trimmed square as a numpy array.
        """
        h, w = image.shape[:2]
        sy, ey = int(row * h / 8), int((row + 1) * h / 8)
        sx, ex = int(col * w / 8), int((col + 1) * w / 8)
        cell = image[sy:ey, sx:ex]
        ch, cw = cell.shape[:2]
        my, mx = int(ch * self.margin), int(cw * self.margin)
        inner = cell[my:ch - my, mx:cw - mx]
        return inner if inner.size else cell

    def feature(self, patch):
        """Reduce a square to a mean-subtracted, unit-normalised vector.

        Args:
            patch: A square crop from ``get_square`` (grayscale or colour).

        Returns:
            A 1-D numpy vector; normalising here makes ``similarity`` a
            correlation coefficient. A flat patch yields the zero vector.
        """
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
        """Return the normalised cross-correlation of two features.

        Args:
            feature_a: A vector from ``feature``.
            feature_b: Another vector from ``feature``.

        Returns:
            The dot product as a float; since features are unit-normalised
            this is the correlation coefficient in ``[-1, 1]``.
        """
        import numpy as np

        return float(np.dot(feature_a, feature_b))
