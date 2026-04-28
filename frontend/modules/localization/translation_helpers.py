"""
Translation helper functions used everywhere instead of literal strings.

Usage:
    from modules.localization import tr_key
    from modules.localization.localization_keys import Buttons

    self.confirm_btn.setText(tr_key(Common.OK))
"""
from __future__ import annotations

from typing import List, Tuple

from modules.localization.localization_manager import LocalizationManager


def tr_key(key: str, **params) -> str:
    """Resolve a translation key to a localized string (with placeholders)."""
    return LocalizationManager.instance().get(key, **params)


def current_language() -> str:
    return LocalizationManager.instance().current_language()


def available_languages() -> List[Tuple[str, str, str]]:
    return LocalizationManager.instance().available_languages()
