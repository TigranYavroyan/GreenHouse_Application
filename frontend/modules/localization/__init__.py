"""
Public façade for the localization subsystem.

Typical imports:
    from modules.localization import tr_key, IRetranslatable, LocalizationManager
    from modules.localization.localization_keys import Common, Tabs, Buttons
"""
from modules.localization.app_settings import AppSettings
from modules.localization.i_retranslatable import IRetranslatable
from modules.localization.localization_manager import LocalizationManager
from modules.localization.translation_helpers import (
    available_languages,
    current_language,
    tr_key,
)

__all__ = [
    "AppSettings",
    "IRetranslatable",
    "LocalizationManager",
    "available_languages",
    "current_language",
    "tr_key",
]
