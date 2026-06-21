"""Dependency-free mock implementations of the interfaces, for testing.

These need no GUI, screen, numpy or OpenCV. ``render_mock_image`` turns a board
map into a synthetic grayscale image where each piece type has a distinct pixel
pattern; ``MockImageBackend`` matches those patterns with the same
normalised-correlation logic as the real backend. Wiring ``MockSetupProvider``
+ ``MockFrameSource`` + a ``TemplateBoardRecognizer`` over these lets the whole
pipeline be exercised on positions evolving over time.
"""

from chesscheat.mocks.mock_setup_provider import MockSetupProvider
from chesscheat.mocks.mock_frame_source import MockFrameSource
from chesscheat.mocks.mock_image_backend import MockImageBackend
from chesscheat.mocks.synthetic_image import render_mock_image, LABELS

__all__ = [
    "MockSetupProvider",
    "MockFrameSource",
    "MockImageBackend",
    "render_mock_image",
    "LABELS",
]
