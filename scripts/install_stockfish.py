"""Download and install a Stockfish binary for the current platform.

Picks the release asset matching the host CPU/OS -- for an Apple Silicon Mac
(M1 through M4) the ``macos-m1-apple-silicon`` build -- downloads it from the
official Stockfish GitHub releases, extracts the binary and installs it as
``<dest>/stockfish`` (typically ``venv/bin`` so ``shutil.which("stockfish")``
finds it). On macOS the download's quarantine flag is cleared so Gatekeeper
does not block the first run.

Standard-library only, so ``setup.sh`` can run it with the freshly created
venv's Python. The asset-selection logic (``asset_candidates`` /
``select_asset``) is pure and unit-tested without any network.

Usage:
    python3 scripts/install_stockfish.py --dest venv/bin
    STOCKFISH_VERSION=sf_17.1 python3 scripts/install_stockfish.py --dest venv/bin
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

RELEASES_API = "https://api.github.com/repos/official-stockfish/Stockfish/releases"


def asset_candidates(system, machine):
    """Return release-asset name fragments to try, most preferred first.

    Args:
        system: ``platform.system()`` value, e.g. ``"Darwin"``, ``"Linux"``.
        machine: ``platform.machine()`` value, e.g. ``"arm64"``, ``"x86_64"``.

    Returns:
        An ordered list of substrings; an asset whose name contains an
        earlier fragment is preferred. Empty if the platform is unsupported.
    """
    system = system.lower()
    machine = machine.lower()
    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            # One Apple Silicon build covers M1..M4.
            return ["macos-m1-apple-silicon"]
        if machine in ("x86_64", "amd64"):
            return ["macos-x86-64-avx2", "macos-x86-64-sse41-popcnt",
                    "macos-x86-64"]
    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return ["ubuntu-x86-64-avx2", "ubuntu-x86-64-sse41-popcnt",
                    "ubuntu-x86-64"]
        if machine in ("aarch64", "arm64"):
            return ["ubuntu-aarch64", "android-armv8"]
    return []


def select_asset(asset_names, system, machine):
    """Choose the best-matching ``.tar`` asset name for a platform.

    Args:
        asset_names: Asset file names available in a release.
        system: ``platform.system()`` value.
        machine: ``platform.machine()`` value.

    Returns:
        The chosen asset name, or None if none match this platform.
    """
    for fragment in asset_candidates(system, machine):
        matches = sorted(name for name in asset_names
                         if fragment in name and name.endswith(".tar"))
        if matches:
            return matches[0]
    return None


def _fetch_release(version):
    """Fetch a release's JSON from the GitHub API.

    Args:
        version: A release tag (e.g. ``"sf_17.1"``), or ``"latest"``/None for
            the newest release.

    Returns:
        The parsed release object.
    """
    if version in (None, "", "latest"):
        url = f"{RELEASES_API}/latest"
    else:
        url = f"{RELEASES_API}/tags/{version}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "chesscheat-setup",
                      "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _download(url, dest_path):
    """Download ``url`` to ``dest_path``.

    Args:
        url: The file URL.
        dest_path: Where to write the downloaded bytes.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "chesscheat-setup"})
    with urllib.request.urlopen(request, timeout=120) as response, \
            open(dest_path, "wb") as out:
        shutil.copyfileobj(response, out)


def _safe_extract(tar_path, dest_dir):
    """Extract a tar archive, refusing members that escape ``dest_dir``.

    Args:
        tar_path: Path to the ``.tar`` file.
        dest_dir: Directory to extract into.

    Raises:
        ValueError: If a member would extract outside ``dest_dir``.
    """
    dest_dir = os.path.realpath(dest_dir)
    with tarfile.open(tar_path) as tar:
        for member in tar.getmembers():
            target = os.path.realpath(os.path.join(dest_dir, member.name))
            if target != dest_dir and not target.startswith(dest_dir + os.sep):
                raise ValueError(f"unsafe path in archive: {member.name}")
        tar.extractall(dest_dir)


