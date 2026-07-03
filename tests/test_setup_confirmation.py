"""Tests for the capture-confirmation setup step.

After the user selects the board's bounding box, ``app.run`` grabs one frame
from it and asks the ``SetupProvider`` to confirm the capture looks right,
looping back to reselection until it does. These tests drive that flow through
the dependency-free mock pipeline, and cover the provider implementations and
the PPM preview encoding used by the GUI dialog.
"""

import unittest
from unittest import mock

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:
    _HAVE_NUMPY = False

from chesscheat import board, app
from chesscheat.gui.dialogs import _image_to_ppm
from chesscheat.interfaces import SetupProvider
from chesscheat.providers import PromptSetupProvider, FallbackSetupProvider
from chesscheat.recognition import TemplateBoardRecognizer
from chesscheat.mocks import (MockSetupProvider, MockFrameSource,
                              MockImageBackend, render_mock_image)


def _opening_frames():
    """Render the start position and 1.e4 as mock frames.

    Returns:
        A ``(positions, frames)`` pair: the board maps and their rendered
        mock images, from white's perspective.
    """
    start = board.starting_board()
    e4 = dict(start)
    e4[(4, 2)], e4[(4, 4)] = ".", "P"
    return [start, e4], [render_mock_image(p, True) for p in (start, e4)]


def _run(setup, frames):
    """Drive ``app.run`` over scripted ``frames``; return the read maps."""
    seen = []
    app.run(
        setup,
        lambda box: MockFrameSource(frames),
        TemplateBoardRecognizer(MockImageBackend()),
        on_board=lambda board_map, _white: seen.append(board_map),
    )
    return seen


class ConfirmationFlowTests(unittest.TestCase):
    """``app.run`` shows the captured frame and loops until it is confirmed."""

    def test_confirmed_immediately_runs_once(self):
        positions, frames = _opening_frames()
        setup = MockSetupProvider()
        seen = _run(setup, frames)
        self.assertEqual(setup.box_requests, 1)
        self.assertEqual(len(setup.confirmed_images), 1)
        self.assertEqual(seen, positions[1:])

    def test_rejection_reselects_the_box(self):
        positions, frames = _opening_frames()
        setup = MockSetupProvider(confirmations=[False, False, True])
        seen = _run(setup, frames)
        self.assertEqual(setup.box_requests, 3)
        self.assertEqual(len(setup.confirmed_images), 3)
        # The pipeline still calibrates and reads correctly afterwards.
        self.assertEqual(seen, positions[1:])

    def test_confirmation_sees_the_captured_frame(self):
        _, frames = _opening_frames()
        setup = MockSetupProvider()
        _run(setup, frames)
        self.assertEqual(setup.confirmed_images[0], frames[0])

    def test_calibration_frame_is_not_consumed_by_confirmation(self):
        """The confirmation grab must not eat the calibration frame."""
        positions, frames = _opening_frames()
        setup = MockSetupProvider()
        seen = _run(setup, frames)
        # If confirmation had consumed frames[0], calibration would have used
        # the e4 frame and the read-back would be wrong (or empty).
        self.assertEqual(seen, positions[1:])


class PromptConfirmTests(unittest.TestCase):
    """``PromptSetupProvider.confirm_box`` asks y/n on stdin."""

    IMAGE = [[0] * 32 for _ in range(16)]  # 32x16 grayscale frame

    def test_yes_confirms(self):
        with mock.patch("builtins.input", side_effect=["y"]) as asked:
            self.assertTrue(PromptSetupProvider().confirm_box(self.IMAGE))
        self.assertIn("32x16", asked.call_args[0][0])

    def test_no_reselects(self):
        with mock.patch("builtins.input", side_effect=["no"]):
            self.assertFalse(PromptSetupProvider().confirm_box(self.IMAGE))

    def test_reprompts_until_valid(self):
        with mock.patch("builtins.input", side_effect=["maybe", "", "yes"]):
            self.assertTrue(PromptSetupProvider().confirm_box(self.IMAGE))


class FallbackConfirmTests(unittest.TestCase):
    """``FallbackSetupProvider.confirm_box`` forwards the image and falls back."""

    def test_primary_receives_the_image(self):
        primary = MockSetupProvider(confirmations=[False])
        fallback = FallbackSetupProvider(primary, MockSetupProvider())
        image = [[1, 2], [3, 4]]
        self.assertFalse(fallback.confirm_box(image))
        self.assertEqual(primary.confirmed_images, [image])

    def test_falls_back_when_primary_raises(self):
        class Broken(MockSetupProvider):
            def confirm_box(self, image):
                raise RuntimeError("no display")

        secondary = MockSetupProvider(confirmations=[False])
        fallback = FallbackSetupProvider(Broken(), secondary)
        self.assertFalse(fallback.confirm_box([[0]]))
        self.assertEqual(len(secondary.confirmed_images), 1)

    def test_mock_still_satisfies_interface(self):
        self.assertIsInstance(MockSetupProvider(), SetupProvider)


