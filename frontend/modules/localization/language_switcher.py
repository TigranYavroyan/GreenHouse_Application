"""
Language flag switcher widget (top-right of the main window).

Senior UX/UI choices:
- Two clickable flag tiles, fixed 28x20 px (3:2 ratio).
- Active flag: full opacity + 1 px subtle accent border.
- Inactive flag: 50% opacity, brighten on hover.
- Tooltip uses native language name.
- Keyboard accessible: focus ring + Space/Enter activates.
- Pure flat dark style; inherits global stylesheet tokens.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QToolButton,
    QWidget,
)

from modules.localization.app_settings import AppSettings
from modules.localization.localization_manager import LocalizationManager


class _FlagButton(QToolButton):
    """Custom flat button that exposes opacity for active/inactive state."""

    def __init__(self, lang_code: str, native_name: str, icon_path: str, parent=None):
        super().__init__(parent)
        self.lang_code = lang_code
        self.native_name = native_name
        self.setObjectName(f"languageFlagButton_{lang_code}")
        self.setAutoRaise(True)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(28, 20))
        self.setFixedSize(36, 26)
        self.setToolTip(native_name)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self.setStyleSheet(
            """
            QToolButton#languageFlagButton_%s {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 2px;
            }
            QToolButton#languageFlagButton_%s:checked {
                border: 1px solid #6ECBFF;
                background: rgba(110, 203, 255, 0.10);
            }
            QToolButton#languageFlagButton_%s:hover {
                background: rgba(255,255,255,0.08);
            }
            QToolButton#languageFlagButton_%s:focus {
                border: 1px solid #9BD3FF;
                outline: none;
            }
            """
            % (lang_code, lang_code, lang_code, lang_code)
        )

    def set_active(self, is_active: bool) -> None:
        self.setChecked(is_active)
        self._opacity_effect.setOpacity(1.0 if is_active else 0.5)


class LanguageSwitcherWidget(QWidget):
    """Compact horizontal stack of flag buttons that drives language change."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("languageSwitcher")
        self._buttons: Dict[str, _FlagButton] = {}
        self._build_ui()
        manager = LocalizationManager.instance()
        manager.language_changed.connect(self._on_language_changed)
        self._on_language_changed(manager.current_language())

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        manager = LocalizationManager.instance()
        for code, native_name, icon_path in manager.available_languages():
            btn = _FlagButton(code, native_name, icon_path, parent=self)
            btn.clicked.connect(lambda _checked=False, lc=code: self._on_flag_clicked(lc))
            self._buttons[code] = btn
            layout.addWidget(btn)

    def _on_flag_clicked(self, lang_code: str) -> None:
        manager = LocalizationManager.instance()
        if manager.current_language() == lang_code:
            return
        manager.load_language(lang_code)
        AppSettings().set_language(lang_code)

    def _on_language_changed(self, lang_code: str) -> None:
        for code, button in self._buttons.items():
            button.set_active(code == lang_code)
