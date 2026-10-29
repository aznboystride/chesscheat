"""The ``BackgroundRunner`` thread-to-event-loop bridge."""

import queue
import threading


class BackgroundRunner:
    """Runs callables on worker threads, delivering results on an event loop.

    A GUI must not be touched from a thread, and must not block its loop
    on a slow call (an engine search). ``run`` starts a daemon thread for
    the call and queues its outcome; the loop is then polled through the
    ``after`` function it was given (Tk's ``root.after``) until every
    pending outcome has been handed to its ``done`` callback -- on the
    loop's thread, where widgets are safe to use. Polling stops when there
    is nothing pending, so an idle GUI costs nothing.

    Attributes:
        pending: Number of jobs started whose result is not delivered yet.
    """

    def __init__(self, after, poll_ms=25):
        """Create the bridge.

        Args:
            after: ``after(milliseconds, fn)`` scheduling ``fn`` on the GUI
                event loop (e.g. ``tk.Tk().after``).
            poll_ms: How often, in milliseconds, to look for finished jobs
                while any are running.
        """
        self._after = after
        self._poll_ms = poll_ms
        self._results = queue.Queue()   # (done, result, error)
        self.pending = 0

    def run(self, fn, done):
        """Run ``fn`` on a thread and report its outcome on the event loop.

        Args:
            fn: No-argument callable to run on a worker thread.
            done: ``done(result, error)`` called on the event loop;
                ``error`` is the exception ``fn`` raised, else None.
        """
        def work():
            try:
                result = fn()
            except Exception as exc:
                self._results.put((done, None, exc))
            else:
                self._results.put((done, result, None))

        self.pending += 1
        threading.Thread(target=work, daemon=True).start()
        if self.pending == 1:
            self._after(self._poll_ms, self._drain)

    def _drain(self):
        """Deliver every finished outcome; keep polling while jobs remain."""
        while True:
            try:
                done, result, error = self._results.get_nowait()
            except queue.Empty:
                break
            self.pending -= 1
            done(result, error)
        if self.pending > 0:
            self._after(self._poll_ms, self._drain)
