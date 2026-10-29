"""Tkinter front-end: setup dialogs, the live capture preview, mirror board."""

from chesscheat.gui.dialogs import select_side, select_box, confirm_box
from chesscheat.gui.live_preview import LivePreview
from chesscheat.gui.mirror_board import MirrorBoardWindow

__all__ = ["select_side", "select_box", "confirm_box", "LivePreview",
           "MirrorBoardWindow"]
