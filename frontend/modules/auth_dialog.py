from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.core_api_client import ApiRequestError, CoreApiClient, UnauthorizedError
from modules.localization import IRetranslatable, tr_key
from modules.localization.localization_keys import Auth, Common, Dialogs, Errors
from modules.styles import GreenhouseTheme, StyleSheetGenerator
from modules.ui_dialogs import StyledMessageDialog


class AuthDialog(QDialog, IRetranslatable):
    """Sign-in / Sign-up modal supporting live language switching."""

    def __init__(self, api_client: CoreApiClient, auth_session, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.auth_session = auth_session
        self.theme = GreenhouseTheme()
        self.styler = StyleSheetGenerator(self.theme)
        self.authenticated_token: Optional[str] = None
        self.authenticated_user: Optional[dict] = None

        self._title_label = QLabel()
        self._subtitle_label = QLabel()
        self._signin_username_label = QLabel()
        self._signin_password_label = QLabel()
        self._signup_username_label = QLabel()
        self._signup_email_label = QLabel()
        self._signup_password_label = QLabel()
        self._signup_confirm_label = QLabel()
        self._build_ui()
        self.init_localization()

    def _build_ui(self):
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet(self.styler.generate_dialog_style())

        root = QVBoxLayout(self)
        root.setSpacing(10)

        self._title_label.setStyleSheet(self.styler.generate_label_style("title"))
        self._subtitle_label.setProperty("role", "caption")
        self._subtitle_label.setStyleSheet(self.styler.generate_label_style("caption"))
        root.addWidget(self._title_label)
        root.addWidget(self._subtitle_label)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(self.styler.generate_tab_widget_style())
        self._signin_tab = self._build_sign_in_tab()
        self._signup_tab = self._build_sign_up_tab()
        self.tabs.addTab(self._signin_tab, "")
        self.tabs.addTab(self._signup_tab, "")
        root.addWidget(self.tabs)

        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setProperty("role", "caption")
        self.feedback_label.setStyleSheet(self.styler.generate_label_style("caption"))
        root.addWidget(self.feedback_label)

        self.cancel_button = QPushButton()
        self.cancel_button.setStyleSheet(self.styler.generate_button_style("outline"))
        self.cancel_button.clicked.connect(self.reject)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.cancel_button)
        root.addLayout(footer)

    def _build_sign_in_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self.signin_username = QLineEdit()
        self.signin_password = QLineEdit()
        self.signin_password.setEchoMode(QLineEdit.Password)
        self.signin_username.setStyleSheet(self.styler.generate_line_edit_style())
        self.signin_password.setStyleSheet(self.styler.generate_line_edit_style())
        form.addRow(self._signin_username_label, self.signin_username)
        form.addRow(self._signin_password_label, self.signin_password)
        layout.addLayout(form)

        self.signin_button = QPushButton()
        self.signin_button.setStyleSheet(self.styler.generate_button_style("primary"))
        self.signin_button.clicked.connect(self._submit_sign_in)
        layout.addWidget(self.signin_button)
        return tab

    def _build_sign_up_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self.signup_username = QLineEdit()
        self.signup_email = QLineEdit()
        self.signup_password = QLineEdit()
        self.signup_password.setEchoMode(QLineEdit.Password)
        self.signup_confirm_password = QLineEdit()
        self.signup_confirm_password.setEchoMode(QLineEdit.Password)

        for field in (
            self.signup_username,
            self.signup_email,
            self.signup_password,
            self.signup_confirm_password,
        ):
            field.setStyleSheet(self.styler.generate_line_edit_style())

        form.addRow(self._signup_username_label, self.signup_username)
        form.addRow(self._signup_email_label, self.signup_email)
        form.addRow(self._signup_password_label, self.signup_password)
        form.addRow(self._signup_confirm_label, self.signup_confirm_password)
        layout.addLayout(form)

        self.signup_button = QPushButton()
        self.signup_button.setStyleSheet(self.styler.generate_button_style("secondary"))
        self.signup_button.clicked.connect(self._submit_sign_up)
        layout.addWidget(self.signup_button)
        return tab

    def _set_feedback(self, message: str, kind: str = "caption") -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setStyleSheet(self.styler.generate_label_style(kind))
        self._last_feedback_kind = kind

    def _set_busy(self, busy: bool) -> None:
        self.signin_button.setEnabled(not busy)
        self.signup_button.setEnabled(not busy)
        self.cancel_button.setEnabled(not busy)

    @staticmethod
    def _friendly_error_message(error: Exception) -> str:
        """Map technical backend/network errors to user-facing localized text."""
        if isinstance(error, UnauthorizedError):
            return str(error)

        if isinstance(error, ApiRequestError):
            if int(getattr(error, "status_code", 0)) >= 500:
                return tr_key(Errors.SERVER_UNAVAILABLE)
            return str(error) or tr_key(Errors.SERVER_UNAVAILABLE)

        raw_message = str(error or "").strip().lower()
        network_signatures = (
            "connection refused",
            "failed to establish a new connection",
            "max retries exceeded",
            "name or service not known",
            "timed out",
            "connection aborted",
            "connection reset",
        )
        if any(signature in raw_message for signature in network_signatures):
            return tr_key(Errors.SERVER_UNAVAILABLE)
        return str(error) or tr_key(Errors.SERVER_UNAVAILABLE)

    def _submit_sign_in(self) -> None:
        username = self.signin_username.text().strip()
        password = self.signin_password.text()
        if not username or not password:
            self._set_feedback(tr_key(Auth.FB_CREDENTIALS_REQUIRED), "error")
            return

        self._set_busy(True)
        try:
            token = self.api_client.login(username=username, password=password)
            self.auth_session.set_token(token)
            self.authenticated_token = token
            self.authenticated_user = self.auth_session.decode_claims(token)
            self._set_feedback(tr_key(Auth.FB_SIGNED_IN), "success")
            self.accept()
        except UnauthorizedError as error:
            self._set_feedback(str(error), "error")
        except ApiRequestError as error:
            self._set_feedback(self._friendly_error_message(error), "error")
        except Exception as error:
            self._set_feedback(self._friendly_error_message(error), "error")
        finally:
            self._set_busy(False)

    def _submit_sign_up(self) -> None:
        username = self.signup_username.text().strip()
        email = self.signup_email.text().strip()
        password = self.signup_password.text()
        confirm = self.signup_confirm_password.text()

        if not username or not email or not password:
            self._set_feedback(tr_key(Auth.FB_SIGNUP_MISSING), "error")
            return
        if password != confirm:
            self._set_feedback(tr_key(Auth.FB_PASSWORD_MISMATCH), "error")
            return

        self._set_busy(True)
        try:
            self.api_client.register(username=username, password=password, email=email)
            self._set_feedback(tr_key(Auth.FB_SIGNUP_SUCCESS), "success")
            self.tabs.setCurrentIndex(0)
            self.signin_username.setText(username)
            self.signin_password.clear()
        except UnauthorizedError as error:
            self._set_feedback(str(error), "error")
        except ApiRequestError as error:
            self._set_feedback(self._friendly_error_message(error), "error")
        except Exception as error:
            self._set_feedback(self._friendly_error_message(error), "error")
        finally:
            self._set_busy(False)

    def closeEvent(self, event):
        if self.result() != QDialog.Accepted:
            answer = StyledMessageDialog.ask_yes_no(
                self,
                tr_key(Dialogs.EXIT_APP_TITLE),
                tr_key(Dialogs.EXIT_APP_BODY),
            )
            if not answer:
                event.ignore()
                return
        event.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr_key(Auth.DIALOG_TITLE))
        self._title_label.setText(tr_key(Auth.WELCOME_TITLE))
        self._subtitle_label.setText(tr_key(Auth.WELCOME_SUBTITLE))
        self.tabs.setTabText(0, tr_key(Auth.TAB_SIGN_IN))
        self.tabs.setTabText(1, tr_key(Auth.TAB_SIGN_UP))

        self._signin_username_label.setText(tr_key(Auth.USERNAME))
        self._signin_password_label.setText(tr_key(Auth.PASSWORD))
        self.signin_username.setPlaceholderText(tr_key(Auth.USERNAME))
        self.signin_password.setPlaceholderText(tr_key(Auth.PASSWORD))
        self.signin_button.setText(tr_key(Auth.SIGN_IN))

        self._signup_username_label.setText(tr_key(Auth.USERNAME))
        self._signup_email_label.setText(tr_key(Auth.EMAIL))
        self._signup_password_label.setText(tr_key(Auth.PASSWORD))
        self._signup_confirm_label.setText(tr_key(Auth.CONFIRM))
        self.signup_username.setPlaceholderText(tr_key(Auth.USERNAME))
        self.signup_email.setPlaceholderText(tr_key(Auth.EMAIL))
        self.signup_password.setPlaceholderText(tr_key(Auth.PASSWORD))
        self.signup_confirm_password.setPlaceholderText(tr_key(Auth.CONFIRM_PASSWORD))
        self.signup_button.setText(tr_key(Auth.CREATE_ACCOUNT))

        self.cancel_button.setText(tr_key(Common.EXIT))
