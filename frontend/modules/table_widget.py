"""
Simple responsive table widget for displaying data from RabbitMQ.
Adds rows dynamically as data arrives, with scrollable support.
"""
from typing import List, Optional

from PyQt5.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QStyledItemDelegate,
    QStyle,
    QPushButton,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics, QColor

from modules.localization import IRetranslatable, tr_key
from modules.localization.localization_keys import TableColumns, Tables
from modules.styles import GreenhouseTheme


class _NoFocusDelegate(QStyledItemDelegate):
    """Item delegate that suppresses the default focus rectangle on a cell."""

    def paint(self, painter, option, index):
        if option.state & QStyle.State_HasFocus:
            option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)


class SimpleDataTable(QWidget, IRetranslatable):
    """Responsive table for displaying tabular data."""

    ROW_HEIGHT = 35
    MIN_TABLE_HEIGHT = 0

    _STATUS_ROLE_TOKEN = "status"

    def __init__(
        self,
        columns=None,
        parent=None,
        show_clear_button=False,
        on_clear_requested=None,
        on_remove_selected_requested=None,
    ):
        super().__init__(parent)
        self.theme = GreenhouseTheme()
        self.columns = columns or [tr_key(TableColumns.TIMESTAMP), tr_key(TableColumns.DATA)]
        self.on_clear_requested = on_clear_requested
        self.on_remove_selected_requested = on_remove_selected_requested

        self._column_keys: List[Optional[str]] = [None] * len(self.columns)
        self._column_role_tokens: List[str] = ["" for _ in self.columns]

        self.setObjectName("simpleDataTable")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(0)
        self.setMinimumWidth(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if show_clear_button:
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            self.remove_row_button = QPushButton("")
            self.remove_row_button.setObjectName("removeTableRowButton")
            self.remove_row_button.setFixedHeight(32)
            self.remove_row_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.remove_row_button.clicked.connect(self.remove_selected_row)
            btn_row.addWidget(self.remove_row_button, 0, Qt.AlignLeft)

            self.clear_button = QPushButton("")
            self.clear_button.setObjectName("clearTableButton")
            self.clear_button.setFixedHeight(32)
            self.clear_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.clear_button.clicked.connect(self._handle_clear_clicked)
            btn_row.addWidget(self.clear_button, 0, Qt.AlignLeft)
            btn_row.addStretch(1)
            layout.addLayout(btn_row)
        else:
            self.clear_button = None
            self.remove_row_button = None

        self.table = QTableWidget()
        self.table.setObjectName("dataTable")
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)
        self.table.setItemDelegate(_NoFocusDelegate(self.table))
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setRowCount(0)

        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(0)
        self.table.setMinimumWidth(0)
        layout.addWidget(self.table, 1)

        self.init_localization()

    def set_column_keys(self, keys: List[Optional[str]]) -> None:
        """Provide stable translation keys for the column headers.

        When set, `retranslate_ui` will use these to update headers in the
        active language. The list must match `len(self.columns)`.
        """
        normalized = list(keys or [])
        while len(normalized) < self.table.columnCount():
            normalized.append(None)
        self._column_keys = normalized[: self.table.columnCount()]

    def set_column_role_tokens(self, tokens: List[str]) -> None:
        """Locale-independent role tokens (e.g. "status") for cell styling."""
        normalized = [str(t or "").strip().lower() for t in (tokens or [])]
        while len(normalized) < self.table.columnCount():
            normalized.append("")
        self._column_role_tokens = normalized[: self.table.columnCount()]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.table.updateGeometry()
        self.table.viewport().update()

    def add_row(self, data):
        if len(data) != self.table.columnCount():
            if len(data) > self.table.columnCount():
                self.table.setColumnCount(len(data))
                headers = list(self.columns)
                while len(headers) < len(data):
                    headers.append(tr_key(Tables.COLUMN_FALLBACK, n=len(headers) + 1))
                self.table.setHorizontalHeaderLabels(headers)
                self.columns = headers
                while len(self._column_keys) < len(data):
                    self._column_keys.append(None)
                while len(self._column_role_tokens) < len(data):
                    self._column_role_tokens.append("")

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, self.ROW_HEIGHT)
        for col, value in enumerate(data):
            item = QTableWidgetItem(str(value) if value is not None else "")
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._apply_semantic_cell_style(col, item)
            self.table.setItem(row, col, item)
        self.table.scrollToBottom()

    def _apply_semantic_cell_style(self, column_index, item):
        """Apply lightweight semantic colors for status-role columns.

        Uses the locale-independent role token (set via `set_column_role_tokens`),
        so styling works in any language and there's no substring match on
        translated header text.
        """
        if not item:
            return
        if not isinstance(column_index, int) or column_index < 0:
            return
        if column_index >= len(self._column_role_tokens):
            return

        if self._column_role_tokens[column_index] != self._STATUS_ROLE_TOKEN:
            return

        text = str(item.text() or "").strip().lower()
        success_tokens = {
            tr_key(Tables.STATUS_SUCCESS).lower(),
            tr_key(Tables.STATUS_SUCCESS_CACHED).lower(),
            "success",
            "ok",
            "completed",
        }
        failed_tokens = {
            tr_key(Tables.STATUS_FAILED).lower(),
            "failed",
            "error",
            "timeout",
        }
        warning_tokens = {
            "in progress",
            "running",
            "pending",
            "scheduled",
        }

        if any(token in text for token in success_tokens):
            item.setForeground(QColor(self.theme.colors.success))
            return
        if any(token in text for token in failed_tokens):
            item.setForeground(QColor(self.theme.colors.error))
            return
        if any(token in text for token in warning_tokens):
            item.setForeground(QColor(self.theme.colors.warning))
            return
        item.setForeground(QColor(self.theme.colors.text_secondary))

    def clear_data(self):
        self.table.setRowCount(0)

    def get_row_count(self):
        return self.table.rowCount()

    def _handle_clear_clicked(self):
        if callable(self.on_clear_requested):
            self.on_clear_requested()
            return
        self.clear_data()

    def remove_selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            return
        if callable(self.on_remove_selected_requested):
            self.on_remove_selected_requested(row)
            return
        self.table.removeRow(row)

    def retranslate_ui(self) -> None:
        if self.remove_row_button is not None:
            new_label = tr_key(Tables.REMOVE_SELECTED)
            self.remove_row_button.setText(new_label)
            metrics = QFontMetrics(self.remove_row_button.font())
            label_width = metrics.horizontalAdvance(new_label)
            self.remove_row_button.setMinimumWidth(max(170, label_width + 28))
        if self.clear_button is not None:
            new_label = tr_key(Tables.HIDE_ALL)
            self.clear_button.setText(new_label)
            metrics = QFontMetrics(self.clear_button.font())
            label_width = metrics.horizontalAdvance(new_label)
            self.clear_button.setMinimumWidth(max(120, label_width + 28))

        if self._column_keys:
            new_columns = list(self.columns)
            for index, key in enumerate(self._column_keys):
                if key:
                    new_columns[index] = tr_key(key)
            self.columns = new_columns
            self.table.setHorizontalHeaderLabels(self.columns)
