import json
import os
import pathlib
import win32api
from logger import get_logger

log = get_logger("scan")
CACHE_PATH = pathlib.Path(__file__).parent.parent / "cache" / "scan_cache.json"
CACHE_VERSION = 2


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


def _cache_key(path):
    return os.path.normcase(os.path.abspath(path))


def _load_cache():
    try:
        contents = CACHE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        log.exception("Unable to read scan cache at %s", CACHE_PATH)
        return {}

    try:
        cache = json.loads(contents)
    except (json.JSONDecodeError, UnicodeDecodeError):
        log.exception("Unable to parse scan cache at %s", CACHE_PATH)
        return {}

    if (not isinstance(cache, dict)
            or cache.get("version") != CACHE_VERSION
            or not isinstance(cache.get("folders"), dict)):
        log.warning("Invalid scan cache at %s; rebuilding it", CACHE_PATH)
        return {}

    folders = cache["folders"]
    for entry in folders.values():
        if (not isinstance(entry, dict)
                or "signature" not in entry
                or "exe" not in entry
                or (entry["signature"] is not None
                    and not isinstance(entry["signature"], int))):
            log.warning("Invalid scan cache entries at %s; rebuilding it",
                        CACHE_PATH)
            return {}
        exe = entry["exe"]
        if (exe is not None
                and (not isinstance(exe, dict)
                     or not isinstance(exe.get("path"), str)
                     or not isinstance(exe.get("size"), int)
                     or not isinstance(exe.get("mtime"), int))):
            log.warning("Invalid scan cache entries at %s; rebuilding it",
                        CACHE_PATH)
            return {}
    return folders


def _save_cache(folders):
    temporary_path = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    cache = {"version": CACHE_VERSION, "folders": folders}
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(
            json.dumps(cache, indent=2), encoding="utf-8")
        temporary_path.replace(CACHE_PATH)
    except OSError:
        log.exception("Unable to write scan cache at %s", CACHE_PATH)


def find_games(root, force_refresh=False):
    game_dirs = list(game_folders(root))
    cache = _load_cache()
    new_cache = {}
    games = []
    for game_dir in game_dirs:
        key = _cache_key(game_dir)
        try:
            signature = game_dir.stat().st_mtime_ns
        except OSError:
            log.exception("Unable to read folder metadata for %s", game_dir)
            signature = None

        previous = cache.get(key)
        needs_scan = (
            force_refresh
            or signature is None
            or not isinstance(previous, dict)
            or previous.get("signature") != signature
        )

        if not needs_scan:
            cached_exe = previous.get("exe")
            if cached_exe is None:
                new_cache[key] = previous
                continue
            if isinstance(cached_exe, dict):
                exe = pathlib.Path(cached_exe.get("path", ""))
                try:
                    exe.relative_to(game_dir.resolve())
                    stat = exe.stat()
                except (OSError, ValueError):
                    needs_scan = True
                else:
                    if (stat.st_size == cached_exe.get("size")
                            and stat.st_mtime_ns == cached_exe.get("mtime")):
                        games.append((game_dir, exe))
                        new_cache[key] = previous
                        continue
                    needs_scan = True
            else:
                needs_scan = True

        if needs_scan:
            candidates = [
                exe for exe in game_dir.rglob("*.exe")
                if not is_junk(exe, game_dir)
            ]
            if candidates:
                chosen = max(candidates, key=lambda exe: exe.stat().st_size)
                stat = chosen.stat()
                log.info("Selected %s for folder %s",
                         chosen.name, game_dir.name)
                exe_data = {
                    "path": str(chosen.resolve()),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime_ns,
                }
                games.append((game_dir, chosen))
            else:
                log.warning("No game executable found in %s", game_dir.name)
                exe_data = None
            new_cache[key] = {"signature": signature, "exe": exe_data}
        else:
            new_cache[key] = previous

    if new_cache != cache:
        _save_cache(new_cache)

    yield from games


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
