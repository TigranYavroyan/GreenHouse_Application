"""
Centralized translation key constants.

Grouped by namespace to avoid typos in call sites and to act as the
single source of truth for what needs to be present in every locale's
JSON file under `frontend/resources/i18n/<lang>.json`.

All values are *keys*, not user-visible strings. They are passed to
`LocalizationManager.get(...)` / `tr_key(...)` which resolves them via
the active language (with English fallback).
"""


class Common:
    OK = "common.ok"
    CANCEL = "common.cancel"
    YES = "common.yes"
    NO = "common.no"
    EXIT = "common.exit"
    DASH = "common.dash"
    NA = "common.na"
    UNKNOWN = "common.unknown"
    APPLY = "common.apply"
    LOAD = "common.load"
    START_FRESH = "common.start_fresh"
    LOGOUT = "common.logout"
    SETTINGS = "common.settings"
    LANGUAGE = "common.language"


class App:
    WINDOW_TITLE = "app.window_title"


class Tabs:
    CONTROL = "tabs.control"
    SCHEDULING = "tabs.scheduling"
    SERVER = "tabs.server"
    STATISTICS = "tabs.statistics"
    LOGIC = "tabs.logic"


class Session:
    TITLE = "session.title"
    TOOLTIP_TITLE = "session.tooltip_title"
    PLACEHOLDER = "session.placeholder"
    TOOLTIP_BODY = "session.tooltip_body"


class Connection:
    CONNECTING = "connection.connecting"
    CONNECTED = "connection.connected"
    RECONNECTING = "connection.reconnecting"
    DISCONNECTED = "connection.disconnected"
    BANNER_DISCONNECTED = "connection.banner_disconnected"
    BANNER_RECONNECTING = "connection.banner_reconnecting"
    RETRY_NOW = "connection.retry_now"


class Controls:
    GROUP_TITLE = "controls.group_title"
    TEMPERATURE = "controls.temperature"
    HUMIDITY = "controls.humidity"
    CO2 = "controls.co2"
    LIGHT = "controls.light"
    SOIL_PH = "controls.soil_ph"
    SOIL_MOISTURE = "controls.soil_moisture"
    FAN = "controls.fan"
    WATER_CANAL = "controls.water_canal"
    ACTUATOR = "controls.actuator"
    HEATER = "controls.heater"
    SYSTEM_STATUS = "controls.system_status"
    VIEW_SELECTED_DETAILS = "controls.view_selected_details"


class Schedule:
    GROUP_TITLE = "schedule.group_title"
    TARGET_ACTION = "schedule.target_action"
    DELAY = "schedule.delay"
    RUN_AT_FIXED = "schedule.run_at_fixed"
    CUSTOM_DELAY = "schedule.custom_delay"
    CUSTOM_HINT = "schedule.custom_hint"
    SCHEDULE_TASK = "schedule.schedule_task"
    CANCEL_SELECTED = "schedule.cancel_selected"
    CLEAR_ALL = "schedule.clear_all"
    CURRENT_TIME = "schedule.current_time"
    NO_DEVICES = "schedule.no_devices"


class ScheduleDelay:
    AFTER_1M = "schedule.delay_preset.after_1m"
    AFTER_15M = "schedule.delay_preset.after_15m"
    AFTER_30M = "schedule.delay_preset.after_30m"
    AFTER_1H = "schedule.delay_preset.after_1h"
    CUSTOM = "schedule.delay_preset.custom"


class ScheduleTargets:
    TOGGLE_WATER_CANAL = "schedule.targets.toggle_water_canal"
    TOGGLE_FAN = "schedule.targets.toggle_fan"
    TOGGLE_HEATER = "schedule.targets.toggle_heater"
    TOGGLE_ACTUATOR = "schedule.targets.toggle_actuator"
    TOGGLE_NAMED = "schedule.targets.toggle_named"
    READ_NAMED = "schedule.targets.read_named"


