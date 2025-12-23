import sys
import uuid
import logging
import os

from PyQt5.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QMessageBox,
    QSizePolicy,
    QLabel,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5 import uic

from modules.styles import GreenhouseTheme, StyleSheetGenerator
from modules.edge_fog_aggregator import EdgeToFogAggregator
from modules.redis_client import RedisEdgeClient
from modules.table_widget import SimpleDataTable

from modules.greenhouse_commands import CommandPanelMixin
from modules.greenhouse_server import ServerPanelMixin
from modules.greenhouse_edge_fog import EdgeFogMixin

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('greenhouse_system.log', encoding='utf-8')
        ]
    )

class GreenhouseDesktop(QMainWindow, CommandPanelMixin, ServerPanelMixin, EdgeFogMixin):
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
        
        # Initialize Edge-to-Fog aggregator + local Redis client
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
        
        # Setup command worker (mixin)
        self.setup_command_worker()

        # Setup edge-to-fog aggregator (mixin)
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
        """Initialize simple table widgets for displaying RabbitMQ + server data"""
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
        # Double-click on a control row opens detailed view (mixin)
        self.control_table.table.cellDoubleClicked.connect(self.show_control_details)

        # Add a small hint below the control table so users know about double-click
        control_hint = QLabel("Tip: double-click a row in the table to see detailed information.")
        control_hint.setObjectName("controlTableHintLabel")
        control_hint.setStyleSheet("color: #666666; font-size: 11px; margin-top: 4px;")
        layout.addWidget(control_hint, 0)

        # Also set a tooltip on the table itself
        self.control_table.table.setToolTip("Double-click a row to open a detailed view of the result.")

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
        # Double-click on a server row opens detailed view (mixin)
        self.server_table.table.cellDoubleClicked.connect(self.show_server_details)

        # Add a small hint below the server table for discoverability
        server_hint = QLabel("Tip: double-click a row in the table to see detailed server or fog data.")
        server_hint.setObjectName("serverTableHintLabel")
        server_hint.setStyleSheet("color: #666666; font-size: 11px; margin-top: 4px;")
        layout.addWidget(server_hint, 0)

        # Tooltip on the server table itself
        self.server_table.table.setToolTip("Double-click a row to open a detailed view of the selected entry.")

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

    def resizeEvent(self, event):
        """Handle window resize - let layout handle sizing naturally"""
        super().resizeEvent(event)
        # No need to manually update table sizes - layout handles it

    def closeEvent(self, event):
        self.logger.info("Application shutting down")
        if getattr(self, "command_worker", None):
            self.command_worker.disconnect()
        if hasattr(self, "auto_refresh_timer") and self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
        if hasattr(self, "sensor_simulator_timer") and self.sensor_simulator_timer.isActive():
            self.sensor_simulator_timer.stop()
        if self.redis_edge_client:
            self.redis_edge_client.disconnect()
        event.accept()
