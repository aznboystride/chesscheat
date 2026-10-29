"""The ``MirrorBoardWindow`` mirror view."""

from chesscheat import board
from chesscheat.interfaces import MirrorView

LIGHT, DARK = "#f0d9b5", "#b58863"
SELECTED, LAST_MOVE = "#f6f669", "#aad751"
GLYPHS = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗",
          "N": "♘", "P": "♙", "k": "♚", "q": "♛",
          "r": "♜", "b": "♝", "n": "♞", "p": "♟"}


class MirrorBoardWindow(MirrorView):
    """A tkinter board the user enters the opponent's moves on.

    The board is drawn from the **opponent's** perspective (their side at the
    bottom) so mimicking their moves feels natural. The user clicks the
    origin square, then the destination; the pair is handed to ``on_move``
    (the controller validates it). The last move played is highlighted and
    a status line says whose turn it is.

    Driven by ``run`` (Tk mainloop); redrawn through ``update``. tkinter is
    imported lazily so the module is importable without it.

    Attributes:
        bottom_white: True if white is at the bottom of this board.
    """

    def __init__(self, on_move, bottom_white, avoid_box=None, cell=64,
                 title="chesscheat mirror board"):
        """Create the window.

        Args:
            on_move: Callback ``(from_square, to_square)`` in algebraic
                notation, invoked when the user has clicked two squares.
            bottom_white: True to draw white at the bottom (the opponent is
                white), False for black at the bottom.
            avoid_box: Optional ``(x1, y1, x2, y2)`` screen region the
                window must not cover -- the real chess app's board, where
                the program drags the mouse. Placed via
                ``chesscheat.mirror.gui_placement``.
            cell: Square size in pixels.
            title: Window title.
        """
        import tkinter as tk

        from chesscheat.mirror import gui_placement

        self.bottom_white = bottom_white
        self._on_move = on_move
        self._cell = cell
        self._board_map = {}
        self._last_move = None
        self._selected = None   # algebraic name of the first clicked square

        self._root = tk.Tk()
        self._root.title(title)
        self._root.attributes("-topmost", True)
        side = 8 * cell
        if avoid_box is not None:
            x, y = gui_placement(avoid_box, self._root.winfo_screenwidth(),
                                 self._root.winfo_screenheight(),
                                 side, side + 48)
            self._root.geometry(f"+{int(x)}+{int(y)}")
        self._canvas = tk.Canvas(self._root, width=side, height=side,
                                 highlightthickness=0)
        self._canvas.pack()
        self._canvas.bind("<Button-1>", self._on_click)
        self._status = tk.Label(self._root, text="", anchor="w",
                                font=("Helvetica", 12), padx=8, pady=6)
        self._status.pack(fill="x")

    def _square_at(self, x, y):
        """Map a canvas click to the square's algebraic name.

        Args:
            x: Canvas x coordinate.
            y: Canvas y coordinate.

        Returns:
            The square name, e.g. ``"e7"``, or None if outside the board.
        """
        row, col = int(y // self._cell), int(x // self._cell)
        if not (0 <= row < 8 and 0 <= col < 8):
            return None
        return board.square_name(*board.square_coord(row, col,
                                                      self.bottom_white))

    def _on_click(self, event):
        """Collect two clicks into a move and hand it to the controller."""
        name = self._square_at(event.x, event.y)
        if name is None:
            return
        if self._selected is None:
            self._selected = name
            self._draw()
            return
        origin, self._selected = self._selected, None
        if origin != name:
            self._on_move(origin, name)
        else:
            self._draw()

    def _draw(self):
        """Render squares, highlights and piece glyphs."""
        canvas, cell = self._canvas, self._cell
        canvas.delete("all")
        highlighted = set()
        if self._last_move:
            highlighted.update((self._last_move[0:2], self._last_move[2:4]))
        for row in range(8):
            for col in range(8):
                file_rank = board.square_coord(row, col, self.bottom_white)
                name = board.square_name(*file_rank)
                fill = LIGHT if board.is_light(*file_rank) else DARK
                if name in highlighted:
                    fill = LAST_MOVE
                if name == self._selected:
                    fill = SELECTED
                x, y = col * cell, row * cell
                canvas.create_rectangle(x, y, x + cell, y + cell,
                                        fill=fill, outline=fill)
                label = self._board_map.get(file_rank, ".")
                if label != ".":
                    canvas.create_text(x + cell / 2, y + cell / 2,
                                       text=GLYPHS[label],
                                       font=("Helvetica", int(cell * 0.7)))
        # Rank/file hints in the corners of the edge squares.
        for i in range(8):
            file_rank = board.square_coord(7, i, self.bottom_white)
            canvas.create_text(i * cell + 4, 8 * cell - 4, anchor="sw",
                               text=board.FILES[file_rank[0]],
                               font=("Helvetica", 9))
            file_rank = board.square_coord(i, 0, self.bottom_white)
            canvas.create_text(4, i * cell + 4, anchor="nw",
                               text=str(file_rank[1]), font=("Helvetica", 9))

    def update(self, board_map, last_move, status):
        """Redraw with a new position, highlight and status.

        Args:
            board_map: The ``{(file_idx, rank): label}`` position.
            last_move: The last move in UCI to highlight, or None.
            status: The status line text.
        """
        self._board_map = dict(board_map)
        self._last_move = last_move
        self._status.configure(text=status)
        self._draw()
        self._root.update_idletasks()

    def run(self):
        """Run the Tk event loop until the window is closed."""
        self._root.mainloop()
