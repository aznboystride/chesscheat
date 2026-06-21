"""Pure chessboard logic: coordinates, labels, rendering and FEN.

This module has no third-party dependencies and no I/O, so it can be imported
and unit-tested anywhere. It is the orientation-independent source of truth:
screen grid cells are ``(row, col)`` with row 0 at the top, while chess
coordinates are ``(file_idx, rank)`` with file_idx 0=a..7=h and rank 1..8.
"""

BACK_RANK = ["R", "N", "B", "Q", "K", "B", "N", "R"]


def square_coord(row, col, playing_white):
    """Convert a screen grid cell to chess coordinates.

    This is the single place board orientation is handled.

    Args:
        row: Screen grid row, 0 at the top.
        col: Screen grid column, 0 at the left.
        playing_white: True if the board is shown from white's perspective.

    Returns:
        A ``(file_idx, rank)`` tuple, with file_idx 0=a..7=h and rank 1..8.
    """
    if playing_white:
        return col, 8 - row
    return 7 - col, row + 1


def start_label(file_idx, rank):
    """Return the piece on a square in the starting position.

    Args:
        file_idx: File index, 0=a..7=h.
        rank: Rank, 1..8.

    Returns:
        The piece letter (uppercase white, lowercase black), or ``'.'`` for an
        empty square.
    """
    if rank == 1:
        return BACK_RANK[file_idx]
    if rank == 2:
        return "P"
    if rank == 7:
        return "p"
    if rank == 8:
        return BACK_RANK[file_idx].lower()
    return "."


def is_light(file_idx, rank):
    """Return whether a square is a light square.

    Args:
        file_idx: File index, 0=a..7=h.
        rank: Rank, 1..8.

    Returns:
        True for a light square (a8 and h1 are light), False for a dark one.
    """
    return (file_idx + rank) % 2 == 0


def starting_board():
    """Build the standard starting position.

    Returns:
        A ``{(file_idx, rank): label}`` map covering all 64 squares.
    """
    return {(f, rank): start_label(f, rank)
            for f in range(8) for rank in range(1, 9)}


def render(board, playing_white):
    """Render a board as text from the player's perspective.

    Args:
        board: A ``{(file_idx, rank): label}`` map; missing squares render as
            ``'.'``.
        playing_white: True to orient the output from white's perspective,
            False for black's.

    Returns:
        A multi-line string with file/rank labels bordering an 8x8 grid.
    """
    ranks = range(8, 0, -1) if playing_white else range(1, 9)
    files = range(8) if playing_white else range(7, -1, -1)
    header = "   " + "  ".join(chr(ord("a") + f) for f in files)
    rows = (f"{rank}  " + "  ".join(board.get((f, rank), ".") for f in files)
            + f"  {rank}" for rank in ranks)
    return "\n".join([header, *rows, header])


def to_fen(board):
    """Build the piece-placement FEN field for a board.

    The output is always from the canonical white view, regardless of the
    perspective the board was read in.

    Args:
        board: A ``{(file_idx, rank): label}`` map; missing squares are empty.

    Returns:
        The piece-placement field of a FEN string (the part before the first
        space), e.g. ``"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"``.
    """
    def rank_to_fen(rank):
        run, parts = 0, []
        for file_idx in range(8):
            label = board.get((file_idx, rank), ".")
            if label == ".":
                run += 1
            else:
                if run:
                    parts.append(str(run))
                    run = 0
                parts.append(label)
        if run:
            parts.append(str(run))
        return "".join(parts)

    return "/".join(rank_to_fen(rank) for rank in range(8, 0, -1))
