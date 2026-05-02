"""Scheduling tab: targets, one-off schedules, and table rendering."""
from datetime import datetime, timedelta, timezone

from PyQt5.QtCore import QTimer

from modules.qt_thread_tasks import dispatch_thread_failure_to_ui, run_thread_task
from modules.ui_dialogs import StyledMessageDialog
from modules.localization import tr_key
from modules.localization.localization_keys import (
    Common,
    Dialogs,
    ScheduleDelay,
    ScheduleStatus,
    ScheduleTargets,
    Schedule,
    Status,
    Sensors,
)


_DELAY_PRESETS = (
    (ScheduleDelay.AFTER_1M, 60),
    (ScheduleDelay.AFTER_15M, 15 * 60),
    (ScheduleDelay.AFTER_30M, 30 * 60),
    (ScheduleDelay.AFTER_1H, 60 * 60),
    (ScheduleDelay.CUSTOM, -1),
)


class GreenhouseSchedulingMixin:
    def setup_scheduler(self):
        """Initialize scheduling controls backed by persistent backend schedules."""
        if not hasattr(self, "scheduleTargetCombo") or not hasattr(self, "scheduleDelayPresetCombo"):
            self.logger.warning("Scheduling controls not present in UI")
            return

        self._schedule_targets_request_gen = 0
        self._schedule_table_request_gen = 0
        self._schedule_mutate_in_flight = False
        self._schedule_cancel_in_flight = False
        self._schedule_bulk_in_flight = False

        self._refresh_schedule_targets()

        self._populate_schedule_delay_presets()
        self.scheduleDelayPresetCombo.setCurrentIndex(0)

        self.schedule_clock_timer = QTimer(self)
        self.schedule_clock_timer.timeout.connect(self.update_schedule_live_time)
        self.schedule_clock_timer.start(1000)

        self.update_custom_delay_enabled()
        self.update_schedule_live_time()
        self.refresh_schedule_table()

    def _populate_schedule_delay_presets(self):
        """Re-populate delay presets in the active language."""
        if not hasattr(self, "scheduleDelayPresetCombo") or not self.scheduleDelayPresetCombo:
            return
        combo = self.scheduleDelayPresetCombo
        previous_data = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for key, value in _DELAY_PRESETS:
            combo.addItem(tr_key(key), value)
        if previous_data is not None:
            for index in range(combo.count()):
                if combo.itemData(index) == previous_data:
                    combo.setCurrentIndex(index)
                    break
        combo.blockSignals(False)

    def _refresh_schedule_delay_preset_labels(self):
        """Refresh delay preset visible labels (called by retranslate_ui)."""
        self._populate_schedule_delay_presets()

    def _build_schedule_target_entries(self, executors):
        """Build combo entries from executor snapshots (any thread)."""
        options = []
        seen = set()
        for executor in executors or []:
            name = str(getattr(executor, "name", "")).strip()
            if not name:
                continue

            lowered = name.lower()
            command = None
            parameters = {"action": "toggle"}

            icon_prefix = ""
            if "water" in lowered and "canal" in lowered:
                command = "switch_water_canal"
                icon_prefix = "🚰 "
            elif "fan" in lowered:
                command = "switch_fan"
                parameters["fanId"] = name
                icon_prefix = "🌀 "
            elif "heater" in lowered:
                command = "switch_heater"
                parameters["heaterId"] = name
                icon_prefix = "🔥 "
            elif "actuator" in lowered:
                command = "switch_actuator"
                parameters["actuatorId"] = name
                icon_prefix = "⚙️ "

            if not command:
                command = "switch_actuator"
                parameters["actuatorId"] = name
                icon_prefix = "⚙️ "

            key = f"{command}:{name.lower()}"
            if key in seen:
                continue
            seen.add(key)
            label = icon_prefix + tr_key(ScheduleTargets.TOGGLE_NAMED, name=name)
            options.append((label, (command, parameters), key))

        if not options:
            options = [
                (
                    tr_key(ScheduleTargets.TOGGLE_WATER_CANAL),
                    ("switch_water_canal", {"action": "toggle"}),
                    "switch_water_canal:default",
                ),
                (
                    tr_key(ScheduleTargets.TOGGLE_FAN),
                    ("switch_fan", {"fanId": "fan_1", "action": "toggle"}),
                    "switch_fan:fan_1",
                ),
                (
                    tr_key(ScheduleTargets.TOGGLE_HEATER),
                    ("switch_heater", {"heaterId": "heater_1", "action": "toggle"}),
                    "switch_heater:heater_1",
                ),
                (
                    tr_key(ScheduleTargets.TOGGLE_ACTUATOR),
                    ("switch_actuator", {"actuatorId": "actuator_1", "action": "toggle"}),
                    "switch_actuator:actuator_1",
                ),
            ]
        return options

    def _apply_schedule_target_entries(self, executors):
        """Populate target combo from executor list (main thread)."""
        options = self._build_schedule_target_entries(executors)
        new_keys = [item[2] for item in options]
        if new_keys == self.schedule_target_keys:
            return

        self.scheduleTargetCombo.clear()
        self.schedule_target_keys = new_keys
        for label, payload, _key in options:
            self.scheduleTargetCombo.addItem(label, payload)

        if not options:
            self.scheduleTargetCombo.addItem(tr_key(Schedule.NO_DEVICES), None)

    def _refresh_schedule_targets(self):
        """
        Keep scheduling targets aligned with currently available executors/devices.
        Only device control actions are schedulable from this tab.
        """
        if not hasattr(self, "scheduleTargetCombo") or not hasattr(self, "core_api"):
            return

        self._schedule_targets_request_gen += 1
        request_gen = self._schedule_targets_request_gen

        def work():
            return self.core_api.get_executors()

        def on_ok(executors):
            if request_gen != self._schedule_targets_request_gen:
                return
            if not isinstance(executors, list):
                executors = []
            try:
                self._apply_schedule_target_entries(executors)
            except Exception as error:
                self.logger.warning("Failed to apply schedule targets: %s", error)
                self._apply_schedule_target_entries([])

        def on_err(message: str):
            if request_gen != self._schedule_targets_request_gen:
                return
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Schedule targets"):
                return
            self.logger.warning("Failed to refresh schedule targets: %s", message)
            self._apply_schedule_target_entries([])

        run_thread_task(self, work, on_ok, on_err, thread_name="schedule-targets")

    def update_schedule_live_time(self):
        """Update live time UI elements in scheduling tab."""
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(self, "scheduleCurrentTimeLabel"):
            self.scheduleCurrentTimeLabel.setText(
                tr_key(Schedule.CURRENT_TIME, datetime=now_text)
            )
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
            tr_key(Dialogs.RESTORE_DATA_TITLE),
            tr_key(Dialogs.RESTORE_DATA_BODY),
            yes_text=tr_key(Common.LOAD),
            no_text=tr_key(Common.START_FRESH),
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

    def hide_all_schedule_rows_from_view(self):
        """Hide all currently visible rows from schedule table view."""
        self.hidden_schedule_ids.update(self.schedule_table_rows)
        if self.schedule_table:
            self.schedule_table.clear_data()
        self.schedule_table_rows = []
        self._update_schedule_empty_state()

    def remove_selected_schedule_row_from_view(self, row=None):
        """Hide selected row from schedule table view."""
        schedule_id = None
        if isinstance(row, int) and 0 <= row < len(self.schedule_table_rows):
            schedule_id = self.schedule_table_rows[row]
        else:
            schedule_id = self._get_selected_schedule_id()
        if not schedule_id:
            StyledMessageDialog.show_warning(
                self,
                tr_key(Dialogs.NO_SELECTION_TITLE),
                tr_key(Dialogs.NO_SELECTION_SCHEDULE_REMOVE),
            )
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
        if hasattr(self, "_on_control_table_selection_changed"):
            self._on_control_table_selection_changed()

    def _remove_selected_server_row(self, row):
        """Remove selected server-table row and keep history mapping aligned."""
        if not self.server_table:
            return
        if not isinstance(row, int) or row < 0 or row >= self.server_table.table.rowCount():
            return
        self.server_table.table.removeRow(row)
        if 0 <= row < len(self.server_history):
            self.server_history.pop(row)
        if hasattr(self, "_update_server_empty_state"):
            self._update_server_empty_state()

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

    def _core_resolve_schedule_device_id(self, preferred_name, cached_device_id):
        """Resolve or create scheduling device id using HTTP only (worker thread)."""
        if not hasattr(self, "core_api"):
            return None

        devices = self.core_api.list_devices()
        if not devices:
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
            return created_id or None

        device_ids = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            candidate = device.get("id")
            if candidate is None:
                continue
            device_ids.append(str(candidate))

        if not device_ids:
            return None

        cached = str(cached_device_id or "").strip()
        if cached and cached in device_ids:
            return cached

        return device_ids[0]

    def schedule_selected_task(self):
        """Create one-time backend-persisted schedule for the selected action."""
        if not hasattr(self, "core_api"):
            self.show_error(
                tr_key(Dialogs.SCHEDULING_ERROR_TITLE),
                tr_key(Dialogs.SCHEDULING_ERROR_API),
            )
            return

        self._refresh_schedule_targets()
        selected_data = self.scheduleTargetCombo.currentData()
        if not isinstance(selected_data, (tuple, list)) or len(selected_data) != 2:
            self.show_error(
                tr_key(Dialogs.SCHEDULING_ERROR_TITLE),
                tr_key(Dialogs.SCHEDULING_ERROR_TARGET),
            )
            return

        command, parameters = selected_data
        target_label = str(self.scheduleTargetCombo.currentText())
        interval_seconds = self.get_selected_interval_seconds()
        if interval_seconds <= 0:
            self.show_error(
                tr_key(Dialogs.SCHEDULING_ERROR_INTERVAL_TITLE),
                tr_key(Dialogs.SCHEDULING_ERROR_INTERVAL),
            )
            return

        if self._schedule_mutate_in_flight:
            return
        self._schedule_mutate_in_flight = True

        cached_device_id = self.schedule_device_id
        session_id = self.session_id

        def work():
            device_id = self._core_resolve_schedule_device_id(target_label, cached_device_id)
            if not device_id:
                return {"ok": False, "reason": "no_device"}

            run_at_local = datetime.now().astimezone() + timedelta(seconds=interval_seconds)
            cron_expression = self._build_one_time_cron_expression(run_at_local)
            schedule_name = f"{target_label} at {run_at_local.strftime('%Y-%m-%d %H:%M:%S')}"[:120]
            payload = dict(parameters) if isinstance(parameters, dict) else {}
            metadata = {
                "sessionId": session_id,
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
            return {
                "ok": True,
                "device_id": device_id,
                "schedule_label": schedule_label,
                "target_label": target_label,
            }

        def on_ok(result):
            self._schedule_mutate_in_flight = False
            if not isinstance(result, dict) or not result.get("ok"):
                if isinstance(result, dict) and result.get("reason") == "no_device":
                    self.show_error(
                        tr_key(Dialogs.SCHEDULING_ERROR_TITLE),
                        tr_key(Dialogs.SCHEDULING_ERROR_NO_DEVICE),
                    )
                return
            self.schedule_device_id = result.get("device_id")
            schedule_label = result.get("schedule_label", "created")
            target_lbl = result.get("target_label", "")
            if hasattr(self, "set_status_state") and callable(self.set_status_state):
                self.set_status_state(
                    Status.SCHEDULE_CREATED, label=schedule_label, target=target_lbl
                )
            else:
                self.status_label.setText(
                    tr_key(Status.SCHEDULE_CREATED, label=schedule_label, target=target_lbl)
                )
            self.refresh_schedule_table()

        def on_err(message: str):
            self._schedule_mutate_in_flight = False
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Schedule create"):
                return
            self._handle_api_exception(tr_key(Dialogs.SCHEDULING_ERROR_TITLE), RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="schedule-create")

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
            self.show_error(
                tr_key(Dialogs.SCHEDULING_ERROR_TITLE),
                tr_key(Dialogs.SCHEDULING_ERROR_API),
            )
            return

        schedule_id = self._get_selected_schedule_id()
        if not schedule_id:
            StyledMessageDialog.show_warning(
                self,
                tr_key(Dialogs.NO_SELECTION_TITLE),
                tr_key(Dialogs.NO_SELECTION_SCHEDULE_DELETE),
            )
            return

        schedule = self._get_schedule_by_id(schedule_id) or {}
        metadata = dict(schedule.get("metadata") or {})
        metadata["scheduleStatus"] = "canceled"
        metadata["canceledAt"] = datetime.now(timezone.utc).isoformat()
        body = {
            "enabled": False,
            "metadata": metadata,
        }
        short_id = str(schedule_id)[:8]

        if self._schedule_cancel_in_flight:
            return
        self._schedule_cancel_in_flight = True

        def work():
            self.core_api.update_schedule(schedule_id, body)
            return None

        def on_ok(_result):
            self._schedule_cancel_in_flight = False
            self.refresh_schedule_table()
            if hasattr(self, "set_status_state") and callable(self.set_status_state):
                self.set_status_state(Status.SCHEDULE_CANCELED, id=short_id)
            else:
                self.status_label.setText(tr_key(Status.SCHEDULE_CANCELED, id=short_id))

        def on_err(message: str):
            self._schedule_cancel_in_flight = False
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Schedule cancel"):
                return
            self._handle_api_exception(tr_key(Dialogs.SCHEDULING_ERROR_TITLE), RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="schedule-cancel")

    def clear_all_schedules(self):
        """Cancel all pending schedules visible to current user context."""
        if not hasattr(self, "core_api"):
            self.show_error(
                tr_key(Dialogs.SCHEDULING_ERROR_TITLE),
                tr_key(Dialogs.SCHEDULING_ERROR_API),
            )
            return

        confirmation = StyledMessageDialog.ask_yes_no(
            self,
            tr_key(Dialogs.DELETE_ALL_TITLE),
            tr_key(Dialogs.DELETE_ALL_BODY),
            yes_text=tr_key(Common.YES),
            no_text=tr_key(Common.NO),
        )
        if not confirmation:
            return

        if self._schedule_bulk_in_flight:
            return
        self._schedule_bulk_in_flight = True

        def work():
            schedules = self.core_api.list_schedules()
            schedule_ids = []
            schedule_map = {}
            for schedule in schedules if isinstance(schedules, list) else []:
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
                return {"empty": True, "canceled": 0, "errors": []}

            canceled = 0
            errors = []
            for sid in schedule_ids:
                try:
                    schedule = schedule_map.get(sid) or {}
                    metadata = dict(schedule.get("metadata") or {})
                    metadata["scheduleStatus"] = "canceled"
                    metadata["canceledAt"] = datetime.now(timezone.utc).isoformat()
                    self.core_api.update_schedule(
                        sid,
                        {
                            "enabled": False,
                            "metadata": metadata,
                        },
                    )
                    canceled += 1
                except Exception as error:
                    errors.append(f"{sid[:8]}: {error}")
            return {"empty": False, "canceled": canceled, "errors": errors}

        def on_ok(result):
            self._schedule_bulk_in_flight = False
            if not isinstance(result, dict):
                return
            if result.get("empty"):
                if hasattr(self, "set_status_state") and callable(self.set_status_state):
                    self.set_status_state(Status.NO_PENDING_TO_CANCEL)
                else:
                    self.status_label.setText(tr_key(Status.NO_PENDING_TO_CANCEL))
                return
            errors = result.get("errors") or []
            canceled = int(result.get("canceled") or 0)
            self.refresh_schedule_table()
            if errors:
                summary = "\n".join(str(e) for e in errors[:5])
                self.show_error(
                    tr_key(Dialogs.SCHEDULE_PARTIAL_FAIL_TITLE),
                    tr_key(
                        Dialogs.SCHEDULE_PARTIAL_FAIL_BODY,
                        count=canceled,
                        summary=summary,
                    ),
                )
            else:
                if hasattr(self, "set_status_state") and callable(self.set_status_state):
                    self.set_status_state(Status.BULK_CANCELED, count=canceled)
                else:
                    self.status_label.setText(tr_key(Status.BULK_CANCELED, count=canceled))

        def on_err(message: str):
            self._schedule_bulk_in_flight = False
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Schedule bulk cancel"):
                return
            self._handle_api_exception(tr_key(Dialogs.SCHEDULING_ERROR_TITLE), RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="schedule-bulk-cancel")

    def refresh_schedule_table(self):
        """Render backend schedules into the schedule table."""
        if not self.schedule_table or not hasattr(self, "core_api"):
            return

        self._schedule_table_request_gen += 1
        table_gen = self._schedule_table_request_gen

        selected_row = self.schedule_table.table.currentRow()
        selected_schedule_id = None
        if 0 <= selected_row < len(self.schedule_table_rows):
            selected_schedule_id = self.schedule_table_rows[selected_row]

        def work():
            return self.core_api.list_schedules()

        def on_ok(schedules):
            if table_gen != self._schedule_table_request_gen:
                return
            self.schedule_rows = schedules if isinstance(schedules, list) else []
            self._render_schedule_rows(preferred_selected_id=selected_schedule_id)

        def on_err(message: str):
            if table_gen != self._schedule_table_request_gen:
                return
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Schedule list"):
                return
            self.logger.error("Failed to refresh schedules: %s", message)

        run_thread_task(self, work, on_ok, on_err, thread_name="schedule-list")

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
            status_token = self._resolve_schedule_status_token(enabled, metadata)
            status = tr_key(self._SCHEDULE_STATUS_TOKEN_KEYS[status_token])
            time_remaining = self._format_schedule_time_remaining(schedule, cron_expression, enabled, metadata, status)

            if status_token == "completed":
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
        self._update_schedule_empty_state()

    def _update_schedule_empty_state(self):
        if not hasattr(self, "schedule_empty_state_label") or not self.schedule_empty_state_label:
            return
        has_rows = bool(self.schedule_table and self.schedule_table.table.rowCount() > 0)
        self.schedule_empty_state_label.setVisible(not has_rows)

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
            return tr_key(Common.DASH)
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

    _SCHEDULE_STATUS_TOKEN_KEYS = {
        "pending": ScheduleStatus.PENDING,
        "completed": ScheduleStatus.COMPLETED,
        "canceled": ScheduleStatus.CANCELED,
        "not_done": ScheduleStatus.NOT_DONE,
    }

    def _resolve_schedule_status_token(self, enabled, metadata):
        """Return a stable, locale-independent status token."""
        status = str(metadata.get("scheduleStatus", "")).strip().lower()
        if status in self._SCHEDULE_STATUS_TOKEN_KEYS:
            return status
        if enabled:
            return "pending"
        dispatch_status = str(metadata.get("lastDispatchStatus", "")).strip().lower()
        if dispatch_status == "completed":
            return "completed"
        if dispatch_status == "failed":
            return "not_done"
        return "canceled"

    def _format_schedule_status(self, enabled, metadata):
        token = self._resolve_schedule_status_token(enabled, metadata)
        return tr_key(self._SCHEDULE_STATUS_TOKEN_KEYS[token])

    def _is_terminal_schedule_status(self, status):
        terminal_labels = {
            tr_key(ScheduleStatus.COMPLETED),
            tr_key(ScheduleStatus.CANCELED),
            tr_key(ScheduleStatus.NOT_DONE),
        }
        return status in terminal_labels

    def _format_schedule_time_remaining(self, schedule, cron_expression, enabled, metadata, status):
        if self._is_terminal_schedule_status(status):
            return tr_key(Common.DASH)
        if not enabled:
            return tr_key(Common.DASH)

        run_at = self._resolve_run_at(schedule, cron_expression, metadata)
        if not run_at:
            return tr_key(Common.DASH)

        now = datetime.now(timezone.utc)
        seconds_left = int((run_at - now).total_seconds())
        if seconds_left <= 0:
            return tr_key(ScheduleStatus.RUNNING)
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

    _SENSOR_KEY_MAP = {
        "temperature": Sensors.TEMPERATURE,
        "humidity": Sensors.HUMIDITY,
        "light": Sensors.LIGHT,
        "co2": Sensors.CO2,
        "soil_moisture": Sensors.SOIL_MOISTURE,
        "soil_ph": Sensors.SOIL_PH,
    }

    def _format_schedule_target_label(self, action, parameters):
        if action == "read_sensor":
            sensor = str(parameters.get("sensor", "")).strip().lower()
            sensor_key = self._SENSOR_KEY_MAP.get(sensor, Sensors.GENERIC)
            return tr_key(ScheduleTargets.READ_NAMED, sensor=tr_key(sensor_key))
        if action == "switch_water_canal":
            return tr_key(ScheduleTargets.TOGGLE_WATER_CANAL)
        if action == "switch_fan":
            return tr_key(ScheduleTargets.TOGGLE_FAN)
        if action == "switch_heater":
            return tr_key(ScheduleTargets.TOGGLE_HEATER)
        if action == "switch_actuator":
            return tr_key(ScheduleTargets.TOGGLE_ACTUATOR)
        return action
