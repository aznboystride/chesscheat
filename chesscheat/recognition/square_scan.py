"""Per-square colour statistics of a board image (``scan_squares``).

A lightweight companion to template matching for questions that need no
piece identities: *which squares are tinted* (last-move highlights) and
*is there a piece on a square, and how bright is it*. Each square is
summarised by its background colour (the median of the margin-trimmed
patch's four corner blocks, which even large pieces leave clear), the
fraction of pixels
that differ from that background (the piece, if any) and those pixels'
mean brightness. numpy is imported lazily so the module stays importable
without it.
"""


def scan_square(patch, background_tol=60, corner=0.2):
    """Summarise one square patch.

    Args:
        patch: A square crop as an ``(h, w, channels)`` or ``(h, w)`` numpy
            array (any channel order; only consistency matters).
        background_tol: Max per-pixel colour distance (summed over channels)
            to the estimated background for a pixel to count as background
            rather than piece.
        corner: Side of the four corner blocks, as a fraction of the patch
            side, whose pixels estimate the background (pieces are centred
            and rarely reach the corners, unlike a full border ring).

    Returns:
        A ``(background, piece_fraction, piece_brightness)`` triple: the
        background colour as a tuple of floats, the fraction of pixels that
        are not background, and the mean channel value of those pixels (None
        when there are none).
    """
    import numpy as np

    arr = np.asarray(patch, dtype=np.float64)
    if arr.ndim == 2:
        arr = arr[..., None]
    arr = arr[..., :3]
    h, w = arr.shape[:2]
    k = max(1, int(min(h, w) * corner))
    channels = arr.shape[-1]
    corners = np.concatenate([
        arr[:k, :k].reshape(-1, channels), arr[:k, -k:].reshape(-1, channels),
        arr[-k:, :k].reshape(-1, channels), arr[-k:, -k:].reshape(-1, channels),
    ])
    background = np.median(corners, axis=0)
    is_piece = np.abs(arr - background).sum(axis=-1) > background_tol
    fraction = float(is_piece.mean())
    brightness = (float(arr[is_piece].mean()) if is_piece.any() else None)
    return tuple(float(c) for c in background), fraction, brightness


def scan_squares(image, margin=0.12, background_tol=60):
    """Summarise all 64 squares of a board image.

    Args:
        image: The full board as an ``(H, W, ...)`` numpy array (BGRA
            straight from capture is fine).
        margin: Fraction trimmed from each side of a square before
            measuring, dropping borders and coordinate labels.
        background_tol: See ``scan_square``.

    Returns:
        A ``{(row, col): (background, piece_fraction, piece_brightness)}``
        dict over the screen grid (row 0 at the top, col 0 at the left).
    """
    from chesscheat.recognition.numpy_image_backend import NumpyImageBackend

    backend = NumpyImageBackend(margin=margin)
    return {(row, col): scan_square(backend.get_square(image, row, col),
                                    background_tol)
            for row in range(8) for col in range(8)}
