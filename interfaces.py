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
        """Ask which side the user is playing.

        Returns:
            True if the user plays white, False if black.
        """

    @abstractmethod
    def select_box(self):
        """Ask for the board's screen region.

        Returns:
            The bounding box as an ``(x1, y1, x2, y2)`` tuple of absolute
            screen coordinates (top-left and bottom-right).
        """


class FrameSource(ABC):
    """Supplies successive images of the board."""

    @abstractmethod
    def grab(self):
        """Return the next board image.

        Returns:
            An image of the board, in whatever representation the paired
            ``ImageBackend`` expects.

        Raises:
            StopIteration: If no more frames are available. Used by
                finite/mock sources; live sources never stop.
        """


class ImageBackend(ABC):
    """Low-level square operations, abstracting the image representation.

    Splitting these out lets the recognition *algorithm* be shared between a
    real numpy/array backend and a pure-Python mock backend.
    """

    @abstractmethod
    def get_square(self, image, row, col):
        """Crop one square's comparable region from a board image.

        Args:
            image: A full board image from a ``FrameSource``.
            row: Screen grid row, 0 at the top.
            col: Screen grid column, 0 at the left.

        Returns:
            The cropped square region, in the backend's image representation.
        """

    @abstractmethod
    def feature(self, patch):
        """Reduce a square crop to a comparable feature.

        Args:
            patch: A square region from ``get_square``.

        Returns:
            A feature value comparable via ``similarity``.
        """

    @abstractmethod
    def similarity(self, feature_a, feature_b):
        """Score how alike two features are.

        Args:
            feature_a: A feature from ``feature``.
            feature_b: Another feature from ``feature``.

        Returns:
            A similarity score where higher means more alike.
        """


class BoardRecognizer(ABC):
    """Turns board images into a ``{(file_idx, rank): label}`` map."""

    @abstractmethod
    def calibrate(self, image, playing_white):
        """Learn piece templates from an image of the starting position.

        Args:
            image: A board image showing the standard starting position.
            playing_white: True if the board is shown from white's
                perspective, False for black's.
        """

    @abstractmethod
    def read(self, image):
        """Classify every square of an image into a board map.

        Args:
            image: A board image to recognise.

        Returns:
            A ``{(file_idx, rank): label}`` map of all 64 squares.
        """
