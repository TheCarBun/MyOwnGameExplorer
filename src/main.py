import pathlib
import sys

from logger import get_logger
from scan import find_games, get_product_name
from gui import GameLauncherWindow

log = get_logger("main")
GAMES_ROOT = pathlib.Path("D:/Games")


def handle_uncaught(exc_type, exc_value, exc_tb):
    log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


def load_games(root):
    games = []
    for _, exe in find_games(root):
        games.append((get_product_name(exe), exe))
    return games


def main():
    sys.excepthook = handle_uncaught
    log.info("Starting launcher, scanning %s", GAMES_ROOT)

    games = load_games(GAMES_ROOT)
    log.info("Found %d games", len(games))

    app = GameLauncherWindow(games)
    app.mainloop()
    log.info("Launcher closed")


if __name__ == "__main__":
    main()