class ScheduleStatus:
    PENDING = "schedule.status.pending"
    COMPLETED = "schedule.status.completed"
    CANCELED = "schedule.status.canceled"
    NOT_DONE = "schedule.status.not_done"
    RUNNING = "schedule.status.running"


class Server:
    GROUP_TITLE = "server.group_title"
    SYSTEM_HEALTH = "server.system_health"
    REFRESH_ALL_DATA = "server.refresh_all_data"
    SENSOR_TYPES = "server.sensor_types"
    DEVICE_CONTROLS = "server.device_controls"
    SENSOR_READINGS = "server.sensor_readings"
    DEVICE_STATES = "server.device_states"
    CHANGE_DEVICE_MODE = "server.change_device_mode"
    DEVICE_ON = "server.device_on"
    DEVICE_OFF = "server.device_off"
    SET_DEVICE_VALUE = "server.set_device_value"
    AUTO_REFRESH_ENABLED = "server.auto_refresh_enabled"
    AUTO_REFRESH_DISABLED = "server.auto_refresh_disabled"


class ServerData:
    CORE_STATUS = "server.data.core_status"
    GETTER_SCHEMA = "server.data.getter_schema"
    EXECUTOR_SCHEMA = "server.data.executor_schema"
    GETTERS = "server.data.getters"
    EXECUTORS = "server.data.executors"
    SET_MODE = "server.data.set_mode"
    EXECUTOR_ON = "server.data.executor_on"
    EXECUTOR_OFF = "server.data.executor_off"
    EXECUTOR_SET = "server.data.executor_set"


class Statistics:
    GROUP_TITLE = "statistics.group_title"
    DEVICE = "statistics.device"
    SENSOR = "statistics.sensor"
    FROM = "statistics.from"
    TO = "statistics.to"
    ALL_DATA = "statistics.all_data"
    LOAD = "statistics.load"
    REFRESH = "statistics.refresh"
    HINT = "statistics.hint"
    NO_SENSORS = "statistics.no_sensors"
    NO_READINGS = "statistics.no_readings"
    NO_READINGS_IN_RANGE = "statistics.no_readings_in_range"
    LOADED_COUNT = "statistics.loaded_count"


class StatisticsInterval:
    NO_TIMER = "statistics.interval.no_timer"
    ONE_SECOND = "statistics.interval.1s"
    FIVE_SECONDS = "statistics.interval.5s"
    FIFTEEN_SECONDS = "statistics.interval.15s"
    THIRTY_SECONDS = "statistics.interval.30s"


class Charts:
    AXIS_VALUE = "charts.axis_value"
    AXIS_TIME = "charts.axis_time"
    LEGEND_SENSOR = "charts.legend_sensor"
    TITLE_SENSOR = "charts.title_sensor"


