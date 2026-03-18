import sys
import uuid
import logging
import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
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
from modules.auth_dialog import AuthDialog
from modules.auth_session import AuthSessionManager
from modules.core_api_client import CoreApiClient, UnauthorizedError

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
        self.remove_unused_core_controls()
        self.configure_core_server_buttons()
        
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
                    return True
                except Exception as error:
                    self.auth_session.clear_token()
                    QMessageBox.warning(
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
            self.schedule_clock_timer.start(5000)

    def handle_unauthorized_error(self, message="Unauthorized"):
        if self._auth_recovery_in_progress:
            return

        self._auth_recovery_in_progress = True
        timer_state = self._pause_authenticated_timers()
        try:
            self.auth_session.clear_token()
            self.update_auth_user_label()
            QMessageBox.warning(
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
        confirm = QMessageBox.question(
            self,
            "Logout",
            "Sign out from this desktop session?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        if self._auth_recovery_in_progress:
            return

        self._auth_recovery_in_progress = True
        timer_state = self._pause_authenticated_timers()
        try:
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
        if not hasattr(self, 'user_output_container') or not self.user_output_container:
            self.logger.error("Cannot setup control table - user_output_container not found")
            return

        layout = self.user_output_container.layout()
        if not layout:
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.user_output_container.setLayout(layout)

        self.user_output_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.user_output_container.setMinimumHeight(320)
        self.user_output_container.setVisible(True)

        self.control_table = SimpleDataTable(
            columns=['Timestamp', 'Command', 'Status', 'Result'],
            parent=self.user_output_container,
            show_clear_button=True
        )
        layout.addWidget(self.control_table, 1)  # Stretch factor 1
        # Double-click on a control row opens detailed view (mixin)
        self.control_table.table.cellDoubleClicked.connect(self.show_control_details)

        # Add a small hint below the control table so users know about double-click
        control_hint = QLabel("Tip: double-click a row in the table to see detailed information.")
        control_hint.setObjectName("controlTableHintLabel")
        layout.addWidget(control_hint, 0)

        # Also set a tooltip on the table itself
        self.control_table.table.setToolTip("Double-click a row to open a detailed view of the result.")

        self.logger.info(f"Control table created: visible={self.control_table.isVisible()}")

        # Setup scheduling table
        if hasattr(self, 'schedule_output_container') and self.schedule_output_container:
            schedule_layout = self.schedule_output_container.layout()
            if not schedule_layout:
                schedule_layout = QVBoxLayout()
                schedule_layout.setContentsMargins(0, 0, 0, 0)
                schedule_layout.setSpacing(0)
                self.schedule_output_container.setLayout(schedule_layout)

            self.schedule_output_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.schedule_output_container.setMinimumHeight(320)
            self.schedule_output_container.setVisible(True)

            self.schedule_table = SimpleDataTable(
                columns=['Schedule ID', 'Target', 'Cron', 'Enabled', 'Last Dispatch', 'Dispatch Status'],
                parent=self.schedule_output_container,
                show_clear_button=True
            )
            schedule_layout.addWidget(self.schedule_table, 1)
            self.schedule_table.table.setToolTip("Backend-persisted schedules are displayed here with live dispatch status.")

            schedule_hint = QLabel("Tip: schedules are persisted in backend and run by cron.")
            schedule_hint.setObjectName("scheduleTableHintLabel")
            schedule_layout.addWidget(schedule_hint, 0)
        else:
            self.logger.warning("schedule_output_container not found - scheduling table not created")

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

        self.server_info_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.server_info_container.setMinimumHeight(320)
        self.server_info_container.setVisible(True)

        self.server_table = SimpleDataTable(
            columns=['Timestamp', 'Type', 'Data'],
            parent=self.server_info_container,
            show_clear_button=True
        )
        layout.addWidget(self.server_table, 1)  # Stretch factor 1
        # Double-click on a server row opens detailed view (mixin)
        self.server_table.table.cellDoubleClicked.connect(self.show_server_details)

        # Add a small hint below the server table for discoverability
        server_hint = QLabel("Tip: double-click a row in the table to see detailed server or fog data.")
        server_hint.setObjectName("serverTableHintLabel")
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

        if hasattr(self, "schedulingTabLayout"):
            for i in range(self.schedulingTabLayout.count()):
                item = self.schedulingTabLayout.itemAt(i)
                if item and item.widget():
                    widget_name = item.widget().objectName()
                    if widget_name == 'scheduleGroup':
                        self.schedulingTabLayout.setStretch(i, 0)
                    elif widget_name == 'schedule_output_container':
                        self.schedulingTabLayout.setStretch(i, 1)

    def setup_scheduler(self):
        """Initialize scheduling controls backed by persistent backend schedules."""
        if not hasattr(self, "scheduleTargetCombo") or not hasattr(self, "scheduleDelayPresetCombo"):
            self.logger.warning("Scheduling controls not present in UI")
            return

        self._refresh_schedule_targets()

        self.scheduleDelayPresetCombo.clear()
        self.scheduleDelayPresetCombo.addItem("Every minute", 60)
        self.scheduleDelayPresetCombo.addItem("Every 15 minutes", 15 * 60)
        self.scheduleDelayPresetCombo.addItem("Every 30 minutes", 30 * 60)
        self.scheduleDelayPresetCombo.addItem("Every 1 hour", 60 * 60)
        self.scheduleDelayPresetCombo.addItem("Custom recurring interval (hh:mm:ss)", -1)
        self.scheduleDelayPresetCombo.setCurrentIndex(0)

        self.schedule_clock_timer = QTimer(self)
        self.schedule_clock_timer.timeout.connect(self.update_schedule_live_time)
        self.schedule_clock_timer.start(5000)

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

            if not command:
                continue

            key = f"{command}:{name.lower()}"
            if key in seen:
                continue
            seen.add(key)
            options.append((f"{label_prefix} {name}", (command, parameters), key))

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
        self.refresh_schedule_table()

    def update_custom_delay_enabled(self):
        """Enable custom delay controls only for custom preset."""
        is_custom = False
        if hasattr(self, "scheduleDelayPresetCombo"):
            is_custom = self.scheduleDelayPresetCombo.currentData() == -1

        for spin_name in ("scheduleHoursSpin", "scheduleMinutesSpin", "scheduleSecondsSpin"):
            if hasattr(self, spin_name):
                getattr(self, spin_name).setEnabled(is_custom)

    def get_selected_interval_seconds(self):
        """Resolve recurring interval from preset/custom controls."""
        if not hasattr(self, "scheduleDelayPresetCombo"):
            return 60

        preset_value = self.scheduleDelayPresetCombo.currentData()
        if preset_value != -1:
            return int(preset_value or 60)

        hours = self.scheduleHoursSpin.value() if hasattr(self, "scheduleHoursSpin") else 0
        minutes = self.scheduleMinutesSpin.value() if hasattr(self, "scheduleMinutesSpin") else 0
        seconds = self.scheduleSecondsSpin.value() if hasattr(self, "scheduleSecondsSpin") else 0
        return int(hours * 3600 + minutes * 60 + seconds)

    def _build_cron_expression(self, interval_seconds):
        """
        Build a recurring cron expression for supported fixed intervals.

        Supported:
        - Every N seconds (1..59)
        - Every N minutes (1..59, second 0)
        - Every N hours (1..23, minute 0, second 0)
        """
        if interval_seconds <= 0:
            raise ValueError("Interval must be greater than zero.")
        if interval_seconds < 60:
            return f"*/{interval_seconds} * * * * *"
        if interval_seconds % 3600 == 0:
            hours = interval_seconds // 3600
            if 1 <= hours <= 23:
                return f"0 0 */{hours} * * *"
        if interval_seconds % 60 == 0:
            minutes = interval_seconds // 60
            if 1 <= minutes <= 59:
                return f"0 */{minutes} * * * *"
        raise ValueError(
            "Unsupported custom interval. Use seconds (1-59), whole minutes (1-59), or whole hours (1-23)."
        )

    def _get_or_resolve_schedule_device_id(self):
        if self.schedule_device_id:
            return self.schedule_device_id
        if not hasattr(self, "core_api"):
            return None

        devices = self.core_api.list_devices()
        if not devices:
            return None

        first_device = devices[0] if isinstance(devices[0], dict) else {}
        device_id = first_device.get("id")
        if device_id:
            self.schedule_device_id = str(device_id)
            return self.schedule_device_id
        return None

    def schedule_selected_task(self):
        """Create recurring backend-persisted schedule for the selected action."""
        if not hasattr(self, "core_api"):
            self.show_error("Scheduling Error", "Core API client is not available.")
            return

        self._refresh_schedule_targets()
        selected_data = self.scheduleTargetCombo.currentData()
        if not selected_data or len(selected_data) != 2:
            self.show_error("Scheduling Error", "Please choose a valid target action.")
            return

        interval_seconds = self.get_selected_interval_seconds()
        if interval_seconds <= 0:
            self.show_error("Invalid Interval", "Recurring interval must be greater than zero.")
            return

        device_id = self._get_or_resolve_schedule_device_id()
        if not device_id:
            self.show_error("Scheduling Error", "No device is available. Create a device first.")
            return

        command, parameters = selected_data
        target_label = str(self.scheduleTargetCombo.currentText())

        try:
            cron_expression = self._build_cron_expression(interval_seconds)
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            schedule_name = f"{target_label} @ {now_text}"
            payload = parameters
            metadata = {
                "sessionId": self.session_id,
                "createdFrom": "frontend-scheduling-tab",
                "intervalSeconds": interval_seconds,
            }
            created = self.core_api.create_schedule(
                device_id=device_id,
                name=schedule_name,
                cron_expression=cron_expression,
                action=command,
                payload=payload,
                enabled=True,
                metadata=metadata,
            )
            schedule_id = str(created.get("id", ""))[:8]
            self.status_label.setText(f"🗓️ Created backend schedule {schedule_id} for {target_label}")
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

    def cancel_selected_schedule(self):
        """Delete currently selected backend schedule."""
        if not hasattr(self, "core_api"):
            self.show_error("Scheduling Error", "Core API client is not available.")
            return

        schedule_id = self._get_selected_schedule_id()
        if not schedule_id:
            QMessageBox.warning(self, "No Selection", "Select a schedule row to delete.")
            return

        try:
            self.core_api.delete_schedule(schedule_id)
            self.refresh_schedule_table()
            self.status_label.setText(f"🗑️ Deleted schedule {str(schedule_id)[:8]}")
        except Exception as error:
            self._handle_api_exception("Scheduling Error", error)

    def clear_all_schedules(self):
        """Delete all backend schedules visible to current user context."""
        if not hasattr(self, "core_api"):
            self.show_error("Scheduling Error", "Core API client is not available.")
            return

        confirmation = QMessageBox.question(
            self,
            "Delete All Schedules",
            "Delete all schedules for the current user?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmation != QMessageBox.Yes:
            return

        try:
            schedules = self.core_api.list_schedules()
            schedule_ids = [
                str(schedule.get("id", ""))
                for schedule in schedules
                if isinstance(schedule, dict) and schedule.get("id")
            ]
            if not schedule_ids:
                self.status_label.setText("ℹ️ No schedules to delete")
                return

            deleted = 0
            errors = []
            for schedule_id in schedule_ids:
                try:
                    self.core_api.delete_schedule(schedule_id)
                    deleted += 1
                except Exception as error:
                    errors.append(f"{schedule_id[:8]}: {error}")

            self.refresh_schedule_table()
            if errors:
                summary = "\n".join(errors[:5])
                self.show_error(
                    "Scheduling Error",
                    f"Deleted {deleted} schedule(s), but some failed:\n{summary}",
                )
            else:
                self.status_label.setText(f"🧹 Deleted {deleted} schedule(s)")
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
        self.schedule_table_rows = []
        self.schedule_table.clear_data()

        for schedule in schedules:
            if not isinstance(schedule, dict):
                continue
            schedule_id = str(schedule.get("id", ""))
            action = str(schedule.get("action", ""))
            cron_expression = str(schedule.get("cronExpression", ""))
            enabled = bool(schedule.get("enabled", False))
            metadata = schedule.get("metadata", {}) or {}
            last_dispatched = metadata.get("lastDispatchedAt", "-")
            dispatch_status = metadata.get("lastDispatchStatus", "pending")
            dispatch_error = metadata.get("lastDispatchError", "")
            if dispatch_error:
                dispatch_status = f"{dispatch_status}: {dispatch_error}"

            payload = schedule.get("payload", {}) or {}
            parameters = payload if isinstance(payload, dict) else {}
            target_label = self._format_schedule_target_label(action, parameters)

            self.schedule_table_rows.append(schedule_id)
            self.schedule_table.add_row([
                schedule_id[:8],
                target_label,
                cron_expression,
                "yes" if enabled else "no",
                str(last_dispatched),
                str(dispatch_status),
            ])

        if selected_schedule_id:
            try:
                selected_index = self.schedule_table_rows.index(selected_schedule_id)
                self.schedule_table.table.selectRow(selected_index)
            except ValueError:
                pass

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
        if self.schedule_clock_timer and self.schedule_clock_timer.isActive():
            self.schedule_clock_timer.stop()
        if self.redis_edge_client:
            self.redis_edge_client.disconnect()
        event.accept()
