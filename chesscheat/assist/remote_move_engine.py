"""The ``RemoteMoveEngine`` move engine."""

import json
import urllib.request

from chesscheat.interfaces import MoveEngine


class RemoteMoveEngine(MoveEngine):
    """A ``MoveEngine`` that asks a remote service for the best move.

    Sends the position to an HTTP endpoint and reads the reply, so the
    engine can run on another machine (a beefier box, a shared server, a
    cloud function). The wire format is deliberately minimal JSON:

    - request: ``POST <url>`` with body ``{"fen": "<full FEN>"}``
    - response: ``{"move": "e2e4"}`` (UCI), or ``{"move": null}`` for no move

    Standard-library only (``urllib``), so no extra client dependency.

    Attributes:
        url: The endpoint that computes best moves.
        timeout: Seconds to wait for a reply.
    """

    def __init__(self, url, timeout=30.0):
        """Initialise the client.

        Args:
            url: The HTTP(S) endpoint to POST positions to.
            timeout: Seconds to wait for the service to reply.
        """
        self.url = url
        self.timeout = timeout

    def best_move(self, fen):
        """Ask the remote service for the best move.

        Args:
            fen: A full FEN string including the side to move.

        Returns:
            The best move in UCI notation, or None if the service reports no
            move.

        Raises:
            RuntimeError: If the service is unreachable, returns a non-2xx
                status, or replies with malformed JSON.
        """
        body = json.dumps({"fen": fen}).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "User-Agent": "chesscheat"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as r:
                reply = json.load(r)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"remote engine at {self.url} failed: {exc}")
        if not isinstance(reply, dict) or "move" not in reply:
            raise RuntimeError(f"remote engine at {self.url} replied "
                               f"without a 'move' field: {reply!r}")
        return reply["move"] or None
