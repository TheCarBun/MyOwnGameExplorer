import subprocess
from pathlib import Path

from logger import get_logger

log = get_logger("runner")


def launch_game(exe_path):
    exe = Path(exe_path)
    log.info("Launching %s", exe.name)
    log.debug("Full path: %s, working dir: %s", exe, exe.parent)

    if not exe.exists():
        log.error("Executable not found: %s", exe)
        return

    try:
        subprocess.Popen([str(exe)], cwd=str(exe.parent))
    except OSError:
        log.exception("Failed to start %s", exe)
