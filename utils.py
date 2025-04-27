import os
import sys
import logging
from io import StringIO
from datetime import datetime
import json


def setup_logging(logger_name, log_level=logging.INFO):
    """Setup logging with proper formatting"""
    if not os.path.exists("logs"):
        os.makedirs("logs")

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Avoid adding multiple handlers and ensure correct path formation
    if not logger.handlers:
        # Make sure we don't have nested 'logs' directory in the path
        log_file = f"logs/{logger_name}.log"
        if logger_name.startswith(
            "logs/"
        ):  # Remove duplicated 'logs/' prefix if present
            log_file = logger_name + ".log"

        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def capture_output(func, *args, **kwargs):
    """Execute a function while capturing stdout and stderr"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()

    result = None
    try:
        # Execute the function with captured output
        result = func(*args, **kwargs)
    finally:
        # Always restore stdout and stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return result


def print_message(message, type="info"):
    prefix = {"success": "✔", "error": "✘", "info": "ℹ", "warning": "⚠"}.get(type, "")
    print(f"{prefix} {message}")


def print_numbered_list(items):
    if not items:
        print("No items to display")
        return
    for i, item in enumerate(items, 1):
        print(f"{i}. {item}")


def check_file_encryption_status(filename):
    """Check if a file is encrypted by looking it up in the encryption_keys.json file"""
    try:
        if os.path.exists("encryption_keys.json"):
            with open("encryption_keys.json", "r") as f:
                keys = json.load(f)
            if filename in keys:
                return True
        return False
    except Exception as e:
        print(f"Error checking encryption status: {e}")
        return False
