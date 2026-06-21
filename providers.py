"""Real (production) implementations of the setup and frame-source interfaces.

Heavy/optional dependencies (tkinter via ``gui``, ``screenshot``) are imported
lazily inside the methods so importing this module stays cheap and safe.
"""

from interfaces import SetupProvider, FrameSource


class GuiSetupProvider(SetupProvider):
    """Tkinter GUI: button dialog for the side, overlay for the corners."""

    def select_side(self):
        import gui
        return gui.select_side()

    def select_box(self):
        import gui
        return gui.select_box()


class PromptSetupProvider(SetupProvider):
    """Plain text prompts on stdin/stdout."""

    def select_side(self):
        while True:
            side = input("Are you playing white or black? (w/b): ").strip().lower()
            if side in ("w", "white"):
                return True
            if side in ("b", "black"):
                return False
            print("  Please answer 'w' or 'b'.")

    def select_box(self):
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
        self.primary = primary
        self.secondary = secondary

    def _try(self, method):
        try:
            return getattr(self.primary, method)()
        except Exception as exc:
            print(f"GUI unavailable ({exc}); using text prompt.")
            return getattr(self.secondary, method)()

    def select_side(self):
        return self._try("select_side")

    def select_box(self):
        return self._try("select_box")


class ScreenFrameSource(FrameSource):
    """Live screen capture of the board's bounding box."""

    def __init__(self, box):
        self.box = box

    def grab(self):
        from screenshot import screenshot
        return screenshot(*self.box)
