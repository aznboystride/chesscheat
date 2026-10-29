"""Tests for mirror mode: placement, controller, remote engine, CLI.

The controller is driven entirely through mocks (``MockMoveEngine``,
``MockMoveActuator``, ``MockMirrorView``) -- no GUI, no mouse, no Stockfish.
It needs python-chess for the rules and is ``skipUnless``-guarded on it; the
placement, remote-engine and parser tests are dependency-free (the remote
engine is exercised against a real local ``http.server``).
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    import chess  # noqa: F401
    _HAVE_CHESS = True
except ImportError:
    _HAVE_CHESS = False

from chesscheat import board
from chesscheat.app import build_parser
from chesscheat.assist import RemoteMoveEngine
from chesscheat.interfaces import MirrorView, MoveEngine
from chesscheat.mirror import gui_placement, MirrorGame, position_map
from chesscheat.mocks import (MockMoveEngine, MockMoveActuator,
                              MockMirrorView)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
BOX = (100, 100, 900, 900)


class PlacementTests(unittest.TestCase):
    """The GUI window is placed clear of the real board."""

    SCREEN = (2560, 1440)

    def _overlaps(self, pos, size, box):
        x, y = pos
        w, h = size
        x1, y1, x2, y2 = box
        return x < x2 and x + w > x1 and y < y2 and y + h > y1

    def test_prefers_right_of_the_board(self):
        pos = gui_placement(BOX, *self.SCREEN, 560, 600)
        self.assertEqual(pos, (924, 100))
        self.assertFalse(self._overlaps(pos, (560, 600), BOX))

    def test_falls_back_left_when_no_room_on_the_right(self):
        box = (1900, 100, 2500, 700)       # near the right edge
        pos = gui_placement(box, *self.SCREEN, 560, 600)
        self.assertEqual(pos, (1900 - 24 - 560, 100))
        self.assertFalse(self._overlaps(pos, (560, 600), box))

    def test_falls_back_below_then_above(self):
        wide = (0, 100, 2560, 700)         # spans the full width
        pos = gui_placement(wide, *self.SCREEN, 560, 600)
        self.assertEqual(pos, (0, 724))
        low = (0, 800, 2560, 1440)
        pos = gui_placement(low, *self.SCREEN, 560, 600)
        self.assertEqual(pos, (0, 800 - 24 - 600))

    def test_last_resort_is_the_origin(self):
        everywhere = (0, 0, 2560, 1440)
        self.assertEqual(gui_placement(everywhere, *self.SCREEN, 560, 600),
                         (0, 0))


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class PositionMapTests(unittest.TestCase):
    def test_start_position_matches_board_module(self):
        import chess
        self.assertEqual(position_map(chess.Board()), board.starting_board())

    def test_after_a_move(self):
        import chess
        game = chess.Board()
        game.push_uci("e2e4")
        self.assertEqual(board.to_fen(position_map(game)),
                         "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR")


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class MirrorGameTests(unittest.TestCase):
    def _game(self, playing_white, move="e2e4"):
        engine = MockMoveEngine(move)
        actuator = MockMoveActuator()
        view = MockMirrorView()
        events = []
        game = MirrorGame(playing_white, BOX, engine, actuator, view,
                          on_event=lambda k, d: events.append((k, d)))
        return game, engine, actuator, view, events

    def test_program_as_white_moves_first_in_both_places(self):
        game, engine, actuator, view, events = self._game(True, "e2e4")
        game.start()
        # The engine was asked about the start position, white to move.
        self.assertEqual(engine.seen_fens[0].split()[:2], [START_FEN, "w"])
        # Played in the real app via the actuator with the app's orientation.
        self.assertEqual(actuator.applied, [("e2e4", BOX, True)])
        # And on the mirror board: pawn now on e4, highlighted, waiting.
        board_map, last_move, status = view.updates[-1]
        self.assertEqual(board_map[(4, 4)], "P")
        self.assertEqual(last_move, "e2e4")
        self.assertIn("opponent's move (black)", status)
        self.assertIn(("program", "e2e4"), events)

    def test_program_as_black_waits_for_white(self):
        game, engine, actuator, view, _ = self._game(False, "e7e5")
        game.start()
        self.assertEqual(engine.seen_fens, [])
        self.assertEqual(actuator.applied, [])
        self.assertIn("opponent's move (white)", view.updates[-1][2])

        # The user mirrors white's 1.e4; the engine answers with 1...e5.
        reply = game.submit_move("e2", "e4")
        self.assertEqual(reply, "e7e5")
        self.assertEqual(engine.seen_fens[0].split()[1], "b")
        self.assertEqual(actuator.applied, [("e7e5", BOX, False)])
        self.assertEqual(board.to_fen(game.board_map()),
                         "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR")

    def test_illegal_opponent_move_is_rejected_without_consulting_engine(self):
        game, engine, actuator, view, _ = self._game(False, "e7e5")
        game.start()
        self.assertIsNone(game.submit_move("e2", "e5"))
        self.assertEqual(engine.seen_fens, [])
        self.assertEqual(actuator.applied, [])
        self.assertIn("not a legal move", view.updates[-1][2])
        self.assertEqual(board.to_fen(game.board_map()), START_FEN)

    def test_move_out_of_turn_is_rejected(self):
        game, engine, actuator, view, _ = self._game(True, "e2e4")
        # Before start() it is white's (the program's) turn.
        self.assertIsNone(game.submit_move("e7", "e5"))
        self.assertIn("program's turn", view.updates[-1][2])
        self.assertEqual(engine.seen_fens, [])

    def test_opponent_promotion_defaults_to_queen(self):
        import chess
        game, engine, actuator, view, _ = self._game(True, "a1a2")
        # Hand-build: black pawn on b2 about to promote, white to move first.
        game._game = chess.Board("4k3/8/8/8/8/8/1p6/R3K3 w Q - 0 1")
        game.start()                       # program plays Ra1-a2
        reply = game.submit_move("b2", "b1")
        self.assertEqual(game.board_map()[(1, 1)], "q")

    def test_engine_without_a_move_leaves_mouse_alone(self):
        game, engine, actuator, view, _ = self._game(True, None)
        game.start()
        self.assertEqual(actuator.applied, [])
        self.assertIn("no move", view.updates[-1][2])

    def test_engine_error_is_reported_not_raised(self):
        class Broken(MoveEngine):
            def best_move(self, fen):
                raise RuntimeError("remote down")

        view, events = MockMirrorView(), []
        game = MirrorGame(True, BOX, Broken(), MockMoveActuator(), view,
                          on_event=lambda k, d: events.append((k, d)))
        game.start()                       # must not raise
        self.assertIn("Engine error: remote down", view.updates[-1][2])
        self.assertIn(("engine", "failed: remote down"), events)
        self.assertEqual(board.to_fen(game.board_map()), START_FEN)

    def test_illegal_engine_reply_is_refused(self):
        game, engine, actuator, view, _ = self._game(True, "e2e5")
        game.start()
        self.assertEqual(actuator.applied, [])
        self.assertIn("illegal move", view.updates[-1][2])
        self.assertEqual(board.to_fen(game.board_map()), START_FEN)

    def test_actuator_failure_keeps_the_board_in_sync(self):
        class Jammed(MockMoveActuator):
            def apply(self, uci, box, playing_white):
                raise OSError("no accessibility permission")

        view = MockMirrorView()
        game = MirrorGame(True, BOX, MockMoveEngine("e2e4"), Jammed(), view)
        self.assertEqual(game.start(), None)
        # The move stands on the mirror board even though the drag failed.
        self.assertEqual(game.board_map()[(4, 4)], "P")
        self.assertIn("could not move the mouse", view.updates[-1][2])

    def test_mock_view_satisfies_interface(self):
        self.assertIsInstance(MockMirrorView(), MirrorView)


class _Scheduler:
    """Records deferred callbacks so a test can fire them deliberately."""

    def __init__(self):
        self.pending = []   # (seconds, fn)

    def __call__(self, seconds, fn):
        self.pending.append((seconds, fn))

    def fire(self):
        """Run every pending callback (in order), clearing the queue first."""
        pending, self.pending = self.pending, []
        for _seconds, fn in pending:
            fn()


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class AutoToggleTests(unittest.TestCase):
    """Pausing auto-play lets the user move for the program's side."""

    def _game(self, playing_white, move="e2e4", **kwargs):
        engine, actuator, view = (MockMoveEngine(move), MockMoveActuator(),
                                  MockMirrorView())
        events = []
        game = MirrorGame(playing_white, BOX, engine, actuator, view,
                          on_event=lambda k, d: events.append((k, d)),
                          **kwargs)
        return game, engine, actuator, view, events

    def test_paused_program_white_does_not_move_first(self):
        game, engine, actuator, view, _ = self._game(True, auto=False)
        game.start()
        self.assertEqual(engine.seen_fens, [])
        self.assertEqual(actuator.applied, [])
        self.assertIn("paused", view.updates[-1][2])

    def test_manual_move_is_played_in_the_real_app_without_the_engine(self):
        game, engine, actuator, view, events = self._game(True, auto=False)
        game.start()
        self.assertEqual(game.submit_move("g1", "f3"), "g1f3")
        self.assertEqual(engine.seen_fens, [])
        self.assertEqual(actuator.applied, [("g1f3", BOX, True)])
        self.assertIn(("manual", "g1f3"), events)
        self.assertEqual(game.board_map()[(5, 3)], "N")
        # Now it is the opponent's turn again.
        self.assertIn("opponent's move (black)", view.updates[-1][2])

    def test_illegal_manual_move_is_rejected(self):
        game, _, actuator, view, _ = self._game(True, auto=False)
        game.start()
        self.assertIsNone(game.submit_move("g1", "g3"))
        self.assertEqual(actuator.applied, [])
        self.assertIn("not a legal move for white", view.updates[-1][2])

    def test_opponent_move_while_paused_does_not_consult_engine(self):
        game, engine, actuator, view, _ = self._game(False, "e7e5",
                                                     auto=False)
        game.start()
        self.assertIsNone(game.submit_move("e2", "e4"))
        self.assertEqual(engine.seen_fens, [])
        self.assertIn("paused: play black's move", view.updates[-1][2])

    def test_resuming_mid_turn_replies_at_once(self):
        game, engine, actuator, view, events = self._game(False, "e7e5",
                                                          auto=False)
        game.start()
        game.submit_move("e2", "e4")          # program's turn, paused
        game.set_auto(True)
        self.assertEqual(len(engine.seen_fens), 1)
        self.assertEqual(actuator.applied, [("e7e5", BOX, False)])
        self.assertIn(("auto", "on"), events)

    def test_pausing_then_manual_then_resume(self):
        game, engine, actuator, view, _ = self._game(True, "d2d4")
        game.start()                           # engine plays 1.d4
        game.set_auto(False)
        game.submit_move("d7", "d5")           # opponent, no reply (paused)
        game.submit_move("c2", "c4")           # user plays white's 2.c4
        self.assertEqual([a[0] for a in actuator.applied], ["d2d4", "c2c4"])
        self.assertEqual(len(engine.seen_fens), 1)
        game.set_auto(True)                    # opponent to move: nothing
        self.assertEqual(len(engine.seen_fens), 1)
        self.assertIn("opponent's move (black)", view.updates[-1][2])

    def test_automatic_turn_still_refuses_manual_entry(self):
        game, _, actuator, view, _ = self._game(True)
        # Auto on, program (white) to move before start(): user may not move.
        self.assertIsNone(game.submit_move("e2", "e4"))
        self.assertIn("pause auto-play", view.updates[-1][2])
        self.assertEqual(actuator.applied, [])


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class ReplyDelayTests(unittest.TestCase):
    """The reply is held for the minimum delay without blocking the view."""

    def _game(self, delay, move="e7e5"):
        self.now = [100.0]
        self.scheduler = _Scheduler()
        engine, actuator, view = (MockMoveEngine(move), MockMoveActuator(),
                                  MockMirrorView())
        game = MirrorGame(False, BOX, engine, actuator, view, delay=delay,
                          clock=lambda: self.now[0],
                          schedule=self.scheduler)
        game.start()
        return game, engine, actuator, view

    def test_engine_thinks_immediately_but_commit_is_deferred(self):
        game, engine, actuator, view = self._game(delay=5.0)
        self.now[0] = 200.0
        self.assertIsNone(game.submit_move("e2", "e4"))
        self.assertEqual(len(engine.seen_fens), 1)          # thought now
        self.assertEqual(actuator.applied, [])              # not yet played
        self.assertEqual(len(self.scheduler.pending), 1)
        self.assertAlmostEqual(self.scheduler.pending[0][0], 5.0)
        self.assertIn("Waiting 5.0s", view.updates[-1][2])
        # Board not yet changed for the program's side.
        self.assertEqual(game.board_map()[(4, 5)], ".")

    def test_fired_commit_plays_in_both_places(self):
        game, _, actuator, view = self._game(delay=5.0)
        game.submit_move("e2", "e4")
        self.now[0] += 5.0
        self.scheduler.fire()
        self.assertEqual(actuator.applied, [("e7e5", BOX, False)])
        self.assertEqual(game.board_map()[(4, 5)], "p")
        self.assertEqual(self.scheduler.pending, [])

    def test_thinking_time_counts_toward_the_delay(self):
        game, _, actuator, _ = self._game(delay=2.0)
        # Opponent moved at t=100; by the time the engine answered the clock
        # has advanced past the delay, so the reply is not deferred.
        self.now[0] = 100.0
        clock_values = iter([100.0, 103.0, 103.0, 103.0, 103.0, 103.0])
        game._clock = lambda: next(clock_values)
        self.assertEqual(game.submit_move("e2", "e4"), "e7e5")
        self.assertEqual(actuator.applied, [("e7e5", BOX, False)])
        self.assertEqual(self.scheduler.pending, [])

    def test_pausing_during_the_wait_cancels_the_reply(self):
        game, engine, actuator, _ = self._game(delay=5.0)
        game.submit_move("e2", "e4")
        game.set_auto(False)
        self.now[0] += 5.0
        self.scheduler.fire()
        self.assertEqual(actuator.applied, [])
        # Resuming re-thinks and, the delay having elapsed, plays at once.
        game.set_auto(True)
        self.assertEqual(len(engine.seen_fens), 2)
        self.assertEqual(actuator.applied, [("e7e5", BOX, False)])

    def test_position_change_during_the_wait_cancels_the_reply(self):
        game, _, actuator, _ = self._game(delay=5.0)
        game.submit_move("e2", "e4")
        game.set_auto(False)
        game.submit_move("g8", "f6")           # user plays black by hand
        game.set_auto(True)                    # white (opponent) to move
        self.now[0] += 5.0
        self.scheduler.fire()                  # stale e7e5 must not land
        self.assertEqual([a[0] for a in actuator.applied], ["g8f6"])

    def test_raising_the_delay_extends_a_pending_wait(self):
        game, _, actuator, _ = self._game(delay=5.0)
        game.submit_move("e2", "e4")
        game.set_delay(8.0)
        self.now[0] += 5.0
        self.scheduler.fire()                  # original timer: too early
        self.assertEqual(actuator.applied, [])
        self.assertEqual(len(self.scheduler.pending), 1)
        self.assertAlmostEqual(self.scheduler.pending[0][0], 3.0)
        self.now[0] += 3.0
        self.scheduler.fire()
        self.assertEqual(actuator.applied, [("e7e5", BOX, False)])

    def test_zero_delay_plays_immediately(self):
        game, _, actuator, _ = self._game(delay=0.0)
        self.assertEqual(game.submit_move("e2", "e4"), "e7e5")
        self.assertEqual(self.scheduler.pending, [])
        self.assertEqual(actuator.applied, [("e7e5", BOX, False)])

    def test_negative_delay_counts_as_zero(self):
        game, _, _, _ = self._game(delay=-3.0)
        self.assertEqual(game.delay, 0.0)
        game.set_delay(-1)
        self.assertEqual(game.delay, 0.0)


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class StrengthTests(unittest.TestCase):
    def test_strength_is_forwarded_to_the_engine(self):
        engine, events = MockMoveEngine(), []
        game = MirrorGame(True, BOX, engine, MockMoveActuator(),
                          MockMirrorView(),
                          on_event=lambda k, d: events.append((k, d)))
        game.set_strength(1500)
        game.set_strength(None)
        self.assertEqual(engine.strengths, [1500, None])
        self.assertEqual(game.elo, None)
        self.assertIn(("strength", "1500 Elo"), events)
        self.assertIn(("strength", "full"), events)


