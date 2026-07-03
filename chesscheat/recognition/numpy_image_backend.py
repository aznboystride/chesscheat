"""The ``NumpyImageBackend`` image backend."""

from chesscheat.interfaces import ImageBackend


def _resize_nearest(arr, size):
    """Resize an array's first two dimensions via nearest-neighbour sampling.

    Args:
        arr: A 2-D or 3-D numpy array.
        size: Target side length, in pixels.

    Returns:
        A ``size`` x ``size`` (x channels) numpy array sampled from ``arr``.
    """
    import numpy as np

    h, w = arr.shape[:2]
    ys = (np.arange(size) * h) // size
    xs = (np.arange(size) * w) // size
    return arr[ys][:, xs]


class NumpyImageBackend(ImageBackend):
    """Real backend: matches squares by the shape and colour of pieces only.

    The square's own colour is deliberately ignored, because chess UIs tint
    squares (selection and last-move highlights) and that must not throw off
    tracking. Each square is **canonicalised against its own background**
    before matching:

    - the background colour is estimated per patch as the median colour of
      the patch's border ring (pieces sit centred, so the ring is background
      -- highlighted or not);
    - pixels close to that colour are background and are repainted to a
      constant mid-grey; the remaining pixels are the piece, kept as-is.

    Whatever colour the square is -- its calibrated colour or an arbitrary
    highlight -- the canonical patch looks the same, so a highlighted square
    matches the template learned from a clean one.

    A canonical square's feature is a ``(shape, mean, coverage)`` triple:

    - ``shape``: the mean-subtracted, unit-normalised grayscale canonical
      patch, so its dot product is the normalised cross-correlation
      coefficient (OpenCV's ``TM_CCOEFF_NORMED``, numpy-only -- **no cv2**);
      it captures the piece's shape and internal texture.
    - ``mean``: the canonical patch's average brightness, separating light
      pieces from dark ones.
    - ``coverage``: the fraction of piece (non-background) pixels, which
      cleanly separates empty squares (near zero) from occupied ones without
      referring to the square's colour at all.

    ``similarity`` combines the three: correlation plus ``brightness_weight``
    times brightness closeness plus ``coverage_weight`` times coverage
    closeness.

    Attributes:
        size: Side length each square is normalised to before matching.
        margin: Fraction trimmed from each side of a square.
        brightness_weight: Weight of the brightness term in ``similarity``.
        coverage_weight: Weight of the coverage term in ``similarity``.
        background_tol: Max per-pixel colour distance to the estimated
            background for a pixel to count as background.
        recolor_tol: Max per-pixel colour distance to ``from_empty`` for a
            pixel to count as background in ``recolor``.
    """

    _CANONICAL_BG = 127.0  # grey background pixels are repainted to

    def __init__(self, size=48, margin=0.12, brightness_weight=0.5,
                 coverage_weight=0.5, background_tol=40, recolor_tol=40):
        """Initialise the backend.

        Args:
            size: Side length each square is normalised to before matching.
            margin: Fraction trimmed from each side of a square to drop
                borders and coordinate labels.
            brightness_weight: Weight of the brightness-closeness term
                relative to the shape-correlation term in ``similarity``.
            coverage_weight: Weight of the coverage-closeness term relative
                to the shape-correlation term in ``similarity``.
            background_tol: Max per-pixel colour distance (summed over
                channels) to the border-estimated background for a pixel to
                be canonicalised away as background.
            recolor_tol: Max per-pixel colour distance to ``from_empty`` for
                a pixel to count as background in ``recolor``.
        """
        self.size = size
        self.margin = margin
        self.brightness_weight = brightness_weight
        self.coverage_weight = coverage_weight
        self.background_tol = background_tol
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

    def _canonicalise(self, patch):
        """Separate a patch into piece pixels and background.

        Args:
            patch: A square crop from ``get_square`` (grayscale or colour).

        Returns:
            A ``(canonical, coverage)`` pair: ``canonical`` is the resized
            grayscale patch with background pixels repainted to a constant
            grey, and ``coverage`` is the fraction of piece pixels.
        """
        import numpy as np

        arr = np.asarray(patch, dtype=np.float64)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        arr = _resize_nearest(arr[..., :3], self.size)

        ring = max(1, self.size // 10)
        border = np.concatenate([
            arr[:ring].reshape(-1, 3), arr[-ring:].reshape(-1, 3),
            arr[:, :ring].reshape(-1, 3), arr[:, -ring:].reshape(-1, 3),
        ])
        background = np.median(border, axis=0)

        is_piece = np.abs(arr - background).sum(axis=-1) > self.background_tol
        gray = arr.mean(axis=-1)
        canonical = np.where(is_piece, gray, self._CANONICAL_BG)
        return canonical, float(is_piece.mean())

    def feature(self, patch):
        """Reduce a square to a background-independent feature.

        Args:
            patch: A square crop from ``get_square`` (grayscale or colour).

        Returns:
            A ``(shape, mean, coverage)`` triple: ``shape`` is a
            unit-normalised, mean-subtracted numpy vector of the canonicalised
            patch (the zero vector for an empty square); ``mean`` is its
            average intensity scaled to ``[0, 1]``; ``coverage`` is the
            fraction of piece pixels.
        """
        import numpy as np

        canonical, coverage = self._canonicalise(patch)
        vec = canonical.ravel()
        centered = vec - vec.mean()
        norm = np.linalg.norm(centered)
        shape = centered / norm if norm else centered
        return shape, vec.mean() / 255.0, coverage

    def similarity(self, feature_a, feature_b):
        """Score two features by shape, brightness and coverage closeness.

        Args:
            feature_a: A ``(shape, mean, coverage)`` triple from ``feature``.
            feature_b: Another ``(shape, mean, coverage)`` triple.

        Returns:
            ``corr + brightness_weight * (1 - |mean_a - mean_b|) +
            coverage_weight * (1 - |coverage_a - coverage_b|)`` as a float,
            where ``corr`` is the dot product of the shape vectors.
        """
        import numpy as np

        shape_a, mean_a, coverage_a = feature_a
        shape_b, mean_b, coverage_b = feature_b
        corr = float(np.dot(shape_a, shape_b))
        return (corr
                + self.brightness_weight * (1.0 - abs(mean_a - mean_b))
                + self.coverage_weight * (1.0 - abs(coverage_a - coverage_b)))

    def recolor(self, patch, from_empty, to_empty):
        """Repaint background pixels from one empty colour to another.

        The empty crops are assumed near-uniform (assumption: a colour's empty
        squares look identical), so their average colour stands in for the
        whole square. Pixels of ``patch`` within ``recolor_tol`` of the source
        colour are repainted with the target colour; the rest (the piece) are
        kept. Shape-independent, so it tolerates squares differing by a pixel.

        With background canonicalisation the synthesised template's feature is
        (by design) nearly identical to the original's; ``recolor`` is kept so
        every piece still has a template under both colour keys.

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
