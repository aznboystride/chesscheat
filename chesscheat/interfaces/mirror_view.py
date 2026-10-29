"""The ``MirrorView`` interface."""

from abc import ABC, abstractmethod


class MirrorView(ABC):
    """Displays the mirror game's board and collects the opponent's moves.

    The view is passive about game logic: it renders whatever position it is
    given and reports the squares the user picks (via the callback it was
    constructed with) to a controller, which validates and responds.
    """

    @abstractmethod
    def update(self, board_map, last_move, status):
        """Redraw the board.

        Args:
            board_map: A ``{(file_idx, rank): label}`` map of the position
                (``'.'`` for empty squares).
            last_move: The most recently played move in UCI notation, to
                highlight, or None.
            status: A short message for the user, e.g. whose move it is.
        """

    @abstractmethod
    def run(self):
        """Show the view and block until the user closes it."""

    def update_evaluation(self, white_share, label):
        """Show the engine's evaluation of the current position.

        Optional: the default shows nothing.

        Args:
            white_share: Fraction of the bar that is white's, in ``[0, 1]``
                (0.5 = level or unknown).
            label: Short text such as ``"+0.35"``, ``"M3"`` or a game
                result; empty when unknown.
        """
        return None

    def set_orientation(self, bottom_white):
        """Redraw with a side at the bottom (after a new game as the other
        colour).

        Optional: the default does nothing.

        Args:
            bottom_white: True to put white at the bottom.
        """
        return None

    def square_position(self, name):
        """Return where a square is on screen, for parking the pointer.

        Optional: the default reports no position, which disables the
        pointer-return behaviour.

        Args:
            name: A square in algebraic notation, e.g. ``"e5"``.

        Returns:
            The square centre's absolute screen ``(x, y)``, or None if the
            view cannot say (not shown yet, or not a screen view).
        """
        return None
