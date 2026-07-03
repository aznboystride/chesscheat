"""The ``LivePreview`` capture window."""

import collections
import time

from chesscheat import board


def annotations(board_map, playing_white, width, height):
    """Compute the piece overlays to draw on a captured board frame.

    Pure geometry: for every detected piece, one annotation locating its
    square on the image plus the piece's display name.

    Args:
        board_map: A ``{(file_idx, rank): label}`` map of detected pieces
            (``'.'`` marks an empty square), or None for no detections.
        playing_white: True if the frame shows the board from white's
            perspective (matches how the board was calibrated).
        width: Frame width in pixels.
        height: Frame height in pixels.

    Returns:
        A list of ``(x0, y0, x1, y1, name, is_white_piece)`` tuples, one per
        detected piece: the square's pixel bounding box, the piece's name
        (e.g. ``'knight'``), and whether the piece is white.
    """
    if not board_map:
        return []
    cell_w, cell_h = width / 8, height / 8
    return [
        (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h,
         board.piece_name(label), label.isupper())
        for row in range(8) for col in range(8)
        for label in [board_map.get(board.square_coord(row, col,
                                                       playing_white), ".")]
        if label != "."
    ]


class LivePreview:
    """A window surfacing each captured frame in real time, with the rate.

    Call ``show(image, board_map, playing_white)`` with every grabbed frame:
    the first call opens a small always-on-top window, and each call
    refreshes it with the latest capture and puts the measured frame rate in
    the title bar. Every **detected piece is highlighted** on the capture --
    its square outlined and a chip overlaid with the piece's name (white
    chips for white pieces, black chips for black pieces).

    The window is driven by explicit ``update()`` pumping (no ``mainloop``),
    so it works from inside the reader's synchronous loop. If Tk is
    unavailable, the display cannot be opened, or the user closes the
    window, the preview disables itself and every further ``show`` is a
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
        self._canvas = None
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
        self._canvas = tk.Canvas(self._root, highlightthickness=0,
                                 borderwidth=2, relief="solid")
        self._canvas.pack()

    def _draw_annotations(self, board_map, playing_white):
        """Overlay the detected pieces on the current canvas image.

        Args:
            board_map: The detected ``{(file_idx, rank): label}`` map.
            playing_white: Whether the frame is from white's perspective.
        """
        for x0, y0, x1, y1, name, is_white in annotations(
                board_map, playing_white,
                self._photo.width(), self._photo.height()):
            self._canvas.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1,
                                          outline="#22cc55", width=2)
            chip, text = (("white", "black") if is_white
                          else ("black", "white"))
            self._canvas.create_rectangle(x0 + 2, y1 - 15, x1 - 2, y1 - 2,
                                          fill=chip, outline=text)
            self._canvas.create_text((x0 + x1) / 2, y1 - 8, text=name,
                                     fill=text, font=("Helvetica", 9))

    def show(self, image, board_map=None, playing_white=True):
        """Display a captured frame, opening the window if needed.

        Args:
            image: The captured frame, in any representation
                ``chesscheat.gui.dialogs._image_to_ppm`` accepts.
            board_map: Optional ``{(file_idx, rank): label}`` map of detected
                pieces to highlight on the frame; None draws no overlays.
            playing_white: Whether the frame shows the board from white's
                perspective; orients the overlays.
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
            self._canvas.config(width=self._photo.width(),
                                height=self._photo.height())
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
            self._draw_annotations(board_map, playing_white)
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
