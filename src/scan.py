import pathlib
import win32api
from logger import get_logger

log = get_logger("scan")


JUNK_PREFIXES = ("setup", "unins", "install", "dxwebsetup", "dotnet", "vcredist",
                 "oalinst", "quicksfv", "easyanticheat", "eac_", "unitycrashhandler",
                 "crashhandler", "uninstall")
JUNK_DIRS = {"_redist", "redist", "commonredist",
             "directx", "md5", "easyanticheat"}
# folders that hold game folders one level down
CONTAINER_DIRS = {"installers n zips"}


def is_junk(exe, game_dir):
    if any(part.lower() in JUNK_DIRS for part in exe.relative_to(game_dir).parts[:-1]):
        log.debug("Skipping junk executable: %s", exe)
        return True
    return exe.stem.lower().startswith(JUNK_PREFIXES)


def game_folders(root):
    for item in root.iterdir():
        if not item.is_dir():
            continue
        if item.name.lower() in CONTAINER_DIRS:
            yield from game_folders(item)
        else:
            yield item


def find_games(root):
    for game_dir in game_folders(root):
        candidates = [e for e in game_dir.rglob(
            '*.exe') if not is_junk(e, game_dir)]
        if candidates:
            chosen = max(candidates, key=lambda e: e.stat().st_size)
            log.info("Selected %s for folder %s", chosen.name, game_dir.name)
            yield game_dir, chosen
        else:
            log.warning("No game executable found in %s", game_dir.name)


def get_product_name(exe_path):
    try:
        info = win32api.GetFileVersionInfo(str(exe_path), '\\')
        for lang in info['StringFileInfo']:
            name = info['StringFileInfo'][lang].get('ProductName')
            if name:
                return name
    except Exception:
        pass
    return exe_path.stem


if __name__ == "__main__":
    for folder, exe in find_games(pathlib.Path('D:/Games')):
        print(f"{get_product_name(exe):<30} {exe}")
