"""The ``MirrorBoardWindow`` mirror view."""

from chesscheat import board
from chesscheat.interfaces import MirrorView

LIGHT, DARK = "#f0d9b5", "#b58863"
SELECTED, LAST_MOVE = "#f6f669", "#aad751"
GLYPHS = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗",
          "N": "♘", "P": "♙", "k": "♚", "q": "♛",
          "r": "♜", "b": "♝", "n": "♞", "p": "♟"}

# Strength presets offered in the GUI: label -> Elo (None = full strength).
# Stockfish's UCI_Elo spans roughly 1320-3190; the engine clamps as needed.
STRENGTHS = (("Full strength", None), ("2800", 2800), ("2500", 2500),
             ("2200", 2200), ("1900", 1900), ("1600", 1600), ("1400", 1400))


class MirrorBoardWindow(MirrorView):
    """A tkinter board the user enters the opponent's moves on.

    Drawn in the **same orientation as the real chess app** -- the user's
    own side at the bottom -- so the two boards read identically and an
    opponent move is copied square-for-square. The user clicks the origin
    square, then the destination; the pair is handed to ``on_move`` (the
    controller validates it). The last move played is highlighted and a
    status line says whose turn it is.

    A control bar under the board exposes the runtime settings -- an
    **Auto-play** toggle, a minimum **reply delay** in seconds, the engine
    **strength**, and an **Undo** button that takes back the last opponent
    move and the reply to it -- each reported through its own callback. ``schedule`` defers work on the Tk event loop so a delayed
    reply never freezes the window.

    Driven by ``run`` (Tk mainloop); redrawn through ``update``. tkinter is
    imported lazily so the module is importable without it.

    Attributes:
        bottom_white: True if white is at the bottom of this board.
    """

    def __init__(self, on_move, bottom_white, avoid_box=None, cell=64,
                 title="chesscheat mirror board", on_auto=None, on_delay=None,
                 on_strength=None, on_undo=None, auto=True, delay=0.0,
                 elo=None):
        """Create the window.

        Args:
            on_move: Callback ``(from_square, to_square)`` in algebraic
                notation, invoked when the user has clicked two squares.
            bottom_white: True to draw white at the bottom, False for black;
                pass the user's side so the board matches the real app.
            avoid_box: Optional ``(x1, y1, x2, y2)`` screen region the
                window must not cover -- the real chess app's board, where
                the program drags the mouse. Placed via
                ``chesscheat.mirror.gui_placement``.
            cell: Square size in pixels.
            title: Window title.
            on_auto: Callback ``(enabled)`` when the auto-play toggle changes.
            on_delay: Callback ``(seconds)`` when the reply delay changes.
            on_strength: Callback ``(elo_or_None)`` when the strength changes.
            on_undo: Callback ``()`` when the Undo button is pressed (take
                back the last opponent move and the reply to it).
            auto: Initial state of the auto-play toggle.
            delay: Initial reply delay shown, in seconds.
            elo: Initial strength shown (None = full strength).
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
                                 side, side + 96)
            self._root.geometry(f"+{int(x)}+{int(y)}")
        self._canvas = tk.Canvas(self._root, width=side, height=side,
                                 highlightthickness=0)
        self._canvas.pack()
        self._canvas.bind("<Button-1>", self._on_click)
        self._status = tk.Label(self._root, text="", anchor="w",
                                font=("Helvetica", 12), padx=8, pady=6)
        self._status.pack(fill="x")
        self._build_controls(tk, on_auto, on_delay, on_strength, on_undo,
                             auto, delay, elo)

    def _build_controls(self, tk, on_auto, on_delay, on_strength, on_undo,
                        auto, delay, elo):
        """Lay out the auto-play, delay, strength and undo controls.

        Args:
            tk: The imported ``tkinter`` module.
            on_auto: Auto-play toggle callback (or None).
            on_delay: Delay change callback (or None).
            on_strength: Strength change callback (or None).
            on_undo: Undo button callback (or None).
            auto: Initial toggle state.
            delay: Initial delay in seconds.
            elo: Initial strength (None = full).
        """
        bar = tk.Frame(self._root, padx=8, pady=4)
        bar.pack(fill="x")

        self._auto_var = tk.BooleanVar(master=self._root, value=auto)
        tk.Checkbutton(
            bar, text="Auto-play", variable=self._auto_var,
            command=lambda: on_auto and on_auto(self._auto_var.get()),
        ).pack(side="left")

        tk.Label(bar, text="  Reply delay (s):").pack(side="left")
        self._delay_var = tk.StringVar(master=self._root, value=f"{delay:g}")

        def delay_changed(*_args):
            try:
                seconds = max(0.0, float(self._delay_var.get()))
            except ValueError:
                return
            if on_delay:
                on_delay(seconds)

        delay_box = tk.Spinbox(bar, from_=0, to=120, increment=0.5, width=5,
                               textvariable=self._delay_var,
                               command=delay_changed)
        delay_box.bind("<Return>", delay_changed)
        delay_box.bind("<FocusOut>", delay_changed)
        delay_box.pack(side="left")

        tk.Label(bar, text="  Strength:").pack(side="left")
        labels = [label for label, _ in STRENGTHS]
        initial = next((label for label, value in STRENGTHS if value == elo),
                       labels[0])
        self._strength_var = tk.StringVar(master=self._root, value=initial)
        by_label = dict(STRENGTHS)

        def strength_changed(label):
            if on_strength:
                on_strength(by_label[label])

        tk.OptionMenu(bar, self._strength_var, *labels,
                      command=strength_changed).pack(side="left")

        tk.Button(bar, text="Undo", command=lambda: on_undo and on_undo()
                  ).pack(side="right")

    def schedule(self, seconds, fn):
        """Run ``fn`` after ``seconds`` on the Tk event loop (non-blocking).

        Args:
            seconds: Delay before ``fn`` runs.
            fn: A no-argument callable.
        """
        self._root.after(max(0, int(seconds * 1000)), fn)

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
