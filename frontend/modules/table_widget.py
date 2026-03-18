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
    MIN_TABLE_HEIGHT = 320

    def __init__(self, columns=None, parent=None, show_clear_button=False):
        super().__init__(parent)
        self.theme = GreenhouseTheme()
        self.columns = columns or ['Timestamp', 'Data']

        self.setObjectName("simpleDataTable")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(self.MIN_TABLE_HEIGHT + (44 if show_clear_button else 0))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if show_clear_button:
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.addStretch()
            self.clear_button = QPushButton("🗑️ Clear Table")
            self.clear_button.setObjectName("clearTableButton")
            self.clear_button.setFixedHeight(32)
            self.clear_button.setMinimumWidth(100)
            self.clear_button.clicked.connect(self.clear_data)
            btn_row.addWidget(self.clear_button)
            layout.addLayout(btn_row)
        else:
            self.clear_button = None

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
        self.table.setMinimumHeight(self.MIN_TABLE_HEIGHT)
        self.table.setMinimumWidth(400)
        layout.addWidget(self.table, 1)

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
            self.table.setItem(row, col, item)
        self.table.scrollToBottom()

    def clear_data(self):
        self.table.setRowCount(0)

    def get_row_count(self):
        return self.table.rowCount()
