"""The ``BoardRecognizer`` interface."""

from abc import ABC, abstractmethod


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