class Logic:
    CONTROLS_GROUP = "logic.controls_group"
    ADD_ROOT = "logic.add_root"
    ADD_CONDITION = "logic.add_condition"
    ADD_ACTION = "logic.add_action"
    DELETE_SELECTED = "logic.delete_selected"
    CONNECT_SELECTED = "logic.connect_selected"
    GET_CONFIG = "logic.get_config"
    GENERATE_JSON = "logic.generate_json"
    UPLOAD_NEXT = "logic.upload_next"
    RELOAD_NEXT = "logic.reload_next"
    LOAD_PLACEHOLDER = "logic.load_placeholder"
    VALIDATE_PLACEHOLDER = "logic.validate_placeholder"
    TOOLBOX_GROUP = "logic.toolbox_group"
    TOOLBOX_HINT = "logic.toolbox_hint"
    CANVAS_GROUP = "logic.canvas_group"
    CANVAS_READY = "logic.canvas_ready"
    CANVAS_READY_DEFAULT = "logic.canvas_ready_default"
    PROPERTIES_GROUP = "logic.properties_group"
    TYPE_NONE = "logic.type_none"
    TYPE_VALUE = "logic.type_value"
    TITLE_PLACEHOLDER = "logic.title_placeholder"
    ARGS_PLACEHOLDER = "logic.args_placeholder"
    VALUE_PLACEHOLDER = "logic.value_placeholder"
    ACTION_ENABLED = "logic.action_enabled"
    APPLY_BUTTON = "logic.apply_button"
    VALIDATION_GROUP = "logic.validation_group"
    DELETED_COUNT = "logic.deleted_count"
    SELECT_TWO_NODES = "logic.select_two_nodes"
    SOURCE_TARGET_NOT_FOUND = "logic.source_target_not_found"
    INVALID_CONNECTION = "logic.invalid_connection"
    UPDATED_NODE = "logic.updated_node"
    API_NEXT_STEP = "logic.api_next_step"
    SEED_INFO = "logic.seed_info"
    GENERATE_BLOCKED_BY_ERRORS = "logic.generate_blocked_by_errors"
    GENERATED_SAVED = "logic.generated_saved"
    GENERATE_FAILED = "logic.generate_failed"
    LOAD_CONFIG_DONE = "logic.load_config_done"
    LOAD_CONFIG_FAILED = "logic.load_config_failed"
    UPLOAD_DONE = "logic.upload_done"
    UPLOAD_FAILED = "logic.upload_failed"
    RELOAD_DONE = "logic.reload_done"
    RELOAD_FAILED = "logic.reload_failed"
    ARG_FALLBACK_LABEL = "logic.arg_fallback_label"
    ARG_FALLBACK_PLACEHOLDER = "logic.arg_fallback_placeholder"
    ARG_LOCKED_TOOLTIP = "logic.arg_locked_tooltip"
    HELP_DESCRIBE = "logic.help_describe"
    HELP_UNKNOWN = "logic.help_unknown"


class LogicPalette:
    ROOT = "logic.palette.root"
    CONDITION = "logic.palette.condition"
    ACTION = "logic.palette.action"
    LITERAL = "logic.palette.literal"


class LogicValidation:
    CLEAN = "logic_validation.clean"
    SEVERITY_ERROR = "logic_validation.severity.error"
    SEVERITY_WARNING = "logic_validation.severity.warning"
    SEVERITY_INFO = "logic_validation.severity.info"
    ROOT_COUNT = "logic_validation.root_count"
    CYCLE = "logic_validation.cycle"
    ACTION_ONE_RULE = "logic_validation.action_one_rule"
    ACTION_TARGET_REQUIRED = "logic_validation.action_target_required"
    ACTION_UNKNOWN_VALUE_TYPE = "logic_validation.action_unknown_value_type"
    ACTION_UNKNOWN_TRIGGER = "logic_validation.action_unknown_trigger"
    ACTION_BOOL_VALUE = "logic_validation.action_bool_value"
    ACTION_INT_LITERAL = "logic_validation.action_int_literal"
    ACTION_DOUBLE_LITERAL = "logic_validation.action_double_literal"
    UNKNOWN_CONDITION = "logic_validation.unknown_condition"
    ARG_COUNT_MISMATCH = "logic_validation.arg_count_mismatch"
    ARG_REQUIRED = "logic_validation.arg_required"
    ARG_MUST_BE_INT = "logic_validation.arg_must_be_int"
    ARG_MUST_BE_NUMERIC = "logic_validation.arg_must_be_numeric"
    ARG_BOOL_WARNING = "logic_validation.arg_bool_warning"
    MIN_MAX_ORDER = "logic_validation.min_max_order"
    MODULO_POSITIVE = "logic_validation.modulo_positive"
    MODULO_MIN_MAX_ORDER = "logic_validation.modulo_min_max_order"
    PART_SIZE_POSITIVE = "logic_validation.part_size_positive"
    PART_COUNT_POSITIVE = "logic_validation.part_count_positive"
    PART_INDEX_BOUNDS = "logic_validation.part_index_bounds"
    ROOT_NO_INCOMING = "logic_validation.root_no_incoming"
    LIST_LINE = "logic_validation.list_line"


