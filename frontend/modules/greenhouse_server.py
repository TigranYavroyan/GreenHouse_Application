import logging
from typing import Any, Dict, Optional

import requests
from PyQt5.QtCore import QDateTime
from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout

from modules.table_widget import SimpleDataTable
from modules import table_renderers


class ServerPanelMixin:
    """
    Mixin responsible for:
    - HTTP calls to the backend server (health, stats, sessions, cache, queues, logs)
    - Server table population + detailed views
    - Auto-refresh for server status

    Expects the main window to provide:
      - self.backend_url (str)
      - self.logger (logging.Logger)
      - self.server_table (SimpleDataTable or None)
      - self.server_history (list)
      - self.auto_refresh_timer (QTimer)
    """

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
                    "data": data,
                    "data_type": data_type,
                }
            )

            # Compute a short, user-friendly status summary for the main server table
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            status = "✅ OK"
            if isinstance(data, dict) and data.get("error"):
                status = f"❌ Error: {data.get('error')}"

            # Append a compact summary row; detailed view is available on double-click
            self.server_table.add_row([timestamp, title, status])

            self.logger.info(f"Added server summary row for '{title}' ({data_type})")

        except Exception as e:
            self.logger.error(f"Error displaying data table: {e}", exc_info=True)

    def clear_server_tables(self):
        """Clear server info table"""
        if self.server_table:
            self.server_table.clear_data()
        self.server_history = []

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
            if data_type == 'health':
                columns, rows = table_renderers.render_health_data(data)
            elif data_type == 'stats':
                columns, rows = table_renderers.render_stats_data(data)
            elif data_type == 'sessions':
                columns, rows = table_renderers.render_sessions_data(data)
            elif data_type == 'cache_keys':
                columns, rows = table_renderers.render_cache_keys_data(data)
            elif data_type == 'queues':
                columns, rows = table_renderers.render_queues_data(data)
            elif data_type == 'logs':
                columns, rows = table_renderers.render_logs_data(data)
            elif data_type == 'session_log':
                columns, rows = table_renderers.render_session_log_data(data)
            elif data_type == 'fog_aggregated':
                columns, rows = table_renderers.render_fog_aggregated_data(data)
            elif data_type == 'fog_devices':
                columns, rows = table_renderers.render_fog_devices_data(data)
            elif data_type == 'fog_anomalies':
                columns, rows = table_renderers.render_fog_anomalies_data(data)
            elif data_type == 'command_result':
                # Use the generic command result renderer
                timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                cached = bool(data.get('cached', False)) if isinstance(data, Dict) else False
                columns, rows = table_renderers.render_command_result_data(
                    data if isinstance(data, Dict) else {'result': data},
                    command=title,
                    timestamp=timestamp,
                    cached=cached,
                )
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
    # HTTP helper
    # ------------------------------------------------------------------
    def make_server_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None):
        """Make HTTP request to backend server"""
        try:
            url = f"{self.backend_url}{endpoint}"
            self.logger.info(f"{method} {endpoint}")

            if method == 'GET':
                response = requests.get(url, timeout=5)
            elif method == 'DELETE':
                response = requests.delete(url, timeout=5)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=5)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Cannot connect to backend server at {self.backend_url}. Make sure it's running.")
            return None
        except requests.exceptions.Timeout:
            self.logger.error("Request timeout - server is not responding")
            return None
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            return None

    # ------------------------------------------------------------------
    # Server tab actions
    # ------------------------------------------------------------------
    def toggle_auto_refresh(self, enabled: bool):
        if enabled:
            self.auto_refresh_timer.start(10000)  # 10 seconds
            self.logger.info("Auto-refresh enabled")
        else:
            self.auto_refresh_timer.stop()
            self.logger.info("Auto-refresh disabled")

    def refresh_all_status(self):
        """Refresh all server status information"""
        self.check_server_health()
        self.view_server_stats()
        self.list_sessions()

    def check_server_health(self):
        """Check server health status"""
        result = self.make_server_request('/metadata/health/')
        if result:
            self.display_data_table("Server Health", result, 'health')

    def view_server_stats(self):
        """View server statistics"""
        result = self.make_server_request('/metadata/stats/')
        if result:
            self.display_data_table("Server Statistics", result, 'stats')

    def list_sessions(self):
        """List active sessions"""
        result = self.make_server_request('/sessions')
        if result:
            self.display_data_table("Active Sessions", result, 'sessions')

    def list_cache_keys(self):
        """List cache keys"""
        result = self.make_server_request('/cache/keys')
        if result:
            self.display_data_table("Cache Keys", result, 'cache_keys')

    def clear_all_cache(self):
        """Clear all cache"""
        reply = QMessageBox.question(
            self,
            'Clear Cache',
            'Are you sure you want to clear ALL cache?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            result = self.make_server_request('/cache/clear', method='DELETE')
            if result:
                self.display_data_table("Cache Clear Result", result, 'cache_clear')

    def check_queues(self):
        """Check RabbitMQ queue status"""
        result = self.make_server_request('/metadata/queues/')
        if result:
            self.display_data_table("Queue Status", result, 'queues')

    def test_server_command(self):
        """Test server command execution"""
        command_data = {
            "command": "read_sensor",
            "parameters": {}
        }
        result = self.make_server_request('/command', method='POST', data=command_data)
        if result:
            self.display_data_table("Test Command Result", result, 'command_result')

    # ------------------------------------------------------------------
    # Logs + fog data
    # ------------------------------------------------------------------
    def list_log_files(self):
        """List all session log files"""
        result = self.make_server_request('/logs')
        if result:
            self.display_data_table("Session Log Files", result, 'logs')

    def view_session_log(self):
        """View specific session log"""
        # For now, use the current session ID
        session_id = self.session_id

        result = self.make_server_request(f'/sessions/{session_id}/log')
        if result:
            # Use session log renderer
            self.display_data_table(f"Session Log: {result.get('sessionId', 'Unknown')}", result, 'session_log')

    def view_fog_aggregated_data(self):
        """View aggregated fog data from backend"""
        result = self.make_server_request('/fog/aggregated')
        if result:
            self.display_data_table("Fog Aggregated Data", result, 'fog_aggregated')

    def view_fog_devices(self):
        """View fog edge devices from backend"""
        result = self.make_server_request('/fog/devices')
        if result:
            self.display_data_table("Fog Edge Devices", result, 'fog_devices')

    def view_fog_anomalies(self):
        """View fog anomalies from backend"""
        limit = 20
        result = self.make_server_request(f'/fog/anomalies?limit={limit}')
        if result:
            self.display_data_table("Fog Anomalies", result, 'fog_anomalies')



