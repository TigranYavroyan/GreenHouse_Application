"""
Settings dialog with language combo box.

Demonstrates the canonical IRetranslatable pattern:
- No hardcoded user-visible text in the constructor.
- All visible text is set in `retranslate_ui()`.
- Dialog auto-registers with LocalizationManager so live language
  switching from a flag click also updates the dialog while open.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.localization.app_settings import AppSettings
from modules.localization.i_retranslatable import IRetranslatable
from modules.localization.localization_keys import Common, Languages, Settings
from modules.localization.localization_manager import LocalizationManager
from modules.localization.translation_helpers import tr_key


_LANGUAGE_NAME_KEYS = {
    "en": Languages.ENGLISH,
    "hy": Languages.ARMENIAN,
}


class SettingsDialog(QDialog, IRetranslatable):
    """Modal dialog that exposes the language choice."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet(
            """
            QDialog#settingsDialog {
                background-color: #0B1020;
                color: #E7E9EE;
            }
            QLabel { color: #E7E9EE; }
            QComboBox {
                background-color: #131A2E;
                color: #E7E9EE;
                border: 1px solid #344266;
                border-radius: 8px;
                padding: 6px 10px;
                min-height: 22px;
            }
            QComboBox:focus { border: 1px solid #6ECBFF; }
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: #E7E9EE;
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 10px;
                padding: 7px 14px;
                min-height: 22px;
            }
            QPushButton[role="primary"] {
                background-color: #6ECBFF;
                color: #0B1020;
                border: 1px solid #6ECBFF;
                font-weight: 600;
            }
            """
        )

        self._language_label = QLabel(self)
        self._language_combo = QComboBox(self)
        self._apply_button = QPushButton(self)
        self._close_button = QPushButton(self)

        self._populate_languages()
        self._build_layout()
        self._wire_signals()
        self.init_localization()

    def _populate_languages(self) -> None:
        self._language_combo.blockSignals(True)
        self._language_combo.clear()
        manager = LocalizationManager.instance()
        for code, _native, _flag in manager.available_languages():
            self._language_combo.addItem("", code)
        index = self._language_combo.findData(manager.current_language())
        if index >= 0:
            self._language_combo.setCurrentIndex(index)
        self._language_combo.blockSignals(False)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(self._language_label)
        root.addWidget(self._language_combo)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        self._close_button.setObjectName("settingsCloseButton")
        self._apply_button.setObjectName("settingsApplyButton")
        self._apply_button.setProperty("role", "primary")
        buttons.addWidget(self._close_button)
        buttons.addWidget(self._apply_button)
        root.addLayout(buttons)

    def _wire_signals(self) -> None:
        self._language_combo.currentIndexChanged.connect(self._on_combo_changed)
        self._apply_button.clicked.connect(self.accept)
        self._close_button.clicked.connect(self.reject)

    def _on_combo_changed(self, _index: int) -> None:
        code = str(self._language_combo.currentData() or "").strip()
        if not code:
            return
        manager = LocalizationManager.instance()
        if manager.current_language() == code:
            return
        manager.load_language(code)
        AppSettings().set_language(code)

    def _refresh_combo_labels(self) -> None:
        self._language_combo.blockSignals(True)
        for index in range(self._language_combo.count()):
            code = str(self._language_combo.itemData(index) or "")
            label_key = _LANGUAGE_NAME_KEYS.get(code, code)
            self._language_combo.setItemText(index, tr_key(label_key))
        self._language_combo.blockSignals(False)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr_key(Settings.DIALOG_TITLE))
        self._language_label.setText(tr_key(Settings.LANGUAGE_LABEL))
        self._apply_button.setText(tr_key(Common.APPLY))
        self._close_button.setText(tr_key(Settings.CLOSE_BUTTON))
        self._refresh_combo_labels()
