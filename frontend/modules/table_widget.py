"""
Simple responsive table widget for displaying data from RabbitMQ.
Adds rows dynamically as data arrives, with scrollable support.
"""
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
from modules.styles import GreenhouseTheme


class _NoFocusDelegate(QStyledItemDelegate):
    """
    Item delegate that removes the default focus rectangle/editor-looking
    frame that Qt draws around the current cell.

    This keeps row selection highlighting, but avoids the white rectangle
    that visually covers the cell contents when a row is clicked.
    """

    def paint(self, painter, option, index):
        if option.state & QStyle.State_HasFocus:
            option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)


class SimpleDataTable(QWidget):
    """
    Responsive table for displaying tabular data.
    Layout: [Clear button row] [Table - expands with window]
    Min height ensures usability; table grows with available space.
    """

    ROW_HEIGHT = 35
    MIN_TABLE_HEIGHT = 0

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
        self.columns = columns or ['Timestamp', 'Data']
        self.on_clear_requested = on_clear_requested
        self.on_remove_selected_requested = on_remove_selected_requested

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
            self.remove_row_button = QPushButton("Remove Selected Row")
            self.remove_row_button.setObjectName("removeTableRowButton")
            self.remove_row_button.setFixedHeight(32)
            remove_metrics = QFontMetrics(self.remove_row_button.font())
            remove_label_width = remove_metrics.horizontalAdvance(self.remove_row_button.text())
            self.remove_row_button.setMinimumWidth(max(170, remove_label_width + 28))
            self.remove_row_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.remove_row_button.clicked.connect(self.remove_selected_row)
            btn_row.addWidget(self.remove_row_button, 0, Qt.AlignLeft)

            self.clear_button = QPushButton("Hide All Rows")
            self.clear_button.setObjectName("clearTableButton")
            self.clear_button.setFixedHeight(32)
            # Compute width from rendered text so the label is never clipped.
            metrics = QFontMetrics(self.clear_button.font())
            label_width = metrics.horizontalAdvance(self.clear_button.text())
            self.clear_button.setMinimumWidth(max(120, label_width + 28))
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

    def resizeEvent(self, event):
        """
        Keep table geometry in sync with parent/container resizes.
        This is especially important when the main window layout changes
        without explicit table updates (e.g. fullscreen and panel width changes).
        """
        super().resizeEvent(event)
        self.table.updateGeometry()
        self.table.viewport().update()

    def add_row(self, data):
        if len(data) != self.table.columnCount():
            if len(data) > self.table.columnCount():
                self.table.setColumnCount(len(data))
                headers = list(self.columns)
                while len(headers) < len(data):
                    headers.append(f"Column {len(headers) + 1}")
                self.table.setHorizontalHeaderLabels(headers)
                self.columns = headers

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
        """Apply lightweight semantic colors for recognizable status values."""
        if not item:
            return
        if not isinstance(column_index, int) or column_index < 0:
            return
        if column_index >= len(self.columns):
            return

        header = str(self.columns[column_index]).strip().lower()
        if header != "status":
            return

        text = str(item.text() or "").strip().lower()
        if "success" in text or text == "ok":
            item.setForeground(QColor(self.theme.colors.success))
            return
        if "fail" in text or "error" in text or "timeout" in text:
            item.setForeground(QColor(self.theme.colors.error))
            return
        if "progress" in text or "running" in text or "pending" in text:
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
