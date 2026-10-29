"""Tests for the Stockfish installer's platform/asset selection and extraction.

The asset-matching logic and the archive handling are exercised without any
network -- the extraction test builds its own tiny ``.tar.gz``. The installer
lives in ``scripts/`` (outside the package), so it is loaded by path.
"""

import importlib.util
import io
import os
import tarfile
import tempfile
import unittest

_INSTALLER_PATH = os.path.join(os.path.dirname(__file__), os.pardir,
                               "scripts", "install_stockfish.py")
_spec = importlib.util.spec_from_file_location("install_stockfish",
                                               _INSTALLER_PATH)
install_stockfish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install_stockfish)

# The real asset list of Stockfish 19 (universal builds, gzip tarballs).
SF19_ASSETS = [
    "stockfish-linux-riscv64-universal.tar.gz",
    "stockfish-macos-universal.tar.gz",
    "stockfish-linux-arm64-universal.tar.gz",
    "stockfish-windows-x86-64-universal.zip",
    "stockfish-linux-x86-64-universal.tar.gz",
    "stockfish-windows-arm64-universal.zip",
    "stockfish-android-arm64-universal.tar.gz",
    "stockfish-android-armv7-neon.tar.gz",
]

# A representative slice of a pre-19 release (per-CPU builds, plain tar).
LEGACY_ASSETS = [
    "stockfish-macos-m1-apple-silicon.tar",
    "stockfish-macos-x86-64-avx2.tar",
    "stockfish-macos-x86-64-sse41-popcnt.tar",
    "stockfish-ubuntu-x86-64-avx2.tar",
    "stockfish-ubuntu-x86-64-sse41-popcnt.tar",
    "stockfish-windows-x86-64-avx2.zip",
]


class AssetCandidateTests(unittest.TestCase):
    def test_apple_silicon_prefers_universal_then_m1_build(self):
        # M1 through M4 are all arm64 Apple Silicon.
        self.assertEqual(install_stockfish.asset_candidates("Darwin", "arm64"),
                         ["macos-universal", "macos-m1-apple-silicon"])

    def test_case_insensitive(self):
        self.assertEqual(
            install_stockfish.asset_candidates("darwin", "ARM64")[0],
            "macos-universal")

    def test_intel_mac_universal_then_instruction_sets(self):
        cands = install_stockfish.asset_candidates("Darwin", "x86_64")
        self.assertEqual(cands[:2], ["macos-universal", "macos-x86-64-avx2"])

    def test_linux_x86_64(self):
        cands = install_stockfish.asset_candidates("Linux", "x86_64")
        self.assertEqual(cands[:2], ["linux-x86-64-universal",
                                     "ubuntu-x86-64-avx2"])

    def test_linux_arm64(self):
        self.assertEqual(
            install_stockfish.asset_candidates("Linux", "aarch64")[0],
            "linux-arm64-universal")

    def test_unsupported_platform_is_empty(self):
        self.assertEqual(install_stockfish.asset_candidates("Plan9", "pdp11"),
                         [])


