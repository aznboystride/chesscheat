"""Window placement for the mirror GUI: keep it off the real board."""


def gui_placement(box, screen_w, screen_h, win_w, win_h, gap=24):
    """Choose a top-left position for the GUI that avoids the real board.

    The mirror GUI must not overlap the real chess app's board region: the
    program drags the mouse there to play its moves, and a window on top
    would intercept the drag. Tries to the right of the box, then to the
    left, then below, then above; if nothing fits, falls back to the
    top-left corner of the screen (the user can move it).

    Pure geometry, so it is unit-tested without a display.

    Args:
        box: The real board's ``(x1, y1, x2, y2)`` screen bounding box.
        screen_w: Screen width in pixels.
        screen_h: Screen height in pixels.
        win_w: The GUI window's width in pixels.
        win_h: The GUI window's height in pixels.
        gap: Minimum pixels of clearance between the window and the box.

    Returns:
        An ``(x, y)`` top-left position for the window.
    """
    x1, y1, x2, y2 = box
    top = max(0, min(y1, screen_h - win_h))
    left = max(0, min(x1, screen_w - win_w))
    candidates = (
        (x2 + gap, top),                 # right of the board
        (x1 - gap - win_w, top),         # left of the board
        (left, y2 + gap),                # below
        (left, y1 - gap - win_h),        # above
    )

    def fits(pos):
        x, y = pos
        return (0 <= x and x + win_w <= screen_w
                and 0 <= y and y + win_h <= screen_h)

    return next(filter(fits, candidates), (0, 0))
