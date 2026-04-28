"""
objectName -> translation_key mapping for widgets that come from
`front.ui` (loaded with `uic.loadUi`).

Centralizing this mapping keeps `retranslate_ui()` short, prevents
72 hand-written `setText` lines, and makes adding new UI strings a
matter of editing one place.

Each entry tells `apply_ui_text_map()` how to set the text:
    "objectName": ("set_kind", "translation.key")

set_kind:
    "text"        -> widget.setText(...)
    "title"       -> widget.setTitle(...)
    "tooltip"     -> widget.setToolTip(...)
    "placeholder" -> widget.setPlaceholderText(...)
    "suffix"      -> widget.setSuffix(...)
"""
from __future__ import annotations

from typing import Dict, Tuple

from modules.localization.localization_keys import (
    Connection,
    Controls,
    Logic,
    Schedule,
    Server,
    Session,
    Statistics,
    Status,
    Units,
)
from modules.localization.translation_helpers import tr_key


SetEntry = Tuple[str, str]


MAIN_WINDOW_TEXT_MAP: Dict[str, SetEntry] = {
    "sessionTitleLabel": ("text", Session.TITLE),
    "session_label": ("tooltip", Session.TOOLTIP_TITLE),
    "connection_status": ("text", Connection.CONNECTING),
    "controlGroup": ("title", Controls.GROUP_TITLE),
    "tempButton": ("text", Controls.TEMPERATURE),
    "humidityButton": ("text", Controls.HUMIDITY),
    "co2Button": ("text", Controls.CO2),
    "lightButton": ("text", Controls.LIGHT),
    "soilPHButton": ("text", Controls.SOIL_PH),
    "soilMoistureButton": ("text", Controls.SOIL_MOISTURE),
    "fanButton": ("text", Controls.FAN),
    "waterCanalButton": ("text", Controls.WATER_CANAL),
    "actuatorButton": ("text", Controls.ACTUATOR),
    "heaterButton": ("text", Controls.HEATER),
    "statusButton": ("text", Controls.SYSTEM_STATUS),
    "scheduleGroup": ("title", Schedule.GROUP_TITLE),
    "scheduleTargetLabel": ("text", Schedule.TARGET_ACTION),
    "scheduleDelayLabel": ("text", Schedule.DELAY),
    "scheduleCustomDelayLabel": ("text", Schedule.CUSTOM_DELAY),
    "scheduleHintLabel": ("text", Schedule.CUSTOM_HINT),
    "scheduleTaskButton": ("text", Schedule.SCHEDULE_TASK),
    "cancelScheduledButton": ("text", Schedule.CANCEL_SELECTED),
    "clearScheduledButton": ("text", Schedule.CLEAR_ALL),
    "scheduleHoursSpin": ("suffix", Units.HOURS_SUFFIX),
    "scheduleMinutesSpin": ("suffix", Units.MINUTES_SUFFIX),
    "scheduleSecondsSpin": ("suffix", Units.SECONDS_SUFFIX),
    "serverGroup": ("title", Server.GROUP_TITLE),
    "healthButton": ("text", Server.SYSTEM_HEALTH),
    "refreshButton": ("text", Server.REFRESH_ALL_DATA),
    "statsButton": ("text", Server.SENSOR_TYPES),
    "sessionsButton": ("text", Server.DEVICE_CONTROLS),
    "cacheKeysButton": ("text", Server.SENSOR_READINGS),
    "queuesButton": ("text", Server.DEVICE_STATES),
    "clearCacheButton": ("text", Server.CHANGE_DEVICE_MODE),
    "testCommandButton": ("text", Server.DEVICE_ON),
    "logFilesButton": ("text", Server.DEVICE_OFF),
    "viewLogButton": ("text", Server.SET_DEVICE_VALUE),
    "statisticsGroup": ("title", Statistics.GROUP_TITLE),
    "statisticsDeviceLabel": ("text", Statistics.DEVICE),
    "statisticsSensorLabel": ("text", Statistics.SENSOR),
    "statisticsFromLabel": ("text", Statistics.FROM),
    "statisticsToLabel": ("text", Statistics.TO),
    "statisticsAllDataCheck": ("text", Statistics.ALL_DATA),
    "statisticsLoadButton": ("text", Statistics.LOAD),
    "statisticsRefreshIntervalLabel": ("text", Statistics.REFRESH),
    "statisticsHintLabel": ("text", Statistics.HINT),
    "logicControlsGroup": ("title", Logic.CONTROLS_GROUP),
    "logicAddRootButton": ("text", Logic.ADD_ROOT),
    "logicAddConditionButton": ("text", Logic.ADD_CONDITION),
    "logicAddActionButton": ("text", Logic.ADD_ACTION),
    "logicDeleteSelectedButton": ("text", Logic.DELETE_SELECTED),
    "logicConnectSelectedButton": ("text", Logic.CONNECT_SELECTED),
    "logicLoadButton": ("text", Logic.LOAD_PLACEHOLDER),
    "logicValidateButton": ("text", Logic.VALIDATE_PLACEHOLDER),
    "logicUploadButton": ("text", Logic.UPLOAD_NEXT),
    "logicReloadButton": ("text", Logic.RELOAD_NEXT),
    "logicToolboxGroup": ("title", Logic.TOOLBOX_GROUP),
    "logicToolboxHintLabel": ("text", Logic.TOOLBOX_HINT),
    "logicCanvasGroup": ("title", Logic.CANVAS_GROUP),
    "logicCanvasStatusLabel": ("text", Logic.CANVAS_READY_DEFAULT),
    "logicPropertiesGroup": ("title", Logic.PROPERTIES_GROUP),
    "logicPropertyNodeTypeLabel": ("text", Logic.TYPE_NONE),
    "logicPropertyTitleEdit": ("placeholder", Logic.TITLE_PLACEHOLDER),
    "logicPropertyArgsEdit": ("placeholder", Logic.ARGS_PLACEHOLDER),
    "logicPropertyValueEdit": ("placeholder", Logic.VALUE_PLACEHOLDER),
    "logicPropertyEnabledCheck": ("text", Logic.ACTION_ENABLED),
    "logicApplyPropertyButton": ("text", Logic.APPLY_BUTTON),
    "logicValidationGroup": ("title", Logic.VALIDATION_GROUP),
    "statusTitleLabel": ("text", Status.TITLE),
}


# `set_kind` -> setter method name on widget
_KIND_TO_METHOD = {
    "text": "setText",
    "title": "setTitle",
    "tooltip": "setToolTip",
    "placeholder": "setPlaceholderText",
    "suffix": "setSuffix",
}


def apply_ui_text_map(owner, mapping: Dict[str, SetEntry]) -> None:
    """Walk an objectName->key dict and apply translated text to the owner.

    Args:
        owner: The QObject owning the children loaded by `uic.loadUi` (the
            attributes are set by Qt as `owner.<objectName>`).
        mapping: Subset of `MAIN_WINDOW_TEXT_MAP` to apply.
    """
    for object_name, (set_kind, key) in mapping.items():
        widget = getattr(owner, object_name, None)
        if widget is None:
            continue
        method_name = _KIND_TO_METHOD.get(set_kind)
        if not method_name:
            continue
        setter = getattr(widget, method_name, None)
        if not callable(setter):
            continue
        try:
            setter(tr_key(key))
        except Exception:
            continue


