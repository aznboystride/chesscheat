"""Tests for the Stockfish installer's platform/asset selection.

Only the pure asset-matching logic is exercised -- no network, no download.
The installer lives in ``scripts/`` (outside the package), so it is loaded by
path.
"""

import importlib.util
import os
import unittest

_INSTALLER_PATH = os.path.join(os.path.dirname(__file__), os.pardir,
                               "scripts", "install_stockfish.py")
_spec = importlib.util.spec_from_file_location("install_stockfish",
                                               _INSTALLER_PATH)
install_stockfish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install_stockfish)

# A representative slice of a real Stockfish release's asset list.
RELEASE_ASSETS = [
    "stockfish-macos-m1-apple-silicon.tar",
    "stockfish-macos-x86-64-avx2.tar",
    "stockfish-macos-x86-64-sse41-popcnt.tar",
    "stockfish-ubuntu-x86-64-avx2.tar",
    "stockfish-ubuntu-x86-64-sse41-popcnt.tar",
    "stockfish-windows-x86-64-avx2.zip",
]


class AssetCandidateTests(unittest.TestCase):
    def test_apple_silicon_prefers_m1_build(self):
        # M1 through M4 are all arm64 Apple Silicon.
        self.assertEqual(install_stockfish.asset_candidates("Darwin", "arm64"),
                         ["macos-m1-apple-silicon"])

    def test_case_insensitive(self):
        self.assertEqual(install_stockfish.asset_candidates("darwin", "ARM64"),
                         ["macos-m1-apple-silicon"])

    def test_intel_mac_is_ordered_by_instruction_set(self):
        cands = install_stockfish.asset_candidates("Darwin", "x86_64")
        self.assertEqual(cands[0], "macos-x86-64-avx2")
        self.assertIn("macos-x86-64", cands)

    def test_linux_x86_64(self):
        cands = install_stockfish.asset_candidates("Linux", "x86_64")
        self.assertEqual(cands[0], "ubuntu-x86-64-avx2")

    def test_unsupported_platform_is_empty(self):
        self.assertEqual(install_stockfish.asset_candidates("Plan9", "pdp11"),
                         [])


class SelectAssetTests(unittest.TestCase):
    def test_m4_mac_selects_apple_silicon_tar(self):
        self.assertEqual(
            install_stockfish.select_asset(RELEASE_ASSETS, "Darwin", "arm64"),
            "stockfish-macos-m1-apple-silicon.tar")

    def test_intel_mac_selects_avx2(self):
        self.assertEqual(
            install_stockfish.select_asset(RELEASE_ASSETS, "Darwin", "x86_64"),
            "stockfish-macos-x86-64-avx2.tar")

    def test_intel_mac_falls_back_when_avx2_absent(self):
        assets = [a for a in RELEASE_ASSETS if "avx2" not in a]
        self.assertEqual(
            install_stockfish.select_asset(assets, "Darwin", "x86_64"),
            "stockfish-macos-x86-64-sse41-popcnt.tar")

    def test_linux_selects_ubuntu_build(self):
        self.assertEqual(
            install_stockfish.select_asset(RELEASE_ASSETS, "Linux", "x86_64"),
            "stockfish-ubuntu-x86-64-avx2.tar")

    def test_only_tar_assets_are_chosen(self):
        # A Windows .zip must never be selected even if the fragment matched.
        chosen = install_stockfish.select_asset(
            ["stockfish-macos-m1-apple-silicon.zip"], "Darwin", "arm64")
        self.assertIsNone(chosen)

    def test_no_match_returns_none(self):
        self.assertIsNone(
            install_stockfish.select_asset([], "Darwin", "arm64"))
        self.assertIsNone(
            install_stockfish.select_asset(RELEASE_ASSETS, "Plan9", "pdp11"))


if __name__ == "__main__":
    unittest.main()
