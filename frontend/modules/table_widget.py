"""
Simple responsive table widget for displaying data from RabbitMQ.
Adds rows dynamically as data arrives, with scrollable support.
"""
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy, QPushButton, QHBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt
from modules.styles import GreenhouseTheme


class SimpleDataTable(QWidget):
    """Simple responsive table with clear button for displaying RabbitMQ data"""
    
    ROW_HEIGHT = 35
    MAX_VISIBLE_ROWS = 15
    
    def __init__(self, columns=None, parent=None):
        """
        Initialize the simple data table
        
        Args:
            columns: List of column header names (default: Timestamp, Data)
            parent: Parent widget
        """
        super().__init__(parent)
        self.theme = GreenhouseTheme()
        
        # Set size policy to expand to fill available space
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Default columns if not provided
        if columns is None:
            columns = ['Timestamp', 'Data']
        
        self.columns = columns
        
        # Create layout - no margins so table expands to full width
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setLayout(layout)
        
        # Set widget background to make it visible
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme.colors.surface};
            }}
        """)
        
        # Create clear button container
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        self.clear_button = QPushButton("🗑️ Clear Table")
        self.clear_button.setMinimumHeight(36)
        self.clear_button.setMinimumWidth(120)
        self.clear_button.clicked.connect(self.clear_data)
        self.clear_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme.colors.error};
                color: {self.theme.colors.text_light};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 12px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: #D32F2F;
            }}
            QPushButton:pressed {{
                background-color: #B71C1C;
            }}
        """)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        button_widget.setMaximumHeight(40)
        layout.addWidget(button_widget)
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Configure table properties
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        
        # Auto-resize columns
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        # Set size policy to expand to fill available space
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set vertical resize mode
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)
        
        # Enable scrolling
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Set initial row count
        self.table.setRowCount(0)
        
        # Apply styling
        self.apply_styling()
        
        # Add table to layout with stretch factor so it expands
        layout.addWidget(self.table, 1)  # Stretch factor 1 means it takes all available space
        
        # Ensure table expands to fill available space
        self.table.setMinimumHeight(200)  # Minimum height but can grow
        self.table.setVisible(True)  # Ensure table is visible
        self.table.show()  # Explicitly show the table
        self.table.raise_()  # Bring table to front
        
        # Ensure the widget itself expands to full width - no constraints
        self.setMinimumHeight(240)  # Minimum height for widget (button + table)
        self.setVisible(True)  # Ensure widget is visible
        self.show()  # Explicitly show the widget
        self.raise_()  # Bring widget to front
        # Width will be set by parent container
    
    def apply_styling(self):
        """Apply theme-based styling to the table"""
        style = f"""
            QTableWidget {{
                background-color: {self.theme.colors.surface};
                border: 2px solid {self.theme.colors.primary};
                border-radius: 4px;
                gridline-color: {self.theme.colors.grey_200};
                font-family: {self.theme.typography.font_family};
                font-size: {self.theme.typography.body};
                color: {self.theme.colors.text_primary};
                selection-background-color: {self.theme.colors.primary_light};
                selection-color: {self.theme.colors.text_light};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
                border: none;
                border-bottom: 1px solid {self.theme.colors.grey_200};
            }}
            QTableWidget::item:selected {{
                background-color: {self.theme.colors.primary_light};
                color: {self.theme.colors.text_light};
            }}
            QTableWidget::item:hover {{
                background-color: {self.theme.colors.grey_100};
            }}
            QHeaderView::section {{
                background-color: {self.theme.colors.primary};
                color: {self.theme.colors.text_light};
                padding: 8px 12px;
                border: none;
                border-right: 1px solid {self.theme.colors.primary_dark};
                font-weight: {self.theme.typography.medium};
                font-size: {self.theme.typography.body};
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QScrollBar:vertical {{
                background-color: {self.theme.colors.grey_100};
                width: 12px;
                border: none;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {self.theme.colors.primary};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {self.theme.colors.primary_light};
            }}
            QScrollBar:horizontal {{
                background-color: {self.theme.colors.grey_100};
                height: 12px;
                border: none;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {self.theme.colors.primary};
                border-radius: 6px;
                min-width: 30px;
            }}
        """
        self.table.setStyleSheet(style)
    
    def add_row(self, data):
        """
        Add a new row to the table with the provided data
        
        Args:
            data: List of values for each column (will be converted to strings)
        """
        # Ensure data matches column count
        if len(data) != self.table.columnCount():
            # Adjust columns if needed
            if len(data) > self.table.columnCount():
                self.table.setColumnCount(len(data))
                # Update headers - keep existing or add generic names
                headers = list(self.columns)
                while len(headers) < len(data):
                    headers.append(f"Column {len(headers) + 1}")
                self.table.setHorizontalHeaderLabels(headers)
                self.columns = headers
        
        # Add new row
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, self.ROW_HEIGHT)
        
        # Set cell values
        for col, value in enumerate(data):
            item = QTableWidgetItem(str(value) if value is not None else "")
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, col, item)
        
        # Auto-scroll to bottom to show latest data
        self.table.scrollToBottom()
    
    def clear_data(self):
        """Clear all rows from the table"""
        self.table.setRowCount(0)
    
    def get_row_count(self):
        """Get current number of rows"""
        return self.table.rowCount()
    
    def showEvent(self, event):
        """Ensure table expands when shown"""
        super().showEvent(event)
        # Force update geometry to ensure proper sizing
        self.updateGeometry()
        if hasattr(self, 'table'):
            self.table.updateGeometry()
