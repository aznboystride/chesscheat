"""The ``RemoteMoveEngine`` move engine."""

import json
import urllib.request

from chesscheat.interfaces import MoveEngine


class RemoteMoveEngine(MoveEngine):
    """A ``MoveEngine`` that asks a remote service for the best move.

    Sends the position to an HTTP endpoint and reads the reply, so the
    engine can run on another machine (a beefier box, a shared server, a
    cloud function). The wire format is deliberately minimal JSON:

    - request: ``POST <url>`` with body ``{"fen": "<full FEN>", "elo": N,
      "think": S}`` where ``elo`` is the requested strength or ``null`` for
      full strength and ``think`` the search time in seconds or ``null``
      for the service's own default (it may ignore both);
    - response: ``{"move": "e2e4"}`` (UCI), or ``{"move": null}`` for no move.
    - evaluation: ``POST <url>`` with ``{"fen": "<full FEN>", "evaluate":
      true}``; the response may carry ``"score": {"cp": N}`` or
      ``{"mate": N}`` from white's perspective (any ``move`` is ignored). A
      service that does not evaluate simply omits ``score`` (or answers
      ``{"move": null}`` at once) and the bar shows nothing.

    Standard-library only (``urllib``), so no extra client dependency.

    Attributes:
        url: The endpoint that computes best moves.
        timeout: Seconds to wait for a reply.
        elo: Requested strength from ``set_strength``, or None.
        think_time: Requested search seconds from ``set_think_time``, or
            None.
    """

    def __init__(self, url, timeout=30.0):
        """Initialise the client.

        Args:
            url: The HTTP(S) endpoint to POST positions to.
            timeout: Seconds to wait for the service to reply.
        """
        self.url = url
        self.timeout = timeout
        self.elo = None
        self.think_time = None

    def set_think_time(self, seconds):
        """Forward a search-time request to the service with each query.

        Args:
            seconds: Search time in seconds.
        """
        self.think_time = float(seconds)

    def set_strength(self, elo):
        """Forward a strength request to the service with each query.

        Args:
            elo: Target Elo rating, or None for full strength.
        """
        self.elo = elo

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
        reply = self._post({"fen": fen, "elo": self.elo,
                            "think": self.think_time})
        if "move" not in reply:
            raise RuntimeError(f"remote engine at {self.url} replied "
                               f"without a 'move' field: {reply!r}")
        return reply["move"] or None

    def evaluate(self, fen):
        """Ask the remote service to score a position.

        Args:
            fen: A full FEN string including the side to move.

        Returns:
            The reply's ``score`` (``{"cp": n}`` / ``{"mate": n}``) when it
            is a dict, else None.

        Raises:
            RuntimeError: If the service is unreachable, returns a non-2xx
                status, or replies with malformed JSON.
        """
        score = self._post({"fen": fen, "evaluate": True}).get("score")
        return score if isinstance(score, dict) else None

    def _post(self, payload):
        """POST a JSON payload and return the decoded JSON object reply.

        Args:
            payload: The JSON-serialisable request body.

        Returns:
            The reply as a dict.

        Raises:
            RuntimeError: On transport failure, a non-2xx status, malformed
                JSON or a reply that is not a JSON object.
        """
        body = json.dumps(payload).encode("utf-8")
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
        if not isinstance(reply, dict):
            raise RuntimeError(f"remote engine at {self.url} replied with "
                               f"something other than an object: {reply!r}")
        return reply
