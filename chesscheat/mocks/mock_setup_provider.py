"""The ``MockSetupProvider`` setup provider."""

from chesscheat.interfaces import SetupProvider


class MockSetupProvider(SetupProvider):
    """Returns fixed setup values without any UI.

    Attributes:
        _playing_white: The side to report.
        _box: The bounding box to report.
    """

    def __init__(self, playing_white=True, box=(0, 0, 8, 8)):
        """Initialise the mock with canned answers.

        Args:
            playing_white: Value ``select_side`` should return.
            box: Value ``select_box`` should return.
        """
        self._playing_white = playing_white
        self._box = box

    def select_side(self):
        """Return the configured side.

        Returns:
            The ``playing_white`` value passed at construction.
        """
        return self._playing_white

    def select_box(self):
        """Return the configured bounding box.

        Returns:
            The ``box`` tuple passed at construction.
        """
        return self._box
