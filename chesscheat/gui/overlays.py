"""Square-annotation overlays shared by the preview and confirmation UIs.

``annotations`` is pure geometry/labelling (dependency-free and unit-testable
without Tk); ``draw`` renders its specs onto a Tk canvas. Every square of a
reading gets an overlay:

- a detected **piece**: the square outlined, with a chip naming the piece
  ("knight" etc.) -- white chips for white pieces, black chips for black;
- an **empty square**: a chip naming the square's own colour, "white" or
  "black";
- an **unknown square** (best match scored below the recognizer's
  threshold): outlined in red with an ``unknown (score)`` chip showing the
  best SSIM score.
"""

from chesscheat import board

PIECE_OUTLINE = "#22cc55"
UNKNOWN_COLOUR = "#cc2222"


def annotations(scored_map, playing_white, width, height):
    """Compute the overlays to draw on a captured board frame.

    Args:
        scored_map: A ``{(file_idx, rank): value}`` map where each value is
            either a ``(label, score)`` pair (a recognizer's scored reading)
            or a plain label; labels are piece letters, ``'.'`` for empty and
            ``'?'`` for unknown. None or empty produces no overlays.
        playing_white: True if the frame shows the board from white's
            perspective (matches how the board was calibrated).
        width: Frame width in pixels.
        height: Frame height in pixels.

    Returns:
        A list of ``(x0, y0, x1, y1, text, chip_fill, text_fill, outline)``
        tuples, one per square present in ``scored_map``; ``outline`` is None
        for empty squares (chip only).
    """
    if not scored_map:
        return []
    cell_w, cell_h = width / 8, height / 8

    def square_spec(row, col):
        file_rank = board.square_coord(row, col, playing_white)
        if file_rank not in scored_map:
            return None
        value = scored_map[file_rank]
        label, score = value if isinstance(value, tuple) else (value, None)
        box = (col * cell_w, row * cell_h,
               (col + 1) * cell_w, (row + 1) * cell_h)
        if label == "?":
            text = "unknown" if score is None else f"unknown ({score:.2f})"
            return (*box, text, UNKNOWN_COLOUR, "white", UNKNOWN_COLOUR)
        if label == ".":
            name = "white" if board.is_light(*file_rank) else "black"
            chip, text_fill = (("white", "black") if name == "white"
                               else ("black", "white"))
            return (*box, name, chip, text_fill, None)
        chip, text_fill = (("white", "black") if label.isupper()
                           else ("black", "white"))
        return (*box, board.piece_name(label), chip, text_fill, PIECE_OUTLINE)

    return [spec
            for row in range(8) for col in range(8)
            for spec in [square_spec(row, col)] if spec is not None]


def draw(canvas, specs):
    """Render annotation specs onto a Tk canvas.

    Args:
        canvas: A ``tk.Canvas`` already holding the captured frame image.
        specs: Annotation tuples from ``annotations``.
    """
    for x0, y0, x1, y1, text, chip_fill, text_fill, outline in specs:
        if outline:
            canvas.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1,
                                    outline=outline, width=2)
        canvas.create_rectangle(x0 + 2, y1 - 15, x1 - 2, y1 - 2,
                                fill=chip_fill, outline=text_fill)
        canvas.create_text((x0 + x1) / 2, y1 - 8, text=text,
                           fill=text_fill, font=("Helvetica", 8))
