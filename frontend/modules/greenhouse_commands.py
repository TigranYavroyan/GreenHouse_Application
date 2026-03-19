import uuid
import logging
import datetime

from PyQt5.QtCore import QDateTime, QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout

from modules.command_worker import CommandWorker
from modules.table_widget import SimpleDataTable
from modules.json_prettifier import extract_payload, build_user_friendly_rows
from modules import table_renderers
from modules.ui_dialogs import StyledMessageDialog


class CommandPanelMixin:
    """
    Mixin that encapsulates:
    - Command worker lifecycle
    - Sending user commands to RabbitMQ
    - Handling command responses and errors
    - Control table + detailed command result dialogs

    Expects the main window to provide:
      - self.session_id (str)
      - self.theme (GreenhouseTheme)
      - self.logger (logging.Logger)
      - self.pending_commands (dict)
      - self.control_table (SimpleDataTable or None)
      - self.control_history (list)
      - self.connection_status (QLabel)
      - self.status_label (QLabel)
    """

    def setup_command_worker(self):
        self.logger.info("Setting up command worker")
        self.command_worker = CommandWorker()
        self.command_worker.response_received.connect(self.handle_response)
        self.command_worker.connection_status.connect(self.update_connection_status)
        self.command_worker.error_occurred.connect(self.handle_error)

        # Initial connection
        self.command_worker.setup_rabbitmq()

        # Setup connection check timer
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_connection)
        self.connection_timer.start(10000)

        self.pending_command_timeout_ms = 30000
        self.pending_command_check_timer = QTimer()
        self.pending_command_check_timer.timeout.connect(self.expire_pending_commands)
        self.pending_command_check_timer.start(1000)

    # ------------------------------------------------------------------
    # Control table helpers
    # ------------------------------------------------------------------
    def clear_control_table(self):
        """Clear control tab command results table"""
        if self.control_table:
            self.control_table.clear_data()
        self.control_history = []

    def show_control_details(self, row, column):
        """Open a detailed table view for a selected control-table row."""
        if row < 0 or row >= len(self.control_history):
            self.logger.warning(f"Control details requested for invalid row {row}")
            return

        entry = self.control_history[row]
        response = entry.get("response", {})
        timestamp = entry.get("timestamp", "")
        command_name = entry.get("command", "unknown")
        cached = bool(entry.get("cached", False))

        try:
            # For double-click, focus specifically on the "result" JSON payload
            # and present it as simple key/value rows for easy reading.
            if isinstance(response, dict) and "result" in response:
                payload = response.get("result")
            else:
                payload = extract_payload(response)

            # We don't pass summary_text here so all payload fields are shown.
            columns, rows = build_user_friendly_rows(payload, summary_text="")

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Command Result Details - {command_name}")
            dialog.setMinimumSize(800, 400)

            layout = QVBoxLayout(dialog)
            details_table = SimpleDataTable(columns=columns, parent=dialog)
            layout.addWidget(details_table)

            for r in rows:
                details_table.add_row(r)

            dialog.setLayout(layout)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"Error showing control details dialog: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Command worker + messaging
    # ------------------------------------------------------------------
    def update_connection_status(self, connected):
        self.rabbitmq_connected = connected
        if connected:
            self.connection_status.setText("✅ Connected to RabbitMQ")
            self.connection_status.setStyleSheet(f"""
                color: {self.theme.colors.success}; 
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_100};
                padding: 2px 6px;
                border-radius: {self.theme.borderRadius.sm};
                border: 1px solid {self.theme.colors.grey_300};
                border-left: 2px solid {self.theme.colors.success};
            """)
        else:
            self.connection_status.setText("❌ Disconnected from RabbitMQ")
            self.connection_status.setStyleSheet(f"""
                color: {self.theme.colors.error}; 
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_100};
                padding: 2px 6px;
                border-radius: {self.theme.borderRadius.sm};
                border: 1px solid {self.theme.colors.grey_300};
                border-left: 2px solid {self.theme.colors.error};
            """)

    def check_connection(self):
        if not self.rabbitmq_connected:
            self.logger.info("Attempting to reconnect to RabbitMQ...")
            self.command_worker.setup_rabbitmq()

    def send_user_command(self, command, parameters=None):
        """Send a user command with automatic retry"""
        command_id = str(uuid.uuid4())
        command_data = {
            'commandId': command_id,
            'command': command,
            'type': 'user',
            'parameters': parameters or {},
            'sessionId': self.session_id
        }

        self.pending_commands[command_id] = {
            "type": "user",
            "command": command,
            "parameters": parameters or {},
            "command_data": command_data,
            "created_at_ms": QDateTime.currentMSecsSinceEpoch(),
            "retries_left": 1,
            "sent": False
        }

        self.logger.info(f"Sending user command {command_id}: {command}")
        return self._send_pending_command(command_id)

    def _send_pending_command(self, command_id):
        command_info = self.pending_commands.get(command_id)
        if not command_info:
            return False

        command_data = command_info.get("command_data")
        if not command_data:
            self.logger.error(f"Missing command_data for pending command {command_id}")
            self.pending_commands.pop(command_id, None)
            return False

        if self.command_worker.send_command(command_data):
            command_info["sent"] = True
            command_info["sent_at_ms"] = QDateTime.currentMSecsSinceEpoch()
            self.logger.info(f"Command sent: {command_info.get('command', 'unknown')}")
            return True

        retries_left = int(command_info.get("retries_left", 0))
        if retries_left <= 0:
            self.logger.error(f"Failed to send command {command_id} after retry")
            self.pending_commands.pop(command_id, None)
            self.status_label.setText("❌ Failed to send command")
            return False

        command_info["retries_left"] = retries_left - 1
        self.logger.warning(f"Send failed for {command_id}, attempting reconnect retry")

        def _after_reconnect(success):
            if not success:
                self.logger.error(f"Reconnect failed for command {command_id}")
                return
            self._send_pending_command(command_id)

        self.command_worker.attempt_reconnect(callback=_after_reconnect)
        return False

    def expire_pending_commands(self):
        now_ms = QDateTime.currentMSecsSinceEpoch()
        expired_ids = []

        for command_id, command_info in list(self.pending_commands.items()):
            created_at_ms = int(command_info.get("created_at_ms", now_ms))
            if now_ms - created_at_ms <= self.pending_command_timeout_ms:
                continue
            expired_ids.append(command_id)

        for command_id in expired_ids:
            command_info = self.pending_commands.pop(command_id, {})
            command_name = command_info.get("command", "unknown")
            self.logger.error(f"Command timed out waiting for response: {command_id} ({command_name})")
            self.status_label.setText("❌ Command timed out")

    def handle_response(self, response):
        command_id = response.get('commandId')
        result = response.get('result', {})
        cached = response.get('cached', False)
        error = response.get('error')
        session_id = response.get('sessionId')
        current_path = response.get('currentPath')

        self.logger.info(f"Received response for command {command_id}, cached: {cached}, error: {bool(error)}")

        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")

        # Get command name from pending commands or response
        command_name = "unknown"
        if command_id in self.pending_commands:
            command_info = self.pending_commands[command_id]
            command_name = command_info.get('command', 'unknown')
            del self.pending_commands[command_id]
        else:
            command_name = response.get('command', 'unknown')
            self.logger.warning(f"Command ID {command_id} not found in pending_commands!")

        # Add row to table with data from RabbitMQ
        if self.control_table:
            try:
                # Store full response for detailed view
                self.control_history.append(
                    {
                        "timestamp": timestamp,
                        "command": command_name,
                        "response": response,
                        "cached": cached,
                        "error": error,
                    }
                )

                # Use table renderer to format a compact, user-friendly summary
                columns, rows = table_renderers.render_command_result_data(
                    response,
                    command=command_name,
                    timestamp=timestamp,
                    cached=cached,
                )

                # Our control_table is initialized with 4 columns, so we combine
                # the renderer's Result + Cached columns into a single Result cell.
                if rows:
                    rendered_row = rows[0]
                    # Expected from renderer: [timestamp, command, status, result_str, cached_str]
                    if len(rendered_row) >= 5:
                        _, _, status, result_str, cached_str = rendered_row
                        display_result = f"{result_str} (Cached: {cached_str})"
                    else:
                        # Fallback if renderer shape changes
                        status = rendered_row[2] if len(rendered_row) > 2 else ""
                        display_result = rendered_row[3] if len(rendered_row) > 3 else ""

                    self.control_table.add_row([timestamp, command_name, status, display_result])
                    self.logger.info(f"Added row to control table: {command_name} - {status}")
                    if hasattr(self, "persist_user_log"):
                        self.persist_user_log(
                            "control",
                            command_name,
                            {
                                "command": command_name,
                                "status": status,
                                "result": display_result,
                                "response": response if isinstance(response, dict) else {},
                                "cached": cached,
                                "error": error,
                            },
                            {"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                        )

            except Exception as e:
                self.logger.error(f"Error displaying command result in table: {e}", exc_info=True)
        else:
            self.logger.warning("Control table not initialized, cannot display command result")

        status_suffix = " (cached)" if cached else ""
        if error:
            self.status_label.setText(f"❌ Command failed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.error};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 10px 16px;
                min-height: 32px;
                border-radius: {self.theme.borderRadius.md};
                border-left: 3px solid {self.theme.colors.error};
            """)
        else:
            self.status_label.setText(f"✅ Command completed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.success};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 10px 16px;
                min-height: 32px;
                border-radius: {self.theme.borderRadius.md};
                border-left: 3px solid {self.theme.colors.success};
            """)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    def handle_error(self, error_message):
        self.logger.error(f"Command worker error: {error_message}")
        self.show_error("System Error", error_message)

    def show_error(self, title, message):
        self.logger.warning(f"Showing error dialog: {title} - {message}")
        StyledMessageDialog.show_error(self, str(title), str(message))



