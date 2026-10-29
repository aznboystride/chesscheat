"""Tests for the move-assist feature: FEN/geometry helpers, coordinator, loop.

The whole assist path is exercised through the dependency-free mock stack --
no Stockfish, pyautogui, pynput, GUI, screen or numpy required. A single
guarded test runs the real ``StockfishMoveEngine`` when a Stockfish binary is
actually available.
"""

import shutil
import unittest

from chesscheat import app, board
from chesscheat.assist import assist_move, move_pixels
from chesscheat.interfaces import MoveEngine, MoveActuator, MoveTrigger
from chesscheat.mocks import (MockSetupProvider, MockFrameSource,
                              MockImageBackend, MockMoveEngine,
                              MockMoveActuator, MockMoveTrigger,
                              render_mock_image)
from chesscheat.recognition import TemplateBoardRecognizer


class BoardCoordHelperTests(unittest.TestCase):
    def test_cell_of_inverts_square_coord(self):
        for playing_white in (True, False):
            for row in range(8):
                for col in range(8):
                    fr = board.square_coord(row, col, playing_white)
                    self.assertEqual(board.cell_of(*fr, playing_white),
                                     (row, col))

    def test_square_name_and_parse_round_trip(self):
        for file_idx in range(8):
            for rank in range(1, 9):
                name = board.square_name(file_idx, rank)
                self.assertEqual(board.parse_square(name), (file_idx, rank))
        self.assertEqual(board.square_name(4, 2), "e2")
        self.assertEqual(board.parse_square("h8"), (7, 8))


class FenHelperTests(unittest.TestCase):
    def test_castling_field_full_at_start(self):
        self.assertEqual(board.castling_field(board.starting_board()), "KQkq")

    def test_castling_field_drops_side_when_rook_missing(self):
        pos = dict(board.starting_board())
        del pos[(7, 1)]                 # white kingside rook gone
        self.assertEqual(board.castling_field(pos), "Qkq")

    def test_castling_field_none_when_kings_moved(self):
        pos = dict(board.starting_board())
        pos[(4, 1)], pos[(5, 1)] = ".", "K"   # white king off e1
        pos[(4, 8)], pos[(5, 8)] = ".", "k"   # black king off e8
        self.assertEqual(board.castling_field(pos), "-")

    def test_to_full_fen_start_white_to_move(self):
        self.assertEqual(
            board.to_full_fen(board.starting_board(), white_to_move=True),
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

    def test_to_full_fen_black_to_move(self):
        fen = board.to_full_fen(board.starting_board(), white_to_move=False)
        self.assertEqual(fen.split()[1], "b")


class MovePixelsTests(unittest.TestCase):
    # An 800x800 board whose top-left is at screen (100, 200): 100px squares.
    BOX = (100, 200, 900, 1000)

    def test_white_orientation_centres(self):
        (fx, fy), (tx, ty) = move_pixels("e2e4", self.BOX, True)
        # e-file is col 4 -> centre x = 100 + 4.5*100 = 550 for both squares.
        self.assertEqual((fx, tx), (550.0, 550.0))
        # e2 is row 6 (y=850), e4 is row 4 (y=650): the piece moves up-screen.
        self.assertEqual((fy, ty), (850.0, 650.0))

    def test_black_orientation_flips(self):
        (fx, fy), (tx, ty) = move_pixels("e2e4", self.BOX, False)
        # From black's view e-file is col 3 (x=450); e2 row 1, e4 row 3.
        self.assertEqual((fx, tx), (450.0, 450.0))
        self.assertEqual((fy, ty), (350.0, 550.0))

    def test_promotion_suffix_ignored(self):
        self.assertEqual(move_pixels("e7e8q", self.BOX, True),
                         move_pixels("e7e8", self.BOX, True))

    def test_centres_lie_inside_their_squares(self):
        (fx, fy), _ = move_pixels("a1a1", self.BOX, True)
        self.assertTrue(100 < fx < 200 and 900 < fy < 1000)  # a1 bottom-left


class AssistMoveTests(unittest.TestCase):
    def test_builds_fen_with_side_to_move_and_plays(self):
        engine = MockMoveEngine("e2e4")
        actuator = MockMoveActuator()
        box = (0, 0, 800, 800)
        played = assist_move(board.starting_board(), True, box,
                             engine, actuator)
        self.assertEqual(played, "e2e4")
        # The engine saw a white-to-move full FEN of the start position.
        self.assertEqual(engine.seen_fens,
                         ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR "
                          "w KQkq - 0 1"])
        self.assertEqual(actuator.applied, [("e2e4", box, True)])

    def test_black_to_move_fen(self):
        engine = MockMoveEngine("e7e5")
        assist_move(board.starting_board(), False, (0, 0, 8, 8),
                    engine, MockMoveActuator())
        self.assertEqual(engine.seen_fens[0].split()[1], "b")

    def test_no_move_does_not_actuate(self):
        actuator = MockMoveActuator()
        played = assist_move(board.starting_board(), True, (0, 0, 8, 8),
                             MockMoveEngine(move=None), actuator)
        self.assertIsNone(played)
        self.assertEqual(actuator.applied, [])


