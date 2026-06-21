"""The ``SetupProvider`` interface."""

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
