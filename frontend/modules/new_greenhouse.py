import sys
import json
import uuid
import logging
import requests
import os
import math
import random
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QTextEdit, QLineEdit, QTabWidget,
                             QLabel, QGroupBox, QGridLayout, QMessageBox, QCheckBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
                             QListWidget, QListWidgetItem
                            )
from PyQt5.QtCore import QDateTime, Qt, QTimer
from PyQt5.QtGui import QColor

from modules.command_worker import CommandWorker
from modules.styles import GreenhouseTheme, StyleSheetGenerator
from modules.edge_fog_aggregator import EdgeToFogAggregator, SensorType, SensorReading

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('greenhouse_system.log', encoding='utf-8')
        ]
    )

class GreenhouseDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pending_commands = {}
        self.session_id = str(uuid.uuid4())
        self.current_path = "/"
        self.rabbitmq_connected = False
        self.command_worker = None
        
        # Use environment variable for backend URL with Docker fallback
        self.backend_url = os.getenv('BACKEND_URL', 'http://localhost:3000')
        
        # Initialize styling
        self.theme = GreenhouseTheme()
        self.styler = StyleSheetGenerator(self.theme)
        
        # Initialize edge-to-fog aggregator
        self.edge_aggregator = EdgeToFogAggregator()
        
        self.logger = logging.getLogger('GreenhouseDesktop')
        self.logger.info(f"Starting application with session ID: {self.session_id}")
        self.logger.info(f"Backend URL: {self.backend_url}")
        
        self.init_ui()
        self.setup_command_worker()
        self.setup_edge_aggregator()
        self.apply_styles()
        
    def setup_edge_aggregator(self):
        """Setup edge aggregator signals and demo data"""
        # Connect aggregator signals
        self.edge_aggregator.new_aggregated_data.connect(self.on_new_aggregated_data)
        self.edge_aggregator.anomaly_detected.connect(self.on_anomaly_detected)
        self.edge_aggregator.device_status_changed.connect(self.on_device_status_changed)
        
        # Register some demo edge devices
        self.register_demo_devices()
        
        # Setup demo data timer
        self.demo_data_timer = QTimer()
        self.demo_data_timer.timeout.connect(self.generate_demo_sensor_data)
        self.demo_data_timer.start(10000)  # Generate demo data every 10 seconds
        
    def register_demo_devices(self):
        """Register demo edge devices for testing"""
        demo_devices = [
            {
                'id': 'sensor_node_001',
                'type': 'Environmental Sensor Node',
                'location': 'north_wing',
                'capabilities': [SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.LIGHT_INTENSITY]
            },
            {
                'id': 'soil_sensor_001', 
                'type': 'Soil Monitoring Node',
                'location': 'herb_garden',
                'capabilities': [SensorType.SOIL_MOISTURE, SensorType.SOIL_PH, SensorType.TEMPERATURE]
            },
            {
                'id': 'climate_001',
                'type': 'Climate Control Node',
                'location': 'tropical_zone',
                'capabilities': [SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.CO2_LEVEL]
            }
        ]
        
        for device in demo_devices:
            self.edge_aggregator.register_edge_device(
                device['id'],
                device['type'],
                device['location'],
                device['capabilities']
            )
    
    def generate_demo_sensor_data(self):
        """Generate demo sensor data for testing"""
        devices = self.edge_aggregator.get_device_status()
        
        for device in devices:
            device_id = device['device_id']
            location = device['location']
            capabilities = [SensorType(cap) for cap in device['capabilities']]
            
            # Simulate occasional device offline status
            if random.random() < 0.05:  # 5% chance to go offline
                self.edge_aggregator.update_device_status(device_id, 'offline')
                continue
            else:
                self.edge_aggregator.update_device_status(device_id, 'online', random.uniform(20, 100))
            
            # Generate readings for each capability
            for sensor_type in capabilities:
                # Base values with some variation
                base_values = {
                    SensorType.TEMPERATURE: (22.0, 28.0),
                    SensorType.HUMIDITY: (45.0, 75.0),
                    SensorType.SOIL_MOISTURE: (35.0, 65.0),
                    SensorType.LIGHT_INTENSITY: (100.0, 800.0),
                    SensorType.CO2_LEVEL: (400.0, 1200.0),
                    SensorType.SOIL_PH: (6.0, 7.0)
                }
                
                base_min, base_max = base_values.get(sensor_type, (0.0, 100.0))
                value = random.uniform(base_min, base_max)
                
                # Add some realistic patterns
                current_hour = datetime.now().hour
                if sensor_type == SensorType.TEMPERATURE:
                    # Temperature follows daily pattern
                    value += 5 * math.sin(current_hour * math.pi / 12)
                elif sensor_type == SensorType.LIGHT_INTENSITY:
                    # Light intensity follows day/night cycle
                    if 6 <= current_hour <= 18:  # Daytime
                        value = random.uniform(300, 800)
                    else:  # Nighttime
                        value = random.uniform(0, 50)
                
                reading = SensorReading(
                    device_id=device_id,
                    sensor_type=sensor_type,
                    value=value,
                    timestamp=datetime.now(),
                    location=location,
                    quality=random.uniform(0.7, 1.0),
                    battery_level=random.uniform(20, 100),
                    signal_strength=random.uniform(-50, -30)
                )
                
                self.edge_aggregator.add_sensor_reading(reading)
    
    def on_new_aggregated_data(self, data):
        """Handle new aggregated data"""
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.logger.debug(f"New aggregated data: {data['sensor_type']} at {data['location']}")
        
        # Update edge monitoring tab if it exists
        if hasattr(self, 'edge_metrics_display'):
            self.update_edge_metrics_display()
    
    def on_anomaly_detected(self, anomaly):
        """Handle detected anomalies"""
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.logger.warning(f"Anomaly detected: {anomaly['message']}")
        
        # Update anomalies list
        if hasattr(self, 'anomalies_list'):
            self.update_anomalies_list()
        
        # Show notification for critical anomalies
        if anomaly['severity'] == 'critical':
            self.show_anomaly_alert(anomaly)
    
    def on_device_status_changed(self, device_info):
        """Handle device status changes"""
        self.logger.info(f"Device status changed: {device_info['device_id']} - {device_info['status']}")
        
        # Update devices table
        if hasattr(self, 'devices_table'):
            self.update_devices_table()
    
    def show_anomaly_alert(self, anomaly):
        """Show alert for critical anomalies"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("🚨 Critical Anomaly Detected")
        msg.setText(anomaly['message'])
        msg.setInformativeText(f"Location: {anomaly['location']}\nValue: {anomaly['value']:.1f}")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
    def apply_styles(self):
        """Apply modern styles to all widgets"""
        self.setStyleSheet(self.styler.generate_main_window_style())
        self.apply_widget_styles()
        
    def apply_widget_styles(self):
        """Apply styles to individual widget groups"""
        buttons = self.findChildren(QPushButton)
        for button in buttons:
            text = button.text().lower()
            if any(word in text for word in ['read', 'status', 'list', 'show', 'send']):
                button.setStyleSheet(self.styler.generate_button_style("primary"))
            elif any(word in text for word in ['clear', 'cancel', 'test']):
                button.setStyleSheet(self.styler.generate_button_style("secondary"))
            elif any(word in text for word in ['refresh', 'check', 'view']):
                button.setStyleSheet(self.styler.generate_button_style("outline"))
            else:
                button.setStyleSheet(self.styler.generate_button_style("default"))
        
        group_boxes = self.findChildren(QGroupBox)
        for group_box in group_boxes:
            group_box.setStyleSheet(self.styler.generate_group_box_style())
        
        text_edits = self.findChildren(QTextEdit)
        for text_edit in text_edits:
            text_edit.setStyleSheet(self.styler.generate_text_edit_style())
        
        line_edits = self.findChildren(QLineEdit)
        for line_edit in line_edits:
            line_edit.setStyleSheet(self.styler.generate_line_edit_style())
        
        tab_widgets = self.findChildren(QTabWidget)
        for tab_widget in tab_widgets:
            tab_widget.setStyleSheet(self.styler.generate_tab_widget_style())
        
        checkboxes = self.findChildren(QCheckBox)
        for checkbox in checkboxes:
            checkbox.setStyleSheet(self.styler.generate_checkbox_style())
        
        self.apply_label_styles()
        
    def apply_label_styles(self):
        """Apply specific styles to labels based on their content and role"""
        labels = self.findChildren(QLabel)
        for label in labels:
            text = label.text().lower()
            if any(word in text for word in ['session', 'current path']):
                label.setStyleSheet(self.styler.generate_label_style("caption"))
            elif label == self.connection_status:
                pass
            elif label == self.status_label:
                label.setStyleSheet(self.styler.generate_label_style("body"))
            else:
                label.setStyleSheet(self.styler.generate_label_style("body"))
        
    def init_ui(self):
        self.setWindowTitle("🌿 Greenhouse Automation Control System")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Session info
        session_layout = QHBoxLayout()
        session_label = QLabel("Session:")
        session_label.setStyleSheet(self.styler.generate_label_style("caption"))
        session_layout.addWidget(session_label)
        
        self.session_label = QLabel(self.session_id[:8] + "...")
        self.session_label.setStyleSheet(f"""
            font-family: {self.theme.typography.font_family_mono}; 
            color: {self.theme.colors.primary}; 
            background-color: {self.theme.colors.grey_100};
            padding: 2px 6px;
            border-radius: {self.theme.borderRadius.sm};
            font-weight: {self.theme.typography.medium};
            border: 1px solid {self.theme.colors.grey_300};
        """)
        self.session_label.setToolTip(f"Full Session ID: {self.session_id}")
        session_layout.addWidget(self.session_label)
        session_layout.addStretch()
        
        # Connection status
        self.connection_status = QLabel("Connecting to RabbitMQ...")
        self.connection_status.setStyleSheet(f"""
            color: {self.theme.colors.warning}; 
            font-weight: {self.theme.typography.medium};
            background-color: {self.theme.colors.grey_100};
            padding: 2px 6px;
            border-radius: {self.theme.borderRadius.sm};
            border: 1px solid {self.theme.colors.grey_300};
        """)
        session_layout.addWidget(self.connection_status)
        
        layout.addLayout(session_layout)
        
        # Create tabs
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        layout.addWidget(tabs)
        
        # Create all tabs
        user_tab = self.create_user_tab()
        dev_tab = self.create_developer_tab()
        edge_tab = self.create_edge_monitoring_tab()
        server_tab = self.create_server_tab()
        
        tabs.addTab(user_tab, "🏠 Control")
        tabs.addTab(dev_tab, "💻 Terminal")
        tabs.addTab(edge_tab, "📡 Edge Devices")
        tabs.addTab(server_tab, "📊 Server")
        
        # Status area
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setStyleSheet(self.styler.generate_label_style("caption"))
        status_layout.addWidget(status_label)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"""
            color: {self.theme.colors.success};
            font-weight: {self.theme.typography.medium};
            background-color: {self.theme.colors.grey_50};
            padding: 4px 8px;
            border-radius: {self.theme.borderRadius.md};
            border-left: 2px solid {self.theme.colors.success};
        """)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        layout.addLayout(status_layout)
        
    def create_user_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        control_group = QGroupBox("🌱 Greenhouse Controls")
        control_layout = QGridLayout(control_group)
        control_layout.setSpacing(6)
        control_layout.setContentsMargins(10, 16, 10, 10)
        
        buttons = [
            ("🌡️ Temperature", 0, 0),
            ("💧 Humidity", 0, 1),
            ("📊 System Status", 1, 0),
            ("📁 List Files", 1, 1),
            ("📂 Current Path", 2, 0)
        ]
        
        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, cmd="read_sensor": self.send_user_command(cmd))
            btn.setStyleSheet(self.styler.generate_button_style("primary"))
            btn.setMinimumHeight(32)
            control_layout.addWidget(btn, row, col)
        
        output_label = QLabel("Command Output:")
        output_label.setStyleSheet(self.styler.generate_label_style("subtitle"))
        
        self.user_output = QTextEdit()
        self.user_output.setReadOnly(True)
        self.user_output.setPlaceholderText("Command results will appear here...")
        self.user_output.setMinimumHeight(300)
        
        btn_clear_user = QPushButton("🗑️ Clear Output")
        btn_clear_user.clicked.connect(self.user_output.clear)
        btn_clear_user.setStyleSheet(self.styler.generate_button_style("secondary"))
        btn_clear_user.setMinimumHeight(28)
        
        layout.addWidget(control_group)
        layout.addWidget(output_label)
        layout.addWidget(self.user_output)
        layout.addWidget(btn_clear_user)
        
        return widget
        
    def create_developer_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        path_layout = QHBoxLayout()
        path_label = QLabel("Current Path:")
        path_label.setStyleSheet(self.styler.generate_label_style("caption"))
        path_layout.addWidget(path_label)
        
        self.path_label = QLabel("/")
        self.path_label.setStyleSheet(f"""
            font-family: {self.theme.typography.font_family_mono}; 
            background-color: {self.theme.colors.grey_100}; 
            padding: 4px 8px;
            border-radius: {self.theme.borderRadius.md};
            border: 1px solid {self.theme.colors.grey_300};
            color: {self.theme.colors.text_primary};
            font-weight: {self.theme.typography.medium};
        """)
        path_layout.addWidget(self.path_label)
        path_layout.addStretch()
        
        history_layout = QHBoxLayout()
        history_label = QLabel("Quick Commands:")
        history_label.setStyleSheet(self.styler.generate_label_style("subtitle"))
        history_layout.addWidget(history_label)
        
        quick_commands = [
            ("📁 ls", "ls"),
            ("📂 pwd", "pwd"),
            ("💾 df", "df -H"),
            ("🔍 ps", "ps aux")
        ]
        
        for icon_text, command in quick_commands:
            btn = QPushButton(icon_text)
            btn.clicked.connect(lambda checked, cmd=command: self.send_developer_command(cmd))
            btn.setStyleSheet(self.styler.generate_button_style("outline"))
            btn.setMinimumHeight(28)
            history_layout.addWidget(btn)
        
        history_layout.addStretch()
        
        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter shell command...")
        self.command_input.returnPressed.connect(self.send_developer_command)
        self.command_input.setMinimumHeight(30)
        
        btn_send = QPushButton("🚀 Send")
        btn_send.clicked.connect(self.send_developer_command)
        btn_send.setStyleSheet(self.styler.generate_button_style("primary"))
        btn_send.setMinimumHeight(30)
        
        btn_cancel = QPushButton("❌ Cancel")
        btn_cancel.clicked.connect(self.cancel_last_command)
        btn_cancel.setStyleSheet(self.styler.generate_button_style("secondary"))
        btn_cancel.setMinimumHeight(30)
        
        input_layout.addWidget(self.command_input)
        input_layout.addWidget(btn_send)
        input_layout.addWidget(btn_cancel)
        
        output_label = QLabel("Terminal Output:")
        output_label.setStyleSheet(self.styler.generate_label_style("subtitle"))
        
        self.dev_output = QTextEdit()
        self.dev_output.setReadOnly(True)
        self.dev_output.setPlaceholderText("Terminal output will appear here...")
        self.dev_output.setMinimumHeight(300)
        
        btn_clear_dev = QPushButton("🗑️ Clear Output")
        btn_clear_dev.clicked.connect(self.dev_output.clear)
        btn_clear_dev.setStyleSheet(self.styler.generate_button_style("secondary"))
        btn_clear_dev.setMinimumHeight(28)
        
        layout.addLayout(path_layout)
        layout.addLayout(history_layout)
        layout.addLayout(input_layout)
        layout.addWidget(output_label)
        layout.addWidget(self.dev_output)
        layout.addWidget(btn_clear_dev)
        
        return widget

    def create_edge_monitoring_tab(self):
        """Create the edge monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Edge devices status section
        devices_group = QGroupBox("📡 Edge Devices Status")
        devices_layout = QVBoxLayout(devices_group)
        
        # Devices table
        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(6)
        self.devices_table.setHorizontalHeaderLabels([
            "Device ID", "Type", "Location", "Status", "Battery", "Last Seen"
        ])
        self.devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        devices_layout.addWidget(self.devices_table)
        
        # Device control buttons
        device_buttons_layout = QHBoxLayout()
        btn_refresh_devices = QPushButton("🔄 Refresh")
        btn_refresh_devices.clicked.connect(self.update_devices_table)
        btn_refresh_devices.setStyleSheet(self.styler.generate_button_style("outline"))
        
        btn_add_device = QPushButton("➕ Add Demo Device")
        btn_add_device.clicked.connect(self.add_demo_device)
        btn_add_device.setStyleSheet(self.styler.generate_button_style("primary"))
        
        device_buttons_layout.addWidget(btn_refresh_devices)
        device_buttons_layout.addWidget(btn_add_device)
        device_buttons_layout.addStretch()
        
        devices_layout.addLayout(device_buttons_layout)
        
        # Aggregated metrics section
        metrics_group = QGroupBox("📊 Aggregated Metrics")
        metrics_layout = QVBoxLayout(metrics_group)
        
        # Metrics selector
        metrics_selector_layout = QHBoxLayout()
        metrics_selector_layout.addWidget(QLabel("Sensor Type:"))
        
        self.metrics_sensor_combo = QComboBox()
        self.metrics_sensor_combo.addItems([st.value for st in SensorType])
        self.metrics_sensor_combo.currentTextChanged.connect(self.update_edge_metrics_display)
        
        metrics_selector_layout.addWidget(self.metrics_sensor_combo)
        metrics_selector_layout.addStretch()
        
        btn_refresh_metrics = QPushButton("🔄 Refresh Metrics")
        btn_refresh_metrics.clicked.connect(self.update_edge_metrics_display)
        btn_refresh_metrics.setStyleSheet(self.styler.generate_button_style("outline"))
        metrics_selector_layout.addWidget(btn_refresh_metrics)
        
        metrics_layout.addLayout(metrics_selector_layout)
        
        # Metrics display
        self.edge_metrics_display = QTextEdit()
        self.edge_metrics_display.setReadOnly(True)
        self.edge_metrics_display.setPlaceholderText("Aggregated metrics will appear here...")
        metrics_layout.addWidget(self.edge_metrics_display)
        
        # Anomalies section
        anomalies_group = QGroupBox("🚨 Detected Anomalies")
        anomalies_layout = QVBoxLayout(anomalies_group)
        
        # Anomalies list
        self.anomalies_list = QListWidget()
        anomalies_layout.addWidget(self.anomalies_list)
        
        # Anomaly controls
        anomaly_controls_layout = QHBoxLayout()
        btn_clear_anomalies = QPushButton("🗑️ Clear Anomalies")
        btn_clear_anomalies.clicked.connect(self.clear_anomalies)
        btn_clear_anomalies.setStyleSheet(self.styler.generate_button_style("secondary"))
        
        btn_refresh_anomalies = QPushButton("🔄 Refresh")
        btn_refresh_anomalies.clicked.connect(self.update_anomalies_list)
        btn_refresh_anomalies.setStyleSheet(self.styler.generate_button_style("outline"))
        
        anomaly_controls_layout.addWidget(btn_clear_anomalies)
        anomaly_controls_layout.addWidget(btn_refresh_anomalies)
        anomaly_controls_layout.addStretch()
        
        anomalies_layout.addLayout(anomaly_controls_layout)
        
        # Add all sections to main layout
        layout.addWidget(devices_group)
        layout.addWidget(metrics_group)
        layout.addWidget(anomalies_group)
        
        # Initial updates
        self.update_devices_table()
        self.update_edge_metrics_display()
        self.update_anomalies_list()
        
        return widget

    def create_server_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        
        server_group = QGroupBox("🖥️ Server Monitoring & Management")
        server_layout = QGridLayout(server_group)
        server_layout.setSpacing(8)
        server_layout.setContentsMargins(12, 20, 12, 12)
        
        server_buttons = [
            ("❤️ Check Health", self.check_server_health),
            ("📈 View Statistics", self.view_server_stats),
            ("👥 List Sessions", self.list_sessions),
            ("🔑 List Cache Keys", self.list_cache_keys),
            ("🧹 Clear All Cache", self.clear_all_cache),
            ("📨 Check Queues", self.check_queues),
            ("⚡ Test Command", self.test_server_command),
            ("🔄 Refresh All", self.refresh_all_status),
            ("📋 List Log Files", self.list_log_files),
            ("📖 View Session Log", self.view_session_log)
        ]
        
        row, col = 0, 0
        for text, callback in server_buttons:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            if "Clear" in text:
                btn.setStyleSheet(self.styler.generate_button_style("secondary"))
            elif "Refresh" in text or "Test" in text:
                btn.setStyleSheet(self.styler.generate_button_style("outline"))
            else:
                btn.setStyleSheet(self.styler.generate_button_style("primary"))
            server_layout.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        log_selection_layout = QHBoxLayout()
        log_selection_layout.addWidget(QLabel("Session ID:"))
        self.session_log_input = QLineEdit()
        self.session_log_input.setPlaceholderText("Enter session ID to view log...")
        log_selection_layout.addWidget(self.session_log_input)
        log_selection_layout.addStretch()
        
        info_group = QGroupBox("📊 Server Information")
        info_layout = QVBoxLayout(info_group)
        
        self.server_info = QTextEdit()
        self.server_info.setReadOnly(True)
        self.server_info.setPlaceholderText("Server information will appear here...")
        
        refresh_layout = QHBoxLayout()
        self.auto_refresh = QCheckBox("🔄 Auto-refresh every 10 seconds")
        self.auto_refresh.toggled.connect(self.toggle_auto_refresh)
        refresh_layout.addWidget(self.auto_refresh)
        refresh_layout.addStretch()
        
        btn_clear_server = QPushButton("🗑️ Clear Output")
        btn_clear_server.clicked.connect(self.server_info.clear)
        refresh_layout.addWidget(btn_clear_server)
        
        info_layout.addWidget(self.server_info)
        info_layout.addLayout(refresh_layout)
        
        layout.addWidget(server_group)
        layout.addLayout(log_selection_layout)
        layout.addWidget(info_group)
        
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_all_status)
        
        return widget

    def update_devices_table(self):
        """Update the edge devices table"""
        devices = self.edge_aggregator.get_device_status()
        self.devices_table.setRowCount(len(devices))
        
        for row, device in enumerate(devices):
            self.devices_table.setItem(row, 0, QTableWidgetItem(device['device_id']))
            self.devices_table.setItem(row, 1, QTableWidgetItem(device['type']))
            self.devices_table.setItem(row, 2, QTableWidgetItem(device['location']))
            
            # Status with color coding
            status_item = QTableWidgetItem(device['status'])
            if device['status'] == 'online':
                status_item.setBackground(QColor(self.theme.colors.success))
            elif device['status'] == 'offline':
                status_item.setBackground(QColor(self.theme.colors.error))
            else:
                status_item.setBackground(QColor(self.theme.colors.warning))
            self.devices_table.setItem(row, 3, status_item)
            
            # Battery level with progress bar
            battery_item = QTableWidgetItem(f"{device['battery_level']:.1f}%")
            self.devices_table.setItem(row, 4, battery_item)
            
            self.devices_table.setItem(row, 5, QTableWidgetItem(device['last_seen']))
    
    def update_edge_metrics_display(self):
        """Update the aggregated metrics display"""
        sensor_type_str = self.metrics_sensor_combo.currentText()
        sensor_type = SensorType(sensor_type_str)
        
        metrics = self.edge_aggregator.get_aggregated_metrics(sensor_type)
        
        self.edge_metrics_display.clear()
        self.edge_metrics_display.append(f"=== Aggregated Metrics: {sensor_type_str} ===\n")
        
        for location, sensor_data in metrics.items():
            if sensor_type_str in sensor_data:
                self.edge_metrics_display.append(f"📍 Location: {location}")
                
                for timeframe, data in sensor_data[sensor_type_str].items():
                    self.edge_metrics_display.append(
                        f"  {timeframe}: {data['average']:.2f} "
                        f"(min: {data['min']:.2f}, max: {data['max']:.2f}) "
                        f"[{data['count']} samples, quality: {data['quality_score']:.2f}]"
                    )
                
                self.edge_metrics_display.append("")
        
        if not metrics:
            self.edge_metrics_display.append("No data available for selected sensor type.")
    
    def update_anomalies_list(self):
        """Update the anomalies list"""
        anomalies = self.edge_aggregator.get_recent_anomalies(20)
        self.anomalies_list.clear()
        
        for anomaly in anomalies:
            item_text = f"[{anomaly['timestamp'][11:19]}] {anomaly['severity'].upper()}: {anomaly['message']}"
            item = QListWidgetItem(item_text)
            
            # Color code by severity
            if anomaly['severity'] == 'critical':
                item.setBackground(QColor(self.theme.colors.error))
            elif anomaly['severity'] == 'warning':
                item.setBackground(QColor(self.theme.colors.warning))
            elif anomaly['severity'] == 'info':
                item.setBackground(QColor(self.theme.colors.info))
            
            self.anomalies_list.addItem(item)
    
    def clear_anomalies(self):
        """Clear all anomalies"""
        # This would clear the display, but keep the aggregator's internal list
        self.anomalies_list.clear()
    
    def add_demo_device(self):
        """Add a new demo edge device"""
        device_id = f"demo_sensor_{uuid.uuid4().hex[:8]}"
        locations = ['north_wing', 'south_wing', 'herb_garden', 'tropical_zone', 'seedling_area']
        sensor_types = list(SensorType)
        
        location = random.choice(locations)
        capabilities = random.sample(sensor_types, random.randint(1, 3))
        
        self.edge_aggregator.register_edge_device(
            device_id,
            "Demo Sensor Node",
            location,
            capabilities
        )
        
        self.update_devices_table()
        self.logger.info(f"Added demo device: {device_id} at {location}")

    def list_log_files(self):
        """List all session log files"""
        result = self.make_server_request('/logs')
        if result:
            self.display_formatted_json("Session Log Files", result)

    def view_session_log(self):
        """View specific session log"""
        session_id = self.session_log_input.text().strip()
        if not session_id:
            self.show_error("Session ID Required", "Please enter a session ID")
            return
        
        result = self.make_server_request(f'/sessions/{session_id}/log')
        if result:
            self.server_info.append(f"=== Session Log: {result.get('sessionId', 'Unknown')} ===\n")
            self.server_info.append(f"Session Number: {result.get('sessionNumber', 'Unknown')}\n")
            self.server_info.append(f"Log File: {result.get('logFile', 'Unknown')}\n")
            self.server_info.append("=" * 50 + "\n")
            self.server_info.append(result.get('content', 'No log content available'))
            self.server_info.append("\n" + "=" * 50 + "\n")
        
    def toggle_auto_refresh(self, enabled):
        if enabled:
            self.auto_refresh_timer.start(10000)  # 10 seconds
            self.server_info.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] Auto-refresh enabled")
        else:
            self.auto_refresh_timer.stop()
            self.server_info.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] Auto-refresh disabled")
        
    def refresh_all_status(self):
        """Refresh all server status information"""
        self.check_server_health()
        self.view_server_stats()
        self.list_sessions()
        
    def make_server_request(self, endpoint, method='GET', data=None):
        """Make HTTP request to backend server"""
        try:
            url = f"{self.backend_url}{endpoint}"
            self.server_info.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] {method} {endpoint}")
            
            if method == 'GET':
                response = requests.get(url, timeout=5)
            elif method == 'DELETE':
                response = requests.delete(url, timeout=5)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=5)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == 200:
                return response.json()
            else:
                self.server_info.append(f"Error: {response.status_code} - {response.text}\n")
                return None
                
        except requests.exceptions.ConnectionError:
            self.server_info.append(f"Error: Cannot connect to backend server at {self.backend_url}. Make sure it's running.\n")
            return None
        except requests.exceptions.Timeout:
            self.server_info.append("Error: Request timeout - server is not responding\n")
            return None
        except Exception as e:
            self.server_info.append(f"Error: {str(e)}\n")
            return None
        
    def check_server_health(self):
        """Check server health status"""
        result = self.make_server_request('/health')
        if result:
            self.display_formatted_json("Server Health", result)
        
    def view_server_stats(self):
        """View server statistics"""
        result = self.make_server_request('/stats')
        if result:
            self.display_formatted_json("Server Statistics", result)
        
    def list_sessions(self):
        """List active sessions"""
        result = self.make_server_request('/sessions')
        if result:
            self.display_formatted_json("Active Sessions", result)
        
    def list_cache_keys(self):
        """List cache keys"""
        result = self.make_server_request('/cache/keys')
        if result:
            self.display_formatted_json("Cache Keys", result)
        
    def clear_all_cache(self):
        """Clear all cache"""
        reply = QMessageBox.question(self, 'Clear Cache', 
                                   'Are you sure you want to clear ALL cache?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            result = self.make_server_request('/cache/clear', method='DELETE')
            if result:
                self.display_formatted_json("Cache Clear Result", result)
        
    def check_queues(self):
        """Check RabbitMQ queue status"""
        result = self.make_server_request('/queues')
        if result:
            self.display_formatted_json("Queue Status", result)
        
    def test_server_command(self):
        """Test server command execution"""
        command_data = {
            "command": "read_sensor",
            "parameters": {}
        }
        result = self.make_server_request('/command', method='POST', data=command_data)
        if result:
            self.display_formatted_json("Test Command Result", result)
        
    def display_formatted_json(self, title, data):
        """Display formatted JSON in server info panel"""
        self.server_info.append(f"=== {title} ===")
        self.server_info.append(json.dumps(data, indent=2))
        self.server_info.append("=" * 50 + "\n")
        
    def setup_command_worker(self):
        self.logger.info("Setting up command worker")
        self.command_worker = CommandWorker()
        self.command_worker.response_received.connect(self.handle_response)
        self.command_worker.connection_status.connect(self.update_connection_status)
        self.command_worker.error_occurred.connect(self.handle_error)
        
        # Initial connection
        self.command_worker.setup_rabbitmq()
        
        # Setup connection check timer
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_connection)
        self.connection_timer.start(10000)
        
    def update_connection_status(self, connected):
        self.rabbitmq_connected = connected
        if connected:
            self.connection_status.setText("✅ Connected to RabbitMQ")
            self.connection_status.setStyleSheet(f"""
                color: {self.theme.colors.success}; 
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_100};
                padding: 2px 6px;
                border-radius: {self.theme.borderRadius.sm};
                border: 1px solid {self.theme.colors.grey_300};
                border-left: 2px solid {self.theme.colors.success};
            """)
        else:
            self.connection_status.setText("❌ Disconnected from RabbitMQ")
            self.connection_status.setStyleSheet(f"""
                color: {self.theme.colors.error}; 
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_100};
                padding: 2px 6px;
                border-radius: {self.theme.borderRadius.sm};
                border: 1px solid {self.theme.colors.grey_300};
                border-left: 2px solid {self.theme.colors.error};
            """)
        
    def check_connection(self):
        if not self.rabbitmq_connected:
            self.logger.info("Attempting to reconnect to RabbitMQ...")
            self.command_worker.setup_rabbitmq()
        
    def send_user_command(self, command, parameters=None):
        """Send a user command with automatic retry"""
        command_id = str(uuid.uuid4())
        command_data = {
            'commandId': command_id,
            'command': command,
            'type': 'user',
            'parameters': parameters or {},
            'sessionId': self.session_id
        }
        
        self.pending_commands[command_id] = {
            "type": "user",
            "command": command,
            "parameters": parameters or {}
        }
        
        self.logger.info(f"Sending user command {command_id}: {command}")
        
        import time
        time.sleep(0.1)
        
        if self.command_worker.send_command(command_data):
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.user_output.append(f"[{timestamp}] Sent: {command}")
            return True
        else:
            self.logger.warning("First send attempt failed, attempting reconnect...")
            if self.command_worker.attempt_reconnect():
                time.sleep(0.1)
                if self.command_worker.send_command(command_data):
                    self.logger.info("Command sent successfully after reconnect")
                    timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                    self.user_output.append(f"[{timestamp}] Sent: {command} [after reconnect]")
                    return True
            
            self.logger.error("Failed to send command after retry")
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.user_output.append(f"[{timestamp}] Failed to send: {command}")
            return False
        
    def send_developer_command(self, command_text=None):
        if command_text is None:
            command_text = self.command_input.text().strip()
            
        if not command_text:
            return
            
        if not self.rabbitmq_connected:
            self.show_error("Not connected to RabbitMQ", "Please check if RabbitMQ server is running")
            return
            
        if hasattr(self, 'command_input') and self.command_input.text().strip() == command_text:
            self.command_input.clear()
        
        if command_text.startswith('cd '):
            path = command_text[3:].strip()
            command = "change_directory"
            parameters = {"path": path}
        else:
            command = "execute_raw"
            parameters = {"raw_command": command_text}
        
        command_id = str(uuid.uuid4())
        command_data = {
            "commandId": command_id,
            "command": command,
            "type": "developer",
            "parameters": parameters,
            "sessionId": self.session_id,
            "raw_command": command_text,
            "timestamp": QDateTime.currentDateTime().toString(Qt.ISODate)
        }
        
        self.pending_commands[command_id] = {
            "type": "developer",
            "command": command_text,
            "raw_command": command_text
        }
        
        success = self.command_worker.send_command(command_data)
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        if success:
            self.dev_output.append(f"[{timestamp}] $ {command_text}")
            self.status_label.setText(f"Sent: {command_text}")
            self.logger.info(f"Developer command {command_id} sent: {command_text}")
        else:
            self.dev_output.append(f"[{timestamp}] $ {command_text} [FAILED TO SEND]")
            self.status_label.setText(f"Failed to send: {command_text}")
            self.logger.error(f"Failed to send developer command {command_id}: {command_text}")
        
    def cancel_last_command(self):
        if self.pending_commands:
            last_id = list(self.pending_commands.keys())[-1]
            last_command = self.pending_commands[last_id]
            del self.pending_commands[last_id]
            self.status_label.setText(f"Cancelled: {last_command.get('command', 'last command')}")
            self.dev_output.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] Command cancelled: {last_command.get('command', 'last command')}")
            self.logger.info(f"Cancelled command: {last_command.get('command', 'last command')}")
            
    def handle_response(self, response):
        command_id = response.get('commandId')
        result = response.get('result', {})
        cached = response.get('cached', False)
        error = response.get('error')
        session_id = response.get('sessionId')
        current_path = response.get('currentPath')
        
        self.logger.info(f"Received response for command {command_id}, cached: {cached}, error: {bool(error)}")
        
        # DEBUG: Log pending commands
        self.logger.info(f"Pending commands: {list(self.pending_commands.keys())}")
        
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        
        if command_id in self.pending_commands:
            command_info = self.pending_commands[command_id]
            self.logger.info(f"Found command info: type={command_info.get('type')}, command={command_info.get('command')}")
            
            # Update current path if provided
            if current_path:
                self.current_path = current_path
                self.path_label.setText(self.current_path)
                self.logger.info(f"Current path updated to: {self.current_path}")
            
            if error:
                output_text = f"ERROR: {error}"
                self.logger.error(f"Command {command_id} failed: {error}")
            else:
                if isinstance(result, dict):
                    if 'output' in result:
                        output_text = result['output']
                    elif 'newPath' in result:
                        output_text = result['output'] if 'output' in result else f"Changed to: {result['newPath']}"
                    else:
                        output_text = json.dumps(result, indent=2)
                else:
                    output_text = str(result)
            
            cache_indicator = " [CACHED]" if cached else ""
            session_indicator = f" [Session: {session_id[:8]}...]" if session_id else ""
            
            if command_info['type'] == 'user':
                self.logger.info(f"Appending to USER output: {output_text[:100]}...")
                self.user_output.append(f"[{timestamp}] Result{cache_indicator}{session_indicator}:\n{output_text}\n{'-'*50}")
            else:
                self.logger.info(f"Appending to DEV output: {output_text[:100]}...")
                self.dev_output.append(f"[{timestamp}] Result{cache_indicator}{session_indicator}:\n{output_text}\n{'-'*50}")
                
            del self.pending_commands[command_id]
            
        else:
            self.logger.warning(f"Command ID {command_id} not found in pending_commands!")
            # Fallback: try to display anyway
            if error:
                output_text = f"ERROR: {error}"
            else:
                output_text = str(result)
            
            self.user_output.append(f"[{timestamp}] [UNKNOWN COMMAND] Result:\n{output_text}\n{'-'*50}")
            
        status_suffix = " (cached)" if cached else ""
        if error:
            self.status_label.setText(f"❌ Command failed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.error};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 6px 12px;
                border-radius: {self.theme.borderRadius.md};
                border-left: 3px solid {self.theme.colors.error};
            """)
        else:
            self.status_label.setText(f"✅ Command completed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.success};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 6px 12px;
                border-radius: {self.theme.borderRadius.md};
                border-left: 3px solid {self.theme.colors.success};
            """)

    def handle_error(self, error_message):
        self.logger.error(f"Command worker error: {error_message}")
        self.show_error("System Error", error_message)

    def show_error(self, title, message):
        self.logger.warning(f"Showing error dialog: {title} - {message}")
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec_()

    def closeEvent(self, event):
        self.logger.info("Application shutting down")
        if self.command_worker:
            self.command_worker.disconnect()
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
        if self.demo_data_timer.isActive():
            self.demo_data_timer.stop()
        event.accept()


if __name__ == "__main__":
    setup_logging()
    app = QApplication(sys.argv)
    window = GreenhouseDesktop()
    window.show()
    sys.exit(app.exec_())