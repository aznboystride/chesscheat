"""Move-assist orchestration: read a position, pick a move, play it."""

from chesscheat import board


def assist_move(board_map, playing_white, box, engine, actuator):
    """Compute the best move for the current board and play it on screen.

    Builds a full FEN from the detected position (the user's side is to move,
    since the assist fires on the user's turn), asks the engine for the best
    move, and drives the actuator to play it. Pure orchestration -- all
    effects go through the injected ``engine`` and ``actuator``.

    Args:
        board_map: The detected ``{(file_idx, rank): label}`` position.
        playing_white: True if the user (to move) plays white.
        box: The board's ``(x1, y1, x2, y2)`` screen bounding box.
        engine: A ``MoveEngine`` that turns a FEN into a best move.
        actuator: A ``MoveActuator`` that plays a UCI move on the board.

    Returns:
        The UCI move that was played, or None if the engine offered none (in
        which case the actuator is not invoked).
    """
    fen = board.to_full_fen(board_map, white_to_move=playing_white)
    uci = engine.best_move(fen)
    if uci:
        actuator.apply(uci, box, playing_white)
    return uci
