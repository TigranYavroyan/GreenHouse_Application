from typing import Any, Dict, List, Optional
from copy import deepcopy

from PyQt5.QtCore import QDateTime
from PyQt5.QtWidgets import QDialog, QVBoxLayout

from modules.table_widget import SimpleDataTable
from modules import table_renderers
from modules.core_api_client import CoreApiClient, UnauthorizedError
from modules.core_dtos import ExecutorSnapshotDto, GetterSnapshotDto
from modules.ui_dialogs import StyledInputDialog, StyledMessageDialog


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

            # Compute a short status summary for the main server table
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            status = "Success"
            if isinstance(data, dict) and data.get("error"):
                status = "Failed"

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
        title = entry.get("title", "Server Data")
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
            dialog.setWindowTitle(f"{title} - Details")
            dialog.setMinimumSize(800, 400)

            layout = QVBoxLayout(dialog)
            details_table = SimpleDataTable(columns=columns, parent=dialog)
            layout.addWidget(details_table)

            for r in rows:
                details_table.add_row(r)

            dialog.setLayout(layout)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"Error showing server details dialog: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Backend core helper
    # ------------------------------------------------------------------
    def _show_core_error(self, action_label: str, error: Exception):
        message = str(error) or "Unknown error"
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
                "Turn selected MANUAL digital executor ON."
                if has_manual_digital
                else "No MANUAL digital executors available."
            )
        if hasattr(self, "logFilesButton"):
            self.logFilesButton.setEnabled(has_manual_digital)
            self.logFilesButton.setToolTip(
                "Turn selected MANUAL digital executor OFF."
                if has_manual_digital
                else "No MANUAL digital executors available."
            )
        if hasattr(self, "viewLogButton"):
            self.viewLogButton.setEnabled(has_manual_value)
            self.viewLogButton.setToolTip(
                "Set value for selected MANUAL value executor."
                if has_manual_value
                else "No MANUAL value executors available."
            )

    def _pick_executor_name(
        self,
        title: str,
        for_kind: Optional[str] = None,
        manual_only: bool = False,
    ) -> Optional[str]:
        if not self.core_executors:
            self._refresh_executors()
        if not self.core_executor_schema:
            self._refresh_executor_schema()

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
                "No Executors",
                (
                    "No matching MANUAL executors are available."
                    if manual_only
                    else "No matching executors are available."
                ),
            )
            return None

        selected, ok = StyledInputDialog.get_item(self, title, "Select executor:", candidates, 0, False)
        if not ok or not selected:
            return None
        return str(selected)

    def ensure_executor_manual(self, executor_name: str) -> bool:
        """Validate executor mode is MANUAL before on/off/set commands."""
        try:
            self._refresh_executors()
            target = self._find_executor(executor_name)
            if not target:
                raise RuntimeError(f'Executor "{executor_name}" not found')

            if str(target.mode).upper() == "MANUAL":
                return True

            StyledMessageDialog.show_warning(
                self,
                "Executor in AUTO mode",
                (
                    f'Executor "{executor_name}" is in AUTO mode.\n'
                    "Switch it to MANUAL mode first."
                ),
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
        """Poll greenhouse status/schemas/data and display them."""
        try:
            status = self.core_api.get_status()
            self.display_data_table("Core Status", {"status": status.status}, "core_status")

            self._refresh_getter_schema()
            self.display_data_table("Getter Schema", self.core_getter_schema, "getter_schema")

            self._refresh_executor_schema()
            self.display_data_table("Executor Schema", self.core_executor_schema, "executor_schema")

            self._refresh_getters()
            self.display_data_table("Getters", self.core_getters, "getters")

            self._refresh_executors()
            self.display_data_table("Executors", self.core_executors, "executors")

            self.status_label.setText("Greenhouse state refreshed")
        except Exception as error:
            self._show_core_error("Refresh greenhouse snapshot", error)

    def view_core_status(self):
        try:
            status = self.core_api.get_status()
            self.display_data_table("Core Status", {"status": status.status}, "core_status")
        except Exception as error:
            self._show_core_error("Core status", error)

    def view_getter_schema(self):
        try:
            self._refresh_getter_schema()
            self.display_data_table("Getter Schema", self.core_getter_schema, "getter_schema")
        except Exception as error:
            self._show_core_error("Getter schema", error)

    def view_executor_schema(self):
        try:
            self._refresh_executor_schema()
            self.display_data_table("Executor Schema", self.core_executor_schema, "executor_schema")
        except Exception as error:
            self._show_core_error("Executor schema", error)

    def view_getters(self):
        try:
            self._refresh_getters()
            self.display_data_table("Getters", self.core_getters, "getters")
        except Exception as error:
            self._show_core_error("Getters", error)

    def view_executors(self):
        try:
            self._refresh_executors()
            self.display_data_table("Executors", self.core_executors, "executors")
        except Exception as error:
            self._show_core_error("Executors", error)

    def prompt_switch_executor_mode(self):
        try:
            name = self._pick_executor_name("Switch Executor Mode")
            if not name:
                return

            selected_mode, ok = StyledInputDialog.get_item(
                self,
                "Executor Mode",
                "Mode:",
                ["manual", "auto"],
                0,
                False,
            )
            if not ok or not selected_mode:
                return

            result = self.core_api.set_executor_mode(name, str(selected_mode))
            self.display_data_table(f"Set Mode ({name})", result, "core_action")
            self.refresh_core_snapshot()
        except Exception as error:
            self._show_core_error("Set executor mode", error)

    def prompt_executor_on(self):
        try:
            name = self._pick_executor_name(
                "Turn Executor ON",
                for_kind="digital",
                manual_only=True,
            )
            if not name:
                return

            if not self.ensure_executor_manual(name):
                return

            result = self.core_api.executor_on(name)
            self.display_data_table(f"Executor ON ({name})", result, "core_action")
            self.refresh_core_snapshot()
        except Exception as error:
            self._show_core_error("Executor ON", error)

    def prompt_executor_off(self):
        try:
            name = self._pick_executor_name(
                "Turn Executor OFF",
                for_kind="digital",
                manual_only=True,
            )
            if not name:
                return

            if not self.ensure_executor_manual(name):
                return

            result = self.core_api.executor_off(name)
            self.display_data_table(f"Executor OFF ({name})", result, "core_action")
            self.refresh_core_snapshot()
        except Exception as error:
            self._show_core_error("Executor OFF", error)

    def prompt_executor_set(self):
        try:
            name = self._pick_executor_name(
                "Set Executor Value",
                for_kind="value",
                manual_only=True,
            )
            if not name:
                return

            if not self.ensure_executor_manual(name):
                return

            value, ok = StyledInputDialog.get_text(self, "Set Executor Value", "Value:")
            if not ok:
                return
            value = str(value).strip()
            if not value:
                StyledMessageDialog.show_warning(self, "Invalid value", "Value is required.")
                return

            result = self.core_api.executor_set(name, value)
            self.display_data_table(f"Executor SET ({name})", result, "core_action")
            self.refresh_core_snapshot()
        except Exception as error:
            self._show_core_error("Executor SET", error)



