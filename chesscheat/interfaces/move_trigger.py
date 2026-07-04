"""The ``MoveTrigger`` interface."""

from abc import ABC, abstractmethod


class MoveTrigger(ABC):
    """Signals, on demand, that the user wants the assistant to move.

    A trigger typically listens for a keybind in the background. The read
    loop polls it once per frame: ``poll`` returns True at most once per
    activation (it consumes the signal), so a single keypress produces a
    single move.
    """

    @abstractmethod
    def start(self):
        """Begin listening for the activation signal."""

    @abstractmethod
    def poll(self):
        """Report and consume a pending activation.

        Returns:
            True if the trigger has fired since the last poll, clearing the
            pending state; False otherwise.
        """

    @abstractmethod
    def stop(self):
        """Stop listening and release any resources."""
