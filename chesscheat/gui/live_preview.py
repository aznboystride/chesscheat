"""The ``LivePreview`` capture window."""

import collections
import time


class LivePreview:
    """A window surfacing each captured frame in real time, with the rate.

    Call ``show(image)`` with every grabbed frame: the first call opens a
    small always-on-top window, and each call refreshes it with the latest
    capture and puts the measured frame rate in the title bar. The window is
    driven by explicit ``update()`` pumping (no ``mainloop``), so it works
    from inside the reader's synchronous loop.

    If Tk is unavailable, the display cannot be opened, or the user closes
    the window, the preview disables itself and every further ``show`` is a
    no-op -- the reader keeps running without it.

    Attributes:
        disabled: True once the preview cannot (or should no longer) be
            shown; it never re-enables.
    """

    def __init__(self, title="chesscheat live capture"):
        """Initialise the preview.

        Args:
            title: Base window title; the frame rate is appended to it.
        """
        self.disabled = False
        self._title = title
        self._root = None
        self._label = None
        self._photo = None
        self._times = collections.deque(maxlen=20)

    def _rate_text(self):
        """Format the measured capture rate for the title bar.

        Returns:
            A short human-readable rate string, e.g. ``"3.3 fps"``.
        """
        if len(self._times) < 2 or self._times[-1] <= self._times[0]:
            return "measuring..."
        rate = (len(self._times) - 1) / (self._times[-1] - self._times[0])
        return f"{rate:.1f} fps"

    def _open(self, tk):
        """Create the preview window on first use.

        Args:
            tk: The imported ``tkinter`` module.
        """
        self._root = tk.Tk()
        self._root.title(self._title)
        self._root.attributes("-topmost", True)
        self._root.protocol("WM_DELETE_WINDOW", self.close)
        self._label = tk.Label(self._root, borderwidth=2, relief="solid")
        self._label.pack()

    def show(self, image):
        """Display a captured frame, opening the window if needed.

        Args:
            image: The captured frame, in any representation
                ``chesscheat.gui.dialogs._image_to_ppm`` accepts.
        """
        if self.disabled:
            return
        try:
            import tkinter as tk
            from chesscheat.gui.dialogs import _image_to_ppm

            self._times.append(time.time())
            if self._root is None:
                self._open(tk)
            self._photo = tk.PhotoImage(master=self._root,
                                        data=_image_to_ppm(image))
            self._label.configure(image=self._photo)
            self._root.title(f"{self._title} — {self._rate_text()}")
            self._root.update()
        except Exception:
            # No Tk, no display, or the window was torn down mid-update:
            # drop the preview but never break the read loop.
            self.close()

    def close(self):
        """Disable the preview and destroy its window if one is open."""
        self.disabled = True
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None
