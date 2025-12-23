import sys
import uuid
import logging
import requests
import os
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QTextEdit, QLineEdit, QTabWidget,
                             QLabel, QGroupBox, QGridLayout, QMessageBox, QCheckBox,
                             QScrollArea, QSizePolicy,
                            )
from PyQt5.QtCore import QDateTime, Qt, QTimer, QEvent
from PyQt5 import uic

from modules.command_worker import CommandWorker
from modules.styles import GreenhouseTheme, StyleSheetGenerator
from modules.edge_fog_aggregator import EdgeToFogAggregator, SensorReading, SensorType
from modules.redis_client import RedisEdgeClient
from modules.table_widget import SimpleDataTable
from modules import table_renderers
from modules.json_prettifier import extract_payload, build_user_friendly_rows
from PyQt5.QtWidgets import QDialog, QVBoxLayout

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
        self.rabbitmq_connected = False
        self.command_worker = None
        # History for detailed views
        self.control_history = []  # One entry per control_table row
        self.server_history = []   # One entry per server_table row
        
        # Import config after it's initialized
        from modules.config import config
        self.backend_url = config.BACKEND_URL
        
        # Initialize Edge-to-Fog aggregator
        self.edge_aggregator = EdgeToFogAggregator()
        self.redis_edge_client = RedisEdgeClient()
        
        # Initialize styling
        self.theme = GreenhouseTheme()
        self.styler = StyleSheetGenerator(self.theme)
        
        self.logger = logging.getLogger('GreenhouseDesktop')
        self.logger.info(f"Starting application with session ID: {self.session_id}")
        self.logger.info(f"Backend URL: {self.backend_url}")
        
        # Load UI from .ui file
        self.setupUI()
        
        # Setup functionality and signal connections
        self.add_functions()
        
        # No need to connect tab change - layout handles sizing
        
        # Setup command worker
        self.setup_command_worker()
        
        # Setup edge-to-fog aggregator
        self.setup_edge_aggregator()
        
        # Apply custom styles (UI file already has styles, but we can override if needed)
        self.apply_styles()
        
    def setupUI(self):
        """Load UI from .ui file in frontend directory"""
        # UI file is always in the frontend directory (same level as modules/)
        # From frontend/modules/greenhouse.py -> frontend/front.ui
        frontend_dir = os.path.dirname(os.path.dirname(__file__))
        ui_path = os.path.join(frontend_dir, 'front.ui')
        
        if not os.path.exists(ui_path):
            error_msg = f"UI file not found at: {ui_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        self.logger.info(f"Loading UI from: {ui_path}")
        uic.loadUi(ui_path, self)
        
        # Update session label with actual session ID
        self.session_label.setText(self.session_id[:8] + "...")
        self.session_label.setToolTip(f"Full Session ID: {self.session_id}")
        
        # Path label removed (no longer needed without shell commands)
        # self.path_label.setText(self.current_path)
        
        # Initialize auto-refresh timer
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_all_status)
        
        # Initialize table management before setting up tables
        self.control_table = None  # Simple table for control tab - adds rows from RabbitMQ
        self.server_table = None  # Simple table for server tab - adds rows from button clicks
        
        # Ensure layouts are properly set up
        self._ensure_layouts_initialized()
        
        # Force find containers if they weren't found
        self._find_containers()
        
        # Setup tables after UI is loaded
        self.setup_tables()
        
        # Layout handles sizing automatically - no manual updates needed
        
    def add_functions(self):
        """Setup signal connections and functionality"""
        # User Tab - Sensor reading buttons
        self.tempButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "temperature"}))
        self.humidityButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "humidity"}))
        self.lightButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "light"}))
        self.co2Button.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "co2"}))
        self.soilMoistureButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "soil_moisture"}))
        self.soilPHButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "soil_ph"}))
        
        # User Tab - Device control buttons
        self.waterCanalButton.clicked.connect(lambda: self.send_user_command("switch_water_canal", {"action": "toggle"}))
        self.fanButton.clicked.connect(lambda: self.send_user_command("switch_fan", {"fanId": "fan_1", "action": "toggle"}))
        self.heaterButton.clicked.connect(lambda: self.send_user_command("switch_heater", {"heaterId": "heater_1", "action": "toggle"}))
        self.actuatorButton.clicked.connect(lambda: self.send_user_command("switch_actuator", {"actuatorId": "actuator_1", "action": "toggle"}))
        
        # User Tab - Clear button removed (using table only)
        
        # Legacy buttons (kept for backward compatibility, can be removed if not needed)
        if hasattr(self, 'statusButton'):
            self.statusButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "temperature"}))
        if hasattr(self, 'pathButton'):
            # Remove or repurpose this button
            pass
        
        # Server Tab - Server management buttons
        self.healthButton.clicked.connect(self.check_server_health)
        self.statsButton.clicked.connect(self.view_server_stats)
        self.sessionsButton.clicked.connect(self.list_sessions)
        self.cacheKeysButton.clicked.connect(self.list_cache_keys)
        self.clearCacheButton.clicked.connect(self.clear_all_cache)
        self.queuesButton.clicked.connect(self.check_queues)
        self.testCommandButton.clicked.connect(self.test_server_command)
        self.refreshButton.clicked.connect(self.refresh_all_status)
        self.logFilesButton.clicked.connect(self.list_log_files)
        self.viewLogButton.clicked.connect(self.view_session_log)
        
        # Fog Data buttons (if they exist in UI, otherwise will be added dynamically)
        if hasattr(self, 'fogAggregatedButton'):
            self.fogAggregatedButton.clicked.connect(self.view_fog_aggregated_data)
        if hasattr(self, 'fogDevicesButton'):
            self.fogDevicesButton.clicked.connect(self.view_fog_devices)
        if hasattr(self, 'fogAnomaliesButton'):
            self.fogAnomaliesButton.clicked.connect(self.view_fog_anomalies)
        
        # Server Tab - Auto-refresh checkbox (if exists in UI)
        if hasattr(self, 'auto_refresh'):
            self.auto_refresh.toggled.connect(self.toggle_auto_refresh)
        
        # Server Tab - Clear button removed (using table only)
        
    def apply_styles(self):
        """Apply custom styles if needed (UI file already has styles)"""
        # The UI file already contains styles, but we can override specific widgets if needed
        # For example, update connection status and status label styles dynamically
        pass
    
    def _find_containers(self):
        """Find containers from UI"""
        # Containers are loaded from UI file, just ensure server_info_container is set
        if hasattr(self, 'server_info_scroll') and self.server_info_scroll:
            container = self.server_info_scroll.widget()
            if container:
                self.server_info_container = container
                self.logger.info("Found server_info_container")
        else:
            self.logger.warning("server_info_scroll not found in UI")
        
        # Ensure user_output_container exists
        if not hasattr(self, 'user_output_container') or not self.user_output_container:
            self.logger.error("user_output_container not found in UI!")
    
    def _ensure_layouts_initialized(self):
        """Ensure all layouts are properly initialized after UI load"""
        if hasattr(self, 'user_output_container') and self.user_output_container:
            if not self.user_output_container.layout():
                layout = QVBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                self.user_output_container.setLayout(layout)
            # Ensure it's visible
            self.user_output_container.setVisible(True)
        else:
            self.logger.error("user_output_container not available for layout initialization")
        
        if hasattr(self, 'server_info_container') and self.server_info_container:
            if not self.server_info_container.layout():
                layout = QVBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                self.server_info_container.setLayout(layout)
            # Ensure it's visible
            self.server_info_container.setVisible(True)
        else:
            self.logger.warning("server_info_container not available for layout initialization")
    
    def setup_tables(self):
        """Initialize simple table widgets for displaying RabbitMQ data"""
        # Setup control table for command results from RabbitMQ
        if not hasattr(self, 'user_output_container') or not self.user_output_container:
            self.logger.error("Cannot setup control table - user_output_container not found")
            return
        
        layout = self.user_output_container.layout()
        if not layout:
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.user_output_container.setLayout(layout)
        
        # Ensure container expands and is visible - override UI file minimum size
        self.user_output_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.user_output_container.setMinimumSize(1200, 300)  # Minimum width 1200px, height 300px
        self.user_output_container.setVisible(True)
        self.user_output_container.show()
        self.user_output_container.raise_()  # Bring to front
        
        # Create simple table with clear button
        self.control_table = SimpleDataTable(
            columns=['Timestamp', 'Command', 'Status', 'Result'],
            parent=self.user_output_container
        )
        self.control_table.setVisible(True)
        self.control_table.show()
        self.control_table.raise_()  # Bring to front
        self.control_table.setMinimumSize(1200, 250)  # Minimum width 1200px, height 250px
        layout.addWidget(self.control_table, 1)  # Stretch factor 1
        # Double-click on a control row opens detailed view
        self.control_table.table.cellDoubleClicked.connect(self.show_control_details)
        
        # Layout will handle sizing naturally
        self.logger.info(f"Control table created: visible={self.control_table.isVisible()}")
        
        # Setup server info table
        if not hasattr(self, 'server_info_container') or not self.server_info_container:
            self.logger.error("Cannot setup server table - server_info_container not found")
            return
        
        layout = self.server_info_container.layout()
        if not layout:
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.server_info_container.setLayout(layout)
        
        # Ensure container expands and is visible - override UI file minimum size
        self.server_info_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.server_info_container.setMinimumSize(1200, 300)  # Minimum width 1200px, height 300px
        self.server_info_container.setVisible(True)
        self.server_info_container.show()
        self.server_info_container.raise_()  # Bring to front
        
        # Create simple table with clear button
        self.server_table = SimpleDataTable(
            columns=['Timestamp', 'Type', 'Data'],
            parent=self.server_info_container
        )
        self.server_table.setVisible(True)
        self.server_table.show()
        self.server_table.raise_()  # Bring to front
        self.server_table.setMinimumSize(1200, 250)  # Minimum width 1200px, height 250px
        layout.addWidget(self.server_table, 1)  # Stretch factor 1
        # Double-click on a server row opens detailed view
        self.server_table.table.cellDoubleClicked.connect(self.show_server_details)
        
        # Layout will handle sizing naturally
        self.logger.info(f"Server table created: visible={self.server_table.isVisible()}")
        
        # Set stretch factors for tab layouts - tables should fill space between buttons and status
        for i in range(self.userTabLayout.count()):
            item = self.userTabLayout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget_name = widget.objectName()
                if widget_name == 'controlGroup':
                    self.userTabLayout.setStretch(i, 0)  # Buttons take minimal space
                elif widget_name == 'user_output_container':
                    self.userTabLayout.setStretch(i, 1)  # Table takes all remaining space
        
        for i in range(self.serverTabLayout.count()):
            item = self.serverTabLayout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget_name = widget.objectName()
                if widget_name == 'serverGroup':
                    self.serverTabLayout.setStretch(i, 0)  # Buttons take minimal space
                elif widget_name == 'infoGroup':
                    self.serverTabLayout.setStretch(i, 1)  # Table takes all remaining space
    
    def display_data_table(self, title, data, data_type):
        """
        Display data in table using specialized renderers for each data type.
        
        Args:
            title: Display title/type
            data: Data to display (dict or list)
            data_type: Type identifier (for logging)
        """
        if not self.server_table:
            self.logger.warning("Server table not initialized, cannot display data")
            return
        
        try:
            # Store full response for detailed view
            self.server_history.append(
                {
                    "title": title,
                    "data": data,
                    "data_type": data_type,
                }
            )

            # Compute a short, user-friendly status summary for the main server table
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            status = "✅ OK"
            if isinstance(data, dict) and data.get("error"):
                status = f"❌ Error: {data.get('error')}"

            # Append a compact summary row; detailed view is available on double-click
            self.server_table.add_row([timestamp, title, status])

            self.logger.info(f"Added server summary row for '{title}' ({data_type})")

        except Exception as e:
            self.logger.error(f"Error displaying data table: {e}", exc_info=True)
    
    def clear_server_tables(self):
        """Clear server info table"""
        if self.server_table:
            self.server_table.clear_data()
        self.server_history = []
    
    def clear_control_table(self):
        """Clear control tab command results table"""
        if self.control_table:
            self.control_table.clear_data()
        self.control_history = []

    def show_control_details(self, row, column):
        """Open a detailed table view for a selected control-table row."""
        if row < 0 or row >= len(self.control_history):
            self.logger.warning(f"Control details requested for invalid row {row}")
            return

        entry = self.control_history[row]
        response = entry.get("response", {})
        timestamp = entry.get("timestamp", "")
        command_name = entry.get("command", "unknown")
        cached = bool(entry.get("cached", False))

        try:
            # For double-click, focus specifically on the "result" JSON payload
            # and present it as simple key/value rows for easy reading.
            if isinstance(response, dict) and "result" in response:
                payload = response.get("result")
            else:
                payload = extract_payload(response)

            # We don't pass summary_text here so all payload fields are shown.
            columns, rows = build_user_friendly_rows(payload, summary_text="")

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Command Result Details - {command_name}")
            dialog.setMinimumSize(800, 400)

            layout = QVBoxLayout(dialog)
            details_table = SimpleDataTable(columns=columns, parent=dialog)
            layout.addWidget(details_table)

            for r in rows:
                details_table.add_row(r)

            dialog.setLayout(layout)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"Error showing control details dialog: {e}", exc_info=True)

    def show_server_details(self, row, column):
        """Open a detailed table view for a selected server-table row."""
        if row < 0 or row >= len(self.server_history):
            self.logger.warning(f"Server details requested for invalid row {row}")
            return

        entry = self.server_history[row]
        title = entry.get("title", "Server Data")
        data = entry.get("data", {})
        data_type = entry.get("data_type", "generic")

        try:
            # Choose appropriate renderer based on data_type
            if data_type == 'health':
                columns, rows = table_renderers.render_health_data(data)
            elif data_type == 'stats':
                columns, rows = table_renderers.render_stats_data(data)
            elif data_type == 'sessions':
                columns, rows = table_renderers.render_sessions_data(data)
            elif data_type == 'cache_keys':
                columns, rows = table_renderers.render_cache_keys_data(data)
            elif data_type == 'queues':
                columns, rows = table_renderers.render_queues_data(data)
            elif data_type == 'logs':
                columns, rows = table_renderers.render_logs_data(data)
            elif data_type == 'session_log':
                columns, rows = table_renderers.render_session_log_data(data)
            elif data_type == 'fog_aggregated':
                columns, rows = table_renderers.render_fog_aggregated_data(data)
            elif data_type == 'fog_devices':
                columns, rows = table_renderers.render_fog_devices_data(data)
            elif data_type == 'fog_anomalies':
                columns, rows = table_renderers.render_fog_anomalies_data(data)
            elif data_type == 'command_result':
                # Use the generic command result renderer
                timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                cached = bool(data.get('cached', False)) if isinstance(data, dict) else False
                columns, rows = table_renderers.render_command_result_data(
                    data if isinstance(data, dict) else {'result': data},
                    command=title,
                    timestamp=timestamp,
                    cached=cached,
                )
            else:
                # Fallback to generic renderer
                columns, rows = table_renderers.render_generic_data(data)

            dialog = QDialog(self)
            dialog.setWindowTitle(f"{title} - Details")
            dialog.setMinimumSize(800, 400)

            layout = QVBoxLayout(dialog)
            details_table = SimpleDataTable(columns=columns, parent=dialog)
            layout.addWidget(details_table)

            for r in rows:
                details_table.add_row(r)

            dialog.setLayout(layout)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"Error showing server details dialog: {e}", exc_info=True)

    def list_log_files(self):
        """List all session log files"""
        result = self.make_server_request('/logs')
        if result:
            self.display_data_table("Session Log Files", result, 'logs')

    def view_session_log(self):
        """View specific session log"""
        # Session log input removed - can be added back as a dialog if needed
        # For now, use the current session ID
        session_id = self.session_id
        
        result = self.make_server_request(f'/sessions/{session_id}/log')
        if result:
            # Use session log renderer
            self.display_data_table(f"Session Log: {result.get('sessionId', 'Unknown')}", result, 'session_log')
        
    def toggle_auto_refresh(self, enabled):
        if enabled:
            self.auto_refresh_timer.start(10000)  # 10 seconds
            self.logger.info("Auto-refresh enabled")
        else:
            self.auto_refresh_timer.stop()
            self.logger.info("Auto-refresh disabled")
        
    def refresh_all_status(self):
        """Refresh all server status information"""
        self.check_server_health()
        self.view_server_stats()
        self.list_sessions()
        
    def make_server_request(self, endpoint, method='GET', data=None):
        """Make HTTP request to backend server"""
        try:
            url = f"{self.backend_url}{endpoint}"
            self.logger.info(f"{method} {endpoint}")
            
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
                self.logger.error(f"Error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Cannot connect to backend server at {self.backend_url}. Make sure it's running.")
            return None
        except requests.exceptions.Timeout:
            self.logger.error("Request timeout - server is not responding")
            return None
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            return None
        
    def check_server_health(self):
        """Check server health status"""
        result = self.make_server_request('/health')
        if result:
            self.display_data_table("Server Health", result, 'health')
        
    def view_server_stats(self):
        """View server statistics"""
        result = self.make_server_request('/stats')
        if result:
            self.display_data_table("Server Statistics", result, 'stats')
        
    def list_sessions(self):
        """List active sessions"""
        result = self.make_server_request('/sessions')
        if result:
            self.display_data_table("Active Sessions", result, 'sessions')
        
    def list_cache_keys(self):
        """List cache keys"""
        result = self.make_server_request('/cache/keys')
        if result:
            self.display_data_table("Cache Keys", result, 'cache_keys')
        
    def clear_all_cache(self):
        """Clear all cache"""
        reply = QMessageBox.question(self, 'Clear Cache', 
                                   'Are you sure you want to clear ALL cache?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            result = self.make_server_request('/cache/clear', method='DELETE')
            if result:
                self.display_data_table("Cache Clear Result", result, 'cache_clear')
        
    def check_queues(self):
        """Check RabbitMQ queue status"""
        result = self.make_server_request('/queues')
        if result:
            self.display_data_table("Queue Status", result, 'queues')
        
    def test_server_command(self):
        """Test server command execution"""
        command_data = {
            "command": "read_sensor",
            "parameters": {}
        }
        result = self.make_server_request('/command', method='POST', data=command_data)
        if result:
            self.display_data_table("Test Command Result", result, 'command_result')
        
        
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
    
    def setup_edge_aggregator(self):
        """Setup Edge-to-Fog aggregator and connect signals"""
        self.logger.info("Setting up Edge-to-Fog aggregator")
        
        # Connect aggregator signals to UI handlers
        self.edge_aggregator.new_aggregated_data.connect(self.handle_aggregated_data)
        self.edge_aggregator.anomaly_detected.connect(self.handle_anomaly)
        self.edge_aggregator.device_status_changed.connect(self.handle_device_status)
        
        # Connect to Redis for local caching
        self.redis_edge_client.connect()
        
        # Setup sensor data consumer (if RabbitMQ is available)
        # For now, we'll simulate sensor data or receive from RabbitMQ
        self.setup_sensor_data_consumer()
        
        # Register some example edge devices (in real scenario, these would come from discovery)
        self.register_example_devices()
        
        self.logger.info("Edge-to-Fog aggregator setup complete")
    
    def setup_sensor_data_consumer(self):
        """Setup consumer for sensor data from RabbitMQ or simulate it"""
        # For now, we'll use a timer to simulate sensor readings
        # In production, this would consume from a RabbitMQ queue
        self.sensor_simulator_timer = QTimer()
        self.sensor_simulator_timer.timeout.connect(self.simulate_sensor_reading)
        self.sensor_simulator_timer.start(5000)  # Every 5 seconds
        
        self.logger.info("Sensor data consumer started (simulation mode)")
    
    def simulate_sensor_reading(self):
        """Simulate sensor readings for testing"""
        from datetime import datetime
        import random
        
        # Simulate readings from different locations
        locations = ["Zone_A", "Zone_B", "Zone_C"]
        devices = ["device_001", "device_002", "device_003"]
        
        for i, (location, device_id) in enumerate(zip(locations, devices)):
            # Temperature
            temp_reading = SensorReading(
                device_id=device_id,
                sensor_type=SensorType.TEMPERATURE,
                value=20.0 + random.uniform(-5, 10),
                timestamp=datetime.now(),
                location=location,
                quality=random.uniform(0.8, 1.0),
                battery_level=random.uniform(80, 100),
                signal_strength=random.uniform(70, 100)
            )
            self.edge_aggregator.add_sensor_reading(temp_reading)
            
            # Humidity
            humidity_reading = SensorReading(
                device_id=device_id,
                sensor_type=SensorType.HUMIDITY,
                value=50.0 + random.uniform(-10, 20),
                timestamp=datetime.now(),
                location=location,
                quality=random.uniform(0.8, 1.0),
                battery_level=random.uniform(80, 100),
                signal_strength=random.uniform(70, 100)
            )
            self.edge_aggregator.add_sensor_reading(humidity_reading)
    
    def register_example_devices(self):
        """Register example edge devices"""
        self.edge_aggregator.register_edge_device(
            device_id="device_001",
            device_type="sensor_node",
            location="Zone_A",
            capabilities=[SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.SOIL_MOISTURE],
            ip_address="192.168.1.101"
        )
        self.edge_aggregator.register_edge_device(
            device_id="device_002",
            device_type="sensor_node",
            location="Zone_B",
            capabilities=[SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.LIGHT_INTENSITY],
            ip_address="192.168.1.102"
        )
        self.edge_aggregator.register_edge_device(
            device_id="device_003",
            device_type="sensor_node",
            location="Zone_C",
            capabilities=[SensorType.TEMPERATURE, SensorType.CO2_LEVEL, SensorType.SOIL_PH],
            ip_address="192.168.1.103"
        )
    
    def handle_aggregated_data(self, data: dict):
        """Handle new aggregated data from edge aggregator"""
        self.logger.debug(f"Received aggregated data: {data.get('sensor_type')} at {data.get('location')}")
        
        # Cache aggregated data locally
        cache_key = f"agg:{data.get('sensor_type')}:{data.get('location')}:{data.get('timeframe')}"
        self.redis_edge_client.set(cache_key, data, ttl=600)  # 10 minutes
        
        # Sync to backend (async, don't block UI)
        self.sync_aggregated_data_to_backend(data)
        
        # Display in appropriate UI component (if available)
        # Log aggregated data (tables will be updated via API calls)
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.logger.info(
            f"[{timestamp}] 📊 AGG: {data.get('sensor_type')} @ {data.get('location')} "
            f"({data.get('timeframe')}): avg={data.get('average'):.2f}, "
            f"min={data.get('min'):.2f}, max={data.get('max'):.2f}, "
            f"count={data.get('count')}, quality={data.get('quality_score'):.2f}"
        )
    
    def sync_aggregated_data_to_backend(self, data: dict):
        """Sync aggregated data to backend via HTTP API"""
        try:
            payload = {
                'sensorType': data.get('sensor_type'),
                'location': data.get('location'),
                'timeframe': data.get('timeframe'),
                'data': {
                    'average': data.get('average'),
                    'min': data.get('min'),
                    'max': data.get('max'),
                    'count': data.get('count'),
                    'std_dev': data.get('std_dev'),
                    'quality_score': data.get('quality_score'),
                    'timestamp': data.get('timestamp')
                }
            }
            
            # Use requests in a non-blocking way (could be improved with QThread)
            import threading
            def sync_thread():
                try:
                    response = requests.post(
                        f"{self.backend_url}/fog/aggregated",
                        json=payload,
                        timeout=5
                    )
                    if response.status_code == 200:
                        self.logger.debug(f"Synced aggregated data to backend: {data.get('sensor_type')}")
                    else:
                        self.logger.warning(f"Failed to sync aggregated data: {response.status_code}")
                except Exception as e:
                    self.logger.debug(f"Backend sync failed (non-critical): {e}")
            
            thread = threading.Thread(target=sync_thread, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.debug(f"Error syncing to backend: {e}")
    
    def handle_anomaly(self, anomaly: dict):
        """Handle detected anomaly"""
        self.logger.warning(f"Anomaly detected: {anomaly.get('message')}")
        
        # Sync anomaly to backend
        self.sync_anomaly_to_backend(anomaly)
        
        # Log anomaly (tables will be updated via API calls)
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        severity_icon = "🔴" if anomaly.get('severity') == 'critical' else "🟡" if anomaly.get('severity') == 'warning' else "🔵"
        self.logger.warning(
            f"[{timestamp}] {severity_icon} ANOMALY: {anomaly.get('message')} "
            f"({anomaly.get('sensor_type')} @ {anomaly.get('location')})"
        )
    
    def sync_anomaly_to_backend(self, anomaly: dict):
        """Sync anomaly to backend via HTTP API"""
        try:
            import threading
            def sync_thread():
                try:
                    response = requests.post(
                        f"{self.backend_url}/fog/anomalies",
                        json=anomaly,
                        timeout=5
                    )
                    if response.status_code == 200:
                        self.logger.debug(f"Synced anomaly to backend: {anomaly.get('anomaly_id')}")
                    else:
                        self.logger.warning(f"Failed to sync anomaly: {response.status_code}")
                except Exception as e:
                    self.logger.debug(f"Backend sync failed (non-critical): {e}")
            
            thread = threading.Thread(target=sync_thread, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.debug(f"Error syncing anomaly to backend: {e}")
    
    def handle_device_status(self, status: dict):
        """Handle device status change"""
        self.logger.info(f"Device status: {status.get('device_id')} - {status.get('status')}")
    
    def view_fog_aggregated_data(self):
        """View aggregated fog data from backend"""
        result = self.make_server_request('/fog/aggregated')
        if result:
            self.display_data_table("Fog Aggregated Data", result, 'fog_aggregated')
    
    def view_fog_devices(self):
        """View fog edge devices from backend"""
        result = self.make_server_request('/fog/devices')
        if result:
            self.display_data_table("Fog Edge Devices", result, 'fog_devices')
    
    def view_fog_anomalies(self):
        """View fog anomalies from backend"""
        limit = 20
        result = self.make_server_request(f'/fog/anomalies?limit={limit}')
        if result:
            self.display_data_table("Fog Anomalies", result, 'fog_anomalies')
        
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
            self.logger.info(f"Command sent: {command}")
            return True
        else:
            self.logger.warning("First send attempt failed, attempting reconnect...")
            if self.command_worker.attempt_reconnect():
                time.sleep(0.1)
                if self.command_worker.send_command(command_data):
                    self.logger.info("Command sent successfully after reconnect")
                    return True
            
            self.logger.error("Failed to send command after retry")
            return False
        
    def handle_response(self, response):
        command_id = response.get('commandId')
        result = response.get('result', {})
        cached = response.get('cached', False)
        error = response.get('error')
        session_id = response.get('sessionId')
        current_path = response.get('currentPath')
        
        self.logger.info(f"Received response for command {command_id}, cached: {cached}, error: {bool(error)}")
        
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        
        # Get command name from pending commands or response
        command_name = "unknown"
        if command_id in self.pending_commands:
            command_info = self.pending_commands[command_id]
            command_name = command_info.get('command', 'unknown')
            del self.pending_commands[command_id]
        else:
            command_name = response.get('command', 'unknown')
            self.logger.warning(f"Command ID {command_id} not found in pending_commands!")
        
        # Add row to table with data from RabbitMQ
        if self.control_table:
            try:
                # Store full response for detailed view
                self.control_history.append(
                    {
                        "timestamp": timestamp,
                        "command": command_name,
                        "response": response,
                        "cached": cached,
                        "error": error,
                    }
                )

                # Use table renderer to format a compact, user-friendly summary
                columns, rows = table_renderers.render_command_result_data(
                    response,
                    command=command_name,
                    timestamp=timestamp,
                    cached=cached,
                )

                # Our control_table is initialized with 4 columns, so we combine
                # the renderer's Result + Cached columns into a single Result cell.
                if rows:
                    rendered_row = rows[0]
                    # Expected from renderer: [timestamp, command, status, result_str, cached_str]
                    if len(rendered_row) >= 5:
                        _, _, status, result_str, cached_str = rendered_row
                        display_result = f"{result_str} (Cached: {cached_str})"
                    else:
                        # Fallback if renderer shape changes
                        status = rendered_row[2] if len(rendered_row) > 2 else ""
                        display_result = rendered_row[3] if len(rendered_row) > 3 else ""

                    self.control_table.add_row([timestamp, command_name, status, display_result])
                    self.logger.info(f"Added row to control table: {command_name} - {status}")
                    
            except Exception as e:
                self.logger.error(f"Error displaying command result in table: {e}", exc_info=True)
        else:
            self.logger.warning("Control table not initialized, cannot display command result")
            
        status_suffix = " (cached)" if cached else ""
        if error:
            self.status_label.setText(f"❌ Command failed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.error};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 10px 16px;
                min-height: 32px;
                border-radius: {self.theme.borderRadius.md};
                border-left: 3px solid {self.theme.colors.error};
            """)
        else:
            self.status_label.setText(f"✅ Command completed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.success};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 10px 16px;
                min-height: 32px;
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

    def resizeEvent(self, event):
        """Handle window resize - let layout handle sizing naturally"""
        super().resizeEvent(event)
        # No need to manually update table sizes - layout handles it
    
    def closeEvent(self, event):
        self.logger.info("Application shutting down")
        if self.command_worker:
            self.command_worker.disconnect()
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
        if self.sensor_simulator_timer.isActive():
            self.sensor_simulator_timer.stop()
        if self.redis_edge_client:
            self.redis_edge_client.disconnect()
        event.accept()