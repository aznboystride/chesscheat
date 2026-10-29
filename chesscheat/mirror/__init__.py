"""Mirror mode: play the opponent's moves on a GUI, the program answers.

No screen detection. The user mirrors each opponent move on a
``MirrorView`` board; ``MirrorGame`` asks a ``MoveEngine`` for the reply and
plays it both on the mirror board and in the real chess app (through a
``MoveActuator`` dragging the mouse over the app's bounding box).
``gui_placement`` keeps the GUI window clear of that box and
``view_bottom_white`` orients it like the real app (the user's side at the
bottom). python-chess is imported lazily, so importing this package stays
dependency-free.
"""

from chesscheat.mirror.mirror_game import MirrorGame, position_map
from chesscheat.mirror.placement import gui_placement, view_bottom_white

__all__ = ["MirrorGame", "position_map", "gui_placement", "view_bottom_white"]
