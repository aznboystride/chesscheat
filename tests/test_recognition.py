"""End-to-end recognition tests using only the dependency-free mock stack.

These exercise the *real* recognition algorithm (``TemplateBoardRecognizer``)
against synthetic board images via ``MockImageBackend``, wired through the same
``run`` loop the application uses -- proving the program captures positions that
evolve over time, with no GUI, screen, numpy or OpenCV required.
"""

import unittest

from chesscheat import board
from chesscheat import app
from chesscheat.interfaces import (SetupProvider, FrameSource, ImageBackend,
                                   BoardRecognizer)
from chesscheat.recognition import TemplateBoardRecognizer
from chesscheat.mocks import (MockSetupProvider, MockFrameSource,
                              MockImageBackend, render_mock_image)


def move(position, *changes):
    """Return a copy of ``position`` with ``(square, label)`` changes applied."""
    updated = dict(position)
    updated.update(changes)
    return updated


def opening_sequence():
    """Starting position followed by 1.e4 c5 2.Nf3 (canonical board maps)."""
    start = board.starting_board()
    e4 = move(start, ((4, 2), "."), ((4, 4), "P"))
    c5 = move(e4, ((2, 7), "."), ((2, 5), "p"))
    nf3 = move(c5, ((6, 1), "."), ((5, 3), "N"))
    return [start, e4, c5, nf3]


def collect_reads(positions, playing_white):
    """Run the full pipeline over rendered ``positions``; return read maps."""
    frames = [render_mock_image(p, playing_white) for p in positions]
    seen = []
    app.run(
        MockSetupProvider(playing_white, (0, 0, 8, 8)),
        lambda box: MockFrameSource(frames),
        TemplateBoardRecognizer(MockImageBackend()),
        on_board=lambda board_map, _white: seen.append(board_map),
    )
    return seen


class CalibrationTests(unittest.TestCase):
    def test_recovers_starting_position(self):
        recognizer = TemplateBoardRecognizer(MockImageBackend())
        image = render_mock_image(board.starting_board(), True)
        recognizer.calibrate(image, True)
        self.assertEqual(recognizer.read(image), board.starting_board())


class EvolvingPositionTests(unittest.TestCase):
    def test_pipeline_white(self):
        positions = opening_sequence()
        # First frame calibrates; the rest are read back exactly.
        self.assertEqual(collect_reads(positions, True), positions[1:])

    def test_pipeline_black_orientation(self):
        positions = opening_sequence()
        seen = collect_reads(positions, False)
        self.assertEqual(seen, positions[1:])
        # Canonical FEN is orientation independent.
        self.assertEqual(board.to_fen(seen[0]),
                         "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR")

    def test_background_tint_is_ignored(self):
        # A pawn pushed onto an opposite-colour square is still recognised.
        start = board.starting_board()
        pushed = move(start, ((4, 2), "."), ((4, 4), "P"))
        self.assertEqual(collect_reads([start, pushed], True)[0], pushed)


class InterfaceConformanceTests(unittest.TestCase):
    def test_mocks_implement_interfaces(self):
        self.assertIsInstance(MockSetupProvider(), SetupProvider)
        self.assertIsInstance(MockFrameSource([]), FrameSource)
        self.assertIsInstance(MockImageBackend(), ImageBackend)
        self.assertIsInstance(TemplateBoardRecognizer(MockImageBackend()),
                              BoardRecognizer)


if __name__ == "__main__":
    unittest.main()
