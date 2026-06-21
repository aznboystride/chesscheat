"""Synthetic board-image rendering for the mock recognition pipeline."""

from chesscheat import board

LABELS = ".PNBRQKpnbrqk"


def _pattern_value(label_index, i, j):
    """Compute a deterministic, label-specific pixel value.

    Pseudo-random per piece so that distinct pieces yield low-correlation
    patterns while identical pieces match exactly.

    Args:
        label_index: Index of the piece label in ``LABELS``.
        i: Row offset within the square.
        j: Column offset within the square.

    Returns:
        An integer pixel value in ``[0, 250]``.
    """
    mixed = (label_index + 1) * 1009 + i * 97 + j * 53 + i * j * (label_index + 1) * 13
    return (mixed * 2654435761) % 251


def render_mock_image(board_map, playing_white, cell=8):
    """Render a board map to a synthetic grayscale image.

    Each square is a ``cell`` x ``cell`` block carrying its piece's pattern,
    plus a small constant tint for the square colour. Because matching is
    brightness-invariant, the tint is ignored -- mirroring how a real piece is
    recognised regardless of the light/dark square it sits on.

    Args:
        board_map: A ``{(file_idx, rank): label}`` map to render.
        playing_white: True to lay the board out from white's perspective,
            False for black's.
        cell: Side length, in pixels, of each square.

    Returns:
        An ``8*cell`` x ``8*cell`` grayscale image as a list of lists of ints.
    """
    n = 8 * cell
    image = [[0] * n for _ in range(n)]
    for row in range(8):
        for col in range(8):
            file_rank = board.square_coord(row, col, playing_white)
            label = board_map.get(file_rank, ".")
            k = LABELS.index(label)
            tint = 6 if board.is_light(*file_rank) else -6
            for i in range(cell):
                for j in range(cell):
                    image[row * cell + i][col * cell + j] = _pattern_value(k, i, j) + tint
    return image
