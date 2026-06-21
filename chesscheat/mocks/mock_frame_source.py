"""The ``MockFrameSource`` frame source."""

from chesscheat.interfaces import FrameSource


class MockFrameSource(FrameSource):
    """Yields a fixed sequence of frames, then signals exhaustion."""

    def __init__(self, frames):
        """Initialise the source.

        Args:
            frames: An iterable of frames to yield in order.
        """
        self._frames = iter(frames)

    def grab(self):
        """Return the next scripted frame.

        Returns:
            The next frame in the sequence.

        Raises:
            StopIteration: When the sequence is exhausted.
        """
        return next(self._frames)
