"""
Persistent application settings (currently: selected language).

Uses Qt's QSettings so persistence is platform-native and survives
restarts. The organization/application names are set by `main.py`
before any QSettings instance is created.
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import QSettings


_LANGUAGE_KEY = "i18n/language"


class AppSettings:
    """Thin facade over QSettings for app-level preferences."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("AppSettings")
        self._settings = QSettings()

    def get_language(self) -> Optional[str]:
        try:
            value = self._settings.value(_LANGUAGE_KEY, None)
        except Exception as error:
            self._logger.warning("QSettings read failed: %s", error)
            return None
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def set_language(self, lang_code: str) -> None:
        try:
            self._settings.setValue(_LANGUAGE_KEY, str(lang_code or ""))
            self._settings.sync()
        except Exception as error:
            self._logger.warning("QSettings write failed: %s", error)