class StrengthOptionTests(unittest.TestCase):
    """Pure mapping from a rating to Stockfish's UCI options (dep-free)."""

    def test_full_strength_sends_nothing(self):
        from chesscheat.assist import limit_strength_options
        self.assertEqual(limit_strength_options(None, 1320, 3190), {})

    def test_rating_is_clamped_to_the_engine_range(self):
        from chesscheat.assist import limit_strength_options
        self.assertEqual(limit_strength_options(1500, 1320, 3190),
                         {"UCI_LimitStrength": True, "UCI_Elo": 1500})
        self.assertEqual(limit_strength_options(800, 1320, 3190)["UCI_Elo"],
                         1320)
        self.assertEqual(limit_strength_options(9000, 1320, 3190)["UCI_Elo"],
                         3190)

    def test_base_engine_ignores_strength(self):
        class Fixed(MoveEngine):
            def best_move(self, fen):
                return "e2e4"

        self.assertIsNone(Fixed().set_strength(1500))   # no-op, no error


class _BestMoveHandler(BaseHTTPRequestHandler):
    """A tiny best-move service: records requests, replies as configured."""

    reply = {"move": "e2e4"}
    status = 200
    seen = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.seen.append(json.loads(self.rfile.read(length)))
        body = json.dumps(self.reply).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class RemoteMoveEngineTests(unittest.TestCase):
    """``RemoteMoveEngine`` speaks the documented JSON protocol."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _BestMoveHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/best-move"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _BestMoveHandler.reply = {"move": "e2e4"}
        _BestMoveHandler.status = 200
        _BestMoveHandler.seen = []

    def test_posts_fen_and_strength_and_returns_move(self):
        fen = board.to_full_fen(board.starting_board(), True)
        engine = RemoteMoveEngine(self.url)
        self.assertEqual(engine.best_move(fen), "e2e4")
        self.assertEqual(_BestMoveHandler.seen, [{"fen": fen, "elo": None}])
        engine.set_strength(1800)
        engine.best_move(fen)
        self.assertEqual(_BestMoveHandler.seen[-1]["elo"], 1800)

    def test_null_move_becomes_none(self):
        _BestMoveHandler.reply = {"move": None}
        self.assertIsNone(RemoteMoveEngine(self.url).best_move("x"))

    def test_server_error_raises_runtime_error(self):
        _BestMoveHandler.status = 500
        with self.assertRaises(RuntimeError):
            RemoteMoveEngine(self.url).best_move("x")

    def test_malformed_reply_raises_runtime_error(self):
        _BestMoveHandler.reply = {"bestmove": "e2e4"}
        with self.assertRaises(RuntimeError):
            RemoteMoveEngine(self.url).best_move("x")

    def test_unreachable_service_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            RemoteMoveEngine("http://127.0.0.1:9/nothing",
                             timeout=1).best_move("x")

    def test_is_a_move_engine(self):
        self.assertIsInstance(RemoteMoveEngine(self.url), MoveEngine)


class ParserTests(unittest.TestCase):
    def test_defaults_to_reader_and_local_engine(self):
        args = build_parser().parse_args([])
        self.assertEqual((args.mode, args.engine_url), ("reader", None))

    def test_mirror_mode_with_remote_engine(self):
        args = build_parser().parse_args(
            ["--mode", "mirror", "--engine-url", "http://host/best"])
        self.assertEqual((args.mode, args.engine_url),
                         ("mirror", "http://host/best"))

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--mode", "telepathy"])


class RequireTkTests(unittest.TestCase):
    """Mirror mode fails fast, with install guidance, when Tk is missing."""

    def test_missing_tkinter_exits_with_brew_hint(self):
        from unittest import mock
        from chesscheat.app import _require_tk

        with mock.patch.dict("sys.modules", {"tkinter": None}):
            with self.assertRaises(SystemExit) as raised:
                _require_tk()
        message = str(raised.exception)
        self.assertIn("tkinter", message)
        self.assertIn("brew install python-tk@", message)


if __name__ == "__main__":
    unittest.main()
