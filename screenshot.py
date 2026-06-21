"""Fast screen capture backed by a single reused ``mss`` instance."""

import numpy as np
from mss import mss

# One module-level mss instance reused across calls -- recreating it per call
# is the main thing that would slow capture down.
_sct = mss()


def screenshot(x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    """Capture a rectangular screen region.

    Args:
        x1: Left edge, in screen pixels.
        y1: Top edge, in screen pixels.
        x2: Right edge, in screen pixels.
        y2: Bottom edge, in screen pixels.

    Returns:
        A BGRA numpy array of the captured region.
    """
    bbox = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
    return np.array(_sct.grab(bbox))
