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

    def test_calibration_reports_progress(self):
        calls = []
        recognizer = TemplateBoardRecognizer(
            MockImageBackend(),
            on_progress=lambda done, total: calls.append((done, total)))
        recognizer.calibrate(render_mock_image(board.starting_board(), True),
                             True)
        self.assertEqual(calls[0], (1, 64))
        self.assertEqual(calls[-1], (64, 64))
        self.assertEqual(len(calls), 64)


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


class ScoredReadingTests(unittest.TestCase):
    """``read`` records per-square best scores and marks unknowns."""

    def _corrupt(self, image, row, col):
        """Overwrite one square of a rendered image with an alien pattern."""
        cell = len(image) // 8
        for i in range(cell):
            for j in range(cell):
                image[row * cell + i][col * cell + j] = (i * 37 + j * 11) % 251
        return image

    def test_unknown_marked_below_threshold(self):
        recognizer = TemplateBoardRecognizer(MockImageBackend(),
                                             match_threshold=0.99)
        start = board.starting_board()
        recognizer.calibrate(render_mock_image(start, True), True)

        image = self._corrupt(render_mock_image(start, True), 3, 4)  # e5
        result = recognizer.read(image)

        label, score = recognizer.last_scored[(4, 5)]
        self.assertEqual(label, "?")
        self.assertLess(score, 0.99)
        # Untouched squares match their templates exactly.
        label, score = recognizer.last_scored[(0, 1)]
        self.assertEqual(label, "R")
        self.assertAlmostEqual(score, 1.0)
        # The returned map still carries the best guess, never '?'.
        self.assertNotIn("?", result.values())

    def test_no_threshold_trusts_every_match(self):
        recognizer = TemplateBoardRecognizer(MockImageBackend())
        start = board.starting_board()
        recognizer.calibrate(render_mock_image(start, True), True)
        recognizer.read(self._corrupt(render_mock_image(start, True), 3, 4))
        self.assertNotIn("?", (label for label, _ in
                               recognizer.last_scored.values()))

    def test_clean_reading_has_no_unknowns_and_full_scores(self):
        recognizer = TemplateBoardRecognizer(MockImageBackend(),
                                             match_threshold=0.9)
        start = board.starting_board()
        recognizer.calibrate(render_mock_image(start, True), True)
        result = recognizer.read(render_mock_image(start, True))
        self.assertEqual(result, start)
        self.assertEqual(len(recognizer.last_scored), 64)
        for square, (label, score) in recognizer.last_scored.items():
            self.assertEqual(label, start[square])
            self.assertGreaterEqual(score, 0.9)


class FrameCallbackTests(unittest.TestCase):
    def test_on_frame_sees_every_read_frame(self):
        positions = opening_sequence()
        frames = [render_mock_image(p, True) for p in positions]
        raw = []
        app.run(
            MockSetupProvider(True, (0, 0, 8, 8)),
            lambda box: MockFrameSource(frames),
            TemplateBoardRecognizer(MockImageBackend()),
            on_board=lambda board_map, _white: None,
            on_frame=raw.append,
        )
        # The calibration frame is consumed before the loop; every frame that
        # is read is first surfaced raw through on_frame.
        self.assertEqual(raw, frames[1:])


class InterfaceConformanceTests(unittest.TestCase):
    def test_mocks_implement_interfaces(self):
        self.assertIsInstance(MockSetupProvider(), SetupProvider)
        self.assertIsInstance(MockFrameSource([]), FrameSource)
        self.assertIsInstance(MockImageBackend(), ImageBackend)
        self.assertIsInstance(TemplateBoardRecognizer(MockImageBackend()),
                              BoardRecognizer)


if __name__ == "__main__":
    unittest.main()
