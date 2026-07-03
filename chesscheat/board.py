"""Pure chessboard logic: coordinates, labels, rendering and FEN.

This module has no third-party dependencies and no I/O, so it can be imported
and unit-tested anywhere. It is the orientation-independent source of truth:
screen grid cells are ``(row, col)`` with row 0 at the top, while chess
coordinates are ``(file_idx, rank)`` with file_idx 0=a..7=h and rank 1..8.
"""

BACK_RANK = ["R", "N", "B", "Q", "K", "B", "N", "R"]
FILES = "abcdefgh"

_PIECE_NAMES = {"p": "pawn", "n": "knight", "b": "bishop",
                "r": "rook", "q": "queen", "k": "king"}


def piece_name(label):
    """Return the human-readable name of a piece label.

    Args:
        label: A piece letter (uppercase white, lowercase black),
            e.g. ``'N'`` or ``'q'``.

    Returns:
        The piece's name, e.g. ``'knight'`` or ``'queen'``.

    Raises:
        KeyError: If ``label`` is not a piece letter.
    """
    return _PIECE_NAMES[label.lower()]


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


def cell_of(file_idx, rank, playing_white):
    """Convert chess coordinates back to a screen grid cell.

    The inverse of ``square_coord``: given a chess square and the board
    orientation, return where it sits in the 8x8 screen grid.

    Args:
        file_idx: File index, 0=a..7=h.
        rank: Rank, 1..8.
        playing_white: True if the board is shown from white's perspective.

    Returns:
        A ``(row, col)`` tuple with row 0 at the top and col 0 at the left.
    """
    if playing_white:
        return 8 - rank, file_idx
    return rank - 1, 7 - file_idx


def square_name(file_idx, rank):
    """Return the algebraic name of a square.

    Args:
        file_idx: File index, 0=a..7=h.
        rank: Rank, 1..8.

    Returns:
        The square in algebraic notation, e.g. ``"e4"``.
    """
    return f"{FILES[file_idx]}{rank}"


def parse_square(name):
    """Parse an algebraic square name into chess coordinates.

    Args:
        name: A square in algebraic notation, e.g. ``"e4"``.

    Returns:
        A ``(file_idx, rank)`` tuple.
    """
    return FILES.index(name[0]), int(name[1])


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


def castling_field(board):
    """Infer FEN castling rights from where the kings and rooks sit.

    A right is granted only when the king and the relevant rook are both on
    their home squares. This can over-grant if a piece returned home after
    moving, but for an image-only reader it keeps engine suggestions sane
    without needing move history.

    Args:
        board: A ``{(file_idx, rank): label}`` map.

    Returns:
        The FEN castling field in ``KQkq`` order, or ``"-"`` if none apply.
    """
    rights = []
    if board.get((4, 1)) == "K":
        if board.get((7, 1)) == "R":
            rights.append("K")
        if board.get((0, 1)) == "R":
            rights.append("Q")
    if board.get((4, 8)) == "k":
        if board.get((7, 8)) == "r":
            rights.append("k")
        if board.get((0, 8)) == "r":
            rights.append("q")
    return "".join(rights) or "-"


def to_full_fen(board, white_to_move):
    """Build a complete FEN from a board map and whose turn it is.

    The placement is canonical (white view); castling rights are inferred
    from piece positions; en passant is left unknown (``"-"``) and the clocks
    are set to a neutral ``0 1``. This is enough for an engine to pick a move.

    Args:
        board: A ``{(file_idx, rank): label}`` map.
        white_to_move: True if it is white's turn, False for black's.

    Returns:
        A full FEN string, e.g.
        ``"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"``.
    """
    side = "w" if white_to_move else "b"
    return f"{to_fen(board)} {side} {castling_field(board)} - 0 1"
