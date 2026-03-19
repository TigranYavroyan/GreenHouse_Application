from typing import List, Optional, Sequence, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class _BaseStyledDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0B1020;
                color: #E7E9EE;
            }
            QLabel {
                color: #E7E9EE;
                font-size: 12px;
            }
            QLabel[role="caption"] {
                color: #A3ADC2;
                font-size: 11px;
            }
            QLineEdit, QComboBox {
                background-color: #131A2E;
                color: #E7E9EE;
                border: 1px solid #344266;
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #6ECBFF;
            }
            QComboBox QAbstractItemView {
                background-color: #131A2E;
                color: #E7E9EE;
                border: 1px solid #344266;
                selection-background-color: #344266;
                selection-color: #E7E9EE;
                outline: 0;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #344266;
                color: #E7E9EE;
            }
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: #E7E9EE;
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 10px;
                padding: 7px 12px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.14);
            }
            QPushButton[role="primary"] {
                background-color: #6ECBFF;
                color: #0B1020;
                border: 1px solid #6ECBFF;
                font-weight: 600;
            }
            QPushButton[role="danger"] {
                background-color: #FF6B6B;
                color: #0B1020;
                border: 1px solid #FF6B6B;
                font-weight: 600;
            }
            """
        )


class StyledMessageDialog(_BaseStyledDialog):
    def __init__(
        self,
        title: str,
        message: str,
        parent=None,
        *,
        kind: str = "info",
        confirm_text: str = "OK",
        cancel_text: Optional[str] = None,
    ):
        super().__init__(title, parent=parent)
        self._confirmed = False
        root = QVBoxLayout(self)
        root.setSpacing(10)

        text = QLabel(str(message or ""))
        text.setWordWrap(True)
        root.addWidget(text)

        buttons = QHBoxLayout()
        buttons.addStretch()

        if cancel_text:
            cancel_btn = QPushButton(cancel_text)
            cancel_btn.clicked.connect(self.reject)
            buttons.addWidget(cancel_btn)

        confirm_btn = QPushButton(confirm_text)
        if kind == "error":
            confirm_btn.setProperty("role", "danger")
        else:
            confirm_btn.setProperty("role", "primary")
        confirm_btn.clicked.connect(self._accept_confirm)
        buttons.addWidget(confirm_btn)
        root.addLayout(buttons)

    def _accept_confirm(self):
        self._confirmed = True
        self.accept()

    @staticmethod
    def show_error(parent, title: str, message: str):
        dialog = StyledMessageDialog(title, message, parent=parent, kind="error")
        dialog.exec_()

    @staticmethod
    def show_warning(parent, title: str, message: str):
        dialog = StyledMessageDialog(title, message, parent=parent, kind="warning")
        dialog.exec_()

    @staticmethod
    def show_info(parent, title: str, message: str):
        dialog = StyledMessageDialog(title, message, parent=parent, kind="info")
        dialog.exec_()

    @staticmethod
    def ask_yes_no(parent, title: str, message: str, yes_text: str = "Yes", no_text: str = "No") -> bool:
        dialog = StyledMessageDialog(
            title,
            message,
            parent=parent,
            kind="warning",
            confirm_text=yes_text,
            cancel_text=no_text,
        )
        dialog.exec_()
        return dialog._confirmed


class StyledInputDialog:
    @staticmethod
    def get_item(
        parent,
        title: str,
        label: str,
        items: Sequence[str],
        current: int = 0,
        editable: bool = False,
    ) -> Tuple[str, bool]:
        dialog = _BaseStyledDialog(title, parent=parent)
        root = QVBoxLayout(dialog)
        root.setSpacing(10)

        caption = QLabel(label)
        caption.setProperty("role", "caption")
        root.addWidget(caption)

        combo = QComboBox()
        combo.setEditable(bool(editable))
        combo.addItems([str(item) for item in items])
        if items:
            combo.setCurrentIndex(max(0, min(int(current), len(items) - 1)))
        root.addWidget(combo)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("OK")
        ok_btn.setProperty("role", "primary")
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        root.addLayout(buttons)

        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)

        accepted = dialog.exec_() == QDialog.Accepted
        return combo.currentText(), accepted

    @staticmethod
    def get_text(parent, title: str, label: str, initial_text: str = "") -> Tuple[str, bool]:
        dialog = _BaseStyledDialog(title, parent=parent)
        root = QVBoxLayout(dialog)
        root.setSpacing(10)

        caption = QLabel(label)
        caption.setProperty("role", "caption")
        root.addWidget(caption)

        input_field = QLineEdit()
        input_field.setText(str(initial_text or ""))
        root.addWidget(input_field)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("OK")
        ok_btn.setProperty("role", "primary")
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        root.addLayout(buttons)

        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)

        accepted = dialog.exec_() == QDialog.Accepted
        return input_field.text(), accepted
