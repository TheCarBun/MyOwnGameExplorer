# -*- mode: python ; coding: utf-8 -*-
import json
import sys
from pathlib import Path


ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT / "src"))
from app_icon import create_app_icon

theme_config = json.loads(
    (ROOT / "config" / "theme.json").read_text(encoding="utf-8"))
themes = theme_config.get("themes", {})
icon_colors = themes.get(theme_config.get("selected_theme"), {})
required_colors = ("surface", "icon_tile", "border", "accent")
if not all(key in icon_colors for key in required_colors):
    raise ValueError("Selected theme is missing colors required for the app icon.")

icon_path = ROOT / "build" / "app_icon.ico"
icon_path.parent.mkdir(parents=True, exist_ok=True)
create_app_icon(256, icon_colors).save(
    icon_path,
    format="ICO",
    sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48),
        (64, 64), (128, 128), (256, 256),
    ],
)

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    # settings.json is user-specific and intentionally not part of the release.
    datas=[
        (str(ROOT / "config" / "text.json"), "config"),
        (str(ROOT / "config" / "theme.json"), "config"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MyOwnGameExplorer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon_path),
    contents_directory=".",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MyOwnGameExplorer",
)
