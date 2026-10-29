"""``OpponentWatcher`` through the mocks: polling, submitting, toggling."""

import unittest

try:
    import chess  # noqa: F401
    _HAVE_CHESS = True
except ImportError:
    _HAVE_CHESS = False

from chesscheat.mirror import MirrorGame, OpponentWatcher
from chesscheat.mocks import MockMoveEngine, MockMoveActuator, MockMirrorView
from tests.test_move_inference import _scans, _after

BOX = (100, 100, 900, 900)


class _Scheduler:
    """Records deferred callbacks so a test can fire them deliberately."""

    def __init__(self):
        self.pending = []

    def __call__(self, seconds, fn):
        self.pending.append((seconds, fn))

    def fire_one(self):
        _seconds, fn = self.pending.pop(0)
        fn()


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class OpponentWatcherTests(unittest.TestCase):
    """The watcher feeds detected opponent moves into the game."""

    def _setup(self, playing_white, frames, move="e2e4", **kwargs):
        self.engine = MockMoveEngine(move)
        self.actuator = MockMoveActuator()
        self.events = []
        self.grabs = 0
        self.scheduler = _Scheduler()
        frames = iter(frames)

        def grab():
            self.grabs += 1
            return next(frames)

        game = MirrorGame(playing_white, BOX, self.engine, self.actuator,
                          MockMirrorView(),
                          on_event=lambda k, d: self.events.append((k, d)))
        game.start()
        kwargs.setdefault("threaded", False)
        watcher = OpponentWatcher(game, grab, self.scheduler, interval=0.2,
                                  on_event=lambda k, d:
                                  self.events.append((k, d)),
                                  scan=lambda image: image, **kwargs)
        return game, watcher

    def test_nothing_is_captured_on_our_turn(self):
        game, watcher = self._setup(True, [], move="e2e4")
        game.set_auto(False)
        game.submit_move("e7", "e5")       # now it is our (white's) turn
        self.assertFalse(game.opponent_to_move)
        self.assertIsNone(watcher.poll())
        self.assertEqual(self.grabs, 0)

    def test_opponent_to_move_is_false_at_game_over(self):
        game, watcher = self._setup(True, [], move="f2f3")
        game.set_auto(False)
        for move in (("e7", "e5"), ("g2", "g4"), ("d8", "h4")):
            game.submit_move(*move)        # fool's mate
        self.assertFalse(game.opponent_to_move)
        self.assertIsNone(watcher.poll())
        self.assertEqual(self.grabs, 0)

    def test_detected_move_is_submitted_and_answered(self):
        frame = _scans(_after("e2e4", "c7c5"), highlighted=("c7", "c5"))
        game, watcher = self._setup(True, [frame], move="e2e4")
        self.engine.move = "g1f3"
        self.assertEqual(watcher.poll(), ("c7", "c5"))
        self.assertIn(("opponent", "c7c5"), self.events)
        self.assertIn(("detected", "c7c5 (from the app's highlight)"),
                      self.events)
        self.assertEqual([a[0] for a in self.actuator.applied],
                         ["e2e4", "g1f3"])

    def test_own_highlight_is_not_a_move(self):
        frame = _scans(_after("e2e4"), highlighted=("e2", "e4"))
        game, watcher = self._setup(True, [frame, frame])
        self.assertIsNone(watcher.poll())
        self.assertEqual(game.fen.split()[0],
                         "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR")

    def test_program_as_black_reads_whites_first_move(self):
        frame = _scans(_after("e2e4"), bottom_white=False,
                       highlighted=("e2", "e4"), playing_white=False)
        game, watcher = self._setup(False, [frame], move="e7e5")
        self.assertEqual(watcher.poll(), ("e2", "e4"))
        self.assertEqual([a[0] for a in self.actuator.applied], ["e7e5"])

    def test_toggle_off_skips_capture(self):
        frame = _scans(_after("e2e4", "c7c5"), highlighted=("c7", "c5"))
        game, watcher = self._setup(True, [frame])
        watcher.set_enabled(False)
        self.assertIsNone(watcher.poll())
        self.assertEqual(self.grabs, 0)
        self.assertIn(("watch", "off"), self.events)
        watcher.set_enabled(True)
        self.assertEqual(watcher.poll(), ("c7", "c5"))

    def test_polling_loop_rearms_until_stopped(self):
        frames = [_scans(_after("e2e4")),
                  _scans(_after("e2e4", "c7c5"), highlighted=("c7", "c5"))]
        game, watcher = self._setup(True, frames)
        watcher.start()
        watcher.start()                       # idempotent
        self.assertEqual(len(self.scheduler.pending), 1)
        self.assertEqual(self.scheduler.pending[0][0], 0.2)
        self.scheduler.fire_one()             # clean frame: nothing
        self.assertEqual(self.grabs, 1)
        self.scheduler.fire_one()             # highlight: submitted
        self.assertIn(("opponent", "c7c5"), self.events)
        watcher.stop()
        self.scheduler.fire_one()             # last armed tick: no re-arm
        self.assertEqual(self.scheduler.pending, [])

    def test_capture_errors_are_logged_once_and_polling_survives(self):
        def failing():
            raise OSError("no screen")

        game = MirrorGame(True, BOX, MockMoveEngine("e2e4"),
                          MockMoveActuator(), MockMirrorView())
        game.start()
        events = []
        watcher = OpponentWatcher(game, failing, _Scheduler(), threaded=False,
                                  on_event=lambda k, d: events.append((k, d)))
        self.assertIsNone(watcher.poll())
        self.assertIsNone(watcher.poll())
        self.assertEqual(events, [("watch", "capture failed: OSError: "
                                            "no screen")])


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class ContinuousCaptureTests(unittest.TestCase):
    """The threaded watcher captures back to back only while wanted."""

    def _wait(self, condition, seconds=3.0):
        import time

        deadline = time.time() + seconds
        while time.time() < deadline:
            if condition():
                return True
            time.sleep(0.005)
        return False

    def _setup(self, playing_white, frame, move="e2e4"):
        import threading

        self.engine = MockMoveEngine(move)
        self.actuator = MockMoveActuator()
        self.events = []
        self.grabs = 0
        self.lock = threading.Lock()
        self.frame = frame

        def grab():
            with self.lock:
                self.grabs += 1
                return self.frame

        game = MirrorGame(playing_white, BOX, self.engine, self.actuator,
                          MockMirrorView(),
                          on_event=lambda k, d: self.events.append((k, d)))
        game.start()
        self.scheduler = _Scheduler()
        watcher = OpponentWatcher(game, grab, self.scheduler, interval=0.02,
                                  on_event=lambda k, d:
                                  self.events.append((k, d)),
                                  scan=lambda image: image, idle_sleep=0.005)
        self.addCleanup(watcher.stop)
        return game, watcher

    def test_thread_captures_continuously_and_tick_submits(self):
        clean = _scans(_after("e2e4"))
        game, watcher = self._setup(True, clean)
        watcher.start()
        self.assertTrue(watcher.threaded)
        self.scheduler.fire_one()            # first tick: wanted = True
        self.assertTrue(self._wait(lambda: self.grabs >= 5))   # back to back
        with self.lock:
            self.frame = _scans(_after("e2e4", "c7c5"),
                                highlighted=("c7", "c5"))
            seen = self.grabs
        self.assertTrue(self._wait(lambda: self.grabs > seen + 1))
        self.scheduler.fire_one()            # tick: consumes the newest scan
        self.assertIn(("opponent", "c7c5"), self.events)
        self.assertIn(("detected", "c7c5 (from the app's highlight)"),
                      self.events)
        self.assertEqual(game.fen.split()[0],
                         "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR")

    def test_nothing_is_captured_on_our_turn(self):
        frame = _scans(_after("e2e4", "c7c5"), highlighted=("c7", "c5"))
        game, watcher = self._setup(True, frame)
        game.set_auto(False)
        game.submit_move("c7", "c5")         # entered by hand: our turn now
        watcher.start()
        self.scheduler.fire_one()
        self.assertFalse(self._wait(lambda: self.grabs > 0, seconds=0.1))
        self.assertEqual(self.grabs, 0)

    def test_capture_error_on_the_thread_is_reported_once(self):
        game, watcher = self._setup(True, None)

        def failing():
            raise OSError("no screen")

        watcher._grab = failing
        watcher.start()
        self.scheduler.fire_one()
        self.assertTrue(self._wait(lambda: watcher._latest_error is not None))
        self.scheduler.fire_one()
        self.assertEqual(
            [e for e in self.events if e[0] == "watch"],
            [("watch", "capture failed: OSError: no screen")])
        self.scheduler.fire_one()
        self.assertEqual(
            len([e for e in self.events if e[0] == "watch"]), 1)

    def test_stop_ends_the_thread(self):
        game, watcher = self._setup(True, _scans(_after("e2e4")))
        watcher.start()
        thread = watcher._thread
        watcher.stop()
        thread.join(2.0)
        self.assertFalse(thread.is_alive())
