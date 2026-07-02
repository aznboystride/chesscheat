"""Tests for the live terminal display.

``_console_ui`` clears the terminal on each repaint, which erases everything
printed earlier (including the calibration progress bar). These tests pin the
behaviour that keeps the user informed anyway: the status header, the board,
the recent-activity log and the capture-rate line are all part of every
repaint, unchanged positions do not repaint, and the frame rate is estimated
from capture timestamps.
"""

import io
import unittest
from unittest import mock

from chesscheat import board
from chesscheat.app import _console_ui


def _capture(fn, *calls):
    """Invoke ``fn(*args)`` for each args tuple; return the printed output."""
    with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
        for args in calls:
            fn(*args)
    return out.getvalue()


class BoardRepaintTests(unittest.TestCase):
    def setUp(self):
        self.on_board, self.on_frame, self.on_event = _console_ui("STATUS")
        self.start = board.starting_board()
        self.e4 = dict(self.start)
        self.e4[(4, 2)], self.e4[(4, 4)] = ".", "P"

    def test_header_survives_every_repaint(self):
        output = _capture(self.on_board, (self.start, True), (self.e4, True))
        # Two repaints (position changed) -> the header appears twice, so it
        # is still on screen after the clear-screen escape wipes the rest.
        self.assertEqual(output.count("STATUS"), 2)
        self.assertEqual(output.count("FEN:"), 2)

    def test_unchanged_position_is_not_reprinted(self):
        output = _capture(self.on_board, (self.start, True),
                          (dict(self.start), True), (dict(self.start), True))
        self.assertEqual(output.count("STATUS"), 1)


class ActivityLogTests(unittest.TestCase):
    def test_events_appear_with_timestamp_and_label(self):
        on_board, _, on_event = _console_ui()
        output = _capture(on_event, ("move", "e4"),
                          ("dropped", "3 square(s) changed"))
        self.assertIn("move: e4", output)
        self.assertIn("frame dropped: 3 square(s) changed", output)
        self.assertRegex(output, r"\[\d{2}:\d{2}:\d{2}\] move: e4")

    def test_events_survive_board_repaints(self):
        on_board, _, on_event = _console_ui()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            on_event("move", "e4")
            on_board(board.starting_board(), True)
        # The board repaint re-renders the activity log rather than wiping it.
        self.assertEqual(out.getvalue().count("move: e4"), 2)


class FrameRateTests(unittest.TestCase):
    def test_rate_is_estimated_from_capture_times(self):
        ticks = iter([0.0, 0.25, 0.5, 0.75, 1.0])
        _, on_frame, _ = _console_ui(clock=lambda: next(ticks))
        output = _capture(on_frame, *[(None,)] * 5)
        self.assertIn("capturing at 4.0 fps", output)

    def test_single_frame_shows_placeholder(self):
        _, on_frame, _ = _console_ui(clock=lambda: 1.0)
        output = _capture(on_frame, (None,))
        self.assertIn("capturing...", output)

    def test_rate_line_is_part_of_repaints(self):
        ticks = iter([0.0, 0.5])
        on_board, on_frame, _ = _console_ui(clock=lambda: next(ticks))
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            on_frame(None)
            on_frame(None)
            on_board(board.starting_board(), True)
        self.assertIn("capturing at 2.0 fps", out.getvalue().split("FEN:")[1])


if __name__ == "__main__":
    unittest.main()
