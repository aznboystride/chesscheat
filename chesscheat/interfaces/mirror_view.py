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
