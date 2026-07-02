"""Tkinter dialogs for configuring the chessboard reader.

Three interactions:

- ``select_side()`` pops up a small window with White / Black buttons.
- ``select_box()`` puts up a semi-transparent fullscreen overlay; the user
  hovers (a crosshair tracks the cursor and shows live screen coordinates)
  and clicks the board's top-left then bottom-right corner. The overlay is
  fully torn down (unmapped and repainted away) before the function returns,
  so nothing is left covering the board afterwards -- the user can interact
  with it normally while the reader runs.
- ``confirm_box(image)`` shows the frame captured from the selected region so
  the user can check the crop before the reader starts, with **Looks good**
  / **Reselect** buttons.

tkinter is imported lazily inside each function so the rest of the package
stays importable on machines without Tk (e.g. for the unit tests).
"""

import sys
import time


def _dismiss(root):
    """Tear a dialog window down so it is really gone from the screen.

    ``destroy()`` alone only *schedules* the close; if the program then blocks
    without pumping the Tk event queue (e.g. while calibrating or waiting on
    stdin), the dead window can linger on screen -- unrepainted, showing a
    busy cursor. Unmapping first and flushing the queue guarantees the window
    has disappeared by the time this returns.

    Args:
        root: The ``tk.Tk`` window to close.
    """
    root.withdraw()
    root.update_idletasks()
    root.update()
    root.destroy()


def _image_to_ppm(image):
    """Encode a captured frame as binary PPM (P6) bytes.

    Tk's ``PhotoImage`` accepts PPM data directly, which lets the preview be
    shown without Pillow. Handles the representations the frame sources
    produce: a BGRA numpy array (``mss`` capture), an RGB(A) or grayscale
    numpy array, or a grayscale list of lists (the mock renderer).

    Args:
        image: The captured frame.

    Returns:
        The frame encoded as PPM ``bytes``.
    """
    try:
        import numpy as np
    except ImportError:
        np = None

    if np is not None and hasattr(image, "ndim"):
        arr = np.asarray(image)
        if arr.ndim == 2:
            rgb = np.stack([arr] * 3, axis=-1)
        elif arr.shape[2] == 4:
            rgb = arr[..., 2::-1]  # mss gives BGRA; flip to RGB
        else:
            rgb = arr[..., :3]
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        h, w = rgb.shape[:2]
        return f"P6 {w} {h} 255\n".encode() + rgb.tobytes()

    # Pure-Python fallback: a grayscale list of lists.
    h, w = len(image), len(image[0])
    body = bytes(max(0, min(255, int(v)))
                 for row in image for v in row for _ in range(3))
    return f"P6 {w} {h} 255\n".encode() + body


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
        _dismiss(root)

    buttons = tk.Frame(root)
    buttons.pack()
    tk.Button(buttons, text="White", width=10, height=2,
              command=lambda: pick(True)).pack(side="left", padx=10)
    tk.Button(buttons, text="Black", width=10, height=2,
              command=lambda: pick(False)).pack(side="left", padx=10)

    root.bind("<Escape>", lambda e: _dismiss(root))
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
    if sys.platform == "darwin":
        # macOS: Tk's -fullscreen moves the window into its own fullscreen
        # Space -- everything behind it (the board!) disappears and the
        # overlay shows as solid black. A borderless window sized to the
        # screen stays in the current Space, so the board remains visible
        # through the translucent overlay.
        root.overrideredirect(True)
        root.geometry(f"{root.winfo_screenwidth()}"
                      f"x{root.winfo_screenheight()}+0+0")
    else:
        root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.35)   # see the board through the overlay
    except tk.TclError:
        pass
    root.configure(bg="black")

    canvas = tk.Canvas(root, cursor="crosshair", highlightthickness=0, bg="black")
    canvas.pack(fill="both", expand=True)

    PROMPTS = ("Click the TOP-LEFT corner of the board"
               "  (Esc or right-click cancels)",
               "Click the BOTTOM-RIGHT corner of the board"
               "  (Esc or right-click cancels)")
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
            _dismiss(root)

    def cancel(_event):
        clicks.clear()
        _dismiss(root)

    canvas.bind("<Motion>", on_motion)
    canvas.bind("<Button-1>", on_click)
    # Borderless windows (the macOS path) do not reliably receive key
    # events, so offer right-click as a cancel gesture alongside Escape.
    canvas.bind("<Button-2>", cancel)
    canvas.bind("<Button-3>", cancel)
    root.bind("<Escape>", cancel)
    root.lift()
    root.focus_force()
    root.mainloop()

    if len(clicks) < 2:
        raise SystemExit("Box selection cancelled.")
    time.sleep(0.2)  # let the desktop repaint before the region is captured
    (x1, y1), (x2, y2) = clicks
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def confirm_box(image):
    """Show the captured region and ask whether it looks right.

    Displays ``image`` (the frame grabbed from the selected bounding box) in
    a window with **Looks good** and **Reselect** buttons, so the user can
    verify the crop covers exactly the board before the reader starts.

    Args:
        image: The frame captured from the selected bounding box.

    Returns:
        True if the user confirms the capture, False to reselect the region.

    Raises:
        SystemExit: If the window is closed without choosing.
    """
    import tkinter as tk

    answer = {"ok": None}

    root = tk.Tk()
    root.title("Confirm the captured board")

    tk.Label(root, text="Is this exactly the board, with the pieces in the"
                        " starting position?\nCalibration begins as soon as"
                        " you confirm.",
             font=("Helvetica", 13)).pack(pady=(14, 8))

    photo = tk.PhotoImage(master=root, data=_image_to_ppm(image))
    # Shrink an oversized capture so the dialog fits comfortably on screen.
    max_w = int(root.winfo_screenwidth() * 0.7)
    max_h = int(root.winfo_screenheight() * 0.7)
    factor = max(1, -(-photo.width() // max_w), -(-photo.height() // max_h))
    if factor > 1:
        photo = photo.subsample(factor, factor)
    tk.Label(root, image=photo, borderwidth=2, relief="solid").pack(padx=14)

    if sys.platform == "darwin":
        # Without Screen Recording permission macOS returns only the desktop
        # wallpaper, which is exactly what this dialog would then be showing.
        tk.Label(root, fg="gray25", font=("Helvetica", 11),
                 text=("Seeing only your wallpaper? Grant your terminal "
                       "Screen Recording permission\n(System Settings → "
                       "Privacy & Security → Screen Recording), restart it, "
                       "then Reselect.")).pack(pady=(8, 0))

    def pick(ok):
        answer["ok"] = ok
        _dismiss(root)

    buttons = tk.Frame(root)
    buttons.pack(pady=14)
    tk.Button(buttons, text="Looks good", width=12, height=2,
              command=lambda: pick(True)).pack(side="left", padx=10)
    tk.Button(buttons, text="Reselect", width=12, height=2,
              command=lambda: pick(False)).pack(side="left", padx=10)

    root.bind("<Escape>", lambda e: _dismiss(root))
    root.eval("tk::PlaceWindow . center")
    root.focus_force()
    root.mainloop()

    if answer["ok"] is None:
        raise SystemExit("Capture confirmation cancelled.")
    return answer["ok"]
