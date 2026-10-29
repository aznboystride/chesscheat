"""The ``MirrorBoardWindow`` mirror view."""

from chesscheat import board
from chesscheat.gui.background_runner import BackgroundRunner
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

# Playing styles offered in the GUI: label -> name (see assist.style).
STYLE_LABELS = (("Best move", "best"), ("Aggressive", "aggressive"),
                ("Solid", "solid"), ("Unusual", "unusual"))

EVAL_WIDTH = 24           # width of the evaluation bar beside the board
EVAL_WHITE, EVAL_BLACK = "#f4f4f4", "#3a3a3a"


class MirrorBoardWindow(MirrorView):
    """A tkinter board the user enters the opponent's moves on.

    Drawn in the **same orientation as the real chess app** -- the user's
    own side at the bottom -- so the two boards read identically and an
    opponent move is copied square-for-square. The user clicks the origin
    square, then the destination; the pair is handed to ``on_move`` (the
    controller validates it). The last move played is highlighted and a
    status line says whose turn it is.

    An **evaluation bar** runs down the left of the board (white's share
    grows from white's side; the score or result is printed on it), fed by
    ``update_evaluation``.

    A control bar under the board exposes the runtime settings -- an
    **Auto-play** toggle, a **Watch app** toggle (read the opponent's moves
    off the real app's last-move highlight instead of entering them), a
    **reply delay range** (min/max seconds; equal for a fixed delay, apart
    for random jitter), the engine **strength**, the engine **think time**
    with a **Think in delay** toggle, the playing **style** with the
    margin (in pawns) it may stray from the best line, an **Undo** button
    that takes back the
    last opponent move and the reply to it, and a **New game** button that
    asks which colour the user plays now (the real board is reused) -- each
    reported through its own callback. ``set_orientation`` flips the board
    for a new game as the other colour. ``run_in_background`` runs the
    engine search on a thread and delivers the result on the Tk loop, so
    the window stays live while the engine thinks.
    ``square_position`` tells the controller where a square is on screen so
    the pointer can be returned here after a move in the real app. ``schedule`` defers work on the Tk event loop so a delayed
    reply never freezes the window.

    Driven by ``run`` (Tk mainloop); redrawn through ``update``. tkinter is
    imported lazily so the module is importable without it.

    Attributes:
        bottom_white: True if white is at the bottom of this board.
    """

    def __init__(self, on_move, bottom_white, avoid_box=None, cell=64,
                 title="chesscheat mirror board", on_auto=None, on_delay=None,
                 on_strength=None, on_undo=None, on_watch=None,
                 on_new_game=None, on_think=None, on_think_in_delay=None,
                 on_style=None, auto=True, delay=0.0, elo=None, watch=True,
                 think=0.3, think_in_delay=True, style="best",
                 style_margin=0.3):
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
            on_delay: Callback ``(min_seconds, max_seconds)`` whenever either
                end of the reply-delay range changes; equal ends mean a
                fixed delay, otherwise each reply is jittered within them.
            on_strength: Callback ``(elo_or_None)`` when the strength changes.
            on_undo: Callback ``()`` when the Undo button is pressed (take
                back the last opponent move and the reply to it).
            on_watch: Callback ``(enabled)`` when the Watch-app toggle
                changes.
            on_new_game: Callback ``(playing_white)`` after the user pressed
                New game and chose a colour (not called on cancel).
            on_think: Callback ``(seconds)`` when the think-time box changes.
            on_think_in_delay: Callback ``(enabled)`` when the Think-in-delay
                toggle changes.
            on_style: Callback ``(style, margin_pawns)`` when the style
                menu or its margin box changes.
            auto: Initial state of the auto-play toggle.
            delay: Initial reply delay shown: seconds, or a ``(min, max)``
                pair.
            elo: Initial strength shown (None = full strength).
            watch: Initial state of the Watch-app toggle.
            think: Initial think time shown, in seconds.
            think_in_delay: Initial state of the Think-in-delay toggle.
            style: Initial style name shown.
            style_margin: Initial style margin shown, in pawns.
        """
        import tkinter as tk

        from chesscheat.mirror import gui_placement

        self.bottom_white = bottom_white
        self._on_move = on_move
        self._cell = cell
        self._board_map = {}
        self._last_move = None
        self._selected = None   # algebraic name of the first clicked square
        self._evaluation = (0.5, "")
        self._on_new_game = on_new_game

        self._root = tk.Tk()
        self._root.title(title)
        self._root.attributes("-topmost", True)
        self._runner = BackgroundRunner(self._root.after)
        side = 8 * cell
        if avoid_box is not None:
            x, y = gui_placement(avoid_box, self._root.winfo_screenwidth(),
                                 self._root.winfo_screenheight(),
                                 side + EVAL_WIDTH, side + 96)
            self._root.geometry(f"+{int(x)}+{int(y)}")
        boards = tk.Frame(self._root)
        boards.pack()
        self._eval = tk.Canvas(boards, width=EVAL_WIDTH, height=side,
                               highlightthickness=0, bg=EVAL_BLACK)
        self._eval.pack(side="left")
        self._canvas = tk.Canvas(boards, width=side, height=side,
                                 highlightthickness=0)
        self._canvas.pack(side="left")
        self._canvas.bind("<Button-1>", self._on_click)
        self._status = tk.Label(self._root, text="", anchor="w",
                                font=("Helvetica", 12), padx=8, pady=6)
        self._status.pack(fill="x")
        self._build_controls(tk, on_auto, on_delay, on_strength, on_undo,
                             on_watch, auto, delay, elo, watch)
        self._build_engine_controls(tk, on_strength, on_think,
                                    on_think_in_delay, elo, think,
                                    think_in_delay)
        self._build_style_controls(tk, on_style, style, style_margin)
        self._draw_evaluation()

    def _build_controls(self, tk, on_auto, on_delay, on_strength, on_undo,
                        on_watch, auto, delay, elo, watch):
        """Lay out the auto-play, watch, delay, strength and undo controls.

        Args:
            tk: The imported ``tkinter`` module.
            on_auto: Auto-play toggle callback (or None).
            on_delay: Delay change callback (or None).
            on_strength: Strength change callback (or None).
            on_undo: Undo button callback (or None).
            on_watch: Watch-app toggle callback (or None).
            auto: Initial auto-play toggle state.
            delay: Initial delay in seconds.
            elo: Initial strength (None = full).
            watch: Initial Watch-app toggle state.
        """
        bar = tk.Frame(self._root, padx=8, pady=4)
        bar.pack(fill="x")

        self._auto_var = tk.BooleanVar(master=self._root, value=auto)
        tk.Checkbutton(
            bar, text="Auto-play", variable=self._auto_var,
            command=lambda: on_auto and on_auto(self._auto_var.get()),
        ).pack(side="left")

        self._watch_var = tk.BooleanVar(master=self._root, value=watch)
        tk.Checkbutton(
            bar, text="Watch app", variable=self._watch_var,
            command=lambda: on_watch and on_watch(self._watch_var.get()),
        ).pack(side="left")

        tk.Label(bar, text="  Reply delay (s) min:").pack(side="left")
        lo, hi = delay if isinstance(delay, (tuple, list)) else (delay, delay)
        self._delay_lo = tk.StringVar(master=self._root, value=f"{lo:g}")
        self._delay_hi = tk.StringVar(master=self._root, value=f"{hi:g}")

        def delay_changed(*_args):
            # Either box changing reports the whole range; the controller
            # clamps (no negatives, max never below min).
            try:
                lo = float(self._delay_lo.get())
                hi = float(self._delay_hi.get())
            except ValueError:
                return
            if on_delay:
                on_delay(lo, hi)

        for var in (self._delay_lo, self._delay_hi):
            box = tk.Spinbox(bar, from_=0, to=120, increment=0.5, width=5,
                             textvariable=var, command=delay_changed)
            box.bind("<Return>", delay_changed)
            box.bind("<FocusOut>", delay_changed)
            box.pack(side="left")
            if var is self._delay_lo:
                tk.Label(bar, text=" max:").pack(side="left")

        tk.Button(bar, text="Undo", command=lambda: on_undo and on_undo()
                  ).pack(side="right")
        tk.Button(bar, text="New game", command=self._new_game
                  ).pack(side="right")

    def _build_engine_controls(self, tk, on_strength, on_think,
                               on_think_in_delay, elo, think, think_in_delay):
        """Lay out the engine row: strength, think time, think-in-delay.

        Args:
            tk: The imported ``tkinter`` module.
            on_strength: Strength change callback (or None).
            on_think: Think-time change callback (or None).
            on_think_in_delay: Think-in-delay toggle callback (or None).
            elo: Initial strength (None = full).
            think: Initial think time in seconds.
            think_in_delay: Initial toggle state.
        """
        bar = tk.Frame(self._root, padx=8, pady=4)
        bar.pack(fill="x")

        tk.Label(bar, text="Strength:").pack(side="left")
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

        tk.Label(bar, text="  Think (s):").pack(side="left")
        self._think_var = tk.StringVar(master=self._root, value=f"{think:g}")

        def think_changed(*_args):
            try:
                seconds = float(self._think_var.get())
            except ValueError:
                return
            if on_think:
                on_think(seconds)

        box = tk.Spinbox(bar, from_=0.05, to=10, increment=0.1, width=5,
                         textvariable=self._think_var, command=think_changed)
        box.bind("<Return>", think_changed)
        box.bind("<FocusOut>", think_changed)
        box.pack(side="left")

        self._think_in_delay_var = tk.BooleanVar(master=self._root,
                                                 value=think_in_delay)
        tk.Checkbutton(
            bar, text="Think in delay", variable=self._think_in_delay_var,
            command=lambda: on_think_in_delay and on_think_in_delay(
                self._think_in_delay_var.get()),
        ).pack(side="left")

    def _build_style_controls(self, tk, on_style, style, margin):
        """Lay out the style row: style menu and its margin in pawns.

        Args:
            tk: The imported ``tkinter`` module.
            on_style: Style change callback ``(style, margin)`` (or None).
            style: Initial style name.
            margin: Initial margin in pawns.
        """
        bar = tk.Frame(self._root, padx=8, pady=4)
        bar.pack(fill="x")

        tk.Label(bar, text="Style:").pack(side="left")
        labels = [label for label, _ in STYLE_LABELS]
        by_label = dict(STYLE_LABELS)
        initial = next((label for label, name in STYLE_LABELS
                        if name == style), labels[0])
        self._style_var = tk.StringVar(master=self._root, value=initial)
        self._margin_var = tk.StringVar(master=self._root,
                                        value=f"{margin:g}")

        def style_changed(*_args):
            try:
                pawns = float(self._margin_var.get())
            except ValueError:
                return
            if on_style:
                on_style(by_label[self._style_var.get()], pawns)

        tk.OptionMenu(bar, self._style_var, *labels,
                      command=style_changed).pack(side="left")
        tk.Label(bar, text="  within (pawns):").pack(side="left")
        box = tk.Spinbox(bar, from_=0, to=5, increment=0.1, width=5,
                         textvariable=self._margin_var, command=style_changed)
        box.bind("<Return>", style_changed)
        box.bind("<FocusOut>", style_changed)
        box.pack(side="left")

    def run_in_background(self, fn, done):
        """Run ``fn`` on a thread and report its result on the Tk loop.

        The controller's ``worker``: the engine searches off the GUI thread
        so clicks keep working, and ``done(result, error)`` is invoked from
        the event loop (never from the thread), where touching widgets is
        safe.

        Args:
            fn: No-argument callable to run on a worker thread.
            done: ``done(result, error)`` called on the Tk loop; ``error``
                is the exception ``fn`` raised, else None.
        """
        self._runner.run(fn, done)

    def ask_side(self):
        """Ask which colour the user plays, for a new game.

        Returns:
            True for white, False for black, None if the dialog was
            cancelled.
        """
        from tkinter import messagebox

        return messagebox.askyesnocancel(
            "New game",
            "Start a new game on the same board.\n\nAre you playing white?"
            "\n(Yes = white, No = black)", parent=self._root)

    def _new_game(self):
        """Handle the New game button: ask the side, then tell the controller."""
        side = self.ask_side()
        if side is not None and self._on_new_game:
            self._on_new_game(bool(side))

    def set_orientation(self, bottom_white):
        """Flip the board so the given side is at the bottom.

        Args:
            bottom_white: True to put white at the bottom.
        """
        self.bottom_white = bottom_white
        self._selected = None
        self._draw()
        self._draw_evaluation()

    def update_evaluation(self, white_share, label):
        """Show an evaluation on the bar beside the board.

        Args:
            white_share: White's fraction of the bar, in ``[0, 1]``.
            label: Text printed on the bar (score or result).
        """
        self._evaluation = (max(0.0, min(1.0, float(white_share))), label)
        self._draw_evaluation()

    def _draw_evaluation(self):
        """Render the evaluation bar: white's share grows from white's side."""
        share, label = self._evaluation
        side = 8 * self._cell
        canvas = self._eval
        canvas.delete("all")
        white_px = share * side
        if self.bottom_white:
            canvas.create_rectangle(0, side - white_px, EVAL_WIDTH, side,
                                    fill=EVAL_WHITE, outline=EVAL_WHITE)
        else:
            canvas.create_rectangle(0, 0, EVAL_WIDTH, white_px,
                                    fill=EVAL_WHITE, outline=EVAL_WHITE)
        if label:
            # Print the label at the end of the bar belonging to whoever is
            # ahead, in the contrasting colour.
            white_ahead = share >= 0.5
            at_bottom = white_ahead == self.bottom_white
            canvas.create_text(
                EVAL_WIDTH / 2, side - 4 if at_bottom else 4,
                text=label, angle=90, anchor="w" if at_bottom else "e",
                font=("Helvetica", 9, "bold"),
                fill=EVAL_BLACK if white_ahead else EVAL_WHITE)

    def schedule(self, seconds, fn):
        """Run ``fn`` after ``seconds`` on the Tk event loop (non-blocking).

        Args:
            seconds: Delay before ``fn`` runs.
            fn: A no-argument callable.
        """
        self._root.after(max(0, int(seconds * 1000)), fn)

    def square_position(self, name):
        """Return a square's centre in absolute screen coordinates.

        Lets the controller park the mouse back on this board after playing
        a move in the real app. Tk reports the canvas origin in the same
        logical coordinates ``pyautogui`` uses, so the result can be passed
        straight to the actuator.

        Args:
            name: A square in algebraic notation, e.g. ``"e5"``.

        Returns:
            The ``(x, y)`` screen centre of the square, or None if the
            window is not mapped yet.
        """
        try:
            origin_x = self._canvas.winfo_rootx()
            origin_y = self._canvas.winfo_rooty()
        except Exception:
            return None
        row, col = board.cell_of(*board.parse_square(name), self.bottom_white)
        return (origin_x + (col + 0.5) * self._cell,
                origin_y + (row + 0.5) * self._cell)

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
