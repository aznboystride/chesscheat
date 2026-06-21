"""The ``ScreenFrameSource`` frame source."""

from chesscheat.interfaces import FrameSource


class ScreenFrameSource(FrameSource):
    """Live screen capture of the board's bounding box.

    Attributes:
        box: The ``(x1, y1, x2, y2)`` screen region to capture.
    """

    def __init__(self, box):
        """Initialise the capture source.

        Args:
            box: The board's ``(x1, y1, x2, y2)`` bounding box.
        """
        self.box = box

    def grab(self):
        """Capture the board region once.

        Returns:
            A BGRA numpy array of the board's bounding box.
        """
        from chesscheat.capture import screenshot
        return screenshot(*self.box)