class LivePreviewTests(unittest.TestCase):
    """``LivePreview`` disables itself instead of breaking the read loop."""

    def test_show_without_tk_disables_quietly(self):
        from chesscheat.gui import LivePreview

        preview = LivePreview()
        with mock.patch.dict("sys.modules", {"tkinter": None}):
            preview.show([[0, 1], [2, 3]], board.starting_board(), True)
            preview.show([[0, 1], [2, 3]])   # must not raise either way
        self.assertTrue(preview.disabled)

    def test_close_is_idempotent(self):
        from chesscheat.gui import LivePreview

        preview = LivePreview()
        preview.close()
        preview.close()
        self.assertTrue(preview.disabled)
        preview.show([[0]])   # no-op after close, must not raise


class AnnotationTests(unittest.TestCase):
    """Overlay specs mark every detected piece with its name (dep-free)."""

    def test_every_piece_gets_one_annotation(self):
        from chesscheat.gui.live_preview import annotations

        specs = annotations(board.starting_board(), True, 512, 512)
        self.assertEqual(len(specs), 32)
        names = {spec[4] for spec in specs}
        self.assertEqual(names, {"pawn", "knight", "bishop",
                                 "rook", "queen", "king"})

    def test_annotation_locates_the_square(self):
        from chesscheat.gui.live_preview import annotations

        # Only a white knight on g1: white view -> row 7, col 6 of 64px cells.
        specs = annotations({(6, 1): "N"}, True, 512, 512)
        self.assertEqual(specs, [(384.0, 448.0, 448.0, 512.0,
                                  "knight", True)])

    def test_orientation_flips_for_black(self):
        from chesscheat.gui.live_preview import annotations

        # From black's perspective g1 appears at row 0, col 1.
        specs = annotations({(6, 1): "N"}, False, 512, 512)
        self.assertEqual(specs, [(64.0, 0.0, 128.0, 64.0, "knight", True)])

    def test_piece_colour_is_reported(self):
        from chesscheat.gui.live_preview import annotations

        specs = annotations({(0, 1): "R", (0, 8): "r"}, True, 80, 80)
        by_white = {is_white for *_rest, is_white in specs}
        self.assertEqual(by_white, {True, False})

    def test_no_detections_no_annotations(self):
        from chesscheat.gui.live_preview import annotations

        self.assertEqual(annotations(None, True, 512, 512), [])
        self.assertEqual(annotations({}, True, 512, 512), [])


class PpmEncodingTests(unittest.TestCase):
    """``_image_to_ppm`` encodes captured frames for Tk's ``PhotoImage``."""

    def test_grayscale_list_of_lists(self):
        ppm = _image_to_ppm([[0, 128], [255, 300]])  # 300 must clamp to 255
        header, _, body = ppm.partition(b"\n")
        self.assertEqual(header, b"P6 2 2 255")
        self.assertEqual(body, bytes([0] * 3 + [128] * 3 + [255] * 3 + [255] * 3))

    @unittest.skipUnless(_HAVE_NUMPY, "requires numpy")
    def test_bgra_array_flips_to_rgb(self):
        bgra = np.zeros((1, 1, 4), dtype=np.uint8)
        bgra[0, 0] = (10, 20, 30, 255)  # B, G, R, A
        ppm = _image_to_ppm(bgra)
        self.assertTrue(ppm.startswith(b"P6 1 1 255\n"))
        self.assertEqual(ppm[-3:], bytes([30, 20, 10]))  # R, G, B

    @unittest.skipUnless(_HAVE_NUMPY, "requires numpy")
    def test_rgb_array_passes_through(self):
        rgb = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
        ppm = _image_to_ppm(rgb)
        self.assertTrue(ppm.startswith(b"P6 2 1 255\n"))
        self.assertEqual(ppm[-6:], bytes([1, 2, 3, 4, 5, 6]))

    @unittest.skipUnless(_HAVE_NUMPY, "requires numpy")
    def test_grayscale_array_replicates_channels(self):
        gray = np.array([[7]], dtype=np.uint8)
        ppm = _image_to_ppm(gray)
        self.assertEqual(ppm[-3:], bytes([7, 7, 7]))


if __name__ == "__main__":
    unittest.main()