class Auth:
    DIALOG_TITLE = "auth.dialog_title"
    WELCOME_TITLE = "auth.welcome_title"
    WELCOME_SUBTITLE = "auth.welcome_subtitle"
    TAB_SIGN_IN = "auth.tab_sign_in"
    TAB_SIGN_UP = "auth.tab_sign_up"
    SIGN_IN = "auth.sign_in"
    CREATE_ACCOUNT = "auth.create_account"
    USERNAME = "auth.username"
    PASSWORD = "auth.password"
    EMAIL = "auth.email"
    CONFIRM = "auth.confirm"
    CONFIRM_PASSWORD = "auth.confirm_password"
    USER_LABEL = "auth.user_label"
    USER_LABEL_EMPTY = "auth.user_label_empty"
    USER_TOOLTIP = "auth.user_tooltip"
    NO_USER_TOOLTIP = "auth.no_user_tooltip"
    SIGNED_OUT = "auth.signed_out"
    SIGNED_IN_AGAIN = "auth.signed_in_again"
    REAUTHENTICATED = "auth.reauthenticated"
    FB_CREDENTIALS_REQUIRED = "auth.feedback.credentials_required"
    FB_SIGNUP_MISSING = "auth.feedback.signup_missing"
    FB_PASSWORD_MISMATCH = "auth.feedback.password_mismatch"
    FB_SIGNED_IN = "auth.feedback.signed_in"
    FB_SIGNUP_SUCCESS = "auth.feedback.signup_success"


class Hints:
    CONTROL_TABLE_USAGE = "hints.control_table_usage"
    CONTROL_TABLE_TOOLTIP = "hints.control_table_tooltip"
    SCHEDULE_COUNTDOWN = "hints.schedule_countdown"
    SCHEDULE_TABLE_TOOLTIP = "hints.schedule_table_tooltip"
    SERVER_DOUBLE_CLICK = "hints.server_double_click"
    SERVER_TABLE_TOOLTIP = "hints.server_table_tooltip"


class Empty:
    CONTROL_NO_ACTIONS = "empty.control_no_actions"
    SCHEDULE_NONE = "empty.schedule_none"
    SERVER_NONE = "empty.server_none"


class Status:
    TITLE = "status.title"
    READY = "status.ready"
    RECONNECTING = "status.reconnecting"
    GREENHOUSE_REFRESHED = "status.greenhouse_refreshed"
    NO_PENDING_TO_CANCEL = "status.no_pending_to_cancel"
    SCHEDULE_CREATED = "status.schedule_created"
    SCHEDULE_CANCELED = "status.schedule_canceled"
    BULK_CANCELED = "status.bulk_canceled"
    RESTORED_PREVIOUS = "status.restored_previous"


class CommandStatus:
    IN_PROGRESS = "command_status.in_progress"
    DONE = "command_status.done"
    FAILED = "command_status.failed"
    TIMED_OUT = "command_status.timed_out"
    BUSY_BUTTON = "command_status.busy_button"
    CACHED_SUFFIX = "command_status.cached_suffix"


class CommandDisplay:
    READ_SENSOR = "commands.display.read_sensor"
    TOGGLE_WATER_CANAL = "commands.display.toggle_water_canal"
    TOGGLE_FAN = "commands.display.toggle_fan"
    TOGGLE_HEATER = "commands.display.toggle_heater"
    TOGGLE_ACTUATOR = "commands.display.toggle_actuator"
    GENERIC = "commands.display.generic"
    FALLBACK = "commands.display.fallback"


class Sensors:
    TEMPERATURE = "sensors.temperature"
    HUMIDITY = "sensors.humidity"
    LIGHT = "sensors.light"
    CO2 = "sensors.co2"
    SOIL_MOISTURE = "sensors.soil_moisture"
    SOIL_PH = "sensors.soil_ph"
    GENERIC = "sensors.generic"


