"""Template-matching board recognition.

The recognition algorithm (``TemplateBoardRecognizer``) is decoupled from the
image representation (``ImageBackend``); ``NumpyImageBackend`` is the real
backend, and ``chesscheat.mocks`` provides a pure-Python one.
"""

from chesscheat.recognition.template_board_recognizer import TemplateBoardRecognizer
from chesscheat.recognition.numpy_image_backend import NumpyImageBackend

__all__ = ["TemplateBoardRecognizer", "NumpyImageBackend"]
