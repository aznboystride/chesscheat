"""The ``NumpyImageBackend`` image backend."""

from chesscheat.interfaces import ImageBackend


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

    Attributes:
        size: Side length each square is normalised to before matching.
        margin: Fraction trimmed from each side of a square.
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
