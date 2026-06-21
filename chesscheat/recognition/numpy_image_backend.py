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
    """Real backend: crops numpy frames and matches squares by similarity.

    Each square's feature is a pair ``(shape, mean)``:

    - ``shape`` is the mean-subtracted, unit-normalised grayscale patch, so its
      dot product is the normalised cross-correlation coefficient (OpenCV's
      ``TM_CCOEFF_NORMED``). Removing the mean makes piece matching robust to a
      piece sitting on a different-coloured square than its calibration square.
    - ``mean`` is the average brightness, which keeps *flat* squares
      distinguishable: with the mean removed a flat (empty) square would be the
      zero vector and correlate with nothing, so empty light/dark squares are
      told apart -- and from pieces -- by brightness instead.

    ``similarity`` combines the two: correlation plus ``brightness_weight``
    times brightness closeness.

    Attributes:
        size: Side length each square is normalised to before matching.
        margin: Fraction trimmed from each side of a square.
        brightness_weight: Weight of the brightness term in ``similarity``.
    """

    def __init__(self, size=48, margin=0.12, brightness_weight=0.5,
                 recolor_tol=40):
        """Initialise the backend.

        Args:
            size: Side length each square is normalised to before matching.
            margin: Fraction trimmed from each side of a square to drop
                borders and coordinate labels.
            brightness_weight: Weight of the brightness-closeness term relative
                to the shape-correlation term in ``similarity``.
            recolor_tol: Max per-pixel colour distance to ``from_empty`` for a
                pixel to count as background in ``recolor``.
        """
        self.size = size
        self.margin = margin
        self.brightness_weight = brightness_weight
        self.recolor_tol = recolor_tol

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
        """Reduce a square to a ``(shape, mean)`` feature.

        Args:
            patch: A square crop from ``get_square`` (grayscale or colour).

        Returns:
            A ``(shape, mean)`` tuple: ``shape`` is a unit-normalised,
            mean-subtracted numpy vector (the zero vector for a flat patch);
            ``mean`` is the average intensity scaled to ``[0, 1]``.
        """
        import numpy as np

        arr = np.asarray(patch, dtype=np.float64)
        if arr.ndim == 3:
            arr = arr[..., :3].mean(axis=2)
        arr = _resize_nearest(arr, self.size)
        vec = arr.ravel()
        centered = vec - vec.mean()
        norm = np.linalg.norm(centered)
        shape = centered / norm if norm else centered
        return shape, vec.mean() / 255.0

    def similarity(self, feature_a, feature_b):
        """Score two features by shape correlation plus brightness closeness.

        Args:
            feature_a: A ``(shape, mean)`` tuple from ``feature``.
            feature_b: Another ``(shape, mean)`` tuple from ``feature``.

        Returns:
            ``corr + brightness_weight * (1 - |mean_a - mean_b|)`` as a float,
            where ``corr`` is the dot product of the shape vectors.
        """
        import numpy as np

        shape_a, mean_a = feature_a
        shape_b, mean_b = feature_b
        corr = float(np.dot(shape_a, shape_b))
        return corr + self.brightness_weight * (1.0 - abs(mean_a - mean_b))

    def recolor(self, patch, from_empty, to_empty):
        """Repaint background pixels from one empty colour to another.

        The empty crops are assumed near-uniform (assumption: a colour's empty
        squares look identical), so their average colour stands in for the
        whole square. Pixels of ``patch`` within ``recolor_tol`` of the source
        colour are repainted with the target colour; the rest (the piece) are
        kept. Shape-independent, so it tolerates squares differing by a pixel.

        Args:
            patch: A square crop with a piece on a ``from_empty`` square.
            from_empty: A crop of an empty square of the current colour.
            to_empty: A crop of an empty square of the target colour.

        Returns:
            A numpy array like ``patch`` with the background repainted.
        """
        import numpy as np

        arr = np.asarray(patch, dtype=np.int64)
        from_color = np.asarray(from_empty, dtype=np.float64).reshape(
            -1, arr.shape[-1]).mean(axis=0) if arr.ndim == 3 else \
            float(np.asarray(from_empty, dtype=np.float64).mean())
        to_color = np.asarray(to_empty, dtype=np.float64).reshape(
            -1, arr.shape[-1]).mean(axis=0) if arr.ndim == 3 else \
            float(np.asarray(to_empty, dtype=np.float64).mean())

        out = arr.copy()
        if arr.ndim == 3:
            mask = np.abs(arr - from_color).sum(axis=-1) <= self.recolor_tol
            out[mask] = np.round(to_color).astype(np.int64)
        else:
            mask = np.abs(arr - from_color) <= self.recolor_tol
            out[mask] = int(round(to_color))
        return out
