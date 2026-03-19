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
from modules.auth_dialog import AuthDialog
from modules.auth_session import AuthSessionManager
from modules.core_api_client import CoreApiClient, UnauthorizedError
from modules.ui_dialogs import StyledMessageDialog

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
        self.setup_statistics_tab()
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

        # Setup scheduling service and controls
        self.setup_scheduler()
        self.setup_statistics_tab()

    def _setup_layout_stretch(self):
        """Main layout stretch for tab widget."""
        if hasattr(self, "mainLayout") and self.mainLayout:
            self.mainLayout.setStretch(1, 1)

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

    def setup_auth_controls(self):
        if not hasattr(self, "sessionLayout") or not self.sessionLayout:
            return

        self.auth_user_label = QLabel("")
        self.auth_user_label.setObjectName("authUserLabel")
        self.logoutButton = QPushButton("Logout")
        self.logoutButton.setObjectName("logoutButton")
        self.logoutButton.setMinimumHeight(24)

        self.sessionLayout.insertWidget(2, self.auth_user_label)
        self.sessionLayout.addWidget(self.logoutButton)
        self.update_auth_user_label()

    def update_auth_user_label(self):
        if not self.auth_user_label:
            return
        claims = self.auth_session.decode_claims()
        username = str(claims.get("username", "")).strip()
        if username:
            self.auth_user_label.setText(f"User: {username}")
            self.auth_user_label.setToolTip("Authenticated user")
        else:
            self.auth_user_label.setText("User: -")
            self.auth_user_label.setToolTip("No authenticated user")

    def get_auth_token(self):
        return self.auth_session.get_token()

    def _build_auth_api_client(self):
        return CoreApiClient(self.backend_url, auth_token_provider=self.get_auth_token)

    def _reauthenticate_or_exit(self):
        while True:
            dialog = AuthDialog(CoreApiClient(self.backend_url), self.auth_session, parent=self)
            result = dialog.exec_()
            if result == dialog.Accepted:
                try:
                    self._build_auth_api_client().get_current_user()
                    self.update_auth_user_label()
                    self._prompt_restore_user_data_preference()
                    return True
                except Exception as error:
                    self.auth_session.clear_token()
                    StyledMessageDialog.show_warning(
                        self,
                        "Authentication Error",
                        f"Sign in succeeded but session validation failed: {error}",
                    )
                    continue
            return False

    def _pause_authenticated_timers(self):
        state = {
            "auto_refresh": bool(
                hasattr(self, "auto_refresh_timer") and self.auto_refresh_timer.isActive()
            ),
            "schedule_clock": bool(
                getattr(self, "schedule_clock_timer", None)
                and self.schedule_clock_timer.isActive()
            ),
        }
        if state["auto_refresh"]:
            self.auto_refresh_timer.stop()
        if state["schedule_clock"]:
            self.schedule_clock_timer.stop()
        return state

    def _resume_authenticated_timers(self, state):
        if not isinstance(state, dict):
            return
        if state.get("auto_refresh") and hasattr(self, "auto_refresh_timer"):
            self.auto_refresh_timer.start(10000)
        if state.get("schedule_clock") and getattr(self, "schedule_clock_timer", None):
            self.schedule_clock_timer.start(1000)

    def _reset_user_scoped_tables(self):
        """Clear user-scoped table data before switching authentication context."""
        if self.control_table:
            self.control_table.clear_data()
        if self.server_table:
            self.server_table.clear_data()
        if self.schedule_table:
            self.schedule_table.clear_data()

        self.control_history = []
        self.server_history = []
        self.schedule_table_rows = []
        self.schedule_rows = []
        self.schedule_device_id = None
        self.schedule_target_keys = []
        self.hidden_schedule_ids = set()

        if hasattr(self, "statisticsDeviceCombo"):
            self.statisticsDeviceCombo.clear()
        if hasattr(self, "statisticsSensorCombo"):
            self.statisticsSensorCombo.clear()
        if self.statistics_curve:
            self.statistics_curve.setData([], [])

    def handle_unauthorized_error(self, message="Unauthorized"):
        if self._auth_recovery_in_progress:
            return

        self._auth_recovery_in_progress = True
        timer_state = self._pause_authenticated_timers()
        try:
            self._reset_user_scoped_tables()
            self.auth_session.clear_token()
            self.update_auth_user_label()
            StyledMessageDialog.show_warning(
                self,
                "Session Expired",
                f"{message}\n\nPlease sign in again.",
            )

            if self._reauthenticate_or_exit():
                self._resume_authenticated_timers(timer_state)
                self.status_label.setText("✅ Re-authenticated successfully")
                return

            self.close()
        finally:
            self._auth_recovery_in_progress = False

    def logout_user(self):
        confirm = StyledMessageDialog.ask_yes_no(
            self,
            "Logout",
            "Sign out from this desktop session?",
            yes_text="Yes",
            no_text="No",
        )
        if not confirm:
            return

        if self._auth_recovery_in_progress:
            return

        self._auth_recovery_in_progress = True
        timer_state = self._pause_authenticated_timers()
        try:
            self._reset_user_scoped_tables()
            self.auth_session.clear_token()
            self.update_auth_user_label()
            self.status_label.setText("Signed out")
            if self._reauthenticate_or_exit():
                self._resume_authenticated_timers(timer_state)
                self.status_label.setText("✅ Signed in again")
                return
            self.close()
        finally:
            self._auth_recovery_in_progress = False

    def _handle_api_exception(self, title, error):
        if isinstance(error, UnauthorizedError):
            self.handle_unauthorized_error(str(error))
            return
        self.show_error(title, str(error))

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
            columns=["Timestamp", "Command", "Status", "Result"],
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

        # Add a small hint below the control table so users know about double-click
        control_hint = QLabel("Tip: double-click a row in the table to see detailed information.")
        control_hint.setObjectName("controlTableHintLabel")
        self.userTabLayout.insertWidget(control_insert_index + 1, control_hint, 0)

        # Also set a tooltip on the table itself
        self.control_table.table.setToolTip("Double-click a row to open a detailed view of the result.")

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

    def setup_scheduler(self):
        """Initialize scheduling controls backed by persistent backend schedules."""
        if not hasattr(self, "scheduleTargetCombo") or not hasattr(self, "scheduleDelayPresetCombo"):
            self.logger.warning("Scheduling controls not present in UI")
            return

        self._refresh_schedule_targets()

        self.scheduleDelayPresetCombo.clear()
        self.scheduleDelayPresetCombo.addItem("After 1 minute", 60)
        self.scheduleDelayPresetCombo.addItem("After 15 minutes", 15 * 60)
        self.scheduleDelayPresetCombo.addItem("After 30 minutes", 30 * 60)
        self.scheduleDelayPresetCombo.addItem("After 1 hour", 60 * 60)
        self.scheduleDelayPresetCombo.addItem("Custom delay (hh:mm:ss)", -1)
        self.scheduleDelayPresetCombo.setCurrentIndex(0)

        self.schedule_clock_timer = QTimer(self)
        self.schedule_clock_timer.timeout.connect(self.update_schedule_live_time)
        self.schedule_clock_timer.start(1000)

        self.update_custom_delay_enabled()
        self.update_schedule_live_time()
        self.refresh_schedule_table()

    def _refresh_schedule_targets(self):
        """
        Keep scheduling targets aligned with currently available executors/devices.
        Only device control actions are schedulable from this tab.
        """
        if not hasattr(self, "scheduleTargetCombo") or not hasattr(self, "core_api"):
            return

        try:
            executors = self.core_api.get_executors()
        except Exception as error:
            if isinstance(error, UnauthorizedError):
                self.handle_unauthorized_error(str(error))
                return
            self.logger.warning(f"Failed to refresh schedule targets: {error}")
            executors = []

        options = []
        seen = set()
        for executor in executors:
            name = str(getattr(executor, "name", "")).strip()
            if not name:
                continue

            lowered = name.lower()
            command = None
            parameters = {"action": "toggle"}
            label_prefix = None

            if "water" in lowered and "canal" in lowered:
                command = "switch_water_canal"
                label_prefix = "🚰 Toggle"
            elif "fan" in lowered:
                command = "switch_fan"
                parameters["fanId"] = name
                label_prefix = "🌀 Toggle"
            elif "heater" in lowered:
                command = "switch_heater"
                parameters["heaterId"] = name
                label_prefix = "🔥 Toggle"
            elif "actuator" in lowered:
                command = "switch_actuator"
                parameters["actuatorId"] = name
                label_prefix = "⚙️ Toggle"

            # Keep scheduler useful even when executor naming is custom:
            # treat any unrecognized executor as a toggle-capable actuator target.
            if not command:
                command = "switch_actuator"
                parameters["actuatorId"] = name
                label_prefix = "⚙️ Toggle"

            if not command:
                continue

            key = f"{command}:{name.lower()}"
            if key in seen:
                continue
            seen.add(key)
            options.append((f"{label_prefix} {name}", (command, parameters), key))

        # Fallback to known default controls so scheduling remains usable even if
        # executor names don't follow expected fan/heater/actuator naming.
        if not options:
            options = [
                ("Toggle water canal", ("switch_water_canal", {"action": "toggle"}), "switch_water_canal:default"),
                ("Toggle fan", ("switch_fan", {"fanId": "fan_1", "action": "toggle"}), "switch_fan:fan_1"),
                ("Toggle heater", ("switch_heater", {"heaterId": "heater_1", "action": "toggle"}), "switch_heater:heater_1"),
                (
                    "Toggle actuator",
                    ("switch_actuator", {"actuatorId": "actuator_1", "action": "toggle"}),
                    "switch_actuator:actuator_1",
                ),
            ]

        new_keys = [item[2] for item in options]
        if new_keys == self.schedule_target_keys:
            return

        self.scheduleTargetCombo.clear()
        self.schedule_target_keys = new_keys
        for label, payload, _key in options:
            self.scheduleTargetCombo.addItem(label, payload)

        if not options:
            self.scheduleTargetCombo.addItem("No available devices", None)

    def update_schedule_live_time(self):
        """Update live time UI elements in scheduling tab."""
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(self, "scheduleCurrentTimeLabel"):
            self.scheduleCurrentTimeLabel.setText(f"Current Time: {now_text}")
        self._schedule_refresh_tick_count += 1
        if self._schedule_refresh_tick_count >= 5:
            self._schedule_refresh_tick_count = 0
            self.refresh_schedule_table()
            self._refresh_schedule_targets()
            return
        self._render_schedule_rows()

    def _prompt_restore_user_data_preference(self):
        """
        Ask whether user wants to load previously stored user-specific data.
        """
        load_previous = StyledMessageDialog.ask_yes_no(
            self,
            "Load Previous Data",
            "Load your previously saved logs and schedules from database?",
            yes_text="Load",
            no_text="Start Fresh",
        )
        self.include_historical_user_data = bool(load_previous)
        self.hidden_schedule_ids = set()

        if load_previous:
            self.schedule_visibility_cutoff_utc = None
            self.load_user_logs_from_database()
            self.refresh_schedule_table()
            self.refresh_statistics_devices()
            return

        self.schedule_visibility_cutoff_utc = datetime.now(timezone.utc)
        self._reset_user_scoped_tables()
        self.refresh_statistics_devices()

    def setup_statistics_tab(self):
        """Initialize statistics controls and interactive plot widget."""
        if not hasattr(self, "statistics_plot_layout") or not hasattr(self, "core_api"):
            return

        self.logger.info("Setting up statistics tab")

        # Statistics workflow is device + time range only.
        if hasattr(self, "statisticsSensorLabel"):
            self.statisticsSensorLabel.setVisible(False)
        if hasattr(self, "statisticsSensorCombo"):
            self.statisticsSensorCombo.setVisible(False)

        if self.statistics_plot_widget is None:
            axis_items = {"bottom": pg.DateAxisItem(orientation="bottom")}
            self.statistics_plot_widget = pg.PlotWidget(axisItems=axis_items, parent=self.statisticsTab)
            self.statistics_plot_widget.setObjectName("statisticsPlotWidget")
            self.statistics_plot_widget.showGrid(x=True, y=True, alpha=0.25)
            self.statistics_plot_widget.setMouseEnabled(x=True, y=True)
            self.statistics_plot_widget.setLabel("left", "Value")
            self.statistics_plot_widget.setLabel("bottom", "Time")
            self.statistics_plot_widget.setClipToView(True)
            self.statistics_plot_widget.addLegend(offset=(10, 10))
            self.statistics_plot_layout.addWidget(self.statistics_plot_widget)
            self.statistics_curve = self.statistics_plot_widget.plot(
                [],
                [],
                pen=pg.mkPen(color="#57CCF2", width=2),
                name="Sensor value",
            )

        now_local = datetime.now().astimezone()
        from_local = now_local - timedelta(days=1)
        if hasattr(self, "statisticsFromDateTime"):
            self.statisticsFromDateTime.setDateTime(
                QDateTime.fromSecsSinceEpoch(int(from_local.timestamp()))
            )
        if hasattr(self, "statisticsToDateTime"):
            self.statisticsToDateTime.setDateTime(
                QDateTime.fromSecsSinceEpoch(int(now_local.timestamp()))
            )
        if hasattr(self, "statisticsAllDataCheck"):
            # Default to full dataset so users immediately see persisted history.
            self.statisticsAllDataCheck.setChecked(True)

        self._setup_statistics_refresh_interval_controls()
        self._update_statistics_time_filters_enabled()
        self._ensure_statistics_auto_reload_timer()
        self._ensure_statistics_poll_timer()
        self._connect_statistics_runtime_signals()
        self.refresh_statistics_devices()
        self._apply_statistics_refresh_interval(reload_immediately=False)
        self._schedule_statistics_auto_reload()

    def _ensure_statistics_auto_reload_timer(self):
        if self.statistics_auto_reload_timer is not None:
            return
        self.statistics_auto_reload_timer = QTimer(self)
        self.statistics_auto_reload_timer.setSingleShot(True)
        self.statistics_auto_reload_timer.timeout.connect(
            lambda: self.load_statistics_plot(suppress_missing_device_warning=True)
        )

    def _ensure_statistics_poll_timer(self):
        if self.statistics_poll_timer is not None:
            return
        self.statistics_poll_timer = QTimer(self)
        self.statistics_poll_timer.setSingleShot(False)
        self.statistics_poll_timer.timeout.connect(
            lambda: self.load_statistics_plot(suppress_missing_device_warning=True)
        )

    def _setup_statistics_refresh_interval_controls(self):
        if not hasattr(self, "statisticsRefreshIntervalCombo"):
            return
        combo = self.statisticsRefreshIntervalCombo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("No timer", 0)
        combo.addItem("1s", 1000)
        combo.addItem("5s", 5000)
        combo.addItem("15s", 15000)
        combo.addItem("30s", 30000)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _current_statistics_refresh_interval_ms(self):
        if not hasattr(self, "statisticsRefreshIntervalCombo"):
            return 0
        data = self.statisticsRefreshIntervalCombo.currentData()
        try:
            value = int(data)
        except (TypeError, ValueError):
            return 0
        return value if value > 0 else 0

    def _apply_statistics_refresh_interval(self, reload_immediately=False):
        self._ensure_statistics_poll_timer()
        interval_ms = self._current_statistics_refresh_interval_ms()

        if interval_ms <= 0 or not self._is_statistics_tab_active():
            self.statistics_poll_timer.stop()
            if interval_ms <= 0:
                self.logger.info("Statistics auto-refresh timer is disabled (manual mode)")
            return

        self.statistics_poll_timer.setInterval(interval_ms)
        self.statistics_poll_timer.start()
        self.logger.info(f"Statistics auto-refresh timer set to {interval_ms}ms")
        if reload_immediately:
            self.load_statistics_plot(suppress_missing_device_warning=True)

    def _on_statistics_refresh_interval_changed(self, _index):
        self._apply_statistics_refresh_interval(reload_immediately=True)

    def _connect_statistics_runtime_signals(self):
        if self._statistics_signals_connected:
            return
        self._statistics_signals_connected = True

    def _is_statistics_tab_active(self):
        if not hasattr(self, "tabWidget") or not hasattr(self, "statisticsTab"):
            return False
        return self.tabWidget.currentWidget() is self.statisticsTab

    def _schedule_statistics_auto_reload(self):
        if not self._is_statistics_tab_active():
            return
        if self._current_statistics_refresh_interval_ms() <= 0:
            return
        self._ensure_statistics_auto_reload_timer()
        self.statistics_auto_reload_timer.start(250)

    def _on_main_tab_changed(self, _index):
        if not self._is_statistics_tab_active():
            if self.statistics_poll_timer is not None:
                self.statistics_poll_timer.stop()
            return
        self.refresh_statistics_devices()
        self._apply_statistics_refresh_interval(reload_immediately=True)
        self._schedule_statistics_auto_reload()

    def _statistics_selection_key(self, selection):
        if isinstance(selection, dict):
            sensor_id = str(selection.get("sensor_id", "")).strip()
            if sensor_id:
                return f"sensor:{sensor_id}"
        return ""

    def _find_statistics_selection_index(self, selection_key):
        if not selection_key or not hasattr(self, "statisticsDeviceCombo"):
            return -1
        for index in range(self.statisticsDeviceCombo.count()):
            key = self._statistics_selection_key(self.statisticsDeviceCombo.itemData(index))
            if key == selection_key:
                return index
        return -1

    def _get_selected_sensor(self):
        """Return the sensor selection dict from the current combo item, or None."""
        if not hasattr(self, "statisticsDeviceCombo"):
            return None
        selected = self.statisticsDeviceCombo.currentData()
        if isinstance(selected, dict) and selected.get("sensor_id"):
            return selected
        return None

    def refresh_statistics_devices(self):
        """Populate statistics selector with concrete sensor names from the DB."""
        if not hasattr(self, "statisticsDeviceCombo") or not hasattr(self, "core_api"):
            return

        self.logger.info("Refreshing statistics sensor sources")
        selected_key = self._statistics_selection_key(self.statisticsDeviceCombo.currentData())
        self.statisticsDeviceCombo.clear()

        try:
            sensors = self.core_api.list_sensors()
        except UnauthorizedError as error:
            self.handle_unauthorized_error(str(error))
            return
        except Exception as error:
            self.logger.warning("Failed to fetch sensors for statistics: %s", error)
            sensors = []

        seen_ids = set()
        for sensor in sensors if isinstance(sensors, list) else []:
            if not isinstance(sensor, dict):
                continue
            sensor_id = str(sensor.get("id", "")).strip()
            sensor_name = str(sensor.get("name", "")).strip()
            sensor_type = str(sensor.get("type", "")).strip()
            if not sensor_id or sensor_id in seen_ids:
                continue
            seen_ids.add(sensor_id)
            display_name = sensor_name or sensor_type or sensor_id[:8]
            self.statisticsDeviceCombo.addItem(
                display_name,
                {
                    "sensor_id": sensor_id,
                    "sensor_name": sensor_name,
                    "sensor_type": sensor_type,
                },
            )

        if self.statisticsDeviceCombo.count() == 0:
            self.statisticsDeviceCombo.addItem("No sensors available", "")
            return

        self.logger.info(
            "Statistics combo populated with %d sensor(s)",
            self.statisticsDeviceCombo.count(),
        )

        if selected_key:
            index = self._find_statistics_selection_index(selected_key)
            if index >= 0:
                self.statisticsDeviceCombo.setCurrentIndex(index)

    def _parse_reading_timestamp(self, value):
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _parse_reading_numeric_value(self, reading):
        if not isinstance(reading, dict):
            return None

        candidates = [
            reading.get("value"),
            reading.get("reading"),
            reading.get("data"),
            reading.get("result"),
        ]
        for candidate in candidates:
            if isinstance(candidate, (int, float)):
                return float(candidate)
            if isinstance(candidate, str):
                stripped = candidate.strip()
                if not stripped:
                    continue
                try:
                    return float(stripped)
                except ValueError:
                    match = re.search(r"-?\d+(?:\.\d+)?", stripped)
                    if match:
                        try:
                            return float(match.group(0))
                        except ValueError:
                            pass
            if isinstance(candidate, dict):
                nested_value = candidate.get("value")
                if isinstance(nested_value, (int, float)):
                    return float(nested_value)
                if isinstance(nested_value, str):
                    try:
                        return float(nested_value.strip())
                    except ValueError:
                        pass
        return None

    def _collect_nested_values(self, payload, target_keys):
        values = []
        if payload is None:
            return values

        target_set = {str(key).lower() for key in target_keys}

        def _walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if str(key).lower() in target_set and value is not None:
                        values.append(value)
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        return values

    def _extract_device_id_from_payload(self, payload):
        candidates = self._collect_nested_values(
            payload,
            target_keys=("deviceid", "device_id", "device"),
        )
        for candidate in candidates:
            if isinstance(candidate, dict):
                nested_id = (
                    str(candidate.get("id", "")).strip()
                    or str(candidate.get("deviceId", "")).strip()
                    or str(candidate.get("device_id", "")).strip()
                )
                if nested_id:
                    return nested_id
                continue
            normalized = str(candidate).strip()
            if normalized and normalized.lower() != "none":
                return normalized
        return ""

    def _extract_timestamp_from_payload(self, payload):
        candidates = self._collect_nested_values(
            payload,
            target_keys=("timestamp", "createdat", "created_at", "time", "date"),
        )
        for candidate in candidates:
            parsed = self._parse_reading_timestamp(candidate)
            if parsed:
                return parsed
        return None

    def _extract_numeric_value_from_payload(self, payload):
        if isinstance(payload, dict):
            numeric = self._parse_reading_numeric_value(payload)
            if numeric is not None:
                return numeric

        candidates = self._collect_nested_values(
            payload,
            target_keys=("value", "reading", "result", "data", "output"),
        )
        for candidate in candidates:
            if isinstance(candidate, (int, float)):
                return float(candidate)
            if isinstance(candidate, str):
                stripped = candidate.strip()
                if not stripped:
                    continue
                try:
                    return float(stripped)
                except ValueError:
                    match = re.search(r"-?\d+(?:\.\d+)?", stripped)
                    if match:
                        try:
                            return float(match.group(0))
                        except ValueError:
                            continue
            if isinstance(candidate, dict):
                nested = self._parse_reading_numeric_value(candidate)
                if nested is not None:
                    return nested
        return None

    def _is_sensor_read_command(self, command_name):
        normalized = str(command_name or "").strip().lower()
        return normalized in {
            "read_sensor",
            "read_temperature_data",
            "read_humidity_data",
            "read_light_data",
            "read_co2_data",
            "read_soil_moisture_data",
            "read_soil_ph_data",
        }

    def _sensor_type_from_command(self, command_name):
        normalized = str(command_name or "").strip().lower()
        if normalized == "read_sensor":
            return "generic"
        if normalized.startswith("read_") and normalized.endswith("_data"):
            sensor_type = normalized[len("read_") : -len("_data")]
            return sensor_type or "generic"
        return "generic"

    def _sensor_unit_for_type(self, sensor_type):
        mapping = {
            "temperature": "C",
            "humidity": "%",
            "light": "lux",
            "co2": "ppm",
            "soil_moisture": "%",
            "soil_ph": "pH",
        }
        return mapping.get(str(sensor_type or "").strip().lower(), "")

    def _extract_response_payload(self, response):
        if not isinstance(response, dict):
            return {}
        result = response.get("result")
        if isinstance(result, dict):
            if isinstance(result.get("data"), dict):
                return result.get("data")
            if isinstance(result.get("data"), str):
                try:
                    parsed = json.loads(result.get("data"))
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
            if isinstance(result.get("result"), dict):
                return result.get("result")
            if isinstance(result.get("result"), str):
                try:
                    parsed = json.loads(result.get("result"))
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
            if isinstance(result.get("output"), str):
                try:
                    parsed = json.loads(result.get("output"))
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
        if isinstance(response.get("result"), dict):
            return response.get("result")
        return response

    def _extract_sensor_reading_fields(self, command_name, response, command_context=None):
        payload = self._extract_response_payload(response)
        if not isinstance(payload, dict):
            return None

        sensor_type = self._sensor_type_from_command(command_name)
        if sensor_type == "generic":
            explicit_type = str(payload.get("type", "")).strip().lower()
            if explicit_type:
                sensor_type = explicit_type
        if sensor_type == "generic" and isinstance(command_context, dict):
            params = command_context.get("parameters")
            if isinstance(params, dict):
                explicit_from_params = str(params.get("sensor", "")).strip().lower()
                if explicit_from_params:
                    sensor_type = explicit_from_params

        value = self._extract_numeric_value_from_payload(payload)
        if value is None and isinstance(response, dict):
            # Some responses keep numeric value only in top-level/result.output shape.
            value = self._extract_numeric_value_from_payload(response)
        if value is None:
            self.logger.info(
                "Sensor persistence value extraction failed: command=%s payload_keys=%s response_keys=%s",
                command_name,
                list(payload.keys()),
                list(response.keys()) if isinstance(response, dict) else [],
            )
            return None

        timestamp = (
            self._extract_timestamp_from_payload(payload)
            or self._parse_reading_timestamp(payload.get("timestamp"))
            or self._extract_timestamp_from_payload(response if isinstance(response, dict) else {})
            or datetime.now(timezone.utc)
        )
        if not timestamp:
            timestamp = datetime.now(timezone.utc)

        response_name = str(response.get("name", "")).strip() if isinstance(response, dict) else ""
        sensor_name = (
            str(payload.get("name", "")).strip()
            or response_name
            or sensor_type.replace("_", " ").title()
        )
        response_location = str(response.get("location", "")).strip() if isinstance(response, dict) else ""
        location_name = str(payload.get("location", "")).strip() or response_location

        response_device_name = str(response.get("deviceName", "")).strip() if isinstance(response, dict) else ""
        payload_device_name = str(payload.get("deviceName", "")).strip()
        payload_device = str(payload.get("device", "")).strip()
        # Keep concrete device naming from payload/context only (no synthetic fallback names).
        device_name = payload_device_name or response_device_name or payload_device or location_name

        core_sensor_id = str(payload.get("sensorId", "")).strip()
        if not core_sensor_id and isinstance(response, dict):
            core_sensor_id = str(response.get("sensorId", "")).strip()

        return {
            "sensor_type": sensor_type,
            "sensor_name": sensor_name,
            "value": float(value),
            "timestamp_iso": timestamp.astimezone(timezone.utc).isoformat(),
            "unit": self._sensor_unit_for_type(sensor_type),
            "device_name": device_name,
            "location": location_name,
            "core_sensor_id": core_sensor_id,
            "raw_payload": payload,
            "command_id": str(response.get("commandId", "")).strip() if isinstance(response, dict) else "",
        }

    def _ensure_persistence_device(self, device_name, sensor_type, location_name="", core_sensor_id=""):
        normalized_device_name = str(device_name or "").strip()
        normalized_sensor_type = str(sensor_type or "").strip().lower()
        normalized_location = str(location_name or "").strip().lower()
        normalized_core_sensor_id = str(core_sensor_id or "").strip()
        cache_key = f"{normalized_device_name.lower()}::{normalized_sensor_type}"
        cached_id = str(self._sensor_persistence_device_cache.get(cache_key, "")).strip()
        if cached_id:
            self.logger.info("Sensor persistence device cache hit: %s -> %s", normalized_device_name or "[auto]", cached_id)
            return cached_id

        devices = self.core_api.list_devices()
        if not isinstance(devices, list):
            devices = []

        for device in devices:
            if not isinstance(device, dict):
                continue
            candidate_id = str(device.get("id", "")).strip()
            candidate_name = str(device.get("name", "")).strip()
            if not candidate_id:
                continue
            if candidate_name == normalized_device_name:
                self._sensor_persistence_device_cache[cache_key] = candidate_id
                self.logger.info("Sensor persistence matched device '%s' -> %s", normalized_device_name, candidate_id)
                return candidate_id

            metadata = device.get("metadata") if isinstance(device.get("metadata"), dict) else {}
            metadata_core_sensor_id = str(metadata.get("coreSensorId", "")).strip()
            if normalized_core_sensor_id and metadata_core_sensor_id == normalized_core_sensor_id:
                self._sensor_persistence_device_cache[cache_key] = candidate_id
                self.logger.info("Sensor persistence matched device by coreSensorId '%s' -> %s", normalized_core_sensor_id, candidate_id)
                return candidate_id

        create_name = normalized_device_name or f"sensor_{normalized_sensor_type}" or "device"
        metadata = {"createdFrom": "sensor-persistence", "sensorType": normalized_sensor_type}
        if normalized_location:
            metadata["location"] = normalized_location
        if normalized_core_sensor_id:
            metadata["coreSensorId"] = normalized_core_sensor_id

        created = self.core_api.create_device(name=create_name, metadata=metadata)
        created_id = ""
        if isinstance(created, dict):
            created_id = str(created.get("id", "")).strip()
            if not created_id:
                nested = created.get("data")
                if isinstance(nested, dict):
                    created_id = str(nested.get("id", "")).strip()

        if created_id:
            self._sensor_persistence_device_cache[cache_key] = created_id
            self.logger.info("Sensor persistence auto-created device '%s' -> %s", create_name, created_id)
            return created_id

        self.logger.warning("Sensor persistence: failed to create device '%s'", create_name)
        return ""

    def _ensure_persistence_sensor(self, *, device_id, sensor_name, sensor_type, unit, core_sensor_id):
        cache_key = f"{device_id}::{sensor_type}::{sensor_name.lower()}"
        cached_id = str(self._sensor_persistence_sensor_cache.get(cache_key, "")).strip()
        if cached_id:
            self.logger.info(f"Sensor persistence sensor cache hit: {sensor_name} -> {cached_id}")
            return cached_id

        sensors = self.core_api.list_sensors(device_id=device_id)
        for sensor in sensors:
            if not isinstance(sensor, dict):
                continue
            candidate_id = str(sensor.get("id", "")).strip()
            if not candidate_id:
                continue
            candidate_type = str(sensor.get("type", "")).strip().lower()
            candidate_name = str(sensor.get("name", "")).strip().lower()
            metadata = sensor.get("metadata") if isinstance(sensor.get("metadata"), dict) else {}
            candidate_core_id = str(metadata.get("coreSensorId", "")).strip()

            if core_sensor_id and candidate_core_id and candidate_core_id == core_sensor_id:
                self._sensor_persistence_sensor_cache[cache_key] = candidate_id
                self.logger.info(f"Sensor persistence matched by coreSensorId: {sensor_name} -> {candidate_id}")
                return candidate_id
            if candidate_type == sensor_type and candidate_name == sensor_name.lower():
                self._sensor_persistence_sensor_cache[cache_key] = candidate_id
                self.logger.info(f"Sensor persistence matched by name/type: {sensor_name} -> {candidate_id}")
                return candidate_id

        created = self.core_api.create_sensor(
            device_id=device_id,
            name=sensor_name,
            sensor_type=sensor_type,
            unit=unit,
            metadata={
                "createdFrom": "frontend-sensor-reading-persistence",
                "coreSensorId": core_sensor_id,
            },
        )
        sensor_id = str(created.get("id", "")).strip()
        if not sensor_id and isinstance(created.get("data"), dict):
            sensor_id = str(created["data"].get("id", "")).strip()
        if sensor_id:
            self._sensor_persistence_sensor_cache[cache_key] = sensor_id
            self.logger.info(f"Sensor persistence created sensor '{sensor_name}' -> {sensor_id}")
        return sensor_id

    def persist_sensor_reading_from_command(self, command_name, response, command_context=None):
        """
        Persist sensor read responses into device/sensor/sensor_readings tables.
        This keeps statistics backed by actual time-series entities, not only logs.
        """
        if not hasattr(self, "core_api"):
            return
        if not self._is_sensor_read_command(command_name):
            return

        fields = self._extract_sensor_reading_fields(command_name, response, command_context=command_context)
        if not fields:
            self.logger.info(f"Sensor persistence skipped command={command_name}: no plottable fields")
            return

        self.logger.info(
            "Sensor persistence start: command=%s sensorType=%s sensorName=%s deviceName=%s",
            command_name,
            fields["sensor_type"],
            fields["sensor_name"],
            fields["device_name"],
        )

        try:
            device_id = self._ensure_persistence_device(
                device_name=fields["device_name"],
                sensor_type=fields["sensor_type"],
                location_name=fields.get("location", ""),
                core_sensor_id=fields.get("core_sensor_id", ""),
            )
            if not device_id:
                self.logger.warning(
                    "Sensor persistence skipped: unresolved DB device for command=%s sensorType=%s sensorName=%s",
                    command_name,
                    fields["sensor_type"],
                    fields["sensor_name"],
                )
                return

            sensor_id = self._ensure_persistence_sensor(
                device_id=device_id,
                sensor_name=fields["sensor_name"],
                sensor_type=fields["sensor_type"],
                unit=fields["unit"],
                core_sensor_id=fields["core_sensor_id"],
            )
            if not sensor_id:
                return

            created = self.core_api.create_sensor_reading(
                sensor_id=sensor_id,
                value=fields["value"],
                timestamp_iso=fields["timestamp_iso"],
                metadata={
                    "createdFrom": "frontend-sensor-reading-persistence",
                    "command": str(command_name or "").strip(),
                    "sessionId": self.session_id,
                    "location": fields["location"],
                    "coreSensorId": fields["core_sensor_id"],
                    "commandId": fields.get("command_id", ""),
                    "sourcePayload": fields.get("raw_payload", {}),
                    "sensorType": fields["sensor_type"],
                    "sensorName": fields["sensor_name"],
                    "deviceName": fields["device_name"],
                },
            )
            if isinstance(created, dict):
                self.logger.info(
                    "Sensor persistence saved reading: deviceId=%s sensorId=%s value=%s timestamp=%s",
                    device_id,
                    sensor_id,
                    fields["value"],
                    fields["timestamp_iso"],
                )
                self._after_sensor_reading_persisted(device_id=device_id, sensor_id=sensor_id)
        except Exception as error:
            self.logger.warning(f"Failed to persist sensor reading from command: {error}")

    def _after_sensor_reading_persisted(self, *, device_id="", sensor_id=""):
        if not hasattr(self, "statisticsDeviceCombo"):
            return

        try:
            self._schedule_statistics_auto_reload()
        except Exception as error:
            self.logger.warning(
                "Failed to schedule statistics reload after persistence for "
                "device=%s, sensor=%s: %s",
                device_id,
                sensor_id,
                error,
            )

    def _load_sensor_points_from_user_logs(self, device_id="", from_dt=None, to_dt=None):
        if not hasattr(self, "core_api"):
            return [], [], []
        try:
            entries = self.core_api.list_user_logs()
        except Exception as error:
            self.logger.warning(f"Failed to read user logs for statistics fallback: {error}")
            return [], [], []

        points = []
        discovered_device_ids = []
        seen_devices = set()

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                continue

            command_name = payload.get("command") or entry.get("title")
            if not self._is_sensor_read_command(command_name):
                continue

            response_payload = payload.get("response")
            if not isinstance(response_payload, dict):
                response_payload = payload

            inferred_device_id = self._extract_device_id_from_payload(response_payload)
            if inferred_device_id and inferred_device_id not in seen_devices:
                seen_devices.add(inferred_device_id)
                discovered_device_ids.append(inferred_device_id)

            if device_id and inferred_device_id and inferred_device_id != device_id:
                continue

            timestamp = (
                self._extract_timestamp_from_payload(response_payload)
                or self._parse_reading_timestamp(entry.get("createdAt"))
                or self._parse_reading_timestamp(entry.get("created_at"))
            )
            if not timestamp:
                continue
            if from_dt and timestamp < from_dt:
                continue
            if to_dt and timestamp > to_dt:
                continue

            value = self._extract_numeric_value_from_payload(response_payload)
            if value is None:
                continue
            points.append((timestamp.timestamp(), value))

        if points:
            points.sort(key=lambda item: item[0])
            x_values = [item[0] for item in points]
            y_values = [item[1] for item in points]
        else:
            x_values = []
            y_values = []

        self.logger.info(
            "Statistics fallback from user logs: deviceId=%s points=%s discoveredDevices=%s",
            str(device_id or "").strip(),
            len(x_values),
            len(discovered_device_ids),
        )
        return x_values, y_values, discovered_device_ids

    def _update_statistics_time_filters_enabled(self):
        """Toggle From/To controls when loading all device data."""
        use_all_data = bool(
            hasattr(self, "statisticsAllDataCheck") and self.statisticsAllDataCheck.isChecked()
        )
        enable_time_filters = not use_all_data
        for widget_name in (
            "statisticsFromLabel",
            "statisticsFromDateTime",
            "statisticsToLabel",
            "statisticsToDateTime",
        ):
            if hasattr(self, widget_name):
                getattr(self, widget_name).setEnabled(enable_time_filters)

    def _readings_to_points(self, readings):
        """Parse raw reading dicts into sorted (epoch, value) pairs."""
        points = []
        for reading in readings:
            if not isinstance(reading, dict):
                continue
            timestamp = (
                self._parse_reading_timestamp(reading.get("timestamp"))
                or self._parse_reading_timestamp(reading.get("createdAt"))
                or self._parse_reading_timestamp(reading.get("created_at"))
            )
            if not timestamp:
                continue
            value = self._parse_reading_numeric_value(reading)
            if value is None:
                continue
            points.append((timestamp.timestamp(), value))
        points.sort(key=lambda item: item[0])
        return points

    def load_statistics_plot(self, suppress_missing_device_warning=False):
        """Fetch sensor readings for the selected sensor and render interactive plot."""
        if not self.statistics_plot_widget or not self.statistics_curve:
            return
        if not hasattr(self, "core_api"):
            return

        sensor = self._get_selected_sensor()
        if not sensor:
            if not suppress_missing_device_warning:
                StyledMessageDialog.show_warning(
                    self,
                    "Statistics",
                    "Please select a sensor first.",
                )
            return

        sensor_id = sensor["sensor_id"]
        display_name = self.statisticsDeviceCombo.currentText()

        use_all_data = bool(
            hasattr(self, "statisticsAllDataCheck") and self.statisticsAllDataCheck.isChecked()
        )

        from_dt = None
        to_dt = None
        if not use_all_data:
            from_dt = self.statisticsFromDateTime.dateTime().toPyDateTime().astimezone()
            to_dt = self.statisticsToDateTime.dateTime().toPyDateTime().astimezone()
            if from_dt > to_dt:
                StyledMessageDialog.show_warning(
                    self,
                    "Invalid Time Range",
                    "From date-time must be before To date-time.",
                )
                return

        query_kwargs = {"sensor_id": sensor_id, "order": "ASC"}
        if from_dt:
            query_kwargs["from_iso"] = from_dt.isoformat()
        if to_dt:
            query_kwargs["to_iso"] = to_dt.isoformat()

        try:
            self.logger.info("Statistics query: %s", query_kwargs)
            readings = self.core_api.list_sensor_readings(**query_kwargs)
        except Exception as error:
            self._handle_api_exception("Statistics Error", error)
            return

        self.logger.info("Statistics readings fetched: count=%d", len(readings))
        points = self._readings_to_points(readings)
        x_values = [p[0] for p in points]
        y_values = [p[1] for p in points]

        if not x_values:
            self.statistics_curve.setData([], [])
            if use_all_data:
                self.status_label.setText(f"No readings found for {display_name}")
            else:
                self.status_label.setText(f"No readings in time range for {display_name}")
            return

        self.statistics_curve.setData(x_values, y_values)
        unit = str(sensor.get("sensor_type", "")).strip()
        title = f"{display_name} ({unit})" if unit else display_name
        self.statistics_plot_widget.getPlotItem().setTitle(title)
        self.statistics_plot_widget.enableAutoRange(axis="xy", enable=True)
        self.status_label.setText(f"Loaded {len(x_values)} reading(s) for {display_name}")
        self.logger.info("Statistics plot updated: sensor=%s points=%d", display_name, len(x_values))

    def persist_user_log(self, category, title, payload, metadata=None):
        """Persist user-visible event to backend database (best effort)."""
        if not hasattr(self, "core_api"):
            return
        try:
            self.core_api.create_user_log(
                category=str(category or "control"),
                title=str(title or "Event"),
                payload=payload if isinstance(payload, dict) else {"value": str(payload)},
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        except Exception as error:
            self.logger.warning(f"Failed to persist user log: {error}")

    def load_user_logs_from_database(self):
        """Load persisted logs from database into control table only."""
        if not hasattr(self, "core_api"):
            return
        if not self.control_table:
            return

        try:
            entries = self.core_api.list_user_logs()
        except Exception as error:
            self.logger.warning(f"Failed to load user logs: {error}")
            return

        self.control_table.clear_data()
        self.control_history = []

        for entry in reversed(entries):
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category", "")).strip().lower()
            if category != "control":
                continue
            title = str(entry.get("title", "")).strip()
            payload = entry.get("payload", {}) or {}
            metadata = entry.get("metadata", {}) or {}
            timestamp = str(metadata.get("timestamp") or entry.get("createdAt") or "")
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            try:
                ts_dt = datetime.fromisoformat(timestamp) if timestamp else None
            except ValueError:
                ts_dt = None
            display_time = ts_dt.astimezone().strftime("%H:%M:%S") if ts_dt else "-"

            command = str(payload.get("command", title or "command"))
            status = str(payload.get("status", "OK"))
            result = str(payload.get("result", ""))
            response = payload.get("response", {})
            cached = bool(payload.get("cached", False))
            self.control_history.append(
                {
                    "timestamp": display_time,
                    "command": command,
                    "response": response if isinstance(response, dict) else {"result": result},
                    "cached": cached,
                    "error": payload.get("error"),
                }
            )
            self.control_table.add_row([display_time, command, status, result])

    def hide_all_schedule_rows_from_view(self):
        """Hide all currently visible rows from schedule table view."""
        self.hidden_schedule_ids.update(self.schedule_table_rows)
        if self.schedule_table:
            self.schedule_table.clear_data()
        self.schedule_table_rows = []

    def remove_selected_schedule_row_from_view(self, row=None):
        """Hide selected row from schedule table view."""
        schedule_id = None
        if isinstance(row, int) and 0 <= row < len(self.schedule_table_rows):
            schedule_id = self.schedule_table_rows[row]
        else:
            schedule_id = self._get_selected_schedule_id()
        if not schedule_id:
            StyledMessageDialog.show_warning(self, "No Selection", "Select a schedule row to remove.")
            return
        self.hidden_schedule_ids.add(schedule_id)
        self._render_schedule_rows()

    def _remove_selected_control_row(self, row):
        """Remove selected control-table row and keep history mapping aligned."""
        if not self.control_table:
            return
        if not isinstance(row, int) or row < 0 or row >= self.control_table.table.rowCount():
            return
        self.control_table.table.removeRow(row)
        if 0 <= row < len(self.control_history):
            self.control_history.pop(row)

    def _remove_selected_server_row(self, row):
        """Remove selected server-table row and keep history mapping aligned."""
        if not self.server_table:
            return
        if not isinstance(row, int) or row < 0 or row >= self.server_table.table.rowCount():
            return
        self.server_table.table.removeRow(row)
        if 0 <= row < len(self.server_history):
            self.server_history.pop(row)

    def update_custom_delay_enabled(self):
        """Enable custom delay controls only for custom preset."""
        is_custom = False
        if hasattr(self, "scheduleDelayPresetCombo"):
            is_custom = self.scheduleDelayPresetCombo.currentData() == -1

        for spin_name in ("scheduleHoursSpin", "scheduleMinutesSpin", "scheduleSecondsSpin"):
            if hasattr(self, spin_name):
                getattr(self, spin_name).setEnabled(is_custom)

    def get_selected_interval_seconds(self):
        """Resolve one-time delay interval from preset/custom controls."""
        if not hasattr(self, "scheduleDelayPresetCombo"):
            return 60

        preset_value = self.scheduleDelayPresetCombo.currentData()
        if preset_value != -1:
            return int(preset_value or 60)

        hours = self.scheduleHoursSpin.value() if hasattr(self, "scheduleHoursSpin") else 0
        minutes = self.scheduleMinutesSpin.value() if hasattr(self, "scheduleMinutesSpin") else 0
        seconds = self.scheduleSecondsSpin.value() if hasattr(self, "scheduleSecondsSpin") else 0
        return int(hours * 3600 + minutes * 60 + seconds)

    def _build_one_time_cron_expression(self, run_at_local):
        """Build cron expression for a single planned timestamp."""
        return (
            f"{run_at_local.second} "
            f"{run_at_local.minute} "
            f"{run_at_local.hour} "
            f"{run_at_local.day} "
            f"{run_at_local.month} *"
        )

    def _get_or_resolve_schedule_device_id(self, preferred_name="Scheduled Device"):
        if not hasattr(self, "core_api"):
            return None

        devices = self.core_api.list_devices()
        if not devices:
            # Scheduling requires a backend device record; auto-create one if absent.
            created_device = self.core_api.create_device(
                name=preferred_name,
                metadata={"createdFrom": "frontend-scheduling-tab"},
            )
            created_id = ""
            if isinstance(created_device, dict):
                created_id = str(created_device.get("id", "")).strip()
                if not created_id:
                    nested = created_device.get("data")
                    if isinstance(nested, dict):
                        created_id = str(nested.get("id", "")).strip()
            if created_id:
                self.schedule_device_id = created_id
                return self.schedule_device_id
            self.schedule_device_id = None
            return None

        device_ids = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            candidate = device.get("id")
            if candidate is None:
                continue
            device_ids.append(str(candidate))

        if not device_ids:
            self.schedule_device_id = None
            return None

        # Keep cached device only while it's still present for this user.
        if self.schedule_device_id and self.schedule_device_id in device_ids:
            return self.schedule_device_id

        self.schedule_device_id = device_ids[0]
        return self.schedule_device_id

    def schedule_selected_task(self):
        """Create one-time backend-persisted schedule for the selected action."""
        if not hasattr(self, "core_api"):
            self.show_error("Scheduling Error", "Core API client is not available.")
            return

        self._refresh_schedule_targets()
        selected_data = self.scheduleTargetCombo.currentData()
        if not isinstance(selected_data, (tuple, list)) or len(selected_data) != 2:
            self.show_error("Scheduling Error", "Please choose a valid target action.")
            return

        command, parameters = selected_data
        target_label = str(self.scheduleTargetCombo.currentText())
        interval_seconds = self.get_selected_interval_seconds()
        if interval_seconds <= 0:
            self.show_error("Invalid Interval", "Recurring interval must be greater than zero.")
            return

        try:
            device_id = self._get_or_resolve_schedule_device_id(preferred_name=target_label)
            if not device_id:
                self.show_error("Scheduling Error", "No device is available. Create a device first.")
                return

            run_at_local = datetime.now().astimezone() + timedelta(seconds=interval_seconds)
            cron_expression = self._build_one_time_cron_expression(run_at_local)
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            schedule_name = f"{target_label} at {run_at_local.strftime('%Y-%m-%d %H:%M:%S')}"[:120]
            payload = dict(parameters) if isinstance(parameters, dict) else {}
            metadata = {
                "sessionId": self.session_id,
                "createdFrom": "frontend-scheduling-tab",
                "intervalSeconds": interval_seconds,
                "runAt": run_at_local.isoformat(),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "scheduleStatus": "pending",
                "scheduleMode": "one_time",
                "oneTime": True,
            }
            created = self.core_api.create_schedule(
                device_id=device_id,
                name=schedule_name,
                cron_expression=cron_expression,
                action=command,
                payload=payload,
                enabled=True,
                metadata=metadata,
                schedule_mode="one_time",
            )
            schedule_id = ""
            if isinstance(created, dict):
                schedule_id = str(created.get("id", "")).strip()[:8]
                if not schedule_id:
                    nested = created.get("data")
                    if isinstance(nested, dict):
                        schedule_id = str(nested.get("id", "")).strip()[:8]
            schedule_label = schedule_id or "created"
            self.status_label.setText(f"🗓️ One-time task {schedule_label} scheduled for {target_label}")
            self.refresh_schedule_table()
        except Exception as error:
            self._handle_api_exception("Scheduling Error", error)

    def _get_selected_schedule_id(self):
        if not self.schedule_table:
            return None
        selected_row = self.schedule_table.table.currentRow()
        if selected_row < 0:
            return None
        if selected_row >= len(self.schedule_table_rows):
            return None
        return self.schedule_table_rows[selected_row]

    def _get_schedule_by_id(self, schedule_id):
        for schedule in self.schedule_rows:
            if isinstance(schedule, dict) and str(schedule.get("id", "")) == str(schedule_id):
                return schedule
        return None

    def cancel_selected_schedule(self):
        """Mark selected schedule as canceled."""
        if not hasattr(self, "core_api"):
            self.show_error("Scheduling Error", "Core API client is not available.")
            return

        schedule_id = self._get_selected_schedule_id()
        if not schedule_id:
            StyledMessageDialog.show_warning(self, "No Selection", "Select a schedule row to delete.")
            return

        try:
            schedule = self._get_schedule_by_id(schedule_id) or {}
            metadata = dict(schedule.get("metadata") or {})
            metadata["scheduleStatus"] = "canceled"
            metadata["canceledAt"] = datetime.now(timezone.utc).isoformat()
            self.core_api.update_schedule(
                schedule_id,
                {
                    "enabled": False,
                    "metadata": metadata,
                },
            )
            self.refresh_schedule_table()
            self.status_label.setText(f"🚫 Canceled task {str(schedule_id)[:8]}")
        except Exception as error:
            self._handle_api_exception("Scheduling Error", error)

    def clear_all_schedules(self):
        """Cancel all pending schedules visible to current user context."""
        if not hasattr(self, "core_api"):
            self.show_error("Scheduling Error", "Core API client is not available.")
            return

        confirmation = StyledMessageDialog.ask_yes_no(
            self,
            "Delete All Schedules",
            "Cancel all pending schedules for the current user?",
            yes_text="Yes",
            no_text="No",
        )
        if not confirmation:
            return

        try:
            schedules = self.core_api.list_schedules()
            schedule_ids = []
            schedule_map = {}
            for schedule in schedules:
                if not isinstance(schedule, dict):
                    continue
                sid = str(schedule.get("id", "")).strip()
                if not sid:
                    continue
                metadata = dict(schedule.get("metadata") or {})
                status = str(metadata.get("scheduleStatus", "pending")).strip().lower()
                enabled = bool(schedule.get("enabled", False))
                if enabled or status == "pending":
                    schedule_ids.append(sid)
                    schedule_map[sid] = schedule

            if not schedule_ids:
                self.status_label.setText("ℹ️ No pending schedules to cancel")
                return

            canceled = 0
            errors = []
            for schedule_id in schedule_ids:
                try:
                    schedule = schedule_map.get(schedule_id) or {}
                    metadata = dict(schedule.get("metadata") or {})
                    metadata["scheduleStatus"] = "canceled"
                    metadata["canceledAt"] = datetime.now(timezone.utc).isoformat()
                    self.core_api.update_schedule(
                        schedule_id,
                        {
                            "enabled": False,
                            "metadata": metadata,
                        },
                    )
                    canceled += 1
                except Exception as error:
                    errors.append(f"{schedule_id[:8]}: {error}")

            self.refresh_schedule_table()
            if errors:
                summary = "\n".join(errors[:5])
                self.show_error(
                    "Scheduling Error",
                    f"Canceled {canceled} schedule(s), but some failed:\n{summary}",
                )
            else:
                self.status_label.setText(f"🧹 Canceled {canceled} pending schedule(s)")
        except Exception as error:
            self._handle_api_exception("Scheduling Error", error)

    def refresh_schedule_table(self):
        """Render backend schedules into the schedule table."""
        if not self.schedule_table or not hasattr(self, "core_api"):
            return

        selected_row = self.schedule_table.table.currentRow()
        selected_schedule_id = None
        if 0 <= selected_row < len(self.schedule_table_rows):
            selected_schedule_id = self.schedule_table_rows[selected_row]

        try:
            schedules = self.core_api.list_schedules()
        except Exception as error:
            if isinstance(error, UnauthorizedError):
                self.handle_unauthorized_error(str(error))
                return
            self.logger.error(f"Failed to refresh schedules: {error}")
            return

        self.schedule_rows = schedules
        self._render_schedule_rows(preferred_selected_id=selected_schedule_id)

    def _render_schedule_rows(self, preferred_selected_id=None):
        """Render cached schedules into the user-friendly one-time schedule table."""
        if not self.schedule_table:
            return

        selected_schedule_id = preferred_selected_id
        if selected_schedule_id is None:
            selected_row = self.schedule_table.table.currentRow()
            if 0 <= selected_row < len(self.schedule_table_rows):
                selected_schedule_id = self.schedule_table_rows[selected_row]

        self.schedule_table_rows = []
        self.schedule_table.clear_data()

        for schedule in self.schedule_rows:
            if not isinstance(schedule, dict):
                continue

            schedule_id = str(schedule.get("id", ""))
            action = str(schedule.get("action", ""))
            cron_expression = str(schedule.get("cronExpression", ""))
            enabled = bool(schedule.get("enabled", False))
            metadata = schedule.get("metadata", {}) or {}
            payload = schedule.get("payload", {}) or {}
            parameters = payload if isinstance(payload, dict) else {}

            task_label = self._format_schedule_target_label(action, parameters)
            started_at = self._format_schedule_start_time(schedule, metadata)
            ended_at = self._format_schedule_end_time(metadata)
            status = self._format_schedule_status(enabled, metadata)
            time_remaining = self._format_schedule_time_remaining(schedule, cron_expression, enabled, metadata, status)

            if status == "completed":
                continue
            if schedule_id in self.hidden_schedule_ids:
                continue
            if not self._is_schedule_visible_for_current_login(schedule, metadata):
                continue

            self.schedule_table_rows.append(schedule_id)
            self.schedule_table.add_row([task_label, time_remaining, started_at, ended_at, status])

        if selected_schedule_id:
            try:
                selected_index = self.schedule_table_rows.index(selected_schedule_id)
                self.schedule_table.table.selectRow(selected_index)
            except ValueError:
                pass

    def _parse_datetime(self, value):
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _format_local_datetime(self, dt):
        if not dt:
            return "-"
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def _format_duration(self, seconds):
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _resolve_interval_seconds(self, schedule, cron_expression, metadata):
        interval_value = metadata.get("intervalSeconds")
        try:
            interval = int(interval_value)
            if interval > 0:
                return interval
        except (TypeError, ValueError):
            pass

        expression = str(cron_expression or "").strip()
        if expression.startswith("*/") and expression.endswith(" * * * * *"):
            chunk = expression.split(" ")[0]
            try:
                seconds = int(chunk.replace("*/", ""))
                return seconds if seconds > 0 else None
            except ValueError:
                return None
        if expression.startswith("0 */") and expression.endswith(" * * * *"):
            chunk = expression.split(" ")[1]
            try:
                minutes = int(chunk.replace("*/", ""))
                return minutes * 60 if minutes > 0 else None
            except ValueError:
                return None
        if expression.startswith("0 0 */") and expression.endswith(" * * *"):
            chunk = expression.split(" ")[2]
            try:
                hours = int(chunk.replace("*/", ""))
                return hours * 3600 if hours > 0 else None
            except ValueError:
                return None
        return None

    def _resolve_run_at(self, schedule, cron_expression, metadata):
        run_at = self._parse_datetime(metadata.get("runAt"))
        if run_at:
            return run_at

        created_at = (
            self._parse_datetime(metadata.get("createdAt"))
            or self._parse_datetime(schedule.get("createdAt"))
            or self._parse_datetime(schedule.get("created_at"))
        )
        interval_seconds = self._resolve_interval_seconds(schedule, cron_expression, metadata)
        if created_at and interval_seconds:
            return created_at + timedelta(seconds=interval_seconds)
        return None

    def _format_schedule_start_time(self, schedule, metadata):
        start_dt = self._resolve_run_at(schedule, str(schedule.get("cronExpression", "")), metadata)
        return self._format_local_datetime(start_dt)

    def _format_schedule_end_time(self, metadata):
        ended_raw = (
            metadata.get("completedAt")
            or metadata.get("failedAt")
            or metadata.get("canceledAt")
            or metadata.get("lastDispatchedAt")
        )
        return self._format_local_datetime(self._parse_datetime(ended_raw))

    def _format_schedule_status(self, enabled, metadata):
        status = str(metadata.get("scheduleStatus", "")).strip().lower()
        if status in {"pending", "completed", "canceled", "not_done"}:
            return status.replace("_", " ")
        if enabled:
            return "pending"
        dispatch_status = str(metadata.get("lastDispatchStatus", "")).strip().lower()
        if dispatch_status == "completed":
            return "completed"
        if dispatch_status == "failed":
            return "not done"
        return "canceled"

    def _format_schedule_time_remaining(self, schedule, cron_expression, enabled, metadata, status):
        if status in {"completed", "canceled", "not done"}:
            return "-"
        if not enabled:
            return "-"

        run_at = self._resolve_run_at(schedule, cron_expression, metadata)
        if not run_at:
            return "-"

        now = datetime.now(timezone.utc)
        seconds_left = int((run_at - now).total_seconds())
        if seconds_left <= 0:
            return "Running..."
        return self._format_duration(seconds_left)

    def _is_schedule_visible_for_current_login(self, schedule, metadata):
        if self.include_historical_user_data:
            return True
        if not self.schedule_visibility_cutoff_utc:
            return True

        created_at = (
            self._parse_datetime(metadata.get("createdAt"))
            or self._parse_datetime(schedule.get("createdAt"))
            or self._parse_datetime(schedule.get("created_at"))
        )
        if not created_at:
            return False
        return created_at >= self.schedule_visibility_cutoff_utc

    def _format_schedule_target_label(self, action, parameters):
        if action == "read_sensor":
            sensor = parameters.get("sensor", "sensor")
            return f"Read {sensor}"
        if action == "switch_water_canal":
            return "Toggle water canal"
        if action == "switch_fan":
            return "Toggle fan"
        if action == "switch_heater":
            return "Toggle heater"
        if action == "switch_actuator":
            return "Toggle actuator"
        return action

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
