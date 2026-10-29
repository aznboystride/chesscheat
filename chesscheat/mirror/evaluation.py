"""Turning an engine score into an evaluation bar (pure functions).

A score is the dict a ``MoveEngine.evaluate`` returns -- ``{"cp": n}``
(centipawns) or ``{"mate": n}`` (moves to mate), both from **white's**
perspective -- or None when unknown.
"""

import math


def white_share(score):
    """Map a score to the fraction of the bar that is white's.

    Uses lichess's logistic mapping of centipawns to win probability, so
    the bar moves perceptibly for small advantages and saturates slowly.

    Args:
        score: ``{"cp": n}``, ``{"mate": n}`` (white's perspective) or None.

    Returns:
        A float in ``[0, 1]``: 1.0 is a win for white, 0.5 level (and the
        answer for an unknown score).
    """
    if not score:
        return 0.5
    mate = score.get("mate")
    if mate is not None:
        return 1.0 if mate > 0 else 0.0 if mate < 0 else 0.5
    cp = score.get("cp")
    if cp is None:
        return 0.5
    return 0.5 + 0.5 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def score_label(score):
    """Format a score the way engines' bars do.

    Args:
        score: ``{"cp": n}``, ``{"mate": n}`` (white's perspective) or None.

    Returns:
        ``"+0.35"`` / ``"-1.20"`` for centipawns, ``"M3"`` / ``"-M2"`` for
        a forced mate (negative = black mates), ``""`` for unknown.
    """
    if not score:
        return ""
    mate = score.get("mate")
    if mate is not None:
        return f"-M{-mate}" if mate < 0 else f"M{mate}"
    cp = score.get("cp")
    return "" if cp is None else f"{cp / 100:+.2f}"
