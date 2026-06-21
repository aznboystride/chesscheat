"""Real (production) implementations of the setup and frame-source interfaces.

Heavy/optional dependencies (tkinter via ``gui``, ``screenshot``) are imported
lazily inside the methods so importing this module stays cheap and safe.
"""

from interfaces import SetupProvider, FrameSource


class GuiSetupProvider(SetupProvider):
    """Tkinter GUI: button dialog for the side, overlay for the corners."""

    def select_side(self):
        """Show the White/Black button dialog.

        Returns:
            True if the user clicks White, False for Black.

        Raises:
            SystemExit: If the user cancels the dialog.
        """
        import gui
        return gui.select_side()

    def select_box(self):
        """Show the fullscreen crosshair overlay to pick two corners.

        Returns:
            The bounding box as an ``(x1, y1, x2, y2)`` tuple of screen
            coordinates.

        Raises:
            SystemExit: If the user cancels the overlay.
        """
        import gui
        return gui.select_box()


class PromptSetupProvider(SetupProvider):
    """Plain text prompts on stdin/stdout."""

    def select_side(self):
        """Prompt for the side on stdin, repeating until valid.

        Returns:
            True for white, False for black.
        """
        while True:
            side = input("Are you playing white or black? (w/b): ").strip().lower()
            if side in ("w", "white"):
                return True
            if side in ("b", "black"):
                return False
            print("  Please answer 'w' or 'b'.")

    def select_box(self):
        """Prompt for two corner coordinates on stdin.

        Returns:
            The normalised bounding box as ``(x1, y1, x2, y2)``.
        """
        def ask(label):
            while True:
                try:
                    x, y = input(f"Enter {label} corner as 'x y': ").split()
                    return int(x), int(y)
                except ValueError:
                    print("  Please enter two integers separated by a space.")

        x1, y1 = ask("top-left")
        x2, y2 = ask("bottom-right")
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


class FallbackSetupProvider(SetupProvider):
    """Use ``primary``; on any (non-cancel) error fall back to ``secondary``.

    A user cancelling the GUI raises ``SystemExit`` (not ``Exception``), which
    propagates so cancelling quits rather than silently dropping to prompts.
    """

    def __init__(self, primary, secondary):
        """Initialise the fallback wrapper.

        Args:
            primary: The preferred ``SetupProvider`` (e.g. the GUI).
            secondary: The provider used if ``primary`` raises (e.g. prompts).
        """
        self.primary = primary
        self.secondary = secondary

    def _try(self, method):
        """Call ``method`` on the primary provider, else on the secondary.

        Args:
            method: Name of the ``SetupProvider`` method to invoke.

        Returns:
            The primary provider's result, or the secondary's if the primary
            raised an ``Exception``.

        Raises:
            SystemExit: Propagated from the primary (e.g. a GUI cancel) so that
                cancelling quits rather than falling back to prompts.
        """
        try:
            return getattr(self.primary, method)()
        except Exception as exc:
            print(f"GUI unavailable ({exc}); using text prompt.")
            return getattr(self.secondary, method)()

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
        from screenshot import screenshot
        return screenshot(*self.box)
