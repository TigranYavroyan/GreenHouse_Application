"""Application-wide logging configuration for the desktop client."""
import logging
import sys


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("greenhouse_system.log", encoding="utf-8"),
        ],
    )
