"""Playing styles: choosing among an engine's top lines by character.

Stockfish has no style knobs, so style is applied *around* the engine:
ask it for its best few lines (``MultiPV``), keep those within a margin of
the best score, and pick one by a rule. ``choose_move`` is the pure
chooser; ``aggression`` and ``solidity`` score a single move's character
from the position (python-chess, imported lazily, for move semantics).

Styles:

- ``"best"`` -- the engine's first choice (no style);
- ``"aggressive"`` -- prefers checks, captures, moves into the enemy half
  and towards the enemy king, dislikes castling and retreats;
- ``"solid"`` -- prefers castling, quiet moves and development, dislikes
  king walks, captures and early queen sorties;
- ``"unusual"`` -- avoids the engine's first choice whenever another line
  is within the margin, picking one of the alternatives at random.
"""

import random

STYLES = ("best", "aggressive", "solid", "unusual")

_VALUES = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}   # by chess.PieceType


def _features(fen, uci):
    """Describe a move's character in its position.

    Args:
        fen: The position before the move (full FEN).
        uci: The move in UCI notation.

    Returns:
        A dict of plain facts: ``capture``, ``captured`` (value), ``check``,
        ``castling``, ``piece`` (type number), ``forward`` (ranks gained
        towards the enemy side), ``into_enemy_half``, ``near_king`` (lands
        within four squares of the enemy king, nearer than it started),
        ``develops`` (a minor piece leaving its home rank), ``king_move``.
    """
    import chess

    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    piece = board.piece_at(move.from_square)
    piece_type = piece.piece_type if piece else chess.PAWN
    victim = board.piece_at(move.to_square)
    captured = (_VALUES[victim.piece_type] if victim
                else 1 if board.is_en_passant(move) else 0)
    home_rank = 0 if board.turn == chess.WHITE else 7
    direction = 1 if board.turn == chess.WHITE else -1
    from_rank, to_rank = (chess.square_rank(move.from_square),
                          chess.square_rank(move.to_square))
    enemy_king = board.king(not board.turn)
    if enemy_king is None:
        near = False
    else:
        after = chess.square_distance(move.to_square, enemy_king)
        near = (after <= 4
                and after < chess.square_distance(move.from_square, enemy_king))
    enemy_half = (to_rank >= 4) if board.turn == chess.WHITE else (to_rank <= 3)
    return {
        "capture": board.is_capture(move),
        "captured": captured,
        "check": board.gives_check(move),
        "castling": board.is_castling(move),
        "piece": piece_type,
        "forward": (to_rank - from_rank) * direction,
        "into_enemy_half": enemy_half,
        "near_king": near,
        "develops": (piece_type in (chess.KNIGHT, chess.BISHOP)
                     and from_rank == home_rank),
        "king_move": piece_type == chess.KING and not board.is_castling(move),
    }


def aggression(fen, uci):
    """Score how aggressive a move is (higher = more aggressive).

    Args:
        fen: The position before the move (full FEN).
        uci: The move in UCI notation.

    Returns:
        An integer: checks and captures score most, advancing into the
        enemy half or landing near the enemy king a little; castling and
        retreating count against.
    """
    f = _features(fen, uci)
    return ((3 if f["check"] else 0) + (2 if f["capture"] else 0)
            + (1 if f["into_enemy_half"] else 0)
            + (1 if f["near_king"] else 0)
            - (2 if f["castling"] else 0) - (1 if f["forward"] < 0 else 0))


def solidity(fen, uci):
    """Score how solid a move is (higher = more solid).

    Args:
        fen: The position before the move (full FEN).
        uci: The move in UCI notation.

    Returns:
        An integer: castling and developing moves score most, quiet moves a
        little; king walks, captures and queen moves count against.
    """
    f = _features(fen, uci)
    quiet = not f["capture"] and not f["check"]
    return ((3 if f["castling"] else 0) + (2 if f["develops"] else 0)
            + (1 if quiet else 0) - (2 if f["king_move"] else 0)
            - (1 if f["capture"] else 0) - (1 if f["piece"] == 5 else 0))


def eligible_moves(candidates, margin_cp):
    """Keep the candidates within ``margin_cp`` of the best score.

    Args:
        candidates: ``[(uci, cp)]`` from the mover's point of view, best
            first (an engine's MultiPV order).
        margin_cp: How far below the best score a line may be.

    Returns:
        The qualifying ``(uci, cp)`` pairs, in the given order.
    """
    if not candidates:
        return []
    best = candidates[0][1]
    return [c for c in candidates if c[1] >= best - margin_cp]


def choose_move(candidates, style, fen, margin_cp=30, rng=random.random):
    """Pick a move from an engine's top lines according to a style.

    Args:
        candidates: ``[(uci, cp)]`` from the mover's point of view, best
            first (mates expressed as large centipawn values).
        style: One of ``STYLES``; anything else behaves like ``"best"``.
        fen: The position the candidates were found in (full FEN).
        margin_cp: Max centipawns below the best line a pick may be.
        rng: Zero-argument callable returning a float in ``[0, 1)``, used
            by ``"unusual"``.

    Returns:
        The chosen move in UCI notation, or None if there are no
        candidates.
    """
    pool = eligible_moves(candidates, margin_cp)
    if not pool:
        return None
    if style == "aggressive":
        return max(pool, key=lambda c: (aggression(fen, c[0]), c[1]))[0]
    if style == "solid":
        return max(pool, key=lambda c: (solidity(fen, c[0]), c[1]))[0]
    if style == "unusual" and len(pool) > 1:
        alternatives = pool[1:]
        return alternatives[min(int(rng() * len(alternatives)),
                                len(alternatives) - 1)][0]
    return pool[0][0]
