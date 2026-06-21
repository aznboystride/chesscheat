"""Real (production) implementations of the setup and frame-source interfaces.

Heavy/optional dependencies (tkinter via ``chesscheat.gui``, screen capture via
``chesscheat.capture``) are imported lazily inside the methods, so importing
this package stays cheap and safe.
"""

from chesscheat.providers.gui_setup_provider import GuiSetupProvider
from chesscheat.providers.prompt_setup_provider import PromptSetupProvider
from chesscheat.providers.fallback_setup_provider import FallbackSetupProvider
from chesscheat.providers.screen_frame_source import ScreenFrameSource

__all__ = [
    "GuiSetupProvider",
    "PromptSetupProvider",
    "FallbackSetupProvider",
    "ScreenFrameSource",
]
