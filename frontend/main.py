from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
import sys
import logging
import argparse
import uuid
import os

# Load configuration first (repository root `.env` when present)
from modules.config import config

from modules.greenhouse import GreenhouseDesktop, setup_logging
from modules.command_worker import CommandWorker
from modules.auth_dialog import AuthDialog
from modules.auth_session import AuthSessionManager
from modules.core_api_client import CoreApiClient, UnauthorizedError
from modules.ui_dialogs import StyledMessageDialog


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
                StyledMessageDialog.show_warning(
                    None,
                    "Authentication Failed",
                    f"Unable to verify authenticated session: {error}",
                )
                continue
        return False

def run_headless():
    # Headless mode removed - shell commands are no longer supported
    # All commands must go through greenhouse core server
    setup_logging()
    logger = logging.getLogger('GreenhouseDesktop')
    logger.warning("Headless mode is no longer supported. Shell commands have been removed.")
    print("Headless mode is no longer supported.")
    print("Please use the GUI application or send commands via RabbitMQ to greenhouse core server.")
    sys.exit(1)

def run_gui(debug=False):
    # Ensure runtime dir exists for Qt
    runtime_dir = f"/tmp/runtime-{os.getuid()}"
    os.environ.setdefault("XDG_RUNTIME_DIR", runtime_dir)
    try:
        os.makedirs(runtime_dir, exist_ok=True, mode=0o700)
    except Exception:
        pass

    setup_logging()
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)

    # Set application-wide font (keeps your existing behavior)
    # (existing font code)
    from PyQt5.QtGui import QFont
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

    # if running headless
    if args.nogui:
        run_headless()
    else:
        run_gui(debug=args.debug)

if __name__ == '__main__':
    main()
