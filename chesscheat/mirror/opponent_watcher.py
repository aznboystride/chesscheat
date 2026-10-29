"""The ``OpponentWatcher`` screen poller for mirror mode."""

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

    Polling is driven by the view's ``schedule`` (the Tk event loop), so no
    thread is involved, and it costs nothing on our turn: the capture is
    skipped until the opponent is to move. Capture or scan errors are
    reported once per distinct message and polling continues.

    Attributes:
        enabled: Whether frames are being inspected (``set_enabled``).
        interval: Seconds between polls.
    """

    def __init__(self, game, grab, schedule, interval=0.25,
                 on_event=lambda kind, detail: None, scan=None,
                 enabled=True):
        """Create the watcher (call ``start`` to begin polling).

        Args:
            game: The ``MirrorGame`` to feed; it answers
                ``opponent_to_move``, ``board_map``, ``is_legal`` and
                ``submit_move``.
            grab: No-argument callable returning the next board image.
            schedule: ``schedule(seconds, fn)`` running ``fn`` later without
                blocking (the view's).
            interval: Seconds between polls.
            on_event: Optional ``(kind, detail)`` callback for logging.
            scan: ``scan(image)`` returning per-square statistics; defaults
                to ``chesscheat.recognition.scan_squares``.
            enabled: Initial state of the toggle.
        """
        self.enabled = enabled
        self.interval = interval
        self._game = game
        self._grab = grab
        self._schedule = schedule
        self._on_event = on_event
        self._scan = scan or _default_scan
        self._running = False
        self._last_error = None

    def set_enabled(self, enabled):
        """Turn inspection of the real board on or off.

        Args:
            enabled: True to infer opponent moves from the screen.
        """
        self.enabled = bool(enabled)
        self._on_event("watch", "on" if self.enabled else "off")

    def start(self):
        """Begin the polling loop (idempotent)."""
        if not self._running:
            self._running = True
            self._schedule(self.interval, self._tick)

    def stop(self):
        """Stop the polling loop after the current tick."""
        self._running = False

    def _tick(self):
        """One scheduled step: poll, then re-arm while running."""
        if not self._running:
            return
        self.poll()
        self._schedule(self.interval, self._tick)

    def poll(self):
        """Inspect the real board once and submit a detected move.

        Returns:
            The ``(from_name, to_name)`` submitted, or None if nothing was
            detected (or it is not the opponent's turn, or watching is off).
        """
        if not (self.enabled and self._game.opponent_to_move):
            return None
        try:
            scans = self._scan(self._grab())
        except Exception as exc:   # capture/scan failures must not stop Tk
            message = f"{type(exc).__name__}: {exc}"
            if message != self._last_error:
                self._last_error = message
                self._on_event("watch", f"capture failed: {message}")
            return None
        self._last_error = None
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