def _find_binary(root):
    """Return the extracted Stockfish executable (the largest regular file).

    The Stockfish tarball holds the binary (tens of MB, embedded NNUE) beside
    small text files, so the largest file is the engine.

    Args:
        root: Directory the archive was extracted into.

    Returns:
        Path to the binary, or None if the tree held no files.
    """
    files = (os.path.join(base, name)
             for base, _dirs, names in os.walk(root) for name in names)
    return max(files, key=os.path.getsize, default=None)


def _verify(binary):
    """Check a binary answers the UCI handshake.

    Args:
        binary: Path to a Stockfish executable.

    Returns:
        True if the engine printed ``uciok`` in response to ``uci``.
    """
    try:
        result = subprocess.run(
            [binary], input="uci\nquit\n", capture_output=True,
            text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return "uciok" in result.stdout


def install(dest_dir, version=None, force=False):
    """Install Stockfish into ``dest_dir`` as ``stockfish``.

    Args:
        dest_dir: Directory to install the binary into (created if needed).
        version: Release tag to install, or None/``"latest"`` for the newest.
        force: Reinstall even if a working binary is already present.

    Returns:
        The installed binary's path.

    Raises:
        RuntimeError: If the platform is unsupported or no asset matches.
    """
    system, machine = platform.system(), platform.machine()
    target = os.path.join(dest_dir, "stockfish")

    if not force and os.path.exists(target) and _verify(target):
        print(f"Stockfish already installed at {target}")
        return target

    if not asset_candidates(system, machine):
        raise RuntimeError(
            f"Unsupported platform {system}/{machine}. Install Stockfish "
            "manually and put it on PATH or set STOCKFISH_PATH.")

    release = _fetch_release(version or os.environ.get("STOCKFISH_VERSION"))
    assets = {a["name"]: a["browser_download_url"]
              for a in release.get("assets", [])}
    asset = select_asset(assets, system, machine)
    if not asset:
        raise RuntimeError(
            f"No Stockfish asset for {system}/{machine} in release "
            f"{release.get('tag_name', '?')}.")

    print(f"Installing Stockfish {release.get('tag_name', '?')} for "
          f"{system}/{machine}: {asset}")
    os.makedirs(dest_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        tar_path = os.path.join(work, asset)
        _download(assets[asset], tar_path)
        _safe_extract(tar_path, work)
        binary = _find_binary(os.path.join(work, "stockfish")) \
            if os.path.isdir(os.path.join(work, "stockfish")) \
            else _find_binary(work)
        if binary is None:
            raise RuntimeError("archive contained no binary")
        shutil.copy2(binary, target)

    os.chmod(target, 0o755)
    if system == "Darwin":
        # Downloaded binaries are quarantined; clear it so Gatekeeper does not
        # block the first launch. Best-effort -- harmless if xattr is absent.
        subprocess.run(["xattr", "-d", "com.apple.quarantine", target],
                       capture_output=True)

    if _verify(target):
        print(f"Stockfish ready at {target}")
    else:
        print(f"Installed {target}, but the UCI self-check did not pass. "
              "It may need a security override, or the build may not match "
              "this machine.", file=sys.stderr)
    return target


def main(argv=None):
    """Command-line entry point.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code: 0 on success, 1 on a handled failure.
    """
    parser = argparse.ArgumentParser(description="Install a Stockfish binary.")
    parser.add_argument("--dest", default="venv/bin",
                        help="directory to install into (default: venv/bin)")
    parser.add_argument("--version", default=None,
                        help="release tag, e.g. sf_17.1 (default: latest)")
    parser.add_argument("--force", action="store_true",
                        help="reinstall even if already present")
    args = parser.parse_args(argv)
    try:
        install(args.dest, version=args.version, force=args.force)
    except Exception as exc:  # keep setup resilient; report and signal failure
        print(f"Could not install Stockfish: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
