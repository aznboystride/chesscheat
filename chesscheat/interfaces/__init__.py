"""Abstract interfaces the application is programmed against.

Concrete implementations live in the ``providers``, ``recognition`` and
``capture`` packages (real) and ``mocks`` (dependency-free fakes). The app loop
in ``chesscheat.app.run`` depends only on these abstractions, so any
combination of real and mock parts can be wired together.
"""

from chesscheat.interfaces.setup_provider import SetupProvider
from chesscheat.interfaces.frame_source import FrameSource
from chesscheat.interfaces.image_backend import ImageBackend
from chesscheat.interfaces.board_recognizer import BoardRecognizer

__all__ = ["SetupProvider", "FrameSource", "ImageBackend", "BoardRecognizer"]
