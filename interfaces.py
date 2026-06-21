"""Abstract interfaces the application is programmed against.

Concrete implementations live in ``providers.py`` (real GUI / prompt / screen
capture / numpy recognition) and ``mocks.py`` (dependency-free fakes for
testing). The app loop in ``chessboard_state.run`` depends only on these
abstractions, so any combination of real and mock parts can be wired together.
"""

from abc import ABC, abstractmethod


class SetupProvider(ABC):
    """Supplies the user's configuration: which side and the board's box."""

    @abstractmethod
    def select_side(self):
        """Return True if the user plays white, False if black."""

    @abstractmethod
    def select_box(self):
        """Return the board's bounding box as ``(x1, y1, x2, y2)``."""


class FrameSource(ABC):
    """Supplies successive images of the board."""

    @abstractmethod
    def grab(self):
        """Return the next board image.

        May raise ``StopIteration`` to signal that no more frames are
        available (used by finite/mock sources; live sources never stop).
        """


class ImageBackend(ABC):
    """Low-level square operations, abstracting the image representation.

    Splitting these out lets the recognition *algorithm* be shared between a
    real numpy/array backend and a pure-Python mock backend.
    """

    @abstractmethod
    def get_square(self, image, row, col):
        """Crop the (row, col) square's comparable region from an image."""

    @abstractmethod
    def feature(self, patch):
        """Reduce a square crop to a comparable feature vector."""

    @abstractmethod
    def similarity(self, feature_a, feature_b):
        """Return a similarity score between two features (higher = closer)."""


class BoardRecognizer(ABC):
    """Turns board images into a ``{(file_idx, rank): label}`` map."""

    @abstractmethod
    def calibrate(self, image, playing_white):
        """Learn templates from an image of the starting position."""

    @abstractmethod
    def read(self, image):
        """Classify every square of ``image`` into a board map."""
