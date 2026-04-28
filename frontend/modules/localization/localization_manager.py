"""
LocalizationManager: globally accessible QObject singleton that owns
translation tables and notifies registered widgets when language changes.

Design constraints (from project rules):
- Inherits QObject; exposes pyqtSignal language_changed.
- Loads JSON files from `frontend/resources/i18n/`.
- Maintains current + English fallback dictionaries.
- Missing key -> "[[<key>]]" placeholder (no exceptions).
- Holds a weak registry of `IRetranslatable` widgets and calls
  `retranslate_ui()` on each on language change.
- All file/IO is done synchronously at language switch time. JSON files
  are small enough that this is fast and avoids cross-thread issues.
"""
from __future__ import annotations

import json
import logging
import os
import weakref
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal


class LocalizationManager(QObject):
    """Singleton holding all translations and the active language."""

    language_changed = pyqtSignal(str)

    DEFAULT_LANGUAGE = "en"
    FALLBACK_LANGUAGE = "en"
    MISSING_KEY_PATTERN = "[[{key}]]"

    _instance: Optional["LocalizationManager"] = None

    @classmethod
    def instance(cls) -> "LocalizationManager":
        if cls._instance is None:
            cls._instance = LocalizationManager()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        if LocalizationManager._instance is not None:
            raise RuntimeError("LocalizationManager is a singleton; use LocalizationManager.instance().")

        self._logger = logging.getLogger("LocalizationManager")
        self._resources_dir = self._resolve_resources_dir()
        self._current_language: str = self.DEFAULT_LANGUAGE
        self._translations_current: Dict[str, str] = {}
        self._translations_fallback_en: Dict[str, str] = {}
        self._registered: "weakref.WeakSet[object]" = weakref.WeakSet()
        self._available: List[Tuple[str, str, str]] = self._discover_available_languages()

        self._translations_fallback_en = self._load_language_file(self.FALLBACK_LANGUAGE)
        self._translations_current = dict(self._translations_fallback_en)

    @staticmethod
    def _resolve_resources_dir() -> str:
        """`frontend/resources/i18n/` (sibling of the `modules/` package)."""
        here = os.path.dirname(os.path.abspath(__file__))
        frontend_dir = os.path.abspath(os.path.join(here, os.pardir, os.pardir))
        return os.path.join(frontend_dir, "resources", "i18n")

    def _resolve_flag_path(self, flag_filename: str) -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        frontend_dir = os.path.abspath(os.path.join(here, os.pardir, os.pardir))
        return os.path.join(frontend_dir, "resources", "flags", flag_filename)

    def _discover_available_languages(self) -> List[Tuple[str, str, str]]:
        """Hard-coded supported languages (code, native_name, flag_path).

        Adding a new language: drop a JSON file in resources/i18n and add
        a tuple here. Name displayed in switcher uses native_name.
        """
        return [
            ("en", "English", self._resolve_flag_path("gb.svg")),
            ("hy", "Հայերեն", self._resolve_flag_path("am.svg")),
        ]

    def available_languages(self) -> List[Tuple[str, str, str]]:
        return list(self._available)

    def current_language(self) -> str:
        return self._current_language

    def is_supported(self, lang_code: str) -> bool:
        return any(code == lang_code for code, _, _ in self._available)

    def _load_language_file(self, lang_code: str) -> Dict[str, str]:
        path = os.path.join(self._resources_dir, f"{lang_code}.json")
        if not os.path.isfile(path):
            self._logger.warning("Translation file not found: %s", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            self._logger.error("Failed to load translation file %s: %s", path, error)
            return {}
        if not isinstance(data, dict):
            self._logger.error("Translation file %s root is not an object", path)
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def load_language(self, lang_code: str) -> None:
        """Switch the active language and notify registered widgets."""
        code = str(lang_code or "").strip() or self.DEFAULT_LANGUAGE
        if not self.is_supported(code):
            self._logger.warning("Unsupported language '%s'; falling back to '%s'.", code, self.DEFAULT_LANGUAGE)
            code = self.DEFAULT_LANGUAGE

        if code == self._current_language and self._translations_current:
            self.language_changed.emit(code)
            return

        if code == self.FALLBACK_LANGUAGE:
            translations = dict(self._translations_fallback_en)
        else:
            translations = self._load_language_file(code)
            if not translations:
                self._logger.warning("Empty/missing translations for '%s'; using fallback only.", code)

        self._current_language = code
        self._translations_current = translations
        self._logger.info("Language changed to '%s' (%d keys)", code, len(translations))
        self.notify_language_changed()

    def get(self, key: str, **params) -> str:
        """Resolve a translation key with optional placeholders."""
        if not isinstance(key, str) or not key:
            return self.MISSING_KEY_PATTERN.format(key=str(key))

        template = self._translations_current.get(key)
        if template is None:
            template = self._translations_fallback_en.get(key)
        if template is None:
            return self.MISSING_KEY_PATTERN.format(key=key)

        if not params:
            return template
        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError) as error:
            self._logger.warning("Format error for key '%s' (%s): %s", key, params, error)
            return template

    def register(self, widget) -> None:
        if widget is None:
            return
        if not hasattr(widget, "retranslate_ui"):
            self._logger.debug("Skipping register: %r has no retranslate_ui()", widget)
            return
        self._registered.add(widget)

    def unregister(self, widget) -> None:
        if widget is None:
            return
        try:
            self._registered.discard(widget)
        except Exception:
            pass

    def notify_language_changed(self) -> None:
        """Iterate the registry and call `retranslate_ui` on each entry."""
        for widget in list(self._registered):
            try:
                widget.retranslate_ui()
            except Exception as error:
                self._logger.warning("retranslate_ui failed for %r: %s", widget, error)
        self.language_changed.emit(self._current_language)
