"""The ``MockMoveTrigger`` move trigger."""

from chesscheat.interfaces import MoveTrigger


class MockMoveTrigger(MoveTrigger):
    """A trigger fired manually in tests instead of by a keybind.

    Call ``fire`` to queue one activation; each queued activation is consumed
    by a single ``poll``.

    Attributes:
        started: True once ``start`` has been called.
        stopped: True once ``stop`` has been called.
    """

    def __init__(self):
        """Initialise the mock with no pending activations."""
        self._pending = 0
        self.started = False
        self.stopped = False

    def fire(self):
        """Queue one activation to be reported by the next ``poll``."""
        self._pending += 1

    def start(self):
        """Record that listening started."""
        self.started = True

    def poll(self):
        """Consume and report one queued activation.

        Returns:
            True if an activation was pending, else False.
        """
        if self._pending > 0:
            self._pending -= 1
            return True
        return False

    def stop(self):
        """Record that listening stopped."""
        self.stopped = True
