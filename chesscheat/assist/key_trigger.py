"""The ``KeyTrigger`` move trigger."""

import sys

from chesscheat.interfaces import MoveTrigger


def has_input_monitoring():
    """Return whether this process may listen to global key events.

    On macOS a global key listener installs a Quartz event tap, which the OS
    permits only if the host app (Terminal, iTerm, the IDE) has been granted
    **Input Monitoring**. Creating the tap without it aborts the whole process
    with a "trace trap" that Python cannot catch -- so this preflight lets the
    caller disable the assist gracefully instead. When the permission is
    missing, the system prompt is requested so the app registers in
    *System Settings -> Privacy & Security -> Input Monitoring* for next time.

    On non-macOS platforms (no such permission model) this returns True, as it
    does when the check APIs are unavailable (older macOS) -- in which case the
    listener is simply allowed to try.

    Returns:
        True if the listener may be started, False if macOS permission is
        required but not yet granted.
    """
    if sys.platform != "darwin":
        return True
    try:
        import Quartz
    except ImportError:
        return True  # cannot check; let the listener attempt to start
    preflight = getattr(Quartz, "CGPreflightListenEventAccess", None)
    request = getattr(Quartz, "CGRequestListenEventAccess", None)
    if preflight is None:
        return True  # older macOS without the API
    if preflight():
        return True
    if request is not None:
        request()  # register the app and show the permission prompt
    return bool(preflight())


class KeyTrigger(MoveTrigger):
    """Fires when a chosen key is pressed anywhere, via a global listener.

    Uses ``pynput`` to watch the keyboard system-wide (so it works while the
    chess site, not the terminal, has focus). Each matching keypress sets a
    flag that ``poll`` consumes, so one press yields one move.

    On macOS the listener needs Input Monitoring permission; ``start`` checks
    for it first (``permission_ok``) and raises rather than letting the native
    event-tap creation abort the process. See ``has_input_monitoring``.

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

    def permission_ok(self):
        """Report whether the listener can be started on this platform.

        Returns:
            True if starting the global listener is permitted (always True off
            macOS); False if macOS Input Monitoring permission is missing.
        """
        return has_input_monitoring()

    def start(self):
        """Start the background keyboard listener.

        Raises:
            PermissionError: On macOS without Input Monitoring permission --
                raised deliberately instead of letting the native event tap
                abort the process with a trace trap.
            ImportError: If ``pynput`` is not installed.
        """
        if not self.permission_ok():
            raise PermissionError(
                f"macOS Input Monitoring permission is required for the "
                f"'{self.key.upper()}' assist keybind. Grant your terminal "
                "Input Monitoring (and Accessibility) in System Settings -> "
                "Privacy & Security, then restart it.")

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
