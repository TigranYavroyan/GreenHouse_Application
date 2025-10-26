from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
import sys
import logging
import argparse
import uuid
import os

from modules.greephouse import GreenhouseDesktop, setup_logging
from modules.command_worker import CommandWorker

def run_headless():
    # Headless behavior: connect CommandWorker and accept simple CLI input
    setup_logging()
    logger = logging.getLogger('GreenhouseDesktop')
    logger.info("Starting headless mode (no GUI)")
    worker = CommandWorker()
    worker.setup_rabbitmq()

    try:
        print("Headless mode. Type commands (or Ctrl+C to quit).")
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue
            # Send as developer execute_raw command
            payload = {
                "commandId": str(uuid.uuid4()),
                "command": "execute_raw",
                "type": "developer",
                "parameters": {"raw_command": cmd},
                "sessionId": str(uuid.uuid4()),
                "raw_command": cmd
            }
            worker.send_command(payload)
    except KeyboardInterrupt:
        logger.info("Headless exiting")
        try:
            worker.disconnect()
        except Exception:
            pass
        sys.exit(0)

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
