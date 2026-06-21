"""Tkinter GUIs for configuring the chessboard reader.

Two interactions:

- ``select_side()`` pops up a small window with White / Black buttons.
- ``select_box()`` puts up a semi-transparent fullscreen overlay; the user
  hovers (a crosshair tracks the cursor and shows live screen coordinates)
  and clicks the board's top-left then bottom-right corner.

tkinter is imported lazily inside each function so the rest of the package
stays importable on machines without Tk (e.g. for the unit tests).
"""


def select_side():
    """Show a window with White/Black buttons.

    Returns:
        True if the user clicks White, False if Black.

    Raises:
        SystemExit: If the window is closed without choosing.
    """
    import tkinter as tk

    choice = {"white": None}

    root = tk.Tk()
    root.title("Choose your side")
    root.geometry("320x160")
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Which side are you playing?",
             font=("Helvetica", 13)).pack(pady=18)

    def pick(is_white):
        choice["white"] = is_white
        root.destroy()

    buttons = tk.Frame(root)
    buttons.pack()
    tk.Button(buttons, text="White", width=10, height=2,
              command=lambda: pick(True)).pack(side="left", padx=10)
    tk.Button(buttons, text="Black", width=10, height=2,
              command=lambda: pick(False)).pack(side="left", padx=10)

    root.bind("<Escape>", lambda e: root.destroy())
    root.focus_force()
    root.mainloop()

    if choice["white"] is None:
        raise SystemExit("Side selection cancelled.")
    return choice["white"]


def select_box():
    """Overlay the screen and let the user click two corners.

    A crosshair tracks the cursor and shows live coordinates; the user clicks
    the top-left corner, then the bottom-right.

    Returns:
        The board's bounding box as ``(x1, y1, x2, y2)`` in absolute screen
        coordinates, normalised so the first pair is the top-left.

    Raises:
        SystemExit: If the selection is cancelled (e.g. via Escape).
    """
    import tkinter as tk

    clicks = []          # absolute screen coords of confirmed corners
    start_xy = [None]    # window coords of the first click (for the rubber band)

    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.35)   # see the board through the overlay
    except tk.TclError:
        pass
    root.configure(bg="black")

    canvas = tk.Canvas(root, cursor="crosshair", highlightthickness=0, bg="black")
    canvas.pack(fill="both", expand=True)

    PROMPTS = ("Click the TOP-LEFT corner of the board",
               "Click the BOTTOM-RIGHT corner of the board")
    prompt = canvas.create_text(0, 30, text=PROMPTS[0], fill="white",
                                font=("Helvetica", 18))
    coord = canvas.create_text(0, 0, text="", fill="yellow",
                               font=("Helvetica", 12), anchor="nw")
    hline = canvas.create_line(0, 0, 0, 0, fill="red")
    vline = canvas.create_line(0, 0, 0, 0, fill="red")
    rect = canvas.create_rectangle(0, 0, 0, 0, outline="lime", width=2,
                                   state="hidden")

    def on_motion(event):
        w, h = root.winfo_width(), root.winfo_height()
        canvas.coords(prompt, w // 2, 30)
        canvas.coords(hline, 0, event.y, w, event.y)
        canvas.coords(vline, event.x, 0, event.x, h)
        canvas.itemconfig(coord, text=f"({event.x_root}, {event.y_root})")
        canvas.coords(coord, event.x + 14, event.y + 14)
        if start_xy[0] is not None:
            sx, sy = start_xy[0]
            canvas.coords(rect, sx, sy, event.x, event.y)

    def on_click(event):
        clicks.append((event.x_root, event.y_root))
        if len(clicks) == 1:
            start_xy[0] = (event.x, event.y)
            canvas.itemconfig(prompt, text=PROMPTS[1])
            canvas.itemconfig(rect, state="normal")
        else:
            root.destroy()

    def cancel(_event):
        clicks.clear()
        root.destroy()

    canvas.bind("<Motion>", on_motion)
    canvas.bind("<Button-1>", on_click)
    root.bind("<Escape>", cancel)
    root.focus_force()
    root.mainloop()

    if len(clicks) < 2:
        raise SystemExit("Box selection cancelled.")
    (x1, y1), (x2, y2) = clicks
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
