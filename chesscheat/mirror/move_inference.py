"""Inferring the opponent's move from last-move highlights (pure logic).

Chess apps tint the two squares of the last move played. Given a scan of
the real board (``chesscheat.recognition.scan_squares``) these functions
work out, without recognising a single piece, which squares are tinted,
whether each holds one of ours or one of theirs, and -- against the game
model's idea of what is legal -- which opponent move the highlight shows.

Nothing here touches numpy or python-chess: scans are plain dicts and
legality is a predicate the caller supplies, so the logic is testable
without any dependency.
"""

from chesscheat import board


def _square_name(row, col, bottom_white):
    """Name the square drawn at a screen cell.

    Args:
        row: Screen row, 0 at the top.
        col: Screen column, 0 at the left.
        bottom_white: True if white is at the bottom of the captured board.

    Returns:
        The algebraic square name.
    """
    return board.square_name(*board.square_coord(row, col, bottom_white))


def _median(values):
    """Return the median of a non-empty sequence of numbers."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    return (ordered[mid] if len(ordered) % 2
            else (ordered[mid - 1] + ordered[mid]) / 2)


def highlighted_squares(scans, bottom_white, tol=40):
    """Find the squares whose background differs from their colour class.

    Light and dark squares each have one normal colour; a tinted square is
    one whose background is far from the (robust, median) colour of the
    other squares of its class. The class is the chequerboard parity of the
    screen cell, which is the same for either orientation.

    Args:
        scans: ``{(row, col): (background, fraction, brightness)}`` from
            ``scan_squares``.
        bottom_white: Orientation of the captured board.
        tol: Min colour distance (summed over channels) from the class
            median for a square to count as highlighted.

    Returns:
        A frozenset of algebraic square names.
    """
    classes = {parity: [scans[cell][0] for cell in scans
                        if sum(cell) % 2 == parity] for parity in (0, 1)}
    reference = {
        parity: tuple(_median([bg[i] for bg in backgrounds])
                      for i in range(len(backgrounds[0])))
        for parity, backgrounds in classes.items() if backgrounds}
    return frozenset(
        _square_name(row, col, bottom_white)
        for (row, col), (background, _f, _b) in scans.items()
        if sum(abs(a - b) for a, b in
               zip(background, reference[(row + col) % 2])) > tol)


def piece_colours(scans, bottom_white, board_map, playing_white,
                  min_fraction=0.06):
    """Classify every square as empty, holding our piece, or the opponent's.

    Occupancy comes from the scan (enough non-background pixels). Colour is
    decided by brightness, nearest to a reference for each side taken from
    the squares the game model says hold that side's pieces -- so no theme
    knowledge is needed and the references are recomputed from each frame
    (a single piece mid-move cannot sway a median).

    Args:
        scans: ``{(row, col): (background, fraction, brightness)}``.
        bottom_white: Orientation of the captured board.
        board_map: The model's ``{(file_idx, rank): label}`` position.
        playing_white: True if the program (our side) plays white.
        min_fraction: Min fraction of piece pixels for a square to count as
            occupied.

    Returns:
        ``{square_name: "own" | "opponent" | None}`` (None = empty). With no
        usable reference for a side every occupied square reads as the
        opponent's, which leaves legality to decide.
    """
    cells = {_square_name(row, col, bottom_white): (row, col)
             for row, col in scans}
    occupied = {name: scans[cell][2] for name, cell in cells.items()
                if scans[cell][1] >= min_fraction
                and scans[cell][2] is not None}

    def reference(white_side):
        samples = [occupied[board.square_name(f, r)]
                   for (f, r), label in board_map.items()
                   if label != "." and label.isupper() == white_side
                   and board.square_name(f, r) in occupied]
        return _median(samples) if samples else None

    own, theirs = reference(playing_white), reference(not playing_white)

    def classify(brightness):
        if own is None or theirs is None:
            return "opponent"
        return ("own" if abs(brightness - own) < abs(brightness - theirs)
                else "opponent")

    return {name: (classify(occupied[name]) if name in occupied else None)
            for name in cells}


def infer_opponent_move(highlighted, colours, is_legal):
    """Pick the opponent move a last-move highlight shows, if any.

    Every ordered pair of highlighted squares is a candidate; it is kept
    only if the origin is now empty, the destination now holds an opponent
    piece, and the move is legal for the opponent in the model. That rules
    out our own move's highlight (no opponent piece can start from our
    squares), a stale highlight of a move already in the model (the piece
    is then on the origin, not off it), a capture still animating (the
    destination shows our piece) and any extra tinted square such as a
    king in check (no legal pairing with it).

    Args:
        highlighted: Iterable of highlighted square names.
        colours: ``{square_name: "own" | "opponent" | None}`` from
            ``piece_colours``.
        is_legal: ``is_legal(from_name, to_name)`` predicate for the side
            to move (the opponent).

    Returns:
        The ``(from_name, to_name)`` of the single consistent candidate, or
        None when there is none or more than one.
    """
    squares = sorted(set(highlighted))
    candidates = [(origin, dest) for origin in squares for dest in squares
                  if origin != dest and colours.get(origin) is None
                  and colours.get(dest) == "opponent"
                  and is_legal(origin, dest)]
    return candidates[0] if len(candidates) == 1 else None
