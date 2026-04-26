"""Scheduling tab: targets, one-off schedules, and table rendering."""
from datetime import datetime, timedelta, timezone

from PyQt5.QtCore import QTimer

from modules.core_api_client import UnauthorizedError
from modules.ui_dialogs import StyledMessageDialog


class GreenhouseSchedulingMixin:
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
            self.status_label.setText(f"One-time task {schedule_label} scheduled for {target_label}")
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
            self.status_label.setText(f"Canceled task {str(schedule_id)[:8]}")
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
                self.status_label.setText("No pending schedules to cancel")
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
                self.status_label.setText(f"Canceled {canceled} pending schedule(s)")
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
