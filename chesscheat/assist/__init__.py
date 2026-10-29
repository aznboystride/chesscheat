"""Move-assist: compute the best move and play it on the user's behalf.

On a keybind (``KeyTrigger``), ``assist_move`` builds a full FEN from the
detected position, asks a ``MoveEngine`` for the best move, and drives a
``MoveActuator`` (``PyAutoGuiActuator``) to drag the piece on screen. Two
decision makers are provided behind the ``MoveEngine`` interface:
``StockfishMoveEngine`` (a local engine binary) and ``RemoteMoveEngine`` (a
remote HTTP service). Heavy/IO deps (``chess.engine``, ``pyautogui``,
``pynput``) are imported lazily inside the methods that use them, so
importing this package stays dependency-free.
"""

from chesscheat.assist.stockfish_move_engine import StockfishMoveEngine
from chesscheat.assist.remote_move_engine import RemoteMoveEngine
from chesscheat.assist.pyautogui_actuator import PyAutoGuiActuator, move_pixels
from chesscheat.assist.key_trigger import KeyTrigger
from chesscheat.assist.coordinator import assist_move

__all__ = ["StockfishMoveEngine", "RemoteMoveEngine", "PyAutoGuiActuator",
           "move_pixels", "KeyTrigger", "assist_move"]
