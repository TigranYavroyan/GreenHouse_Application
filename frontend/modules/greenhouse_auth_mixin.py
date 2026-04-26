"""Authentication UI and session recovery for the desktop shell."""
from datetime import datetime, timezone

from PyQt5.QtWidgets import QLabel, QPushButton

from modules.auth_dialog import AuthDialog
from modules.core_api_client import CoreApiClient, UnauthorizedError
from modules.ui_dialogs import StyledMessageDialog


class GreenhouseAuthMixin:
    def setup_auth_controls(self):
        if not hasattr(self, "sessionLayout") or not self.sessionLayout:
            return

        self.auth_user_label = QLabel("")
        self.auth_user_label.setObjectName("authUserLabel")
        self.logoutButton = QPushButton("Logout")
        self.logoutButton.setObjectName("logoutButton")
        self.logoutButton.setMinimumHeight(24)

        self.sessionLayout.insertWidget(2, self.auth_user_label)
        self.sessionLayout.addWidget(self.logoutButton)
        self.update_auth_user_label()

    def update_auth_user_label(self):
        if not self.auth_user_label:
            return
        claims = self.auth_session.decode_claims()
        username = str(claims.get("username", "")).strip()
        if username:
            self.auth_user_label.setText(f"User: {username}")
            self.auth_user_label.setToolTip("Authenticated user")
        else:
            self.auth_user_label.setText("User: -")
            self.auth_user_label.setToolTip("No authenticated user")

    def get_auth_token(self):
        return self.auth_session.get_token()

    def _build_auth_api_client(self):
        return CoreApiClient(self.backend_url, auth_token_provider=self.get_auth_token)

    def _reauthenticate_or_exit(self):
        while True:
            dialog = AuthDialog(CoreApiClient(self.backend_url), self.auth_session, parent=self)
            result = dialog.exec_()
            if result == dialog.Accepted:
                try:
                    self._build_auth_api_client().get_current_user()
                    self.update_auth_user_label()
                    self._prompt_restore_user_data_preference()
                    return True
                except Exception as error:
                    self.auth_session.clear_token()
                    StyledMessageDialog.show_warning(
                        self,
                        "Authentication Error",
                        f"Sign in succeeded but session validation failed: {error}",
                    )
                    continue
            return False

    def _pause_authenticated_timers(self):
        state = {
            "auto_refresh": bool(
                hasattr(self, "auto_refresh_timer") and self.auto_refresh_timer.isActive()
            ),
            "schedule_clock": bool(
                getattr(self, "schedule_clock_timer", None)
                and self.schedule_clock_timer.isActive()
            ),
        }
        if state["auto_refresh"]:
            self.auto_refresh_timer.stop()
        if state["schedule_clock"]:
            self.schedule_clock_timer.stop()
        return state

    def _resume_authenticated_timers(self, state):
        if not isinstance(state, dict):
            return
        if state.get("auto_refresh") and hasattr(self, "auto_refresh_timer"):
            self.auto_refresh_timer.start(10000)
        if state.get("schedule_clock") and getattr(self, "schedule_clock_timer", None):
            self.schedule_clock_timer.start(1000)

    def _reset_user_scoped_tables(self):
        """Clear user-scoped table data before switching authentication context."""
        if self.control_table:
            self.control_table.clear_data()
        if self.server_table:
            self.server_table.clear_data()
        if self.schedule_table:
            self.schedule_table.clear_data()

        self.control_history = []
        self.server_history = []
        self.schedule_table_rows = []
        self.schedule_rows = []
        self.schedule_device_id = None
        self.schedule_target_keys = []
        self.hidden_schedule_ids = set()

        if hasattr(self, "statisticsDeviceCombo"):
            self.statisticsDeviceCombo.clear()
        if hasattr(self, "statisticsSensorCombo"):
            self.statisticsSensorCombo.clear()
        if self.statistics_curve:
            self.statistics_curve.setData([], [])

    def handle_unauthorized_error(self, message="Unauthorized"):
        if self._auth_recovery_in_progress:
            return

        self._auth_recovery_in_progress = True
        timer_state = self._pause_authenticated_timers()
        try:
            self._reset_user_scoped_tables()
            self.auth_session.clear_token()
            self.update_auth_user_label()
            StyledMessageDialog.show_warning(
                self,
                "Session Expired",
                f"{message}\n\nPlease sign in again.",
            )

            if self._reauthenticate_or_exit():
                self._resume_authenticated_timers(timer_state)
                self.status_label.setText("✅ Re-authenticated successfully")
                return

            self.close()
        finally:
            self._auth_recovery_in_progress = False

    def logout_user(self):
        confirm = StyledMessageDialog.ask_yes_no(
            self,
            "Logout",
            "Sign out from this desktop session?",
            yes_text="Yes",
            no_text="No",
        )
        if not confirm:
            return

        if self._auth_recovery_in_progress:
            return

        self._auth_recovery_in_progress = True
        timer_state = self._pause_authenticated_timers()
        try:
            self._reset_user_scoped_tables()
            self.auth_session.clear_token()
            self.update_auth_user_label()
            self.status_label.setText("Signed out")
            if self._reauthenticate_or_exit():
                self._resume_authenticated_timers(timer_state)
                self.status_label.setText("✅ Signed in again")
                return
            self.close()
        finally:
            self._auth_recovery_in_progress = False

    def _handle_api_exception(self, title, error):
        if isinstance(error, UnauthorizedError):
            self.handle_unauthorized_error(str(error))
            return
        self.show_error(title, str(error))
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
