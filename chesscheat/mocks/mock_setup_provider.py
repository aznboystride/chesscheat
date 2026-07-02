"""The ``MockSetupProvider`` setup provider."""

from chesscheat.interfaces import SetupProvider


class MockSetupProvider(SetupProvider):
    """Returns fixed setup values without any UI.

    Also records how it was used (how many boxes were requested, which images
    were shown for confirmation) so tests can assert on the setup flow.

    Attributes:
        box_requests: Number of times ``select_box`` was called.
        confirmed_images: The images passed to ``confirm_box``, in order.
    """

    def __init__(self, playing_white=True, box=(0, 0, 8, 8),
                 confirmations=None):
        """Initialise the mock with canned answers.

        Args:
            playing_white: Value ``select_side`` should return.
            box: Value ``select_box`` should return.
            confirmations: Optional iterable of booleans that ``confirm_box``
                returns in order; once exhausted (or when None), it confirms.
        """
        self._playing_white = playing_white
        self._box = box
        self._confirmations = iter(confirmations or [])
        self.box_requests = 0
        self.confirmed_images = []

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
        self.box_requests += 1
        return self._box

    def confirm_box(self, image):
        """Return the next scripted confirmation (or True when exhausted).

        Args:
            image: The captured frame; recorded in ``confirmed_images``.

        Returns:
            The next boolean from ``confirmations``, or True once exhausted.
        """
        self.confirmed_images.append(image)
        return next(self._confirmations, True)
