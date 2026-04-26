"""Statistics tab, sensor read persistence, and user log hydration."""
import json
import re
from datetime import datetime, timedelta, timezone

import pyqtgraph as pg
from PyQt5.QtCore import QDateTime, QTimer

from modules.core_api_client import UnauthorizedError
from modules.ui_dialogs import StyledMessageDialog


class GreenhouseStatisticsMixin:
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
        restored_count = 0

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
            command_display = (
                self._command_display_name(command, payload.get("parameters", {}))
                if hasattr(self, "_command_display_name")
                else command.replace("_", " ").title()
            )
            raw_status = str(payload.get("status", "OK"))
            status = (
                self._normalize_control_status(raw_status)
                if hasattr(self, "_normalize_control_status")
                else raw_status
            )
            response = payload.get("response", {})
            cached = bool(payload.get("cached", False))
            self.control_history.append(
                {
                    "timestamp": display_time,
                    "command": command,
                    "command_display": command_display,
                    "response": response if isinstance(response, dict) else {"result": payload.get("result", "")},
                    "cached": cached,
                    "error": payload.get("error"),
                }
            )
            # Keep control table non-technical: details are available on double-click.
            self.control_table.add_row([display_time, command_display, status])
            restored_count += 1
        if hasattr(self, "_on_control_table_selection_changed"):
            self._on_control_table_selection_changed()
        if restored_count > 0:
            self.status_label.setText(f"Restored {restored_count} previous action(s)")

