import sys
import uuid
import logging
import os
from datetime import datetime

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
from modules.scheduler_service import SchedulerService
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
        self.schedule_table_rows = []  # Maps schedule table row index -> task_id
        
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
        self.scheduler_service = None
        self.schedule_clock_timer = None

        # Ensure layouts are properly set up
        self._ensure_layouts_initialized()

        # Force find containers if they weren't found
        self._find_containers()

        # Setup tables after UI is loaded
        self.setup_tables()

        # Setup scheduling service and controls
        self.setup_scheduler()

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

        # Scheduling Tab - One-time task controls
        if hasattr(self, "scheduleTaskButton"):
            self.scheduleTaskButton.clicked.connect(self.schedule_selected_task)
        if hasattr(self, "scheduleDelayPresetCombo"):
            self.scheduleDelayPresetCombo.currentIndexChanged.connect(self.update_custom_delay_enabled)

    def apply_styles(self):
        """Apply custom styles if needed (UI file already has styles)"""
        # The UI file already contains styles, but we can override specific widgets if needed
        # For example, update connection status and status label styles dynamically
        pass

    def configure_core_server_buttons(self):
        """Retitle existing server-tab buttons for greenhouse core controls."""
        server_labels = {
            "healthButton": "Core Status",
            "refreshButton": "Refresh Snapshot",
            "statsButton": "Getter Schema",
            "sessionsButton": "Executor Schema",
            "cacheKeysButton": "Getters",
            "queuesButton": "Executors",
            "clearCacheButton": "Set Mode",
            "testCommandButton": "Executor ON",
            "logFilesButton": "Executor OFF",
            "viewLogButton": "Executor SET",
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
            "cancelScheduledButton",   # local-only scheduler operation
            "clearScheduledButton",    # local-only scheduler operation
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

        # Setup scheduling table
        if hasattr(self, 'schedule_output_container') and self.schedule_output_container:
            schedule_layout = self.schedule_output_container.layout()
            if not schedule_layout:
                schedule_layout = QVBoxLayout()
                schedule_layout.setContentsMargins(0, 0, 0, 0)
                schedule_layout.setSpacing(0)
                self.schedule_output_container.setLayout(schedule_layout)

            self.schedule_output_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.schedule_output_container.setMinimumSize(1200, 300)
            self.schedule_output_container.setVisible(True)
            self.schedule_output_container.show()

            self.schedule_table = SimpleDataTable(
                columns=['Task ID', 'Target', 'Run At', 'Delay', 'Remaining', 'Status'],
                parent=self.schedule_output_container
            )
            self.schedule_table.setVisible(True)
            self.schedule_table.show()
            self.schedule_table.setMinimumSize(1200, 250)
            schedule_layout.addWidget(self.schedule_table, 1)
            self.schedule_table.table.setToolTip("Scheduled tasks are displayed here with live status updates.")

            schedule_hint = QLabel("Tip: use preset delay or switch to Custom and set hours/minutes/seconds.")
            schedule_hint.setObjectName("scheduleTableHintLabel")
            schedule_hint.setStyleSheet("color: #666666; font-size: 11px; margin-top: 4px;")
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
        """Initialize scheduling controls and scheduler service."""
        if not hasattr(self, "scheduleTargetCombo") or not hasattr(self, "scheduleDelayPresetCombo"):
            self.logger.warning("Scheduling controls not present in UI")
            return

        self.scheduleTargetCombo.clear()
        self.scheduleTargetCombo.addItem("🌬️ Read CO2", ("read_sensor", {"sensor": "co2"}))
        self.scheduleTargetCombo.addItem("🚰 Toggle Water Canal", ("switch_water_canal", {"action": "toggle"}))
        self.scheduleTargetCombo.addItem("🌀 Toggle Fan", ("switch_fan", {"fanId": "fan_1", "action": "toggle"}))
        self.scheduleTargetCombo.addItem("🔥 Toggle Heater", ("switch_heater", {"heaterId": "heater_1", "action": "toggle"}))
        self.scheduleTargetCombo.addItem("⚙️ Toggle Actuator", ("switch_actuator", {"actuatorId": "actuator_1", "action": "toggle"}))

        self.scheduleDelayPresetCombo.clear()
        self.scheduleDelayPresetCombo.addItem("Now", 0)
        self.scheduleDelayPresetCombo.addItem("15 minutes", 15 * 60)
        self.scheduleDelayPresetCombo.addItem("30 minutes", 30 * 60)
        self.scheduleDelayPresetCombo.addItem("1 hour", 60 * 60)
        self.scheduleDelayPresetCombo.addItem("Custom (hh:mm:ss)", -1)
        self.scheduleDelayPresetCombo.setCurrentIndex(0)

        self.scheduler_service = SchedulerService(
            execute_callback=self.execute_scheduled_command,
            timer_parent=self,
            on_task_change=self.on_scheduled_task_changed,
        )
        self.schedule_clock_timer = QTimer(self)
        self.schedule_clock_timer.timeout.connect(self.update_schedule_live_time)
        self.schedule_clock_timer.start(1000)

        self.update_custom_delay_enabled()
        self.update_schedule_live_time()
        self.refresh_schedule_table()

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

    def get_selected_delay_seconds(self):
        """Resolve delay from preset/custom controls."""
        if not hasattr(self, "scheduleDelayPresetCombo"):
            return 0

        preset_value = self.scheduleDelayPresetCombo.currentData()
        if preset_value != -1:
            return int(preset_value or 0)

        hours = self.scheduleHoursSpin.value() if hasattr(self, "scheduleHoursSpin") else 0
        minutes = self.scheduleMinutesSpin.value() if hasattr(self, "scheduleMinutesSpin") else 0
        seconds = self.scheduleSecondsSpin.value() if hasattr(self, "scheduleSecondsSpin") else 0
        return int(hours * 3600 + minutes * 60 + seconds)

    def schedule_selected_task(self):
        """Create one-time scheduled task for the selected action."""
        if not self.scheduler_service:
            self.show_error("Scheduling Error", "Scheduler service is not available.")
            return

        selected_data = self.scheduleTargetCombo.currentData()
        if not selected_data or len(selected_data) != 2:
            self.show_error("Scheduling Error", "Please choose a valid target action.")
            return

        delay_seconds = self.get_selected_delay_seconds()
        if delay_seconds < 0:
            self.show_error("Invalid Delay", "Delay cannot be negative.")
            return
        if self.scheduleDelayPresetCombo.currentData() == -1 and delay_seconds == 0:
            self.show_error("Invalid Delay", "Custom delay must be greater than zero.")
            return

        command, parameters = selected_data
        target_label = self.scheduleTargetCombo.currentText()

        task = self.scheduler_service.schedule_once(
            target_label=target_label,
            command=command,
            parameters=parameters,
            delay_seconds=delay_seconds,
        )
        self.refresh_schedule_table()
        self.status_label.setText(f"🗓️ Scheduled task {task.task_id[:8]} for {target_label}")

    def execute_scheduled_command(self, command, parameters):
        """Execution callback used by SchedulerService."""
        self.logger.info(f"Executing scheduled task command: {command}")
        return self.send_user_command(command, parameters)

    def on_scheduled_task_changed(self, task):
        """React to task state changes from scheduler service."""
        self.logger.info(f"Scheduled task {task.task_id} status changed to {task.status}")
        self.refresh_schedule_table()

        if task.status == "running":
            self.status_label.setText(f"⏳ Running scheduled task {task.task_id[:8]}...")
        elif task.status == "completed":
            self.status_label.setText(f"✅ Scheduled task {task.task_id[:8]} completed")
        elif task.status == "failed":
            self.status_label.setText(f"❌ Scheduled task {task.task_id[:8]} failed")

    def refresh_schedule_table(self):
        """Render all scheduled tasks into the schedule table."""
        if not self.schedule_table or not self.scheduler_service:
            return

        selected_row = self.schedule_table.table.currentRow()
        selected_task_id = None
        if 0 <= selected_row < len(self.schedule_table_rows):
            selected_task_id = self.schedule_table_rows[selected_row]

        tasks = self.scheduler_service.list_tasks()
        self.schedule_table_rows = [task.task_id for task in tasks]
        self.schedule_table.clear_data()

        for task in tasks:
            run_at = task.run_at.strftime("%Y-%m-%d %H:%M:%S")
            delay_text = self._format_delay(task.delay_seconds)
            remaining_text = self._format_remaining(task)
            self.schedule_table.add_row([
                task.task_id[:8],
                task.target_label,
                run_at,
                delay_text,
                remaining_text,
                task.status,
            ])

        if selected_task_id:
            try:
                selected_index = self.schedule_table_rows.index(selected_task_id)
                self.schedule_table.table.selectRow(selected_index)
            except ValueError:
                pass

    def _format_delay(self, total_seconds):
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_remaining(self, task):
        if task.status == "pending":
            remaining = max(0, int((task.run_at - datetime.now()).total_seconds()))
            return self._format_delay(remaining)
        if task.status == "running":
            return "running..."
        if task.status == "completed":
            return "done"
        if task.status == "failed":
            return "failed"
        if task.status == "cancelled":
            return "cancelled"
        return "-"

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
        if self.scheduler_service:
            self.scheduler_service.shutdown()
        if self.redis_edge_client:
            self.redis_edge_client.disconnect()
        event.accept()
