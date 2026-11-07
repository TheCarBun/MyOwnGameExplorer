import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "launcher.log"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _setup_root_logger():
    root = logging.getLogger("launcher")
    root.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if the module is imported twice
    if root.handlers:
        return root

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FORMAT))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(_FORMAT))

    root.addHandler(file_handler)
    root.addHandler(console_handler)
    return root


_setup_root_logger()


def get_logger(name):
    """Return a child logger, e.g. get_logger(__name__) inside any module."""
    return logging.getLogger(f"launcher.{name}")
