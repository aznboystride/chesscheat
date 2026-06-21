"""Screen-capture utilities.

Importing this package pulls in numpy and mss; keep it behind a lazy import in
code that must run without those dependencies.
"""

from chesscheat.capture.screenshot import screenshot

__all__ = ["screenshot"]
