"""Live chessboard reader.

Prompts for the screen bounding box of a chessboard (in the starting
position) and the side you are playing, then repeatedly screenshots the
board and prints its current state as text.

Recognition is done with template matching: the starting position tells us
exactly which piece sits on every square, so the first capture is used to
build a template for each piece type (and for empty squares). Every later
frame classifies each square against those templates -- no external piece
images required.
"""

import time

# cv2 and screenshot are imported lazily inside the functions that need them
# so the pure board logic (coordinates, rendering, FEN) can be imported and
# unit-tested without the heavy capture/vision dependencies installed.

SZ = 48          # templates / squares are normalised to SZ x SZ
MARGIN = 0.12    # fraction trimmed from each side of a square before matching
BACK_RANK = ["R", "N", "B", "Q", "K", "B", "N", "R"]


def prompt_box():
    """Ask for the top-left and bottom-right corners of the board."""
    def ask(label):
        while True:
            try:
                x, y = input(f"Enter {label} corner as 'x y': ").split()
                return int(x), int(y)
            except ValueError:
                print("  Please enter two integers separated by a space.")

    x1, y1 = ask("top-left")
    x2, y2 = ask("bottom-right")
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def prompt_side():
    while True:
        side = input("Are you playing white or black? (w/b): ").strip().lower()
        if side in ("w", "white"):
            return True
        if side in ("b", "black"):
            return False
        print("  Please answer 'w' or 'b'.")


def square_coord(row, col, playing_white):
    """Map a screen grid cell (row 0 = top) to (file_index, rank).

    file_index: 0=a .. 7=h.  rank: 1..8.
    """
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


def get_square(board_img, row, col):
    """Crop the inner part of one square from the full board image."""
    h, w = board_img.shape[:2]
    sy, ey = int(row * h / 8), int((row + 1) * h / 8)
    sx, ex = int(col * w / 8), int((col + 1) * w / 8)
    cell = board_img[sy:ey, sx:ex]
    ch, cw = cell.shape[:2]
    my, mx = int(ch * MARGIN), int(cw * MARGIN)
    inner = cell[my:ch - my, mx:cw - mx]
    return inner if inner.size else cell


def prep(cell):
    """Normalise a square to a fixed-size grayscale patch for matching."""
    import cv2

    if cell.shape[2] == 4:
        gray = cv2.cvtColor(cell, cv2.COLOR_BGRA2GRAY)
    else:
        gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (SZ, SZ))


def build_templates(board_img, playing_white):
    """Use the starting position to build a template per piece / empty square."""
    templates = []  # list of (label, patch)
    for row in range(8):
        for col in range(8):
            file_idx, rank = square_coord(row, col, playing_white)
            label = start_label(file_idx, rank)
            patch = prep(get_square(board_img, row, col))
            templates.append((label, patch))
    return templates


def classify(patch, templates):
    """Return the label of the best-matching template for a square."""
    import cv2

    best_label, best_score = ".", -2.0
    for label, tmpl in templates:
        score = cv2.matchTemplate(patch, tmpl, cv2.TM_CCOEFF_NORMED)[0, 0]
        if score > best_score:
            best_score, best_label = score, label
    return best_label


def read_board(board_img, templates, playing_white):
    """Return {(file_idx, rank): label} for every square."""
    board = {}
    for row in range(8):
        for col in range(8):
            patch = prep(get_square(board_img, row, col))
            label = classify(patch, templates)
            file_idx, rank = square_coord(row, col, playing_white)
            board[(file_idx, rank)] = label
    return board


def render(board, playing_white):
    """Render the board as text from the player's perspective."""
    ranks = range(8, 0, -1) if playing_white else range(1, 9)
    files = range(8) if playing_white else range(7, -1, -1)
    header = "   " + "  ".join(chr(ord("a") + f) for f in files)
    lines = [header]
    for rank in ranks:
        cells = [board.get((f, rank), ".") for f in files]
        row = f"{rank}  " + "  ".join(cells) + f"  {rank}"
        lines.append(row)
    lines.append(header)
    return "\n".join(lines)


def to_fen(board):
    """Piece-placement FEN field, always from the canonical (white) view."""
    rows = []
    for rank in range(8, 0, -1):
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
        rows.append("".join(parts))
    return "/".join(rows)


def main():
    from screenshot import screenshot

    print("=== Live Chessboard Reader ===")
    print("Make sure the board is in the standard starting position.\n")

    try:
        import gui
        playing_white = gui.select_side()
        x1, y1, x2, y2 = gui.select_box()
    except Exception as exc:  # no display / Tk unavailable -> text fallback
        print(f"GUI unavailable ({exc}); falling back to text prompts.\n")
        playing_white = prompt_side()
        x1, y1, x2, y2 = prompt_box()

    input("\nPosition the board in the starting position, then press Enter "
          "to calibrate...")
    templates = build_templates(screenshot(x1, y1, x2, y2), playing_white)
    print("Calibrated. Reading board... (press Ctrl+C to stop)\n")

    last = None
    try:
        while True:
            board = read_board(screenshot(x1, y1, x2, y2), templates,
                               playing_white)
            if board != last:
                print("\033[H\033[J", end="")  # clear screen
                print(render(board, playing_white))
                print("\nFEN:", to_fen(board))
                last = board
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
