"""Tests for the console board printer.

``_console_printer`` clears the terminal before each repaint, which erases
everything printed earlier (including the calibration progress bar). These
tests pin the behaviour that keeps the user informed anyway: a status header
is reprinted above the board on every repaint, and unchanged positions do not
repaint at all.
"""

import io
import unittest
from unittest import mock

from chesscheat import board
from chesscheat.app import _console_printer


class ConsolePrinterTests(unittest.TestCase):
    def _capture(self, show, *positions):
        """Feed ``positions`` to ``show``; return the accumulated output."""
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            for position in positions:
                show(position, True)
        return out.getvalue()

    def test_header_survives_every_repaint(self):
        show = _console_printer("STATUS LINE")
        start = board.starting_board()
        e4 = dict(start)
        e4[(4, 2)], e4[(4, 4)] = ".", "P"
        output = self._capture(show, start, e4)
        # Two repaints (position changed) -> the header appears twice, so it
        # is still on screen after the clear-screen escape wipes the rest.
        self.assertEqual(output.count("STATUS LINE"), 2)
        self.assertEqual(output.count("FEN:"), 2)

    def test_unchanged_position_is_not_reprinted(self):
        show = _console_printer("STATUS LINE")
        start = board.starting_board()
        output = self._capture(show, start, dict(start), dict(start))
        self.assertEqual(output.count("STATUS LINE"), 1)

    def test_no_header_by_default(self):
        show = _console_printer()
        output = self._capture(show, board.starting_board())
        self.assertIn("FEN:", output)
        self.assertNotIn("None", output.split("FEN:")[0])


if __name__ == "__main__":
    unittest.main()