class RunTriggerIntegrationTests(unittest.TestCase):
    def _pipeline(self, trigger, on_trigger, frames_played=2):
        positions = [board.starting_board()]
        e4 = dict(positions[0])
        e4[(4, 2)], e4[(4, 4)] = ".", "P"
        positions.append(e4)
        frames = [render_mock_image(p, True) for p in positions]
        app.run(
            MockSetupProvider(True, (0, 0, 8, 8)),
            lambda box: MockFrameSource(frames),
            TemplateBoardRecognizer(MockImageBackend()),
            on_board=lambda board_map, _white: None,
            trigger=trigger, on_trigger=on_trigger,
        )

    def test_trigger_started_and_stopped(self):
        trigger = MockMoveTrigger()
        self._pipeline(trigger, lambda *a: None)
        self.assertTrue(trigger.started)
        self.assertTrue(trigger.stopped)

    def test_fired_trigger_invokes_on_trigger_with_reading(self):
        trigger = MockMoveTrigger()
        trigger.fire()
        calls = []
        self._pipeline(
            trigger,
            lambda board_map, white, box: calls.append((board_map, white, box)))
        self.assertEqual(len(calls), 1)
        board_map, white, box = calls[0]
        self.assertEqual(white, True)
        self.assertEqual(box, (0, 0, 8, 8))
        # Calibration consumed the start frame, so the first looped frame --
        # and thus the reading handed to on_trigger -- is the e4 position.
        self.assertEqual(board.to_fen(board_map),
                         "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR")

    def test_unfired_trigger_never_invokes(self):
        calls = []
        self._pipeline(MockMoveTrigger(), lambda *a: calls.append(a))
        self.assertEqual(calls, [])

    def test_end_to_end_engine_and_actuator(self):
        # A fired trigger drives the whole assist chain through run().
        trigger = MockMoveTrigger()
        trigger.fire()
        engine, actuator = MockMoveEngine("e2e4"), MockMoveActuator()
        self._pipeline(
            trigger,
            lambda board_map, white, box: assist_move(
                board_map, white, box, engine, actuator))
        self.assertEqual(actuator.applied, [("e2e4", (0, 0, 8, 8), True)])


class TriggerStartFailureTests(unittest.TestCase):
    """A trigger that fails to start disables the assist, not the reader."""

    class _FailingTrigger(MockMoveTrigger):
        def start(self):
            raise PermissionError("no input monitoring")

    def test_reader_survives_a_failing_trigger(self):
        positions = [board.starting_board()]
        e4 = dict(positions[0])
        e4[(4, 2)], e4[(4, 4)] = ".", "P"
        positions.append(e4)
        frames = [render_mock_image(p, True) for p in positions]

        trigger = self._FailingTrigger()
        trigger.fire()   # even though queued, it must never be polled
        boards, assists = [], []
        # Must not raise despite start() failing.
        app.run(
            MockSetupProvider(True, (0, 0, 8, 8)),
            lambda box: MockFrameSource(frames),
            TemplateBoardRecognizer(MockImageBackend()),
            on_board=lambda board_map, _white: boards.append(board_map),
            trigger=trigger,
            on_trigger=lambda *a: assists.append(a),
        )
        self.assertEqual(len(boards), 1)   # the reader ran normally
        self.assertEqual(assists, [])      # assist path was disabled


class KeyTriggerPermissionTests(unittest.TestCase):
    def test_permission_ok_true_off_macos(self):
        import sys
        from chesscheat.assist.key_trigger import KeyTrigger, has_input_monitoring

        if sys.platform != "darwin":
            self.assertTrue(has_input_monitoring())
            self.assertTrue(KeyTrigger("a").permission_ok())

    def test_start_raises_instead_of_crashing_without_permission(self):
        from chesscheat.assist.key_trigger import KeyTrigger

        trigger = KeyTrigger("a")
        # Force the "no permission" branch regardless of platform.
        trigger.permission_ok = lambda: False
        with self.assertRaises(PermissionError):
            trigger.start()


class InterfaceConformanceTests(unittest.TestCase):
    def test_mocks_implement_interfaces(self):
        self.assertIsInstance(MockMoveEngine(), MoveEngine)
        self.assertIsInstance(MockMoveActuator(), MoveActuator)
        self.assertIsInstance(MockMoveTrigger(), MoveTrigger)


@unittest.skipUnless(shutil.which("stockfish"), "requires a Stockfish binary")
class StockfishEngineTests(unittest.TestCase):
    def test_best_move_from_start_is_a_legal_opening(self):
        from chesscheat.assist import StockfishMoveEngine

        engine = StockfishMoveEngine(think_time=0.1)
        uci = engine.best_move(board.to_full_fen(board.starting_board(), True))
        # 20 legal first moves; each is a 4-char UCI from a home square.
        self.assertRegex(uci, r"^[a-h][12][a-h][1-4]$")

    def test_game_over_position_returns_none(self):
        from chesscheat.assist import StockfishMoveEngine

        engine = StockfishMoveEngine(think_time=0.1)
        # Fool's mate: black has delivered checkmate, white to move.
        fen = ("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR "
               "w KQkq - 1 3")
        self.assertIsNone(engine.best_move(fen))


if __name__ == "__main__":
    unittest.main()
