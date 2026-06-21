"""Pure chessboard logic: coordinates, labels, rendering and FEN.

This module has no third-party dependencies and no I/O, so it can be imported
and unit-tested anywhere. It is the orientation-independent source of truth:
screen grid cells are ``(row, col)`` with row 0 at the top, while chess
coordinates are ``(file_idx, rank)`` with file_idx 0=a..7=h and rank 1..8.
"""

BACK_RANK = ["R", "N", "B", "Q", "K", "B", "N", "R"]


def square_coord(row, col, playing_white):
    """Map a screen grid cell (row 0 = top) to ``(file_idx, rank)``."""
    if playing_white:
        return col, 8 - row
    return 7 - col, row + 1


def start_label(file_idx, rank):
    """Piece on a given square in the starting position ('.' if empty)."""
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
    """True if the square is a light square (a8 and h1 are light)."""
    return (file_idx + rank) % 2 == 0


def starting_board():
    """The standard starting position as a ``{(file_idx, rank): label}`` map."""
    return {(f, rank): start_label(f, rank)
            for f in range(8) for rank in range(1, 9)}


def render(board, playing_white):
    """Render the board as text from the player's perspective."""
    ranks = range(8, 0, -1) if playing_white else range(1, 9)
    files = range(8) if playing_white else range(7, -1, -1)
    header = "   " + "  ".join(chr(ord("a") + f) for f in files)
    rows = (f"{rank}  " + "  ".join(board.get((f, rank), ".") for f in files)
            + f"  {rank}" for rank in ranks)
    return "\n".join([header, *rows, header])


def to_fen(board):
    """Piece-placement FEN field, always from the canonical (white) view."""
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