class Tables:
    REMOVE_SELECTED = "tables.remove_selected"
    HIDE_ALL = "tables.hide_all"
    COLUMN_FALLBACK = "tables.column_fallback"
    STATUS_SUCCESS = "tables.status.success"
    STATUS_FAILED = "tables.status.failed"
    STATUS_SUCCESS_CACHED = "tables.status.success_cached"
    STATUS_UNKNOWN = "tables.status.unknown"
    CACHED_YES = "tables.cached_yes"
    CACHED_NO = "tables.cached_no"
    CLICK_FOR_DETAILS = "tables.click_for_details"
    COMPLETED_CLICK = "tables.completed_click"
    NO_ITEMS = "tables.no_items"
    ERROR_PREFIX = "tables.error_prefix"


class TableColumns:
    TIMESTAMP = "tables.columns.timestamp"
    COMMAND = "tables.columns.command"
    STATUS = "tables.columns.status"
    RESULT = "tables.columns.result"
    CACHED = "tables.columns.cached"
    TASK = "tables.columns.task"
    TIME_REMAINING = "tables.columns.time_remaining"
    STARTS_AT = "tables.columns.starts_at"
    ENDS_AT = "tables.columns.ends_at"
    TYPE = "tables.columns.type"
    DATA = "tables.columns.data"
    PROPERTY = "tables.columns.property"
    VALUE = "tables.columns.value"
    INFO = "tables.columns.info"
    ITEM = "tables.columns.item"
    ITEM_NUMBER = "tables.columns.item_number"
    FIELD = "tables.columns.field"
    GETTER = "tables.columns.getter"
    EXECUTOR = "tables.columns.executor"
    KEY = "tables.columns.key"
    VALID = "tables.columns.valid"
    MODE = "tables.columns.mode"
    ID = "tables.columns.id"
    NAME = "tables.columns.name"


class JsonPretty:
    NO_ADDITIONAL_DETAILS = "json_pretty.no_additional_details"


class Units:
    HOURS_SUFFIX = "units.hours_suffix"
    MINUTES_SUFFIX = "units.minutes_suffix"
    SECONDS_SUFFIX = "units.seconds_suffix"
    SIZE_B = "units.size.b"
    SIZE_KB = "units.size.kb"
    SIZE_MB = "units.size.mb"
    SIZE_GB = "units.size.gb"
    SIZE_TB = "units.size.tb"


class Errors:
    UNKNOWN = "errors.unknown"
    SERVER_UNAVAILABLE = "errors.server_unavailable"
    EXECUTOR_NOT_FOUND = "errors.executor_not_found"
    NO_VALIDATION = "errors.no_validation_failure"
    AUTHENTICATION_FAILED_TITLE = "errors.authentication_failed.title"
    AUTHENTICATION_FAILED_BODY = "errors.authentication_failed.body"


