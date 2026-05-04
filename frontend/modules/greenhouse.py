import uuid
import logging
import os

from PyQt5.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
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
from modules.greenhouse_auth_mixin import GreenhouseAuthMixin
from modules.greenhouse_statistics_mixin import GreenhouseStatisticsMixin
from modules.greenhouse_scheduling_mixin import GreenhouseSchedulingMixin
from modules.greenhouse_logic_mixin import GreenhouseLogicMixin
from modules.auth_session import AuthSessionManager
from modules.localization import IRetranslatable, tr_key
from modules.localization.language_switcher import LanguageSwitcherWidget
from modules.localization.localization_keys import (
    App,
    CommandStatus,
    Connection,
    Empty,
    Hints,
    Session,
    Status,
    TableColumns,
    Tabs,
)
from modules.localization.ui_text_map import MAIN_WINDOW_TEXT_MAP, apply_ui_text_map


class GreenhouseDesktop(
    QMainWindow,
    GreenhouseAuthMixin,
    GreenhouseStatisticsMixin,
    GreenhouseSchedulingMixin,
    GreenhouseLogicMixin,
    CommandPanelMixin,
    ServerPanelMixin,
    EdgeFogMixin,
    IRetranslatable,
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
        self.language_switcher = None
        # History for detailed views
        self.control_history = []
        self.server_history = []
        self.schedule_table_rows = []
        self.schedule_rows = []
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

        # Dynamic-text state used by retranslate_ui to re-render runtime strings.
        self._status_state = (Status.READY, {})

        from modules.config import config
        self.backend_url = config.BACKEND_URL

        self.edge_aggregator = EdgeToFogAggregator()
        self.redis_edge_client = RedisEdgeClient()

        self.theme = GreenhouseTheme()
        self.styler = StyleSheetGenerator(self.theme)

        self.logger = logging.getLogger('GreenhouseDesktop')
        self.logger.info(f"Starting application with session ID: {self.session_id}")
        self.logger.info(f"Backend URL: {self.backend_url}")

        self.setupUI()
        self.setup_auth_controls()
        self._install_language_switcher()

        self.add_functions()
        self.setup_core_panel()
        self.setup_scheduler()
        self.setup_statistics_tab()
        self.setup_logic_tab()
        self.remove_unused_core_controls()

        self.setup_command_worker()
        self.setup_edge_aggregator()

        self.apply_styles()
        self.init_localization()
        self._prompt_restore_user_data_preference()

    def setupUI(self):
        """Load UI from .ui file in frontend directory"""
        frontend_dir = os.path.dirname(os.path.dirname(__file__))
        ui_path = os.path.join(frontend_dir, 'front.ui')

        if not os.path.exists(ui_path):
            error_msg = f"UI file not found at: {ui_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        self.logger.info(f"Loading UI from: {ui_path}")
        uic.loadUi(ui_path, self)

        self.session_label.setText(self.session_id[:8] + "...")

        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_all_status)

        self.control_table = None
        self.schedule_table = None
        self.server_table = None
        self.schedule_clock_timer = None

        self._ensure_layouts_initialized()
        self._find_containers()
        self.setup_tables()
        self._setup_layout_stretch()

    def _setup_layout_stretch(self):
        if hasattr(self, "mainLayout") and self.mainLayout:
            self.mainLayout.setStretch(1, 1)

    def _install_language_switcher(self):
        """Add the flag switcher to the top-right of `sessionLayout`."""
        if not hasattr(self, "sessionLayout") or not self.sessionLayout:
            return
        if self.language_switcher is not None:
            return
        self.language_switcher = LanguageSwitcherWidget(self)
        self.sessionLayout.addWidget(self.language_switcher)

    def add_functions(self):
        """Setup signal connections and functionality"""
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

        if hasattr(self, 'auto_refresh'):
            self.auto_refresh.toggled.connect(self.toggle_auto_refresh)

        if hasattr(self, "scheduleTaskButton"):
            self.scheduleTaskButton.clicked.connect(self.schedule_selected_task)
        if hasattr(self, "cancelScheduledButton"):
            self.cancelScheduledButton.clicked.connect(self.cancel_selected_schedule)
        if hasattr(self, "clearScheduledButton"):
            self.clearScheduledButton.clicked.connect(self.clear_all_schedules)
        if hasattr(self, "scheduleDelayCheck"):
            self.scheduleDelayCheck.toggled.connect(self.update_schedule_timing_controls)
        if hasattr(self, "scheduleFixedTimeCheck"):
            self.scheduleFixedTimeCheck.toggled.connect(self.update_schedule_timing_controls)
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
        pass

    def remove_unused_core_controls(self):
        unused_buttons = (
            "statusButton",
            "pathButton",
        )
        for widget_name in unused_buttons:
            if hasattr(self, widget_name):
                button = getattr(self, widget_name)
                button.setVisible(False)
                button.setEnabled(False)

    def _find_containers(self):
        if hasattr(self, 'server_info_scroll') and self.server_info_scroll:
            container = self.server_info_scroll.widget()
            if container:
                self.server_info_container = container
                self.logger.info("Found server_info_container")
        else:
            self.logger.warning("server_info_scroll not found in UI")

        if not hasattr(self, 'user_output_container') or not self.user_output_container:
            self.logger.error("user_output_container not found in UI!")

    def _ensure_layouts_initialized(self):
        """Ensure tab containers have a zero-margin column layout (front.ui usually provides one)."""
        for attr in (
            "user_output_container",
            "server_info_container",
            "schedule_output_container",
        ):
            if not hasattr(self, attr):
                continue
            widget = getattr(self, attr)
            if not widget:
                continue
            layout = widget.layout()
            if layout is None:
                layout = QVBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                widget.setLayout(layout)
            else:
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
            widget.setVisible(True)

    def setup_tables(self):
        """Initialize simple table widgets for displaying RabbitMQ + server data"""
        if not hasattr(self, "userTabLayout") or not self.userTabLayout:
            self.logger.error("Cannot setup control table - userTabLayout not found")
            return

        self.control_table = SimpleDataTable(
            columns=[
                tr_key(TableColumns.TIMESTAMP),
                tr_key(TableColumns.COMMAND),
                tr_key(TableColumns.STATUS),
            ],
            parent=self.userTab,
            show_clear_button=True,
            on_clear_requested=self.clear_control_table,
            on_remove_selected_requested=self._remove_selected_control_row,
        )
        # Internal column key tokens used for locale-independent semantic styling.
        self.control_table.set_column_role_tokens(["timestamp", "command", "status"])
        self.control_table.set_column_keys([
            TableColumns.TIMESTAMP,
            TableColumns.COMMAND,
            TableColumns.STATUS,
        ])
        control_insert_index = self.userTabLayout.count()
        if hasattr(self, "user_output_container") and self.user_output_container:
            existing_index = self.userTabLayout.indexOf(self.user_output_container)
            if existing_index >= 0:
                control_insert_index = existing_index
                self.userTabLayout.removeWidget(self.user_output_container)
                self.user_output_container.setVisible(False)
                self.user_output_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.userTabLayout.insertWidget(control_insert_index, self.control_table, 1)
        self.control_table.table.cellDoubleClicked.connect(self.show_control_details)
        self.control_table.table.itemSelectionChanged.connect(self._on_control_table_selection_changed)

        control_connection_row = QHBoxLayout()
        control_connection_row.setContentsMargins(0, 0, 0, 0)
        self.control_connection_banner = QLabel("")
        self.control_connection_banner.setObjectName("controlConnectionBanner")
        self.retry_connection_button = QPushButton("")
        self.retry_connection_button.setObjectName("retryConnectionButton")
        self.retry_connection_button.clicked.connect(self.retry_connection_now)
        control_connection_row.addWidget(self.control_connection_banner, 0, Qt.AlignLeft)
        control_connection_row.addWidget(self.retry_connection_button, 0, Qt.AlignLeft)
        control_connection_row.addStretch(1)
        self.userTabLayout.insertLayout(control_insert_index + 1, control_connection_row)

        control_actions = QHBoxLayout()
        control_actions.setContentsMargins(0, 0, 0, 0)
        self.view_control_details_button = QPushButton("")
        self.view_control_details_button.setObjectName("viewControlDetailsButton")
        self.view_control_details_button.setEnabled(False)
        self.view_control_details_button.clicked.connect(self.view_selected_control_details)
        control_actions.addWidget(self.view_control_details_button, 0, Qt.AlignLeft)
        control_actions.addStretch(1)
        self.userTabLayout.insertLayout(control_insert_index + 2, control_actions)

        self.control_hint_label = QLabel("")
        self.control_hint_label.setObjectName("controlTableHintLabel")
        self.userTabLayout.insertWidget(control_insert_index + 3, self.control_hint_label, 0)

        self.control_empty_state_label = QLabel("")
        self.control_empty_state_label.setObjectName("controlEmptyStateLabel")
        self.userTabLayout.insertWidget(control_insert_index + 4, self.control_empty_state_label, 0)

        self._on_control_table_selection_changed()
        self._update_connection_banner()

        self.logger.info(f"Control table created: visible={self.control_table.isVisible()}")

        if hasattr(self, "schedulingTabLayout") and self.schedulingTabLayout:
            self.schedule_table = SimpleDataTable(
                columns=[
                    tr_key(TableColumns.TASK),
                    tr_key(TableColumns.TIME_REMAINING),
                    tr_key(TableColumns.STARTS_AT),
                    tr_key(TableColumns.ENDS_AT),
                    tr_key(TableColumns.STATUS),
                ],
                parent=self.schedulingTab,
                show_clear_button=True,
                on_clear_requested=self.hide_all_schedule_rows_from_view,
                on_remove_selected_requested=self.remove_selected_schedule_row_from_view,
            )
            self.schedule_table.set_column_role_tokens([
                "task",
                "time_remaining",
                "starts_at",
                "ends_at",
                "status",
            ])
            self.schedule_table.set_column_keys([
                TableColumns.TASK,
                TableColumns.TIME_REMAINING,
                TableColumns.STARTS_AT,
                TableColumns.ENDS_AT,
                TableColumns.STATUS,
            ])
            schedule_insert_index = self.schedulingTabLayout.count()
            if hasattr(self, "schedule_output_container") and self.schedule_output_container:
                existing_index = self.schedulingTabLayout.indexOf(self.schedule_output_container)
                if existing_index >= 0:
                    schedule_insert_index = existing_index
                    self.schedulingTabLayout.removeWidget(self.schedule_output_container)
                    self.schedule_output_container.setVisible(False)
                    self.schedule_output_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

            self.schedulingTabLayout.insertWidget(schedule_insert_index, self.schedule_table, 1)

            self.schedule_hint_label = QLabel("")
            self.schedule_hint_label.setObjectName("scheduleTableHintLabel")
            self.schedulingTabLayout.insertWidget(schedule_insert_index + 1, self.schedule_hint_label, 0)

            self.schedule_empty_state_label = QLabel("")
            self.schedule_empty_state_label.setObjectName("scheduleEmptyStateLabel")
            self.schedulingTabLayout.insertWidget(schedule_insert_index + 2, self.schedule_empty_state_label, 0)
        else:
            self.logger.warning("schedule_output_container not found - scheduling table not created")

        if not hasattr(self, "infoGroupLayout") or not self.infoGroupLayout:
            self.logger.error("Cannot setup server table - infoGroupLayout not found")
            return

        self.server_table = SimpleDataTable(
            columns=[
                tr_key(TableColumns.TIMESTAMP),
                tr_key(TableColumns.TYPE),
                tr_key(TableColumns.DATA),
            ],
            parent=self.infoGroup,
            show_clear_button=True,
            on_clear_requested=self.clear_server_tables,
            on_remove_selected_requested=self._remove_selected_server_row,
        )
        self.server_table.set_column_role_tokens(["timestamp", "type", "status"])
        self.server_table.set_column_keys([
            TableColumns.TIMESTAMP,
            TableColumns.TYPE,
            TableColumns.DATA,
        ])

        server_insert_index = self.infoGroupLayout.count()
        if hasattr(self, "server_info_scroll") and self.server_info_scroll:
            existing_index = self.infoGroupLayout.indexOf(self.server_info_scroll)
            if existing_index >= 0:
                server_insert_index = existing_index
                self.infoGroupLayout.removeWidget(self.server_info_scroll)
                self.server_info_scroll.setVisible(False)
                self.server_info_scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.infoGroupLayout.insertWidget(server_insert_index, self.server_table, 1)

        self.server_table.table.cellDoubleClicked.connect(self.show_server_details)

        self.server_hint_label = QLabel("")
        self.server_hint_label.setObjectName("serverTableHintLabel")
        self.infoGroupLayout.insertWidget(server_insert_index + 1, self.server_hint_label, 0)

        self.server_empty_state_label = QLabel("")
        self.server_empty_state_label.setObjectName("serverEmptyStateLabel")
        self.infoGroupLayout.insertWidget(server_insert_index + 2, self.server_empty_state_label, 0)

        if hasattr(self, "_update_schedule_empty_state"):
            self._update_schedule_empty_state()
        if hasattr(self, "_update_server_empty_state"):
            self._update_server_empty_state()

        self.logger.info(f"Server table created: visible={self.server_table.isVisible()}")

        for i in range(self.userTabLayout.count()):
            item = self.userTabLayout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget_name = widget.objectName()
                if widget_name == 'controlGroup':
                    self.userTabLayout.setStretch(i, 0)
                elif widget_name == 'simpleDataTable':
                    self.userTabLayout.setStretch(i, 1)

        for i in range(self.serverTabLayout.count()):
            item = self.serverTabLayout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget_name = widget.objectName()
                if widget_name == 'serverGroup':
                    self.serverTabLayout.setStretch(i, 0)
                elif widget_name == 'infoGroup':
                    self.serverTabLayout.setStretch(i, 1)

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

    def set_status_state(self, key: str, **params) -> None:
        """Update the bottom status label using a translation key + params.

        Storing the state lets `retranslate_ui()` re-render in the new
        language without losing the current message context.
        """
        self._status_state = (key, dict(params or {}))
        if hasattr(self, "status_label") and self.status_label is not None:
            self.status_label.setText(tr_key(key, **params))

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr_key(App.WINDOW_TITLE))
        apply_ui_text_map(self, MAIN_WINDOW_TEXT_MAP)
        if hasattr(self, "tabWidget") and self.tabWidget:
            tab_keys = [Tabs.CONTROL, Tabs.SCHEDULING, Tabs.SERVER, Tabs.STATISTICS, Tabs.LOGIC]
            for index, key in enumerate(tab_keys):
                if index < self.tabWidget.count():
                    self.tabWidget.setTabText(index, tr_key(key))

        if hasattr(self, "session_label") and self.session_label is not None:
            self.session_label.setToolTip(tr_key(Session.TOOLTIP_BODY, session_id=self.session_id))

        if hasattr(self, "view_control_details_button") and self.view_control_details_button:
            from modules.localization.localization_keys import Controls
            self.view_control_details_button.setText(tr_key(Controls.VIEW_SELECTED_DETAILS))
        if hasattr(self, "control_hint_label") and self.control_hint_label is not None:
            self.control_hint_label.setText(tr_key(Hints.CONTROL_TABLE_USAGE))
        if hasattr(self, "control_empty_state_label") and self.control_empty_state_label is not None:
            self.control_empty_state_label.setText(tr_key(Empty.CONTROL_NO_ACTIONS))
        if self.control_table is not None and hasattr(self.control_table, "table"):
            self.control_table.table.setToolTip(tr_key(Hints.CONTROL_TABLE_TOOLTIP))
        if hasattr(self, "retry_connection_button") and self.retry_connection_button:
            self.retry_connection_button.setText(tr_key(Connection.RETRY_NOW))
        if hasattr(self, "control_connection_banner"):
            self._update_connection_banner()

        if hasattr(self, "schedule_hint_label") and self.schedule_hint_label is not None:
            self.schedule_hint_label.setText(tr_key(Hints.SCHEDULE_COUNTDOWN))
        if hasattr(self, "schedule_empty_state_label") and self.schedule_empty_state_label is not None:
            self.schedule_empty_state_label.setText(tr_key(Empty.SCHEDULE_NONE))
        if self.schedule_table is not None and hasattr(self.schedule_table, "table"):
            self.schedule_table.table.setToolTip(tr_key(Hints.SCHEDULE_TABLE_TOOLTIP))

        if hasattr(self, "server_hint_label") and self.server_hint_label is not None:
            self.server_hint_label.setText(tr_key(Hints.SERVER_DOUBLE_CLICK))
        if hasattr(self, "server_empty_state_label") and self.server_empty_state_label is not None:
            self.server_empty_state_label.setText(tr_key(Empty.SERVER_NONE))
        if self.server_table is not None and hasattr(self.server_table, "table"):
            self.server_table.table.setToolTip(tr_key(Hints.SERVER_TABLE_TOOLTIP))

        for table in (self.control_table, self.schedule_table, self.server_table):
            if table is None:
                continue
            if hasattr(table, "retranslate_ui"):
                table.retranslate_ui()

        if hasattr(self, "scheduleDelayPresetButton") and self.scheduleDelayPresetButton:
            self._refresh_schedule_delay_preset_labels()
        if hasattr(self, "update_schedule_timing_controls"):
            self.update_schedule_timing_controls()
        if hasattr(self, "finalize_schedule_delay_after_localization"):
            self.finalize_schedule_delay_after_localization()

        if hasattr(self, "logicNodePaletteList") and self.logicNodePaletteList:
            self._refresh_logic_palette_labels()

        if hasattr(self, "statisticsRefreshIntervalCombo") and self.statisticsRefreshIntervalCombo:
            self._refresh_statistics_interval_labels()

        if hasattr(self, "statistics_plot_widget") and self.statistics_plot_widget:
            self._retranslate_statistics_chart()

        if hasattr(self, "scheduleCurrentTimeLabel"):
            self.update_schedule_live_time()

        if self.auth_user_label is not None:
            self.update_auth_user_label()
        if self.logoutButton is not None:
            from modules.localization.localization_keys import Common
            self.logoutButton.setText(tr_key(Common.LOGOUT))

        if hasattr(self, "connection_status") and self.connection_status:
            self.update_connection_status(self.rabbitmq_connected)

        if getattr(self, "_status_state", None):
            key, params = self._status_state
            if hasattr(self, "status_label") and self.status_label is not None:
                self.status_label.setText(tr_key(key, **(params or {})))
