from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.core_api_client import ApiRequestError, CoreApiClient, UnauthorizedError
from modules.styles import GreenhouseTheme, StyleSheetGenerator


class AuthDialog(QDialog):
    def __init__(self, api_client: CoreApiClient, auth_session, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.auth_session = auth_session
        self.theme = GreenhouseTheme()
        self.styler = StyleSheetGenerator(self.theme)
        self.authenticated_token: Optional[str] = None
        self.authenticated_user: Optional[dict] = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("Greenhouse Sign In")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet(self.styler.generate_dialog_style())

        root = QVBoxLayout(self)
        root.setSpacing(10)

        title = QLabel("Welcome to Greenhouse Automation")
        title.setStyleSheet(self.styler.generate_label_style("title"))
        subtitle = QLabel("Sign in or create an account to continue.")
        subtitle.setProperty("role", "caption")
        subtitle.setStyleSheet(self.styler.generate_label_style("caption"))
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(self.styler.generate_tab_widget_style())
        self.tabs.addTab(self._build_sign_in_tab(), "Sign In")
        self.tabs.addTab(self._build_sign_up_tab(), "Sign Up")
        root.addWidget(self.tabs)

        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setProperty("role", "caption")
        self.feedback_label.setStyleSheet(self.styler.generate_label_style("caption"))
        root.addWidget(self.feedback_label)

        self.cancel_button = QPushButton("Exit")
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
        self.signin_username.setPlaceholderText("Username")
        self.signin_password = QLineEdit()
        self.signin_password.setEchoMode(QLineEdit.Password)
        self.signin_password.setPlaceholderText("Password")
        self.signin_username.setStyleSheet(self.styler.generate_line_edit_style())
        self.signin_password.setStyleSheet(self.styler.generate_line_edit_style())
        form.addRow("Username", self.signin_username)
        form.addRow("Password", self.signin_password)
        layout.addLayout(form)

        self.signin_button = QPushButton("Sign In")
        self.signin_button.setStyleSheet(self.styler.generate_button_style("primary"))
        self.signin_button.clicked.connect(self._submit_sign_in)
        layout.addWidget(self.signin_button)
        return tab

    def _build_sign_up_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self.signup_username = QLineEdit()
        self.signup_username.setPlaceholderText("Username")
        self.signup_email = QLineEdit()
        self.signup_email.setPlaceholderText("Email")
        self.signup_password = QLineEdit()
        self.signup_password.setEchoMode(QLineEdit.Password)
        self.signup_password.setPlaceholderText("Password")
        self.signup_confirm_password = QLineEdit()
        self.signup_confirm_password.setEchoMode(QLineEdit.Password)
        self.signup_confirm_password.setPlaceholderText("Confirm password")

        for field in (
            self.signup_username,
            self.signup_email,
            self.signup_password,
            self.signup_confirm_password,
        ):
            field.setStyleSheet(self.styler.generate_line_edit_style())

        form.addRow("Username", self.signup_username)
        form.addRow("Email", self.signup_email)
        form.addRow("Password", self.signup_password)
        form.addRow("Confirm", self.signup_confirm_password)
        layout.addLayout(form)

        self.signup_button = QPushButton("Create Account")
        self.signup_button.setStyleSheet(self.styler.generate_button_style("secondary"))
        self.signup_button.clicked.connect(self._submit_sign_up)
        layout.addWidget(self.signup_button)
        return tab

    def _set_feedback(self, message: str, kind: str = "caption") -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setStyleSheet(self.styler.generate_label_style(kind))

    def _set_busy(self, busy: bool) -> None:
        self.signin_button.setEnabled(not busy)
        self.signup_button.setEnabled(not busy)
        self.cancel_button.setEnabled(not busy)

    def _submit_sign_in(self) -> None:
        username = self.signin_username.text().strip()
        password = self.signin_password.text()
        if not username or not password:
            self._set_feedback("Username and password are required.", "error")
            return

        self._set_busy(True)
        try:
            token = self.api_client.login(username=username, password=password)
            self.auth_session.set_token(token)
            self.authenticated_token = token
            self.authenticated_user = self.auth_session.decode_claims(token)
            self._set_feedback("Signed in successfully.", "success")
            self.accept()
        except UnauthorizedError as error:
            self._set_feedback(str(error), "error")
        except ApiRequestError as error:
            self._set_feedback(str(error), "error")
        except Exception as error:
            self._set_feedback(str(error), "error")
        finally:
            self._set_busy(False)

    def _submit_sign_up(self) -> None:
        username = self.signup_username.text().strip()
        email = self.signup_email.text().strip()
        password = self.signup_password.text()
        confirm = self.signup_confirm_password.text()

        if not username or not email or not password:
            self._set_feedback("Username, email and password are required.", "error")
            return
        if password != confirm:
            self._set_feedback("Password and confirmation do not match.", "error")
            return

        self._set_busy(True)
        try:
            self.api_client.register(username=username, password=password, email=email)
            self._set_feedback(
                "Account created. Check your email, verify your account, then sign in.",
                "success",
            )
            self.tabs.setCurrentIndex(0)
            self.signin_username.setText(username)
            self.signin_password.clear()
        except UnauthorizedError as error:
            self._set_feedback(str(error), "error")
        except ApiRequestError as error:
            self._set_feedback(str(error), "error")
        except Exception as error:
            self._set_feedback(str(error), "error")
        finally:
            self._set_busy(False)

    def closeEvent(self, event):
        if self.result() != QDialog.Accepted:
            answer = QMessageBox.question(
                self,
                "Exit Application",
                "Authentication is required. Exit now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()