class SelectAssetTests(unittest.TestCase):
    def test_m4_mac_selects_the_sf19_universal_tarball(self):
        self.assertEqual(
            install_stockfish.select_asset(SF19_ASSETS, "Darwin", "arm64"),
            "stockfish-macos-universal.tar.gz")

    def test_intel_mac_also_takes_the_universal_build(self):
        self.assertEqual(
            install_stockfish.select_asset(SF19_ASSETS, "Darwin", "x86_64"),
            "stockfish-macos-universal.tar.gz")

    def test_linux_sf19(self):
        self.assertEqual(
            install_stockfish.select_asset(SF19_ASSETS, "Linux", "x86_64"),
            "stockfish-linux-x86-64-universal.tar.gz")
        self.assertEqual(
            install_stockfish.select_asset(SF19_ASSETS, "Linux", "aarch64"),
            "stockfish-linux-arm64-universal.tar.gz")

    def test_pinned_older_release_falls_back_to_legacy_names(self):
        self.assertEqual(
            install_stockfish.select_asset(LEGACY_ASSETS, "Darwin", "arm64"),
            "stockfish-macos-m1-apple-silicon.tar")
        self.assertEqual(
            install_stockfish.select_asset(LEGACY_ASSETS, "Darwin", "x86_64"),
            "stockfish-macos-x86-64-avx2.tar")
        self.assertEqual(
            install_stockfish.select_asset(LEGACY_ASSETS, "Linux", "x86_64"),
            "stockfish-ubuntu-x86-64-avx2.tar")

    def test_intel_mac_falls_back_when_avx2_absent(self):
        assets = [a for a in LEGACY_ASSETS if "avx2" not in a]
        self.assertEqual(
            install_stockfish.select_asset(assets, "Darwin", "x86_64"),
            "stockfish-macos-x86-64-sse41-popcnt.tar")

    def test_zip_assets_are_never_chosen(self):
        # Windows ships .zip; a zip must never be selected even if it matched.
        self.assertIsNone(install_stockfish.select_asset(
            ["stockfish-macos-universal.zip"], "Darwin", "arm64"))

    def test_no_match_returns_none(self):
        self.assertIsNone(
            install_stockfish.select_asset([], "Darwin", "arm64"))
        self.assertIsNone(
            install_stockfish.select_asset(SF19_ASSETS, "Plan9", "pdp11"))


class ExtractionTests(unittest.TestCase):
    """Archive handling: gzip tarballs, and never mistaking the archive itself
    for the binary."""

    def _make_tarball(self, work, name, compressed):
        """Write a tarball holding a big 'binary' and a small text file."""
        path = os.path.join(work, name)
        with tarfile.open(path, "w:gz" if compressed else "w") as tar:
            def add(arcname, payload):
                info = tarfile.TarInfo(arcname)
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            add("stockfish/stockfish-macos-universal", b"\x7fELF" + b"x" * 5000)
            add("stockfish/README.md", b"readme")
        return path

    def test_gzip_tarball_extracts_and_binary_is_found(self):
        with tempfile.TemporaryDirectory() as work:
            tar_path = self._make_tarball(work, "sf.tar.gz", compressed=True)
            extracted = os.path.join(work, "extracted")
            os.makedirs(extracted)
            install_stockfish._safe_extract(tar_path, extracted)
            binary = install_stockfish._find_binary(extracted)
            self.assertTrue(binary.endswith("stockfish-macos-universal"))

    def test_plain_tarball_still_works(self):
        with tempfile.TemporaryDirectory() as work:
            tar_path = self._make_tarball(work, "sf.tar", compressed=False)
            extracted = os.path.join(work, "extracted")
            os.makedirs(extracted)
            install_stockfish._safe_extract(tar_path, extracted)
            self.assertIsNotNone(install_stockfish._find_binary(extracted))

    def test_binary_search_never_returns_the_archive(self):
        # Searching the folder that holds the archive would pick the archive
        # (it is the largest file) -- the installer must search a subfolder.
        with tempfile.TemporaryDirectory() as work:
            tar_path = self._make_tarball(work, "sf.tar.gz", compressed=True)
            extracted = os.path.join(work, "extracted")
            os.makedirs(extracted)
            install_stockfish._safe_extract(tar_path, extracted)
            self.assertNotEqual(install_stockfish._find_binary(extracted),
                                tar_path)
            self.assertTrue(install_stockfish._find_binary(extracted)
                            .startswith(extracted))

    def test_unsafe_member_is_refused(self):
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "evil.tar")
            with tarfile.open(path, "w") as tar:
                info = tarfile.TarInfo("../escape")
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                install_stockfish._safe_extract(path, os.path.join(work, "x"))


if __name__ == "__main__":
    unittest.main()
