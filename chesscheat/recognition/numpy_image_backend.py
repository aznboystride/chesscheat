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
    """Real backend: SSIM matching on the shape and colour of pieces only.

    The square's own colour is deliberately ignored, because chess UIs tint
    squares (selection and last-move highlights) and that must not throw off
    the evaluation. Each square is **canonicalised against its own
    background** before matching:

    - the background colour is estimated per patch as the median colour of
      the patch's border ring (pieces sit centred, so the ring is background
      -- highlighted or not);
    - background pixels are repainted to a constant mid-grey; the remaining
      (piece) pixels keep their true colours.

    Whatever colour the square is -- its calibrated colour or an arbitrary
    highlight -- the canonical patch looks the same, so a highlighted square
    matches the template learned from a clean one.

    ``similarity`` is the **structural similarity index (SSIM)** between two
    canonical patches, computed per RGB channel (global window) and averaged
    across channels. Working in colour makes the score sensitive to the
    piece's colour as well as its shape: a white pawn and a black pawn share
    a silhouette but differ in channel intensities, so their SSIM is low.
    Two empty squares canonicalise to identical flat grey and score 1.0.
    Scores are in ``[-1, 1]`` with 1.0 a perfect match, which gives
    ``TemplateBoardRecognizer.match_threshold`` a meaningful scale.

    Attributes:
        size: Side length each square is normalised to before matching.
        margin: Fraction trimmed from each side of a square.
        background_tol: Max per-pixel colour distance to the estimated
            background for a pixel to count as background.
        recolor_tol: Max per-pixel colour distance to ``from_empty`` for a
            pixel to count as background in ``recolor``.
    """

    _CANONICAL_BG = 127.0     # grey that background pixels are repainted to
    _C1 = (0.01 * 255) ** 2   # standard SSIM stabilising constants
    _C2 = (0.03 * 255) ** 2

    def __init__(self, size=48, margin=0.12, background_tol=40,
                 recolor_tol=40):
        """Initialise the backend.

        Args:
            size: Side length each square is normalised to before matching.
            margin: Fraction trimmed from each side of a square to drop
                borders and coordinate labels.
            background_tol: Max per-pixel colour distance (summed over
                channels) to the border-estimated background for a pixel to
                be canonicalised away as background.
            recolor_tol: Max per-pixel colour distance to ``from_empty`` for
                a pixel to count as background in ``recolor``.
        """
        self.size = size
        self.margin = margin
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
        """Repaint a patch's background to a constant grey, keeping the piece.

        Args:
            patch: A square crop from ``get_square`` (grayscale or colour).

        Returns:
            The resized colour patch with background pixels repainted, as a
            ``(size, size, 3)`` float array.
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
        return np.where(is_piece[..., None], arr, self._CANONICAL_BG)

    def feature(self, patch):
        """Reduce a square to a background-independent feature.

        Args:
            patch: A square crop from ``get_square`` (grayscale or colour).

        Returns:
            A ``(canonical, mean, variance)`` triple: the canonicalised
            colour patch plus its per-channel mean and variance, precomputed
            for the SSIM in ``similarity``.
        """
        canonical = self._canonicalise(patch)
        flat = canonical.reshape(-1, 3)
        return canonical, flat.mean(axis=0), flat.var(axis=0)

    def similarity(self, feature_a, feature_b):
        """Return the channel-averaged SSIM of two canonical patches.

        Args:
            feature_a: A ``(canonical, mean, variance)`` triple from
                ``feature``.
            feature_b: Another such triple.

        Returns:
            The mean over RGB channels of the global-window SSIM, as a float
            in ``[-1, 1]``; 1.0 is a perfect match. Colour differences lower
            the score, so piece colour is part of the match.
        """
        patch_a, mu_a, var_a = feature_a
        patch_b, mu_b, var_b = feature_b
        cov = (patch_a * patch_b).reshape(-1, 3).mean(axis=0) - mu_a * mu_b
        ssim = (((2 * mu_a * mu_b + self._C1) * (2 * cov + self._C2))
                / ((mu_a ** 2 + mu_b ** 2 + self._C1)
                   * (var_a + var_b + self._C2)))
        return float(ssim.mean())

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
