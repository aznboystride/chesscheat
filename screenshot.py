import numpy as np
from mss import mss

_sct = mss()

def screenshot(x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    """Capture screen region (x1,y1)-(x2,y2), returns BGR numpy array."""
    bbox = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
    return np.array(_sct.grab(bbox))
