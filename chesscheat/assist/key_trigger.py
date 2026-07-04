"""The ``KeyTrigger`` move trigger."""

from chesscheat.interfaces import MoveTrigger


class KeyTrigger(MoveTrigger):
    """Fires when a chosen key is pressed anywhere, via a global listener.

    Uses ``pynput`` to watch the keyboard system-wide (so it works while the
    chess site, not the terminal, has focus). Each matching keypress sets a
    flag that ``poll`` consumes, so one press yields one move.

    Attributes:
        key: The activation key character (case-insensitive).
    """

    def __init__(self, key="a"):
        """Initialise the trigger.

        Args:
            key: The character that activates the trigger, e.g. ``"a"``.
        """
        self.key = key
        self._event = None
        self._listener = None

    def start(self):
        """Start the background keyboard listener.

        Raises:
            ImportError: If ``pynput`` is not installed.
        """
        import threading
        from pynput import keyboard

        self._event = threading.Event()

        def on_press(pressed):
            char = getattr(pressed, "char", None)
            if char and char.lower() == self.key.lower():
                self._event.set()

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def poll(self):
        """Report and clear a pending keypress.

        Returns:
            True if the key was pressed since the last poll, else False.
        """
        if self._event is not None and self._event.is_set():
            self._event.clear()
            return True
        return False

    def stop(self):
        """Stop the keyboard listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
