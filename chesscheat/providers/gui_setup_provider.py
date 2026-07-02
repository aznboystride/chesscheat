"""The ``GuiSetupProvider`` setup provider."""

from chesscheat.interfaces import SetupProvider


class GuiSetupProvider(SetupProvider):
    """Tkinter GUI: button dialog for the side, overlay for the corners."""

    def select_side(self):
        """Show the White/Black button dialog.

        Returns:
            True if the user clicks White, False for Black.

        Raises:
            SystemExit: If the user cancels the dialog.
        """
        from chesscheat.gui import dialogs
        return dialogs.select_side()

    def select_box(self):
        """Show the fullscreen crosshair overlay to pick two corners.

        Returns:
            The bounding box as an ``(x1, y1, x2, y2)`` tuple of screen
            coordinates.

        Raises:
            SystemExit: If the user cancels the overlay.
        """
        from chesscheat.gui import dialogs
        return dialogs.select_box()

    def confirm_box(self, image):
        """Show the captured region with Looks good / Reselect buttons.

        Args:
            image: The frame captured from the selected bounding box.

        Returns:
            True if the user confirms the capture, False to reselect.

        Raises:
            SystemExit: If the user cancels the dialog.
        """
        from chesscheat.gui import dialogs
        return dialogs.confirm_box(image)
