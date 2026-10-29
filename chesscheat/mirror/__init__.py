"""Mirror mode: play the opponent's moves on a GUI, the program answers.

No piece recognition. The user mirrors each opponent move on a
``MirrorView`` board -- or lets ``OpponentWatcher`` read it off the real
app's last-move highlight (``move_inference``); ``MirrorGame`` asks a
``MoveEngine`` for the reply and plays it both on the mirror board and in
the real chess app (through a ``MoveActuator`` dragging the mouse over the
app's bounding box).
``gui_placement`` keeps the GUI window clear of that box and
``view_bottom_white`` orients it like the real app (the user's side at the
bottom). python-chess is imported lazily, so importing this package stays
dependency-free.
"""

from chesscheat.mirror.mirror_game import MirrorGame, position_map
from chesscheat.mirror.placement import gui_placement, view_bottom_white
from chesscheat.mirror.opponent_watcher import OpponentWatcher
from chesscheat.mirror.evaluation import white_share, score_label
from chesscheat.mirror.move_inference import (highlighted_squares,
                                              piece_colours,
                                              infer_opponent_move)

__all__ = ["MirrorGame", "position_map", "gui_placement", "view_bottom_white",
           "OpponentWatcher", "highlighted_squares", "piece_colours",
           "infer_opponent_move", "white_share", "score_label"]
