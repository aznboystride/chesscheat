"""The ``FrameSource`` interface."""

from abc import ABC, abstractmethod


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
