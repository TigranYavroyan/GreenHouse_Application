from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
import sys
import logging
import argparse
import os

from modules.config import config

from modules.greenhouse import GreenhouseDesktop
from modules.logging_setup import setup_logging
from modules.auth_dialog import AuthDialog
from modules.auth_session import AuthSessionManager
from modules.core_api_client import CoreApiClient, UnauthorizedError, ApiRequestError
from modules.localization import AppSettings, LocalizationManager, tr_key
from modules.localization.localization_keys import Dialogs, Errors
from modules.ui_dialogs import StyledMessageDialog


ORG_NAME = "GreenHouse"
APP_NAME = "Desktop"


def ensure_authenticated(app, backend_url, auth_session):
    validator = CoreApiClient(backend_url, auth_token_provider=auth_session.get_token)
    existing_token = auth_session.get_token()
    if existing_token:
        try:
            validator.get_current_user()
            return True
        except UnauthorizedError:
            auth_session.clear_token()
        except Exception as error:
            logging.getLogger("GreenhouseDesktop").warning(f"Stored token validation failed: {error}")
            auth_session.clear_token()

    while True:
        dialog = AuthDialog(CoreApiClient(backend_url), auth_session)
        result = dialog.exec_()
        if result == dialog.Accepted:
            try:
                validator.get_current_user()
                return True
            except Exception as error:
                auth_session.clear_token()
                if isinstance(error, ApiRequestError) and int(getattr(error, "status_code", 0)) < 500:
                    message = tr_key(Errors.AUTHENTICATION_FAILED_BODY, error=str(error))
                else:
                    message = tr_key(Errors.SERVER_UNAVAILABLE)
                StyledMessageDialog.show_warning(
                    None,
                    tr_key(Errors.AUTHENTICATION_FAILED_TITLE),
                    message,
                )
                continue
        return False


def run_headless():
    setup_logging()
    logger = logging.getLogger('GreenhouseDesktop')
    logger.warning("Headless mode is no longer supported. Shell commands have been removed.")
    print("Headless mode is no longer supported.")
    print("Please use the GUI application or send commands via RabbitMQ to greenhouse core server.")
    sys.exit(1)


def _bootstrap_localization() -> None:
    """Initialize Qt org/app names and load persisted language."""
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationName(APP_NAME)
    manager = LocalizationManager.instance()
    saved_language = AppSettings().get_language() or manager.DEFAULT_LANGUAGE
    manager.load_language(saved_language)


def run_gui(debug=False):
    runtime_dir = f"/tmp/runtime-{os.getuid()}"
    os.environ.setdefault("XDG_RUNTIME_DIR", runtime_dir)
    try:
        os.makedirs(runtime_dir, exist_ok=True, mode=0o700)
    except Exception:
        pass

    setup_logging()
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationName(APP_NAME)

    app = QApplication(sys.argv)

    _bootstrap_localization()

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    auth_session = AuthSessionManager()
    if not ensure_authenticated(app, config.BACKEND_URL, auth_session):
        sys.exit(0)

    window = GreenhouseDesktop(auth_session=auth_session)
    window.show()
    sys.exit(app.exec_())


def main():
    parser = argparse.ArgumentParser(description="Greenhouse Desktop")
    parser.add_argument('--nogui', action='store_true', help='Run without GUI (headless)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    if args.nogui:
        run_headless()
    else:
        run_gui(debug=args.debug)


if __name__ == '__main__':
    main()
