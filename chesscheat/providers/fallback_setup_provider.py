"""The ``FallbackSetupProvider`` setup provider."""

from chesscheat.interfaces import SetupProvider


class FallbackSetupProvider(SetupProvider):
    """Use ``primary``; on any (non-cancel) error fall back to ``secondary``.

    A user cancelling the GUI raises ``SystemExit`` (not ``Exception``), which
    propagates so cancelling quits rather than silently dropping to prompts.

    Attributes:
        primary: The preferred ``SetupProvider``.
        secondary: The provider used when ``primary`` raises.
    """

    def __init__(self, primary, secondary):
        """Initialise the fallback wrapper.

        Args:
            primary: The preferred ``SetupProvider`` (e.g. the GUI).
            secondary: The provider used if ``primary`` raises (e.g. prompts).
        """
        self.primary = primary
        self.secondary = secondary

    def _try(self, method, *args):
        """Call ``method`` on the primary provider, else on the secondary.

        Args:
            method: Name of the ``SetupProvider`` method to invoke.
            *args: Positional arguments forwarded to the method.

        Returns:
            The primary provider's result, or the secondary's if the primary
            raised an ``Exception``.

        Raises:
            SystemExit: Propagated from the primary (e.g. a GUI cancel) so that
                cancelling quits rather than falling back to prompts.
        """
        try:
            return getattr(self.primary, method)(*args)
        except Exception as exc:
            print(f"GUI unavailable ({exc}); using text prompt.")
            return getattr(self.secondary, method)(*args)

    def select_side(self):
        """Select the side via the primary provider, else the secondary.

        Returns:
            True for white, False for black.
        """
        return self._try("select_side")

    def select_box(self):
        """Select the box via the primary provider, else the secondary.

        Returns:
            The bounding box as ``(x1, y1, x2, y2)``.
        """
        return self._try("select_box")

    def confirm_box(self, image, playing_white=True):
        """Confirm the capture via the primary provider, else the secondary.

        Args:
            image: The frame captured from the selected bounding box.
            playing_white: The side the user picked, forwarded for the
                annotation orientation.

        Returns:
            True to proceed with this region, False to select it again.
        """
        return self._try("confirm_box", image, playing_white)
