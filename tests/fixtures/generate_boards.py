"""Compose chessboard fixture images from real piece artwork.

The piece PNGs in ``pieces/<set>/`` are real chess sets pulled from the web:

- ``wikipedia`` and ``alpha`` -- PNGs from the chessboard.js project:
  https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/
- ``merida`` -- lichess's SVG set rasterised to PNG:
  https://raw.githubusercontent.com/lichess-org/lila/master/public/piece/merida/

Each set is pasted onto its own two-tone board theme to produce real board
images for a short opening (start, 1.e4, 1...c5, 2.Nf3), written to
``boards/<set>/``. Run from the repo root:

    python3 tests/fixtures/generate_boards.py

The generated boards are committed as test fixtures, so this only needs to be
re-run if the fixtures are regenerated (see this directory's README for how to
(re)fetch the piece artwork).
"""

import os

from PIL import Image

SQUARE = 64

# set name -> (light square colour, dark square colour); deliberately varied to
# also exercise theme-independence.
THEMES = {
    "wikipedia": ((240, 217, 181), (181, 136, 99)),   # classic brown
    "alpha": ((235, 236, 208), (119, 149, 86)),       # green
    "merida": ((222, 227, 230), (140, 162, 173)),     # blue/grey
}

# label -> piece PNG basename (uppercase = white, lowercase = black)
PIECE_FILE = {
    "P": "wP", "N": "wN", "B": "wB", "R": "wR", "Q": "wQ", "K": "wK",
    "p": "bP", "n": "bN", "b": "bB", "r": "bR", "q": "bQ", "k": "bK",
}

HERE = os.path.dirname(os.path.abspath(__file__))
PIECES_DIR = os.path.join(HERE, "pieces")
BOARDS_DIR = os.path.join(HERE, "boards")

BACK_RANK = "RNBQKBNR"


def starting_board():
    """Return the start position as a ``{(file_idx, rank): label}`` map."""
    board = {}
    for f in range(8):
        board[(f, 1)] = BACK_RANK[f]
        board[(f, 2)] = "P"
        board[(f, 7)] = "p"
        board[(f, 8)] = BACK_RANK[f].lower()
    return board


def move(position, *changes):
    """Return a copy of ``position`` with ``(square, label)`` changes applied."""
    updated = dict(position)
    updated.update(changes)
    return updated


def positions():
    """The opening 1.e4 c5 2.Nf3 as named ``{(file_idx, rank): label}`` maps."""
    start = starting_board()
    e4 = move(start, ((4, 2), "."), ((4, 4), "P"))
    c5 = move(e4, ((2, 7), "."), ((2, 5), "p"))
    nf3 = move(c5, ((6, 1), "."), ((5, 3), "N"))
    return {"start": start, "e4": e4, "c5": c5, "nf3": nf3}


def load_pieces(set_name):
    """Load a set's 12 piece images keyed by label, scaled to ``SQUARE``."""
    folder = os.path.join(PIECES_DIR, set_name)
    return {
        label: Image.open(os.path.join(folder, f"{name}.png"))
                     .convert("RGBA").resize((SQUARE, SQUARE))
        for label, name in PIECE_FILE.items()
    }


def render_board(board, pieces, light, dark):
    """Paste piece images onto a two-tone board (white's perspective)."""
    image = Image.new("RGB", (8 * SQUARE, 8 * SQUARE))
    for file_idx in range(8):
        for rank in range(1, 9):
            col, row = file_idx, 8 - rank  # white at the bottom
            is_light = (file_idx + rank) % 2 == 0
            tile = Image.new("RGB", (SQUARE, SQUARE), light if is_light else dark)
            image.paste(tile, (col * SQUARE, row * SQUARE))
            label = board.get((file_idx, rank), ".")
            if label != ".":
                piece = pieces[label]
                image.paste(piece, (col * SQUARE, row * SQUARE), piece)
    return image


def main():
    boards = positions()
    for set_name, (light, dark) in THEMES.items():
        pieces = load_pieces(set_name)
        out_dir = os.path.join(BOARDS_DIR, set_name)
        os.makedirs(out_dir, exist_ok=True)
        for name, board in boards.items():
            path = os.path.join(out_dir, f"{name}.png")
            render_board(board, pieces, light, dark).save(path)
            print("wrote", path)


if __name__ == "__main__":
    main()
