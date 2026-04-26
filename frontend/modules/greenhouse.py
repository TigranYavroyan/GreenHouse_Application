import sys
import uuid
import logging
import os
import json
import re
from datetime import datetime, timedelta, timezone

from PyQt5.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QLabel,
)
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5 import uic
import pyqtgraph as pg

from modules.styles import GreenhouseTheme, StyleSheetGenerator
from modules.edge_fog_aggregator import EdgeToFogAggregator
from modules.redis_client import RedisEdgeClient
from modules.table_widget import SimpleDataTable

from modules.greenhouse_commands import CommandPanelMixin
from modules.greenhouse_server import ServerPanelMixin
from modules.greenhouse_edge_fog import EdgeFogMixin
from modules.greenhouse_auth_mixin import GreenhouseAuthMixin
from modules.greenhouse_statistics_mixin import GreenhouseStatisticsMixin
from modules.greenhouse_scheduling_mixin import GreenhouseSchedulingMixin
from modules.greenhouse_logic_mixin import GreenhouseLogicMixin
from modules.auth_session import AuthSessionManager
from modules.ui_dialogs import StyledMessageDialog


class GreenhouseDesktop(
    QMainWindow,
    GreenhouseAuthMixin,
    GreenhouseStatisticsMixin,
    GreenhouseSchedulingMixin,
    GreenhouseLogicMixin,
    CommandPanelMixin,
    ServerPanelMixin,
    EdgeFogMixin,
):
    def __init__(self, auth_session=None):
        super().__init__()
        self.pending_commands = {}
        self.session_id = str(uuid.uuid4())
        self.rabbitmq_connected = False
        self.command_worker = None
        self._auth_recovery_in_progress = False
        self.auth_session = auth_session or AuthSessionManager()
        self.auth_user_label = None
        self.logoutButton = None
        # History for detailed views
        self.control_history = []  # One entry per control_table row
        self.server_history = []   # One entry per server_table row
        self.schedule_table_rows = []  # Maps schedule table row index -> schedule_id
        self.schedule_rows = []  # Raw backend schedule rows
        self.schedule_device_id = None
        self.schedule_target_keys = []
        self._schedule_refresh_tick_count = 0
        self.hidden_schedule_ids = set()
        self.include_historical_user_data = True
        self.schedule_visibility_cutoff_utc = None
        self.statistics_plot_widget = None
        self.statistics_curve = None
        self.statistics_auto_reload_timer = None
        self.statistics_poll_timer = None
        self._statistics_signals_connected = False
        self._sensor_persistence_device_cache = {}
        self._sensor_persistence_sensor_cache = {}
        
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
        self.setup_auth_controls()
        
        # Setup functionality and signal connections
        self.add_functions()
        self.setup_core_panel()
        self.setup_scheduler()
        self.setup_statistics_tab()
        self.setup_logic_tab()
        self.remove_unused_core_controls()
        self.configure_core_server_buttons()
        
        # No need to connect tab change - layout handles sizing
        
        # Setup command worker (mixin)
        self.setup_command_worker()

        # Setup edge-to-fog aggregator (mixin)
        self.setup_edge_aggregator()
        
        # Apply custom styles (UI file already has styles, but we can override if needed)
        self.apply_styles()
        self._prompt_restore_user_data_preference()
        
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
        self.schedule_table = None  # Simple table for scheduling tab
        self.server_table = None  # Simple table for server tab - adds rows from button clicks
        self.schedule_clock_timer = None

        # Ensure layouts are properly set up
        self._ensure_layouts_initialized()

        # Force find containers if they weren't found
        self._find_containers()

        # Setup tables after UI is loaded
        self.setup_tables()
        self._setup_layout_stretch()

    def _setup_layout_stretch(self):
        """Main layout stretch for tab widget."""
        if hasattr(self, "mainLayout") and self.mainLayout:
            self.mainLayout.setStretch(1, 1)

    def add_functions(self):
        """Setup signal connections and functionality"""
        # User Tab - Sensor reading buttons
        self.tempButton.clicked.connect(
            lambda: self.send_user_command("read_sensor", {"sensor": "temperature"}, source_button=self.tempButton)
        )
        self.humidityButton.clicked.connect(
            lambda: self.send_user_command("read_sensor", {"sensor": "humidity"}, source_button=self.humidityButton)
        )
        self.lightButton.clicked.connect(
            lambda: self.send_user_command("read_sensor", {"sensor": "light"}, source_button=self.lightButton)
        )
        self.co2Button.clicked.connect(
            lambda: self.send_user_command("read_sensor", {"sensor": "co2"}, source_button=self.co2Button)
        )
        self.soilMoistureButton.clicked.connect(
            lambda: self.send_user_command(
                "read_sensor",
                {"sensor": "soil_moisture"},
                source_button=self.soilMoistureButton,
            )
        )
        self.soilPHButton.clicked.connect(
            lambda: self.send_user_command("read_sensor", {"sensor": "soil_ph"}, source_button=self.soilPHButton)
        )

        # User Tab - Device control buttons
        self.waterCanalButton.clicked.connect(
            lambda: self.send_user_command(
                "switch_water_canal",
                {"action": "toggle"},
                source_button=self.waterCanalButton,
            )
        )
        self.fanButton.clicked.connect(
            lambda: self.send_user_command(
                "switch_fan",
                {"fanId": "fan_1", "action": "toggle"},
                source_button=self.fanButton,
            )
        )
        self.heaterButton.clicked.connect(
            lambda: self.send_user_command(
                "switch_heater",
                {"heaterId": "heater_1", "action": "toggle"},
                source_button=self.heaterButton,
            )
        )
        self.actuatorButton.clicked.connect(
            lambda: self.send_user_command(
                "switch_actuator",
                {"actuatorId": "actuator_1", "action": "toggle"},
                source_button=self.actuatorButton,
            )
        )

        # Server Tab - Server management buttons
        self.healthButton.clicked.connect(self.view_core_status)
        self.refreshButton.clicked.connect(self.refresh_all_status)
        if hasattr(self, "statsButton"):
            self.statsButton.clicked.connect(self.view_getter_schema)
        if hasattr(self, "sessionsButton"):
            self.sessionsButton.clicked.connect(self.view_executor_schema)
        if hasattr(self, "cacheKeysButton"):
            self.cacheKeysButton.clicked.connect(self.view_getters)
        if hasattr(self, "queuesButton"):
            self.queuesButton.clicked.connect(self.view_executors)
        if hasattr(self, "clearCacheButton"):
            self.clearCacheButton.clicked.connect(self.prompt_switch_executor_mode)
        if hasattr(self, "testCommandButton"):
            self.testCommandButton.clicked.connect(self.prompt_executor_on)
        if hasattr(self, "logFilesButton"):
            self.logFilesButton.clicked.connect(self.prompt_executor_off)
        if hasattr(self, "viewLogButton"):
            self.viewLogButton.clicked.connect(self.prompt_executor_set)

        # Server Tab - Auto-refresh checkbox (if exists in UI)
        if hasattr(self, 'auto_refresh'):
            self.auto_refresh.toggled.connect(self.toggle_auto_refresh)

        # Scheduling Tab - Persistent schedule controls
        if hasattr(self, "scheduleTaskButton"):
            self.scheduleTaskButton.clicked.connect(self.schedule_selected_task)
        if hasattr(self, "cancelScheduledButton"):
            self.cancelScheduledButton.clicked.connect(self.cancel_selected_schedule)
        if hasattr(self, "clearScheduledButton"):
            self.clearScheduledButton.clicked.connect(self.clear_all_schedules)
        if hasattr(self, "scheduleDelayPresetCombo"):
            self.scheduleDelayPresetCombo.currentIndexChanged.connect(self.update_custom_delay_enabled)
        if hasattr(self, "statisticsAllDataCheck"):
            self.statisticsAllDataCheck.toggled.connect(self._update_statistics_time_filters_enabled)
            self.statisticsAllDataCheck.toggled.connect(
                lambda _checked: self._schedule_statistics_auto_reload()
            )
        if hasattr(self, "statisticsLoadButton"):
            self.statisticsLoadButton.clicked.connect(self.load_statistics_plot)
        if hasattr(self, "statisticsDeviceCombo"):
            self.statisticsDeviceCombo.currentIndexChanged.connect(
                lambda _index: self._schedule_statistics_auto_reload()
            )
        if hasattr(self, "statisticsRefreshIntervalCombo"):
            self.statisticsRefreshIntervalCombo.currentIndexChanged.connect(
                self._on_statistics_refresh_interval_changed
            )
        if hasattr(self, "statisticsFromDateTime"):
            self.statisticsFromDateTime.dateTimeChanged.connect(
                lambda _dt: self._schedule_statistics_auto_reload()
            )
        if hasattr(self, "statisticsToDateTime"):
            self.statisticsToDateTime.dateTimeChanged.connect(
                lambda _dt: self._schedule_statistics_auto_reload()
            )
        if hasattr(self, "tabWidget"):
            self.tabWidget.currentChanged.connect(self._on_main_tab_changed)

        if self.logoutButton:
            self.logoutButton.clicked.connect(self.logout_user)

    def apply_styles(self):
        """Apply custom styles if needed (UI file already has styles)"""
        # The UI file already contains styles, but we can override specific widgets if needed
        # For example, update connection status and status label styles dynamically
        pass


    def configure_core_server_buttons(self):
        """Retitle existing server-tab buttons for greenhouse core controls."""
        server_labels = {
            "healthButton": "System Health",
            "refreshButton": "Refresh All Data",
            "statsButton": "Available Sensor Types",
            "sessionsButton": "Available Device Controls",
            "cacheKeysButton": "All Sensor Readings",
            "queuesButton": "All Device States",
            "clearCacheButton": "Change Device Mode",
            "testCommandButton": "Turn Device ON",
            "logFilesButton": "Turn Device OFF",
            "viewLogButton": "Set Device Value",
        }
        for widget_name, label in server_labels.items():
            if hasattr(self, widget_name):
                getattr(self, widget_name).setText(label)

    def remove_unused_core_controls(self):
        """
        Hide controls that are not connected to active core logic flows.
        """
        unused_buttons = (
            "statusButton",            # legacy duplicate in Control tab
            "pathButton",              # legacy/no-op control
        )
        for widget_name in unused_buttons:
            if hasattr(self, widget_name):
                button = getattr(self, widget_name)
                button.setVisible(False)
                button.setEnabled(False)

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

        if hasattr(self, 'schedule_output_container') and self.schedule_output_container:
            if not self.schedule_output_container.layout():
                layout = QVBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                self.schedule_output_container.setLayout(layout)
            self.schedule_output_container.setVisible(True)
        else:
            self.logger.warning("schedule_output_container not available for layout initialization")

    def setup_tables(self):
        """Initialize simple table widgets for displaying RabbitMQ + server data"""
        # Setup control table for command results from RabbitMQ
        if not hasattr(self, "userTabLayout") or not self.userTabLayout:
            self.logger.error("Cannot setup control table - userTabLayout not found")
            return

        self.control_table = SimpleDataTable(
            columns=["Timestamp", "Command", "Status"],
            parent=self.userTab,
            show_clear_button=True,
            on_clear_requested=self.clear_control_table,
            on_remove_selected_requested=self._remove_selected_control_row,
        )
        control_insert_index = self.userTabLayout.count()
        if hasattr(self, "user_output_container") and self.user_output_container:
            existing_index = self.userTabLayout.indexOf(self.user_output_container)
            if existing_index >= 0:
                control_insert_index = existing_index
                self.userTabLayout.removeWidget(self.user_output_container)
                self.user_output_container.setVisible(False)
                self.user_output_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.userTabLayout.insertWidget(control_insert_index, self.control_table, 1)
        # Double-click on a control row opens detailed view (mixin)
        self.control_table.table.cellDoubleClicked.connect(self.show_control_details)
        self.control_table.table.itemSelectionChanged.connect(self._on_control_table_selection_changed)

        # Connection banner in user tab for clear reconnect guidance.
        control_connection_row = QHBoxLayout()
        control_connection_row.setContentsMargins(0, 0, 0, 0)
        self.control_connection_banner = QLabel("No connection. Reconnecting automatically...")
        self.control_connection_banner.setObjectName("controlConnectionBanner")
        self.retry_connection_button = QPushButton("Retry now")
        self.retry_connection_button.setObjectName("retryConnectionButton")
        self.retry_connection_button.clicked.connect(self.retry_connection_now)
        control_connection_row.addWidget(self.control_connection_banner, 0, Qt.AlignLeft)
        control_connection_row.addWidget(self.retry_connection_button, 0, Qt.AlignLeft)
        control_connection_row.addStretch(1)
        self.userTabLayout.insertLayout(control_insert_index + 1, control_connection_row)

        # Explicit action for details improves discoverability versus double-click only.
        control_actions = QHBoxLayout()
        control_actions.setContentsMargins(0, 0, 0, 0)
        self.view_control_details_button = QPushButton("View Selected Details")
        self.view_control_details_button.setObjectName("viewControlDetailsButton")
        self.view_control_details_button.setEnabled(False)
        self.view_control_details_button.clicked.connect(self.view_selected_control_details)
        control_actions.addWidget(self.view_control_details_button, 0, Qt.AlignLeft)
        control_actions.addStretch(1)
        self.userTabLayout.insertLayout(control_insert_index + 2, control_actions)

        # Add a small hint below the control table so users know how to open details.
        control_hint = QLabel("Tip: select a row and click 'View Selected Details' (or double-click a row).")
        control_hint.setObjectName("controlTableHintLabel")
        self.userTabLayout.insertWidget(control_insert_index + 3, control_hint, 0)

        self.control_empty_state_label = QLabel(
            "No actions yet. Use any control above to run your first command."
        )
        self.control_empty_state_label.setObjectName("controlEmptyStateLabel")
        self.userTabLayout.insertWidget(control_insert_index + 4, self.control_empty_state_label, 0)

        # Also set a tooltip on the table itself
        self.control_table.table.setToolTip(
            "Select a row and click 'View Selected Details', or double-click a row."
        )
        self._on_control_table_selection_changed()
        self._update_connection_banner()

        self.logger.info(f"Control table created: visible={self.control_table.isVisible()}")

        # Setup scheduling table
        if hasattr(self, "schedulingTabLayout") and self.schedulingTabLayout:
            self.schedule_table = SimpleDataTable(
                columns=["Task", "Time Remaining", "Starts At", "Ends At", "Status"],
                parent=self.schedulingTab,
                show_clear_button=True,
                on_clear_requested=self.hide_all_schedule_rows_from_view,
                on_remove_selected_requested=self.remove_selected_schedule_row_from_view,
            )
            schedule_insert_index = self.schedulingTabLayout.count()
            if hasattr(self, "schedule_output_container") and self.schedule_output_container:
                existing_index = self.schedulingTabLayout.indexOf(self.schedule_output_container)
                if existing_index >= 0:
                    schedule_insert_index = existing_index
                    self.schedulingTabLayout.removeWidget(self.schedule_output_container)
                    self.schedule_output_container.setVisible(False)
                    self.schedule_output_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

            self.schedulingTabLayout.insertWidget(schedule_insert_index, self.schedule_table, 1)
            self.schedule_table.table.setToolTip("One-time tasks with live countdown and status.")

            schedule_hint = QLabel("Tip: one-time tasks update countdown every second. Hide rows if needed.")
            schedule_hint.setObjectName("scheduleTableHintLabel")
            self.schedulingTabLayout.insertWidget(schedule_insert_index + 1, schedule_hint, 0)

            self.schedule_empty_state_label = QLabel(
                "No schedules yet. Create a one-time task from the controls above."
            )
            self.schedule_empty_state_label.setObjectName("scheduleEmptyStateLabel")
            self.schedulingTabLayout.insertWidget(schedule_insert_index + 2, self.schedule_empty_state_label, 0)
        else:
            self.logger.warning("schedule_output_container not found - scheduling table not created")

        # Setup server info table
        if not hasattr(self, "infoGroupLayout") or not self.infoGroupLayout:
            self.logger.error("Cannot setup server table - infoGroupLayout not found")
            return

        self.server_table = SimpleDataTable(
            columns=["Timestamp", "Type", "Data"],
            parent=self.infoGroup,
            show_clear_button=True,
            on_clear_requested=self.clear_server_tables,
            on_remove_selected_requested=self._remove_selected_server_row,
        )

        server_insert_index = self.infoGroupLayout.count()
        if hasattr(self, "server_info_scroll") and self.server_info_scroll:
            existing_index = self.infoGroupLayout.indexOf(self.server_info_scroll)
            if existing_index >= 0:
                server_insert_index = existing_index
                self.infoGroupLayout.removeWidget(self.server_info_scroll)
                self.server_info_scroll.setVisible(False)
                self.server_info_scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.infoGroupLayout.insertWidget(server_insert_index, self.server_table, 1)

        # Double-click on a server row opens detailed view (mixin)
        self.server_table.table.cellDoubleClicked.connect(self.show_server_details)

        # Add a small hint below the server table for discoverability
        server_hint = QLabel("Tip: double-click a row in the table to see detailed server or fog data.")
        server_hint.setObjectName("serverTableHintLabel")
        self.infoGroupLayout.insertWidget(server_insert_index + 1, server_hint, 0)

        self.server_empty_state_label = QLabel(
            "No server checks yet. Click any server action above to load data."
        )
        self.server_empty_state_label.setObjectName("serverEmptyStateLabel")
        self.infoGroupLayout.insertWidget(server_insert_index + 2, self.server_empty_state_label, 0)

        # Tooltip on the server table itself
        self.server_table.table.setToolTip("Double-click a row to open a detailed view of the selected entry.")
        if hasattr(self, "_update_schedule_empty_state"):
            self._update_schedule_empty_state()
        if hasattr(self, "_update_server_empty_state"):
            self._update_server_empty_state()

        self.logger.info(f"Server table created: visible={self.server_table.isVisible()}")

        # Set stretch factors for tab layouts - tables should fill space between buttons and status
        for i in range(self.userTabLayout.count()):
            item = self.userTabLayout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget_name = widget.objectName()
                if widget_name == 'controlGroup':
                    self.userTabLayout.setStretch(i, 0)  # Buttons take minimal space
                elif widget_name == 'simpleDataTable':
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

        if hasattr(self, "schedulingTabLayout"):
            for i in range(self.schedulingTabLayout.count()):
                item = self.schedulingTabLayout.itemAt(i)
                if item and item.widget():
                    widget_name = item.widget().objectName()
                    if widget_name == 'scheduleGroup':
                        self.schedulingTabLayout.setStretch(i, 0)
                    elif widget_name == 'simpleDataTable':
                        self.schedulingTabLayout.setStretch(i, 1)


    def resizeEvent(self, event):
        """Handle window resize and keep table widgets responsive."""
        super().resizeEvent(event)
        for table_widget in (self.control_table, self.schedule_table, self.server_table):
            if not table_widget:
                continue
            table_widget.updateGeometry()
            table_widget.table.updateGeometry()
            table_widget.table.viewport().update()

    def closeEvent(self, event):
        self.logger.info("Application shutting down")
        if getattr(self, "command_worker", None):
            self.command_worker.disconnect()
        if hasattr(self, "auto_refresh_timer") and self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
        if hasattr(self, "sensor_simulator_timer") and self.sensor_simulator_timer.isActive():
            self.sensor_simulator_timer.stop()
        if self.schedule_clock_timer and self.schedule_clock_timer.isActive():
            self.schedule_clock_timer.stop()
        if self.redis_edge_client:
            self.redis_edge_client.disconnect()
        event.accept()
