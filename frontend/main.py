from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
import sys
import logging
import argparse
import uuid
import os

# Load configuration first (this loads .env files based on ENVIRONMENT)
from modules.config import config

from modules.greenhouse import GreenhouseDesktop, setup_logging
from modules.command_worker import CommandWorker

def run_headless():
    # Headless mode removed - shell commands are no longer supported
    # All commands must go through greenhouse core simulator
    setup_logging()
    logger = logging.getLogger('GreenhouseDesktop')
    logger.warning("Headless mode is no longer supported. Shell commands have been removed.")
    print("Headless mode is no longer supported.")
    print("Please use the GUI application or send commands via RabbitMQ to greenhouse core simulator.")
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

    window = GreenhouseDesktop()
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
