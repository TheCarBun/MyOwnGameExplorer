import os
import queue
import pathlib
import sys
import threading
from pathlib import Path

from logger import get_logger
from models import GameEntry
from scan import find_games, get_product_name
from icons import clear_icon_cache
from gui import GameLauncherWindow

log = get_logger("main")
GAMES_ROOT = pathlib.Path("D:/Games")


def handle_uncaught(exc_type, exc_value, exc_tb):
    log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


def load_games(
        root: Path, force_refresh: bool = False) -> list[GameEntry]:
    games = []
    for folder, exe in find_games(root, force_refresh=force_refresh):
        games.append(GameEntry(
            get_product_name(exe), exe, folder, _folder_size(folder)))
    return games


def _folder_size(folder: Path) -> int:
    total = 0

    def on_walk_error(error):
        log.warning("Unable to read folder while calculating size: %s", error)

    for current, _, filenames in os.walk(folder, onerror=on_walk_error):
        for filename in filenames:
            path = pathlib.Path(current) / filename
            try:
                total += path.stat().st_size
            except OSError as exc:
                log.warning("Unable to read file size for %s: %s", path, exc)
    return total


def main():
    sys.excepthook = handle_uncaught
    log.info("Starting launcher for %s", GAMES_ROOT)
    scan_results = queue.Queue()
    scan_running = False

    def start_scan(force_refresh=False):
        nonlocal scan_running
        if scan_running:
            return
        if force_refresh:
            try:
                clear_icon_cache()
            except OSError as exc:
                log.exception("Unable to clear icon cache")
                app.set_status(f"Unable to clear icon cache: {exc}")
                return
        scan_running = True
        app.set_scanning(True)

        def scan_worker():
            try:
                scan_results.put((load_games(GAMES_ROOT, force_refresh), None))
            except Exception as exc:
                log.exception("Game scan failed")
                scan_results.put((None, exc))

        threading.Thread(
            target=scan_worker, daemon=True, name="GameScanner").start()

    def poll_scan_results():
        nonlocal scan_running
        try:
            games, error = scan_results.get_nowait()
        except queue.Empty:
            app.after(100, poll_scan_results)
            return

        scan_running = False
        app.set_scanning(False)
        if error is not None:
            app.set_scan_error(str(error))
        else:
            app.set_games(games)
            app.set_status(f"Found {len(games)} games")
            log.info("Found %d games", len(games))
        app.after(100, poll_scan_results)

    app = GameLauncherWindow([], on_refresh=lambda: start_scan(True))
    app.after(0, start_scan)
    app.after(100, poll_scan_results)
    app.mainloop()
    log.info("Launcher closed")


if __name__ == "__main__":
    main()
