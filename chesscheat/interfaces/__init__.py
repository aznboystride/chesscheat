"""Abstract interfaces the application is programmed against.

Concrete implementations live in the ``providers``, ``recognition``,
``capture`` and ``assist`` packages (real) and ``mocks`` (dependency-free
fakes). The app loop in ``chesscheat.app.run`` depends only on these
abstractions, so any combination of real and mock parts can be wired together.
"""

from chesscheat.interfaces.setup_provider import SetupProvider
from chesscheat.interfaces.frame_source import FrameSource
from chesscheat.interfaces.image_backend import ImageBackend
from chesscheat.interfaces.board_recognizer import BoardRecognizer
from chesscheat.interfaces.move_engine import MoveEngine
from chesscheat.interfaces.move_actuator import MoveActuator
from chesscheat.interfaces.move_trigger import MoveTrigger

__all__ = ["SetupProvider", "FrameSource", "ImageBackend", "BoardRecognizer",
           "MoveEngine", "MoveActuator", "MoveTrigger"]
