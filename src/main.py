import queue
import pathlib
import sys
import threading

from logger import get_logger
from scan import find_games, get_product_name
from gui import GameLauncherWindow

log = get_logger("main")
GAMES_ROOT = pathlib.Path("D:/Games")


def handle_uncaught(exc_type, exc_value, exc_tb):
    log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


def load_games(root, force_refresh=False):
    games = []
    for _, exe in find_games(root, force_refresh=force_refresh):
        games.append((get_product_name(exe), exe))
    return games


def main():
    sys.excepthook = handle_uncaught
    log.info("Starting launcher for %s", GAMES_ROOT)
    scan_results = queue.Queue()
    scan_state = {"running": False}
    app = None

    def start_scan(force_refresh=False):
        if scan_state["running"]:
            return
        scan_state["running"] = True
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
        try:
            games, error = scan_results.get_nowait()
        except queue.Empty:
            app.after(100, poll_scan_results)
            return

        scan_state["running"] = False
        app.set_scanning(False)
        if error is not None:
            app.set_status(f"Scan failed: {error}")
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
