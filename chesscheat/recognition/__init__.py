"""Template-matching board recognition.

The recognition algorithm (``TemplateBoardRecognizer``) is decoupled from the
image representation (``ImageBackend``); ``NumpyImageBackend`` is the real
backend, and ``chesscheat.mocks`` provides a pure-Python one. ``scan_squares``
summarises each square's background, occupancy and brightness without
identifying pieces (used to read last-move highlights in mirror mode).
"""

from chesscheat.recognition.template_board_recognizer import TemplateBoardRecognizer
from chesscheat.recognition.numpy_image_backend import NumpyImageBackend
from chesscheat.recognition.legal_move_filter import LegalMoveFilter
from chesscheat.recognition.square_scan import scan_squares, scan_square

__all__ = ["TemplateBoardRecognizer", "NumpyImageBackend", "LegalMoveFilter",
           "scan_squares", "scan_square"]
