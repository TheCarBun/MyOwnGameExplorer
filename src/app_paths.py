import sys
from pathlib import Path


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = get_app_dir()
CONFIG_DIR = APP_DIR / "config"
LOG_DIR = APP_DIR / "logs"
CACHE_DIR = APP_DIR / "cache"