class Dialogs:
    SYSTEM_ERROR_TITLE = "dialogs.system_error.title"
    NO_SELECTION_TITLE = "dialogs.no_selection.title"
    NO_SELECTION_CONTROL = "dialogs.no_selection.control"
    NO_SELECTION_SCHEDULE_REMOVE = "dialogs.no_selection.schedule_remove"
    NO_SELECTION_SCHEDULE_DELETE = "dialogs.no_selection.schedule_delete"
    COMMAND_DETAILS_TITLE = "dialogs.command_details.title"
    SERVER_DETAILS_TITLE = "dialogs.server_details.title"
    SERVER_DETAILS_FALLBACK = "dialogs.server_details.fallback"
    EXECUTORS_NONE_TITLE = "dialogs.executors_none.title"
    EXECUTORS_NONE_MANUAL = "dialogs.executors_none.manual"
    EXECUTORS_NONE_GENERIC = "dialogs.executors_none.generic"
    EXECUTOR_SELECT_TITLE = "dialogs.executor_select.title"
    EXECUTOR_SELECT_LABEL = "dialogs.executor_select.label"
    EXECUTOR_MODE_TITLE = "dialogs.executor_mode.title"
    EXECUTOR_MODE_LABEL = "dialogs.executor_mode.label"
    EXECUTOR_MODE_MANUAL = "dialogs.executor_mode.manual"
    EXECUTOR_MODE_AUTO = "dialogs.executor_mode.auto"
    EXECUTOR_AUTO_TITLE = "dialogs.executor_auto.title"
    EXECUTOR_AUTO_BODY = "dialogs.executor_auto.body"
    EXECUTOR_ON_TITLE = "dialogs.executor_on.title"
    EXECUTOR_OFF_TITLE = "dialogs.executor_off.title"
    EXECUTOR_SET_TITLE = "dialogs.executor_set.title"
    EXECUTOR_SET_LABEL = "dialogs.executor_set.label"
    INVALID_VALUE_TITLE = "dialogs.invalid_value.title"
    INVALID_VALUE_BODY = "dialogs.invalid_value.body"
    SWITCH_MODE_TITLE = "dialogs.switch_mode.title"
    SCHEDULING_ERROR_TITLE = "dialogs.scheduling_error.title"
    SCHEDULING_ERROR_API = "dialogs.scheduling_error.api"
    SCHEDULING_ERROR_TARGET = "dialogs.scheduling_error.target"
    SCHEDULING_ERROR_INTERVAL_TITLE = "dialogs.scheduling_error.interval_title"
    SCHEDULING_ERROR_INTERVAL = "dialogs.scheduling_error.interval"
    SCHEDULING_ERROR_RUN_AT_PAST = "dialogs.scheduling_error.run_at_past"
    SCHEDULING_ERROR_NO_DEVICE = "dialogs.scheduling_error.no_device"
    SCHEDULE_PARTIAL_FAIL_TITLE = "dialogs.schedule_partial_fail.title"
    SCHEDULE_PARTIAL_FAIL_BODY = "dialogs.schedule_partial_fail.body"
    DELETE_ALL_TITLE = "dialogs.delete_all_schedules.title"
    DELETE_ALL_BODY = "dialogs.delete_all_schedules.body"
    RESTORE_DATA_TITLE = "dialogs.restore_data.title"
    RESTORE_DATA_BODY = "dialogs.restore_data.body"
    SESSION_EXPIRED_TITLE = "dialogs.session_expired.title"
    SESSION_EXPIRED_BODY = "dialogs.session_expired.body"
    LOGOUT_TITLE = "dialogs.logout.title"
    LOGOUT_BODY = "dialogs.logout.body"
    AUTH_ERROR_TITLE = "dialogs.auth_error.title"
    AUTH_VALIDATION_FAILED = "dialogs.auth_error.validation_failed"
    EXIT_APP_TITLE = "dialogs.exit_app.title"
    EXIT_APP_BODY = "dialogs.exit_app.body"
    STATISTICS_TITLE = "dialogs.statistics.title"
    STATISTICS_SELECT_SENSOR = "dialogs.statistics.select_sensor"
    STATISTICS_INVALID_RANGE_TITLE = "dialogs.statistics.invalid_range_title"
    STATISTICS_INVALID_RANGE_BODY = "dialogs.statistics.invalid_range_body"
    STATISTICS_ERROR_TITLE = "dialogs.statistics.error_title"
    JSON_PREVIEW_TITLE = "dialogs.json_preview.title"
    CONFIG_PREVIEW_TITLE = "dialogs.config_preview.title"


class EdgeFog:
    ANOMALY_OUT_OF_RANGE = "edge_fog.anomaly.out_of_range"
    ANOMALY_HIGH_VARIANCE = "edge_fog.anomaly.high_variance"
    ANOMALY_RAPID_CHANGE = "edge_fog.anomaly.rapid_change"
    ANOMALY_TREND_INCREASING = "edge_fog.anomaly.trend_increasing"
    ANOMALY_TREND_DECREASING = "edge_fog.anomaly.trend_decreasing"


class Settings:
    DIALOG_TITLE = "settings.dialog_title"
    LANGUAGE_LABEL = "settings.language_label"
    APPLY_BUTTON = "settings.apply_button"
    CLOSE_BUTTON = "settings.close_button"


class Languages:
    ENGLISH = "languages.english"
    ARMENIAN = "languages.armenian"
