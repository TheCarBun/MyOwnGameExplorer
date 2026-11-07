import hashlib
import os
from pathlib import Path

from PIL import Image, ImageTk
from icoextract import IconExtractor, IconExtractorError

from logger import get_logger

log = get_logger("icons")

CACHE_DIR = Path(__file__).parent.parent / "cache" / "icons"

# Used when an exe has no icon resource at all
PLACEHOLDER = Image.new("RGBA", (128, 128), (60, 60, 60, 255))


def _cache_path(exe_path, size):
    exe_path = Path(exe_path)
    identity = os.path.normcase(str(exe_path.resolve()))
    try:
        stat = exe_path.stat()
        identity += f":{stat.st_size}:{stat.st_mtime_ns}"
    except OSError:
        identity += ":missing"
    key = hashlib.md5(identity.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}_{size}.png"


def _extract_pil_icon(exe_path):
    try:
        # get_icon(num=0) returns the first icon group as a file-like .ico object
        ico_stream = IconExtractor(str(exe_path)).get_icon(num=0)
        return Image.open(ico_stream).convert("RGBA")
    except (IconExtractorError, OSError, ValueError):
        return None


def get_icon_image(exe_path, size=128):
    cached = _cache_path(exe_path, size)

    try:
        with Image.open(cached) as cached_image:
            img = cached_image.copy()
        log.debug("Cache hit for %s", Path(exe_path).name)
    except (OSError, ValueError):
        log.debug("Extracting icon from %s", Path(exe_path).name)
        img = _extract_pil_icon(exe_path)
        if img is None:
            log.warning("No usable icon in %s, using placeholder",
                        Path(exe_path).name)
            img = PLACEHOLDER.copy()
        img = img.resize((size, size), Image.LANCZOS)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img.save(cached)

    return ImageTk.PhotoImage(img)
