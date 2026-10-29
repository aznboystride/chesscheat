"""The ``OpponentWatcher`` screen poller for mirror mode."""

import threading
import time

from chesscheat.mirror.move_inference import (highlighted_squares,
                                              piece_colours,
                                              infer_opponent_move)


class OpponentWatcher:
    """Infers the opponent's moves from the real app instead of the user.

    While it is the opponent's turn, the real board is captured repeatedly
    and each frame is scanned for the app's **last-move highlight**: two
    tinted squares, the origin now empty and the destination now holding an
    opponent piece, forming a legal opponent move in the game model
    (``chesscheat.mirror.move_inference``). The first frame that shows one
    is submitted to the game exactly as if the user had entered it; the
    user can still enter moves by hand meanwhile. Our own moves are
    highlighted by the app too, and are ignored because no legal opponent
    move starts from a square of ours.

    **Capture runs as fast as the screen can be read**: a daemon thread
    grabs and scans frames back to back (the image work, which needs
    nothing from the game) whenever a flag says the opponent is to move,
    and parks the newest scan in a mailbox. The view's ``schedule`` ticks
    the GUI side every ``interval`` seconds: it refreshes the flag from the
    game (so the thread never touches the game model) and runs the cheap
    inference on the latest scan, submitting a detected move. Nothing is
    captured on our turn or while the toggle is off, and the thread sleeps
    then. With ``threaded=False`` every tick captures synchronously instead
    (``poll``), which is also what the tests drive. Capture or scan errors
    are reported once per distinct message and watching continues.

    Attributes:
        enabled: Whether frames are being inspected (``set_enabled``).
        interval: Seconds between GUI-side ticks.
        threaded: Whether capture runs on its own thread.
    """

    def __init__(self, game, grab, schedule, interval=0.02,
                 on_event=lambda kind, detail: None, scan=None,
                 enabled=True, threaded=True, idle_sleep=0.05):
        """Create the watcher (call ``start`` to begin polling).

        Args:
            game: The ``MirrorGame`` to feed; it answers
                ``opponent_to_move``, ``board_map``, ``is_legal`` and
                ``submit_move``.
            grab: No-argument callable returning the next board image.
            schedule: ``schedule(seconds, fn)`` running ``fn`` later without
                blocking (the view's).
            interval: Seconds between GUI-side ticks (inference on the
                latest scan, or a synchronous capture when not threaded).
            on_event: Optional ``(kind, detail)`` callback for logging.
            scan: ``scan(image)`` returning per-square statistics; defaults
                to ``chesscheat.recognition.scan_squares``.
            enabled: Initial state of the toggle.
            threaded: True to capture continuously on a daemon thread;
                False to capture synchronously on each tick.
            idle_sleep: Seconds the capture thread sleeps between checks
                while there is nothing to watch.
        """
        self.enabled = enabled
        self.interval = interval
        self.threaded = threaded
        self._game = game
        self._grab = grab
        self._schedule = schedule
        self._on_event = on_event
        self._scan = scan or _default_scan
        self._idle_sleep = idle_sleep
        self._running = False
        self._last_error = None
        self._wanted = False     # set by the GUI tick; read by the thread
        self._latest = None      # newest scan from the thread, or None
        self._latest_error = None
        self._thread = None

    def set_enabled(self, enabled):
        """Turn inspection of the real board on or off.

        Args:
            enabled: True to infer opponent moves from the screen.
        """
        self.enabled = bool(enabled)
        self._on_event("watch", "on" if self.enabled else "off")

    def start(self):
        """Begin watching (idempotent): the GUI ticks and, if threaded, the
        capture thread."""
        if self._running:
            return
        self._running = True
        if self.threaded:
            self._thread = threading.Thread(target=self._capture_loop,
                                            daemon=True)
            self._thread.start()
        self._schedule(self.interval, self._tick)

    def stop(self):
        """Stop watching after the current tick (the thread exits too)."""
        self._running = False
        self._wanted = False

    def _active(self):
        """Whether frames should be inspected right now."""
        return self.enabled and self._game.opponent_to_move

    def _tick(self):
        """One scheduled GUI step: refresh the flag, consume, re-arm."""
        if not self._running:
            return
        self._wanted = self._active()
        if self.threaded:
            self._consume()
        else:
            self.poll()
        self._schedule(self.interval, self._tick)

    # -- capture thread ----------------------------------------------------

    def _capture_loop(self):
        """Grab and scan back to back while wanted; sleep otherwise."""
        while self._running:
            if not self._wanted:
                time.sleep(self._idle_sleep)
                continue
            try:
                self._latest = self._scan(self._grab())
            except Exception as exc:   # reported from the GUI side
                self._latest_error = f"{type(exc).__name__}: {exc}"
                time.sleep(self._idle_sleep)

    def _consume(self):
        """Infer from the newest scan the thread parked, if any.

        Returns:
            The ``(from_name, to_name)`` submitted, or None.
        """
        error, self._latest_error = self._latest_error, None
        if error is not None:
            self._report_error(error)
        scans, self._latest = self._latest, None
        if scans is None or not self._wanted:
            return None
        self._last_error = None
        return self._infer(scans)

    # -- synchronous path --------------------------------------------------

    def poll(self):
        """Inspect the real board once, synchronously, and submit a move.

        Returns:
            The ``(from_name, to_name)`` submitted, or None if nothing was
            detected (or it is not the opponent's turn, or watching is off).
        """
        if not self._active():
            return None
        try:
            scans = self._scan(self._grab())
        except Exception as exc:   # capture/scan failures must not stop Tk
            self._report_error(f"{type(exc).__name__}: {exc}")
            return None
        self._last_error = None
        return self._infer(scans)

    # -- shared --------------------------------------------------------------

    def _report_error(self, message):
        """Log a capture failure once per distinct message."""
        if message != self._last_error:
            self._last_error = message
            self._on_event("watch", f"capture failed: {message}")

    def _infer(self, scans):
        """Read the opponent's move off a scan and submit it if found.

        Args:
            scans: Per-square statistics of the latest frame.

        Returns:
            The ``(from_name, to_name)`` submitted, or None.
        """
        bottom_white = self._game.playing_white
        highlighted = highlighted_squares(scans, bottom_white)
        colours = piece_colours(scans, bottom_white, self._game.board_map(),
                                self._game.playing_white)
        move = infer_opponent_move(highlighted, colours, self._game.is_legal)
        if move is None:
            return None
        self._on_event("detected", f"{move[0]}{move[1]} (from the app's "
                                   f"highlight)")
        self._game.submit_move(*move)
        return move


def _default_scan(image):
    """Scan a captured frame with the numpy implementation (lazy import)."""
    from chesscheat.recognition.square_scan import scan_squares
    return scan_squares(image)
