import threading
from typing import Any, Dict, List, Optional
from copy import deepcopy

from PyQt5.QtCore import QDateTime, QEventLoop, QObject, pyqtSignal
from PyQt5.QtWidgets import QDialog, QVBoxLayout

from modules.table_widget import SimpleDataTable
from modules import table_renderers
from modules.core_api_client import CoreApiClient, UnauthorizedError
from modules.core_dtos import ExecutorSnapshotDto, GetterSnapshotDto
from modules.ui_dialogs import StyledInputDialog, StyledMessageDialog
from modules.localization import tr_key
from modules.localization.localization_keys import (
    Dialogs,
    Errors,
    ServerData,
    Status,
    Tables,
)
from modules.qt_thread_tasks import dispatch_thread_failure_to_ui, run_thread_task


class _CoreSnapshotSignalBridge(QObject):
    """Payload is ``(request_generation: int, data)`` so stale snapshot work is ignored."""

    snapshot_ready = pyqtSignal(object)
    snapshot_error = pyqtSignal(object)


class ServerPanelMixin:
    """
    Mixin responsible for:
    - Polling greenhouse core state through backend root core endpoints
    - Displaying status, schemas, getters and executors
    - Sending executor mode/on/off/set commands with MANUAL-mode guard
    - Auto-refresh for greenhouse state

    Expects the main window to provide:
      - self.backend_url (str)
      - self.logger
      - self.server_table (SimpleDataTable or None)
      - self.server_history (list)
      - self.auto_refresh_timer (QTimer)
    """

    def setup_core_panel(self):
        """Initialize backend-core API client and local snapshot caches."""
        token_provider = self.get_auth_token if hasattr(self, "get_auth_token") else None
        self.core_api = CoreApiClient(self.backend_url, auth_token_provider=token_provider)
        self.core_getter_schema: Dict[str, str] = {}
        self.core_executor_schema: Dict[str, str] = {}
        self.core_getters: List[GetterSnapshotDto] = []
        self.core_executors: List[ExecutorSnapshotDto] = []
        self._core_snapshot_request_gen = 0
        self._core_snapshot_signals = _CoreSnapshotSignalBridge()
        self._core_snapshot_signals.snapshot_ready.connect(self._on_core_snapshot_ready)
        self._core_snapshot_signals.snapshot_error.connect(self._on_core_snapshot_error)
        self._update_executor_action_buttons_state()

    # ------------------------------------------------------------------
    # Generic display helpers
    # ------------------------------------------------------------------
    def display_data_table(self, title: str, data: Any, data_type: str):
        """
        Display data in table using specialized renderers for each data type.

        Args:
            title: Display title/type
            data: Data to display (dict or list)
            data_type: Type identifier (for logging)
        """
        if not self.server_table:
            self.logger.warning("Server table not initialized, cannot display data")
            return

        try:
            # Store full response for detailed view
            self.server_history.append(
                {
                    "title": title,
                    # Keep immutable snapshot for row/detail consistency.
                    "data": deepcopy(data),
                    "data_type": data_type,
                }
            )

            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            status = tr_key(Tables.STATUS_SUCCESS)
            if isinstance(data, dict) and data.get("error"):
                status = tr_key(Tables.STATUS_FAILED)

            # Append a compact summary row; detailed view is available on double-click
            self.server_table.add_row([timestamp, title, status])
            self._update_server_empty_state()
            self.logger.info(f"Added server summary row for '{title}' ({data_type})")

        except Exception as e:
            self.logger.error(f"Error displaying data table: {e}", exc_info=True)

    def clear_server_tables(self):
        """Clear server info table"""
        if self.server_table:
            self.server_table.clear_data()
        self.server_history = []
        self._update_server_empty_state()

    def _update_server_empty_state(self):
        if not hasattr(self, "server_empty_state_label") or not self.server_empty_state_label:
            return
        has_rows = bool(self.server_table and self.server_table.table.rowCount() > 0)
        self.server_empty_state_label.setVisible(not has_rows)

    def show_server_details(self, row, column):
        """Open a detailed table view for a selected server-table row."""
        if row < 0 or row >= len(self.server_history):
            self.logger.warning(f"Server details requested for invalid row {row}")
            return

        entry = self.server_history[row]
        title = entry.get("title", tr_key(Dialogs.SERVER_DETAILS_FALLBACK))
        data = entry.get("data", {})
        data_type = entry.get("data_type", "generic")

        try:
            # Choose appropriate renderer based on data_type
            if data_type == 'core_status':
                columns, rows = table_renderers.render_core_status_data(data)
            elif data_type == 'getter_schema':
                columns, rows = table_renderers.render_getter_schema_data(data)
            elif data_type == 'executor_schema':
                columns, rows = table_renderers.render_executor_schema_data(data)
            elif data_type == 'getters':
                columns, rows = table_renderers.render_getters_snapshot_data(data)
            elif data_type == 'executors':
                columns, rows = table_renderers.render_executors_snapshot_data(data)
            elif data_type == 'core_action':
                columns, rows = table_renderers.render_core_action_result_data(data)
            else:
                # Fallback to generic renderer
                columns, rows = table_renderers.render_generic_data(data)

            dialog = QDialog(self)
            dialog.setWindowTitle(tr_key(Dialogs.SERVER_DETAILS_TITLE, title=title))
            dialog.setMinimumSize(800, 400)

            layout = QVBoxLayout(dialog)
            details_table = SimpleDataTable(columns=columns, parent=dialog)
            layout.addWidget(details_table)

            for r in rows:
                details_table.add_row(r)

            dialog.exec_()
        except Exception as e:
            self.logger.error(f"Error showing server details dialog: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Backend core helper
    # ------------------------------------------------------------------
    def _show_core_error(self, action_label: str, error: Exception):
        message = str(error) or tr_key(Errors.UNKNOWN)
        if isinstance(error, UnauthorizedError) and hasattr(self, "handle_unauthorized_error"):
            self.handle_unauthorized_error(message)
            return
        self.logger.error(f"{action_label} failed: {message}")
        self.display_data_table(action_label, {"error": message}, "core_action")

    def _refresh_executor_schema(self):
        self.core_executor_schema = self.core_api.get_executor_schema()

    def _refresh_getter_schema(self):
        self.core_getter_schema = self.core_api.get_getter_schema()

    def _refresh_getters(self):
        self.core_getters = self.core_api.get_getters()
        self.logger.info(f"Fetched getters snapshot count: {len(self.core_getters)}")

    def _refresh_executors(self):
        self.core_executors = self.core_api.get_executors()
        self.logger.info(f"Fetched executors snapshot count: {len(self.core_executors)}")
        self._update_executor_action_buttons_state()

    def _find_executor(self, name: str) -> Optional[ExecutorSnapshotDto]:
        for executor in self.core_executors:
            if executor.name == name:
                return executor
        return None

    def _executor_control_kind(self, name: str) -> str:
        """
        Determine control strategy from schema.
        bool -> digital (on/off)
        everything else -> numeric/value set
        """
        schema_type = str(self.core_executor_schema.get(name, "")).lower()
        return "digital" if schema_type == "bool" else "value"

    def _is_executor_manual(self, executor: ExecutorSnapshotDto) -> bool:
        return str(executor.mode).upper() == "MANUAL"

    def _manual_candidates_exist(self, control_kind: str) -> bool:
        for executor in self.core_executors:
            if self._executor_control_kind(executor.name) != control_kind:
                continue
            if self._is_executor_manual(executor):
                return True
        return False

    def _update_executor_action_buttons_state(self):
        """
        Disable ON/OFF/SET controls unless there is at least one matching
        executor in MANUAL mode.
        """
        has_manual_digital = self._manual_candidates_exist("digital")
        has_manual_value = self._manual_candidates_exist("value")

        if hasattr(self, "testCommandButton"):
            self.testCommandButton.setEnabled(has_manual_digital)
            self.testCommandButton.setToolTip(
                tr_key(Dialogs.EXECUTOR_ON_TITLE)
                if has_manual_digital
                else tr_key(Dialogs.EXECUTORS_NONE_MANUAL)
            )
        if hasattr(self, "logFilesButton"):
            self.logFilesButton.setEnabled(has_manual_digital)
            self.logFilesButton.setToolTip(
                tr_key(Dialogs.EXECUTOR_OFF_TITLE)
                if has_manual_digital
                else tr_key(Dialogs.EXECUTORS_NONE_MANUAL)
            )
        if hasattr(self, "viewLogButton"):
            self.viewLogButton.setEnabled(has_manual_value)
            self.viewLogButton.setToolTip(
                tr_key(Dialogs.EXECUTOR_SET_TITLE)
                if has_manual_value
                else tr_key(Dialogs.EXECUTORS_NONE_MANUAL)
            )

    def _sync_refresh_executor_caches_blocking(self):
        """Fetch executors + schema off the GUI thread; block with a local event loop until done.

        Returns:
            (True, False) on success
            (False, True) if unauthorized (handler already notified)
            (False, False) on other failure
        """
        loop = QEventLoop(self)
        state = {"ok": False, "unauthorized": False}

        def work():
            return self.core_api.get_executors(), self.core_api.get_executor_schema()

        def on_ok(data):
            executors, schema = data
            self.core_executors = list(executors) if isinstance(executors, list) else []
            self.core_executor_schema = dict(schema) if isinstance(schema, dict) else {}
            self._update_executor_action_buttons_state()
            state["ok"] = True
            loop.quit()

        def on_err(message: str):
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Executor cache"):
                state["unauthorized"] = True
            else:
                self.logger.warning("Executor cache refresh failed: %s", message)
            state["ok"] = False
            loop.quit()

        run_thread_task(self, work, on_ok, on_err, thread_name="executor-cache-sync")
        loop.exec_()
        return state["ok"], state["unauthorized"]

    def _pick_executor_name(
        self,
        title: str,
        for_kind: Optional[str] = None,
        manual_only: bool = False,
    ) -> Optional[str]:
        if not self.core_executors or not self.core_executor_schema:
            ok, unauthorized = self._sync_refresh_executor_caches_blocking()
            if not ok and not unauthorized:
                self._show_core_error(
                    "Refresh executors",
                    RuntimeError(tr_key(Errors.UNKNOWN)),
                )
                return None
            if not ok:
                return None

        candidates = []
        for executor in self.core_executors:
            kind = self._executor_control_kind(executor.name)
            if for_kind and kind != for_kind:
                continue
            if manual_only and not self._is_executor_manual(executor):
                continue
            candidates.append(executor.name)

        if not candidates:
            StyledMessageDialog.show_warning(
                self,
                tr_key(Dialogs.EXECUTORS_NONE_TITLE),
                (
                    tr_key(Dialogs.EXECUTORS_NONE_MANUAL)
                    if manual_only
                    else tr_key(Dialogs.EXECUTORS_NONE_GENERIC)
                ),
            )
            return None

        selected, ok = StyledInputDialog.get_item(
            self,
            title,
            tr_key(Dialogs.EXECUTOR_SELECT_LABEL),
            candidates,
            0,
            False,
        )
        if not ok or not selected:
            return None
        return str(selected)

    def ensure_executor_manual(self, executor_name: str) -> bool:
        """Validate executor mode is MANUAL before on/off/set commands."""
        try:
            ok, unauthorized = self._sync_refresh_executor_caches_blocking()
            if not ok and not unauthorized:
                self._show_core_error(
                    "Ensure MANUAL mode",
                    RuntimeError(tr_key(Errors.UNKNOWN)),
                )
                return False
            if not ok:
                return False
            target = self._find_executor(executor_name)
            if not target:
                raise RuntimeError(tr_key(Errors.EXECUTOR_NOT_FOUND, name=executor_name))

            if str(target.mode).upper() == "MANUAL":
                return True

            StyledMessageDialog.show_warning(
                self,
                tr_key(Dialogs.EXECUTOR_AUTO_TITLE),
                tr_key(Dialogs.EXECUTOR_AUTO_BODY, name=executor_name),
            )
            return False
        except Exception as error:
            self._show_core_error("Ensure MANUAL mode", error)
            return False

    # ------------------------------------------------------------------
    # Server tab actions (Greenhouse core)
    # ------------------------------------------------------------------
    def toggle_auto_refresh(self, enabled: bool):
        if enabled:
            self.auto_refresh_timer.start(10000)
            self.logger.info("Core auto-refresh enabled")
        else:
            self.auto_refresh_timer.stop()
            self.logger.info("Core auto-refresh disabled")

    def refresh_all_status(self):
        """Compatibility entry point used by timer + refresh button."""
        self.refresh_core_snapshot()

    def refresh_core_snapshot(self):
        """Poll greenhouse status/schemas/data in a worker thread and display them."""
        self._core_snapshot_request_gen += 1
        gen = self._core_snapshot_request_gen

        def _refresh_job():
            try:
                payload = self._fetch_core_snapshot_payload()
                self._core_snapshot_signals.snapshot_ready.emit((gen, payload))
            except Exception as error:
                self._core_snapshot_signals.snapshot_error.emit(
                    (gen, str(error) or "Unknown core refresh error")
                )

        threading.Thread(target=_refresh_job, name="core-snapshot-refresh", daemon=True).start()

    def _fetch_core_snapshot_payload(self) -> Dict[str, Any]:
        """Run blocking HTTP requests away from the Qt GUI thread."""
        status = self.core_api.get_status()
        getter_schema = self.core_api.get_getter_schema()
        executor_schema = self.core_api.get_executor_schema()
        getters = self.core_api.get_getters()
        executors = self.core_api.get_executors()
        return {
            "status": status,
            "getter_schema": getter_schema,
            "executor_schema": executor_schema,
            "getters": getters,
            "executors": executors,
        }

    def _on_core_snapshot_ready(self, packed):
        try:
            gen, payload = packed
            if gen != self._core_snapshot_request_gen:
                return
            status = payload.get("status")
            self.display_data_table(tr_key(ServerData.CORE_STATUS), {"status": status.status}, "core_status")

            self.core_getter_schema = payload.get("getter_schema", {})
            self.display_data_table(tr_key(ServerData.GETTER_SCHEMA), self.core_getter_schema, "getter_schema")

            self.core_executor_schema = payload.get("executor_schema", {})
            self.display_data_table(tr_key(ServerData.EXECUTOR_SCHEMA), self.core_executor_schema, "executor_schema")

            self.core_getters = payload.get("getters", [])
            self.display_data_table(tr_key(ServerData.GETTERS), self.core_getters, "getters")

            self.core_executors = payload.get("executors", [])
            self._update_executor_action_buttons_state()
            self.display_data_table(tr_key(ServerData.EXECUTORS), self.core_executors, "executors")

            if hasattr(self, "set_status_state") and callable(self.set_status_state):
                self.set_status_state(Status.GREENHOUSE_REFRESHED)
            else:
                self.status_label.setText(tr_key(Status.GREENHOUSE_REFRESHED))
        except Exception as error:
            self._show_core_error("Refresh greenhouse snapshot", error)

    def _on_core_snapshot_error(self, packed):
        gen, error_message = packed
        if gen != self._core_snapshot_request_gen:
            return
        self._show_core_error("Refresh greenhouse snapshot", RuntimeError(error_message))

    def view_core_status(self):
        def work():
            return self.core_api.get_status()

        def on_ok(status):
            self.display_data_table(tr_key(ServerData.CORE_STATUS), {"status": status.status}, "core_status")

        def on_err(message: str):
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Core status"):
                return
            self._show_core_error("Core status", RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="core-status")

    def view_getter_schema(self):
        def work():
            return self.core_api.get_getter_schema()

        def on_ok(schema):
            self.core_getter_schema = schema
            self.display_data_table(tr_key(ServerData.GETTER_SCHEMA), self.core_getter_schema, "getter_schema")

        def on_err(message: str):
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Getter schema"):
                return
            self._show_core_error("Getter schema", RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="getter-schema")

    def view_executor_schema(self):
        def work():
            return self.core_api.get_executor_schema()

        def on_ok(schema):
            self.core_executor_schema = schema
            self.display_data_table(tr_key(ServerData.EXECUTOR_SCHEMA), self.core_executor_schema, "executor_schema")

        def on_err(message: str):
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Executor schema"):
                return
            self._show_core_error("Executor schema", RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="executor-schema")

    def view_getters(self):
        def work():
            return self.core_api.get_getters()

        def on_ok(getters):
            self.core_getters = getters
            self.logger.info(f"Fetched getters snapshot count: {len(self.core_getters)}")
            self.display_data_table(tr_key(ServerData.GETTERS), self.core_getters, "getters")

        def on_err(message: str):
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Getters"):
                return
            self._show_core_error("Getters", RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="getters")

    def view_executors(self):
        def work():
            return self.core_api.get_executors()

        def on_ok(executors):
            self.core_executors = executors
            self.logger.info(f"Fetched executors snapshot count: {len(self.core_executors)}")
            self._update_executor_action_buttons_state()
            self.display_data_table(tr_key(ServerData.EXECUTORS), self.core_executors, "executors")

        def on_err(message: str):
            if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Executors"):
                return
            self._show_core_error("Executors", RuntimeError(message))

        run_thread_task(self, work, on_ok, on_err, thread_name="executors")

    def prompt_switch_executor_mode(self):
        try:
            name = self._pick_executor_name(tr_key(Dialogs.SWITCH_MODE_TITLE))
            if not name:
                return

            selected_mode, ok = StyledInputDialog.get_item(
                self,
                tr_key(Dialogs.EXECUTOR_MODE_TITLE),
                tr_key(Dialogs.EXECUTOR_MODE_LABEL),
                [tr_key(Dialogs.EXECUTOR_MODE_MANUAL), tr_key(Dialogs.EXECUTOR_MODE_AUTO)],
                0,
                False,
            )
            if not ok or not selected_mode:
                return

            mode_value = str(selected_mode).strip().lower()
            manual_label = tr_key(Dialogs.EXECUTOR_MODE_MANUAL).strip().lower()
            auto_label = tr_key(Dialogs.EXECUTOR_MODE_AUTO).strip().lower()
            if mode_value == manual_label:
                mode_value = "manual"
            elif mode_value == auto_label:
                mode_value = "auto"

            def work():
                return self.core_api.set_executor_mode(name, mode_value)

            def on_ok(result):
                self.display_data_table(
                    tr_key(ServerData.SET_MODE, name=name), result, "core_action"
                )
                self.refresh_core_snapshot()

            def on_err(message: str):
                if dispatch_thread_failure_to_ui(
                    self, message, logger=self.logger, log_label="Set executor mode"
                ):
                    return
                self._show_core_error("Set executor mode", RuntimeError(message))

            run_thread_task(self, work, on_ok, on_err, thread_name="executor-set-mode")
        except Exception as error:
            self._show_core_error("Set executor mode", error)

    def prompt_executor_on(self):
        try:
            name = self._pick_executor_name(
                tr_key(Dialogs.EXECUTOR_ON_TITLE),
                for_kind="digital",
                manual_only=True,
            )
            if not name:
                return

            if not self.ensure_executor_manual(name):
                return

            def work():
                return self.core_api.executor_on(name)

            def on_ok(result):
                self.display_data_table(
                    tr_key(ServerData.EXECUTOR_ON, name=name), result, "core_action"
                )
                self.refresh_core_snapshot()

            def on_err(message: str):
                if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Executor ON"):
                    return
                self._show_core_error("Executor ON", RuntimeError(message))

            run_thread_task(self, work, on_ok, on_err, thread_name="executor-on")
        except Exception as error:
            self._show_core_error("Executor ON", error)

    def prompt_executor_off(self):
        try:
            name = self._pick_executor_name(
                tr_key(Dialogs.EXECUTOR_OFF_TITLE),
                for_kind="digital",
                manual_only=True,
            )
            if not name:
                return

            if not self.ensure_executor_manual(name):
                return

            def work():
                return self.core_api.executor_off(name)

            def on_ok(result):
                self.display_data_table(
                    tr_key(ServerData.EXECUTOR_OFF, name=name), result, "core_action"
                )
                self.refresh_core_snapshot()

            def on_err(message: str):
                if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Executor OFF"):
                    return
                self._show_core_error("Executor OFF", RuntimeError(message))

            run_thread_task(self, work, on_ok, on_err, thread_name="executor-off")
        except Exception as error:
            self._show_core_error("Executor OFF", error)

    def prompt_executor_set(self):
        try:
            name = self._pick_executor_name(
                tr_key(Dialogs.EXECUTOR_SET_TITLE),
                for_kind="value",
                manual_only=True,
            )
            if not name:
                return

            if not self.ensure_executor_manual(name):
                return

            value, ok = StyledInputDialog.get_text(
                self,
                tr_key(Dialogs.EXECUTOR_SET_TITLE),
                tr_key(Dialogs.EXECUTOR_SET_LABEL),
            )
            if not ok:
                return
            value = str(value).strip()
            if not value:
                StyledMessageDialog.show_warning(
                    self,
                    tr_key(Dialogs.INVALID_VALUE_TITLE),
                    tr_key(Dialogs.INVALID_VALUE_BODY),
                )
                return

            def work():
                return self.core_api.executor_set(name, value)

            def on_ok(result):
                self.display_data_table(
                    tr_key(ServerData.EXECUTOR_SET, name=name), result, "core_action"
                )
                self.refresh_core_snapshot()

            def on_err(message: str):
                if dispatch_thread_failure_to_ui(self, message, logger=self.logger, log_label="Executor SET"):
                    return
                self._show_core_error("Executor SET", RuntimeError(message))

            run_thread_task(self, work, on_ok, on_err, thread_name="executor-set")
        except Exception as error:
            self._show_core_error("Executor SET", error)



