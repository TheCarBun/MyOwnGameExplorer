from collections.abc import Callable, Sequence
import ctypes
from datetime import datetime
import json
import math
import pathlib
import re
import subprocess
import sys
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, ttk

from PIL import ImageTk

from app_paths import CONFIG_DIR
from app_icon import create_app_icon
from icons import get_icon_image
from logger import get_logger
from models import GameEntry
from runner import launch_game

log = get_logger("gui")

BG = "#10151d"
SURFACE = "#171f2b"
CARD_BG = "#1b2532"
CARD_HOVER = "#243242"
TEXT = "#eef3f8"
MUTED = "#93a4b7"
ACCENT = "#61dfb3"
MIN_CARD_WIDTH = 176
MAX_CARD_WIDTH = 284
TARGET_CARD_WIDTH = 232
CARD_GAP = 14
CARD_INSET = 12
GA_ROOT = 2
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
SORT_OPTIONS = (
    "Name (A-Z)",
    "Name (Z-A)",
    "Size (largest)",
    "Size (smallest)",
)
SETTINGS_CONFIG_PATH = CONFIG_DIR / "settings.json"
TEXT_CONFIG_PATH = CONFIG_DIR / "text.json"
THEME_CONFIG_PATH = CONFIG_DIR / "theme.json"
DEFAULT_UI_TEXT = {
    "window_title": "Arcade - Game Launcher",
    "heading": "Your library",
    "subtitle": "All your games, ready when you are.",
    "refresh_button": "Refresh library",
    "choose_folder_button": "Choose games folder",
    "scanning_button": "Scanning...",
    "scan_status": "Scanning your game folders...",
    "sort_label": "SORT BY",
    "details_heading": "GAME DETAILS",
    "loading_text": "Finding your games",
    "empty_library": "No games found. Check your game folder and refresh.",
    "empty_search": "No games match your search.",
    "scan_error": "Could not load games. Check the game folder and try again.",
}
DEFAULT_COLORS = {
    "background": BG,
    "surface": SURFACE,
    "card": CARD_BG,
    "card_hover": CARD_HOVER,
    "text": TEXT,
    "muted": MUTED,
    "accent": ACCENT,
    "icon_tile": "#273342",
    "badge": "#203b38",
    "button": "#2a3746",
    "button_hover": "#35485b",
    "button_disabled": "#202a36",
    "accent_text": "#10221d",
    "accent_hover": "#83ebc7",
    "border": "#34475b",
}


def _read_config(path: pathlib.Path) -> dict:
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        log.exception("Unable to read UI settings from %s", path)
        return {}
    if not isinstance(settings, dict):
        log.warning("Invalid UI settings in %s; using defaults", path)
        return {}
    return settings


def _write_config(path: pathlib.Path, settings: dict) -> bool:
    temporary_path = path.with_suffix(".json.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(
            json.dumps(settings, indent=2), encoding="utf-8")
        temporary_path.replace(path)
    except OSError:
        log.exception("Unable to save UI settings to %s", path)
        return False
    return True


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


class GameLauncherWindow(tk.Tk):
    def __init__(
            self, games: Sequence[GameEntry],
            on_refresh: Callable[[], None],
            on_games_root_change: Callable[[], None]) -> None:
        super().__init__()
        self._settings = self._load_settings()
        self.games_root = pathlib.Path(self._settings["games_root"])
        self.ui_text = self._settings["ui"]["text"]
        self.colors = self._settings["ui"]["themes"][
            self._settings["ui"]["theme"]]
        self.title(self.ui_text["window_title"])
        self.configure(bg=self.colors["background"])
        self.games = []
        self.on_refresh = on_refresh
        self.on_games_root_change = on_games_root_change
        self.card_widgets = {}
        self._search_index = {}
        self._visible_card_keys = set()
        self.columns = 1
        self.target_card_width = TARGET_CARD_WIDTH
        self.card_width = TARGET_CARD_WIDTH
        self.card_height = 264
        self.icon_size = 96
        self._geometry_after = None
        self._expected_window_size = None
        self._layout_after = None
        self._search_after = None
        self._scrollbar_after = None
        self._clear_icon_hovered = False
        self._grid_size = None
        self._details_panel_width = None
        self._scan_complete = False
        self._scan_error = None
        self._initial_fit_pending = True
        self._initial_fit_pending = "window_size" not in self._settings

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.minsize(min(760, screen_width), min(520, screen_height))
        if self._initial_fit_pending:
            self._set_centered_geometry(
                min(1000, screen_width), min(700, screen_height))
        else:
            width, height = self._settings["window_size"]
            self._set_centered_geometry(
                min(width, screen_width), min(height, screen_height))

        self._setup_styles()
        self._build_layout()
        self._update_app_icon()
        self.bind("<Map>", self._on_window_map, add="+")
        if games:
            self.set_games(games)
        else:
            self._render_cards()
            self.loading_bar.start(12)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Configure>", self._queue_save_settings, add="+")
        self.bind("<Configure>", self._on_window_configure, add="+")
        self.bind("<Control-f>", lambda *_: self._focus_search())
        self.bind("<Control-F>", lambda *_: self._focus_search())

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            log.warning("Unable to activate clam theme; using the default theme")
        style.configure(
            "Launcher.TButton",
            background=self.colors["button"],
            foreground=self.colors["text"],
            borderwidth=0,
            padding=(12, 8),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Launcher.TButton",
            background=[
                ("active", self.colors["button_hover"]),
                ("disabled", self.colors["button_disabled"]),
            ],
            foreground=[("disabled", self.colors["muted"])],
        )
        style.configure(
            "Accent.TButton",
            background=self.colors["accent"],
            foreground=self.colors["accent_text"],
            borderwidth=0,
            padding=(12, 8),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", self.colors["accent_hover"])])
        style.configure(
            "Launcher.TCombobox",
            fieldbackground=self.colors["surface"],
            background=self.colors["surface"],
            foreground=self.colors["text"],
            arrowcolor=self.colors["accent"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            borderwidth=0,
            relief="flat",
            padding=8,
        )
        style.map(
            "Launcher.TCombobox",
            background=[
                ("active", self.colors["button_hover"]),
                ("readonly", self.colors["surface"]),
                ("!disabled", self.colors["surface"]),
            ],
            fieldbackground=[
                ("readonly", self.colors["surface"]),
                ("focus", self.colors["surface"]),
            ],
            foreground=[
                ("readonly", self.colors["text"]),
                ("focus", self.colors["text"]),
            ],
            selectbackground=[("readonly", self.colors["surface"])],
            selectforeground=[("readonly", self.colors["text"])],
            bordercolor=[
                ("focus", self.colors["border"]),
                ("!focus", self.colors["border"]),
            ],
            lightcolor=[
                ("focus", self.colors["border"]),
                ("!focus", self.colors["border"]),
            ],
            darkcolor=[
                ("focus", self.colors["border"]),
                ("!focus", self.colors["border"]),
            ],
        )
        style.configure(
            "Launcher.Popup.Vertical.TScrollbar",
            background=self.colors["button"],
            troughcolor=self.colors["surface"],
            bordercolor=self.colors["surface"],
            arrowcolor=self.colors["surface"],
            arrowsize=0,
            borderwidth=0,
            relief="flat",
            width=8,
        )
        style.map(
            "Launcher.Popup.Vertical.TScrollbar",
            background=[("active", self.colors["accent"])],
        )
        self.option_add("*TCombobox*Listbox.background", self.colors["surface"])
        self.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.option_add(
            "*TCombobox*Listbox.selectBackground",
            self.colors["button_hover"])
        self.option_add(
            "*TCombobox*Listbox.selectForeground", self.colors["text"])
        style.configure(
            "Launcher.TEntry",
            fieldbackground=self.colors["surface"],
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=(10, 0),
        )
        style.map(
            "Launcher.TEntry",
            fieldbackground=[
                ("focus", self.colors["surface"]),
                ("!focus", self.colors["surface"]),
            ],
            bordercolor=[
                ("focus", self.colors["border"]),
                ("!focus", self.colors["border"]),
            ],
            lightcolor=[
                ("focus", self.colors["border"]),
                ("!focus", self.colors["border"]),
            ],
            darkcolor=[
                ("focus", self.colors["border"]),
                ("!focus", self.colors["border"]),
            ],
        )
        style.configure(
            "Launcher.Vertical.TScrollbar",
            background=self.colors["surface"],
            troughcolor=self.colors["background"],
            bordercolor=self.colors["background"],
            arrowsize=0,
            borderwidth=0,
            relief="flat",
            width=8,
        )
        style.map(
            "Launcher.Vertical.TScrollbar",
            background=[("active", self.colors["accent"])],
        )
        style.configure(
            "Launcher.Horizontal.TProgressbar",
            troughcolor=self.colors["surface"],
            background=self.colors["accent"],
            borderwidth=0,
            lightcolor=self.colors["accent"],
            darkcolor=self.colors["accent"],
        )

    def _build_layout(self):
        content = tk.Frame(self, bg=self.colors["background"])
        content.pack(fill="both", expand=True, padx=26, pady=(22, 16))

        self.header = tk.Frame(
            content,
            bg=self.colors["surface"],
            padx=18,
            pady=14,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.header.pack(fill="x", pady=(0, 18))
        self.title_block = tk.Frame(self.header, bg=self.colors["surface"])
        self.title_block.pack(side="left", fill="x", expand=True)
        self.heading_label = tk.Label(
            self.title_block,
            text=self.ui_text["heading"],
            fg=self.colors["text"],
            bg=self.colors["surface"],
            font=("Segoe UI Semibold", 25),
        )
        self.heading_label.pack(anchor="w")
        self.subtitle_label = tk.Label(
            self.title_block,
            text=self.ui_text["subtitle"],
            fg=self.colors["muted"],
            bg=self.colors["surface"],
            font=("Segoe UI", 10),
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))
        self.refresh_button = ttk.Button(
            self.header,
            text=self.ui_text["refresh_button"],
            style="Launcher.TButton",
            command=self.on_refresh,
        )
        self.refresh_button.pack(side="right", anchor="center")
        self.choose_folder_button = ttk.Button(
            self.header,
            text=self.ui_text["choose_folder_button"],
            style="Launcher.TButton",
            command=self._choose_games_folder,
        )
        self.choose_folder_button.pack(
            side="right", anchor="center", padx=(0, 8))

        toolbar = tk.Frame(content, bg=self.colors["background"])
        toolbar.pack(fill="x", pady=(0, 16))
        self.search_wrap = tk.Frame(
            toolbar,
            bg=self.colors["border"],
            padx=1,
            pady=1,
            highlightthickness=0,
        )
        self.search_wrap.pack(
            side="left", fill="x", expand=True, padx=(0, 14))
        self.search_inner = tk.Frame(
            self.search_wrap, bg=self.colors["surface"])
        self.search_inner.pack(fill="both", expand=True)
        self.search_icon = tk.Canvas(
            self.search_inner,
            width=38,
            height=38,
            bg=self.colors["surface"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.search_icon.pack(side="left", fill="y")
        self._draw_search_icon()
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            self.search_inner,
            textvariable=self.search_var,
            style="Launcher.TEntry",
        )
        self.search_entry.pack(side="left", fill="both", expand=True)
        self.clear_search_button = tk.Canvas(
            self.search_inner,
            width=38,
            height=38,
            bg=self.colors["surface"],
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            takefocus=True,
        )
        self.clear_search_button.pack(side="right", fill="y")
        self.clear_search_button.bind(
            "<Button-1>", lambda *_: self._clear_search())
        self.clear_search_button.bind(
            "<Return>", lambda *_: self._clear_search())
        self.clear_search_button.bind(
            "<space>", lambda *_: self._clear_search())
        self.clear_search_button.bind(
            "<Enter>",
            lambda *_: self._set_clear_icon_hover(True))
        self.clear_search_button.bind(
            "<Leave>",
            lambda *_: self._set_clear_icon_hover(False))
        self._draw_clear_icon()
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_entry.bind("<Escape>", lambda *_: self._clear_search())
        self.controls = tk.Frame(
            toolbar,
            bg=self.colors["surface"],
            padx=12,
            pady=5,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.controls.pack(side="right")
        self.sort_var = tk.StringVar(
            value=self._settings.get("sort_order", SORT_OPTIONS[0]))
        self.sort_label = tk.Label(
            self.controls, text=self.ui_text["sort_label"],
            fg=self.colors["muted"], bg=self.colors["surface"],
            font=("Segoe UI", 8, "bold"),
        )
        self.sort_label.pack(side="left", padx=(0, 8))
        self.sort_box = ttk.Combobox(
            self.controls,
            textvariable=self.sort_var,
            values=SORT_OPTIONS,
            state="readonly",
            width=17,
            style="Launcher.TCombobox",
        )
        self.sort_box.pack(side="left")
        self.sort_box.bind(
            "<<ComboboxSelected>>", lambda *_: self._on_sort_changed())
        self.theme_label = tk.Label(
            self.controls, text="THEME",
            fg=self.colors["muted"], bg=self.colors["surface"],
            font=("Segoe UI", 8, "bold"),
        )
        self.theme_label.pack(side="left", padx=(16, 8))
        self.theme_var = tk.StringVar(value=self._settings["ui"]["theme"])
        self.theme_box = ttk.Combobox(
            self.controls,
            textvariable=self.theme_var,
            values=tuple(self._settings["ui"]["themes"]),
            state="readonly",
            width=12,
            style="Launcher.TCombobox",
        )
        self.theme_box.pack(side="left")
        self.theme_box.bind(
            "<<ComboboxSelected>>", lambda *_: self._on_theme_changed())

        library = tk.Frame(content, bg=self.colors["background"])
        library.pack(fill="both", expand=True)
        library.grid_rowconfigure(0, weight=1)
        library.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(library, bg=self.colors["background"],
                                highlightthickness=0,
                                borderwidth=0)
        self.scrollbar = ttk.Scrollbar(
            library,
            orient="vertical",
            command=self.canvas.yview,
            style="Launcher.Vertical.TScrollbar",
        )
        self.grid_frame = tk.Frame(self.canvas, bg=self.colors["background"])
        self.grid_frame.bind(
            "<Configure>",
            lambda *_: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")),
        )
        self.grid_window = self.canvas.create_window(
            (0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.scrollbar.grid_remove()
        self.details_panel = tk.Frame(
            library,
            bg=self.colors["surface"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=22,
            pady=20,
        )
        self.details_panel.grid_propagate(False)
        library.grid_columnconfigure(2, weight=0, minsize=0)
        library.grid_columnconfigure(1, weight=0, minsize=0)
        self._build_details_panel()
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        footer = tk.Frame(content, bg=self.colors["background"])
        footer.pack(fill="x", pady=(12, 0))
        self.count_label = tk.Label(
            footer,
            text="Found 0 games",
            fg=self.colors["accent"],
            bg=self.colors["badge"],
            padx=10,
            pady=4,
            font=("Segoe UI", 9, "bold"),
        )
        self.count_label.pack(side="left")
        self.status_label = tk.Label(
            footer,
            text="",
            fg=self.colors["muted"],
            bg=self.colors["background"],
            font=("Segoe UI", 9),
        )
        self.status_label.pack(side="left", padx=(10, 0))
        self.empty_state = tk.Label(
            self.grid_frame,
            text="",
            fg=self.colors["muted"],
            bg=self.colors["background"],
            font=("Segoe UI", 12),
        )
        self.empty_state.place_forget()
        self.loading_frame = tk.Frame(
            self.grid_frame, bg=self.colors["background"])
        tk.Label(
            self.loading_frame,
            text=self.ui_text["loading_text"],
            fg=self.colors["text"],
            bg=self.colors["background"],
            font=("Segoe UI Semibold", 13),
        ).pack(pady=(0, 12))
        self.loading_bar = ttk.Progressbar(
            self.loading_frame,
            mode="indeterminate",
            length=190,
            style="Launcher.Horizontal.TProgressbar",
        )
        self.loading_bar.pack()
        self.loading_frame.place_forget()
        self._apply_combobox_popup_colors()

    def _load_settings(self):
        settings = _read_config(SETTINGS_CONFIG_PATH)
        games_root = settings.get("games_root")
        if isinstance(games_root, str) and games_root.strip():
            settings["games_root"] = str(
                pathlib.Path(games_root).expanduser())
        else:
            if games_root is not None:
                log.warning("Ignoring invalid games_root setting")
            settings["games_root"] = str(pathlib.Path.home() / "Games")
        size = settings.get("window_size")
        if (isinstance(size, list) and len(size) == 2
                and all(type(value) is int and value > 0 for value in size)):
            settings["window_size"] = size
        else:
            settings.pop("window_size", None)
        if settings.get("sort_order") not in SORT_OPTIONS:
            settings.pop("sort_order", None)
        text = _read_config(TEXT_CONFIG_PATH)
        normalized_text = dict(DEFAULT_UI_TEXT)
        for key in normalized_text:
            value = text.get(key)
            if isinstance(value, str) and value.strip():
                normalized_text[key] = value.strip()
            elif value is not None:
                log.warning("Ignoring invalid text.%s setting", key)

        theme_config = _read_config(THEME_CONFIG_PATH)
        configured_themes = theme_config.get("themes")
        normalized_themes = {}
        if isinstance(configured_themes, dict):
            for name, colors in configured_themes.items():
                if not isinstance(name, str) or not name.strip():
                    log.warning("Ignoring theme with an invalid name")
                    continue
                if not isinstance(colors, dict):
                    log.warning("Ignoring invalid theme.%s setting", name)
                    continue
                normalized_colors = dict(DEFAULT_COLORS)
                for key in normalized_colors:
                    value = colors.get(key)
                    if (isinstance(value, str)
                            and re.fullmatch(r"#[0-9a-fA-F]{6}", value)):
                        normalized_colors[key] = value
                    elif value is not None:
                        log.warning(
                            "Ignoring invalid theme.%s.%s setting",
                            name, key)
                normalized_themes[name.strip()] = normalized_colors
        if not normalized_themes:
            normalized_themes = {"Midnight": dict(DEFAULT_COLORS)}
        selected_theme = theme_config.get("selected_theme")
        if (not isinstance(selected_theme, str)
                or selected_theme not in normalized_themes):
            selected_theme = next(iter(normalized_themes))
        settings["ui"] = {
            "text": normalized_text,
            "theme": selected_theme,
            "themes": normalized_themes,
        }
        return settings

    def _save_settings(self, force: bool = False):
        self._geometry_after = None
        size = [self.winfo_width(), self.winfo_height()]
        if min(size) <= 1:
            return
        if self._expected_window_size == tuple(size) and not force:
            return
        settings = {
            "games_root": str(self.games_root),
            "window_size": size,
            "sort_order": self.sort_var.get(),
        }
        if _write_config(SETTINGS_CONFIG_PATH, settings):
            self._expected_window_size = tuple(size)

    def _choose_games_folder(self):
        initial_dir = (
            self.games_root if self.games_root.is_dir()
            else pathlib.Path.home())
        selected = filedialog.askdirectory(
            parent=self,
            title=self.ui_text["choose_folder_button"],
            initialdir=str(initial_dir),
            mustexist=True,
        )
        if not selected:
            return
        games_root = pathlib.Path(selected)
        if games_root == self.games_root:
            return
        self.games_root = games_root
        self._settings["games_root"] = str(games_root)
        settings = _read_config(SETTINGS_CONFIG_PATH)
        settings["games_root"] = str(games_root)
        _write_config(SETTINGS_CONFIG_PATH, settings)
        self.on_games_root_change()

    def _on_theme_changed(self):
        theme = self.theme_var.get()
        colors = self._settings["ui"]["themes"][theme]
        previous_colors = self.colors
        color_map = {
            previous_colors[key]: colors[key]
            for key in colors
        }
        self.colors = colors
        self._settings["ui"]["theme"] = theme
        _write_config(THEME_CONFIG_PATH, {
            "selected_theme": theme,
            "themes": self._settings["ui"]["themes"],
        })
        self.configure(bg=colors["background"])
        self._setup_styles()
        self._recolor_widgets(self, color_map)
        self._apply_top_bar_colors()
        self._update_app_icon()
        self._apply_combobox_popup_colors()
        self._draw_search_icon()
        self._draw_clear_icon()
        self._apply_title_bar_theme()
        self._save_settings(force=True)

    def _apply_top_bar_colors(self):
        surface = self.colors["surface"]
        self.header.configure(
            bg=surface, highlightbackground=self.colors["border"])
        self.title_block.configure(bg=surface)
        self.heading_label.configure(bg=surface, fg=self.colors["text"])
        self.subtitle_label.configure(bg=surface, fg=self.colors["muted"])
        self.search_wrap.configure(bg=self.colors["border"])
        self.search_inner.configure(bg=surface)
        self.search_icon.configure(bg=surface)
        self.clear_search_button.configure(bg=surface)
        self.controls.configure(
            bg=surface, highlightbackground=self.colors["border"])
        self.sort_label.configure(bg=surface, fg=self.colors["muted"])
        self.theme_label.configure(bg=surface, fg=self.colors["muted"])
        self._clear_icon_hovered = False

    def _apply_combobox_popup_colors(self):
        for combobox in (self.sort_box, self.theme_box):
            popdown = self.tk.call(
                "ttk::combobox::PopdownWindow", str(combobox))
            pending = [popdown]
            while pending:
                parent = pending.pop()
                for child in self.tk.splitlist(
                        self.tk.call("winfo", "children", parent)):
                    if self.tk.call("winfo", "class", child) == "Listbox":
                        self.tk.call(
                            child,
                            "configure",
                            "-background", self.colors["surface"],
                            "-foreground", self.colors["text"],
                            "-selectbackground", self.colors["button_hover"],
                            "-selectforeground", self.colors["text"],
                            "-highlightbackground", self.colors["border"],
                            "-highlightcolor", self.colors["border"],
                        )
                    elif self.tk.call("winfo", "class", child) == "TScrollbar":
                        self.tk.call(
                            child,
                            "configure",
                            "-style", "Launcher.Popup.Vertical.TScrollbar",
                        )
                    else:
                        pending.append(child)

    def _create_app_icon(self, size=48):
        return ImageTk.PhotoImage(create_app_icon(size, self.colors))

    def _update_app_icon(self):
        self._app_icon = self._create_app_icon()
        self.iconphoto(True, self._app_icon)

    def _draw_search_icon(self):
        self.search_icon.delete("all")
        self.search_icon.create_oval(
            10, 10, 23, 23,
            outline=self.colors["accent"],
            width=2,
        )
        self.search_icon.create_line(
            21, 21, 28, 28,
            fill=self.colors["accent"],
            width=2,
            capstyle=tk.ROUND,
        )

    def _draw_clear_icon(self):
        self.clear_search_button.delete("all")
        color = self.colors["text"] if self._clear_icon_hovered else (
            self.colors["muted"])
        self.clear_search_button.create_line(
            14, 14, 24, 24, fill=color, width=2, capstyle=tk.ROUND)
        self.clear_search_button.create_line(
            24, 14, 14, 24, fill=color, width=2, capstyle=tk.ROUND)

    def _set_clear_icon_hover(self, hovered):
        self._clear_icon_hovered = hovered
        self.clear_search_button.configure(
            bg=self.colors["button_hover"] if hovered
            else self.colors["surface"])
        self._draw_clear_icon()

    def _apply_title_bar_theme(self):
        if sys.platform != "win32":
            return
        try:
            dwmapi = ctypes.WinDLL("dwmapi")
            user32 = ctypes.WinDLL("user32")
        except OSError:
            log.debug("Windows DWM is unavailable; using the system title bar")
            return

        user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        user32.GetAncestor.restype = wintypes.HWND
        dwmapi.DwmSetWindowAttribute.argtypes = (
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        dwmapi.DwmSetWindowAttribute.restype = wintypes.LONG
        hwnd = user32.GetAncestor(
            wintypes.HWND(self.winfo_id()), GA_ROOT)
        if not hwnd:
            log.debug("Unable to find the native launcher window handle")
            return

        def set_attribute(attribute, value):
            native_value = wintypes.DWORD(value)
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(native_value),
                ctypes.sizeof(native_value),
            )
            if result != 0:
                log.debug("Unable to set Windows title bar attribute %d", attribute)
            return result == 0

        red, green, blue = (
            int(self.colors["background"][index:index + 2], 16)
            for index in (1, 3, 5)
        )
        dark_title_bar = (
            red * 299 + green * 587 + blue * 114) // 1000 < 128
        if not set_attribute(
                DWMWA_USE_IMMERSIVE_DARK_MODE, int(dark_title_bar)):
            set_attribute(
                DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, int(dark_title_bar))

        def colorref(color):
            red, green, blue = (
                int(color[index:index + 2], 16)
                for index in (1, 3, 5)
            )
            return red | green << 8 | blue << 16

        set_attribute(
            DWMWA_CAPTION_COLOR, colorref(self.colors["background"]))
        set_attribute(DWMWA_TEXT_COLOR, colorref(self.colors["text"]))
        set_attribute(DWMWA_BORDER_COLOR, colorref(self.colors["border"]))

    def _on_window_map(self, event):
        if event.widget is self:
            self._apply_title_bar_theme()

    def _recolor_widgets(self, parent, color_map):
        color_options = (
            "background", "foreground", "highlightbackground",
            "insertbackground", "selectbackground", "selectforeground",
            "activebackground", "activeforeground",
        )
        for widget in parent.winfo_children():
            if not isinstance(widget, ttk.Widget):
                options = {
                    option: color_map[widget.cget(option)]
                    for option in color_options
                    if option in widget.keys()
                    and widget.cget(option) in color_map
                }
                if options:
                    widget.configure(**options)
            self._recolor_widgets(widget, color_map)

    def _on_window_configure(self, event):
        if event.widget is self:
            self._set_details_panel_width(event.width)

    def _queue_save_settings(self, event):
        if event.widget is not self:
            return
        if (event.width, event.height) == self._expected_window_size:
            return
        if self._geometry_after is not None:
            self.after_cancel(self._geometry_after)
        self._geometry_after = self.after(500, self._save_settings)

    def _set_centered_geometry(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(width, screen_width)
        height = min(height, screen_height)
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self._expected_window_size = (width, height)

    def _fit_to_library(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        target_columns = max(
            2, min(7, (screen_width - 100) //
                   (TARGET_CARD_WIDTH + CARD_GAP)))
        width = min(
            screen_width - 48,
            max(760, target_columns * (TARGET_CARD_WIDTH + CARD_GAP) + 82),
        )
        rows = max(1, math.ceil(len(self.games) / target_columns))
        height = min(
            screen_height - 70,
            max(520, 208 + rows * (270 + CARD_GAP)),
        )
        self._set_centered_geometry(width, height)
        self._initial_fit_pending = False

    def set_scanning(self, scanning):
        self.refresh_button.configure(
            state="disabled" if scanning else "normal",
            text=self.ui_text["scanning_button"] if scanning
            else self.ui_text["refresh_button"],
        )
        if scanning:
            self.set_status(self.ui_text["scan_status"])
        else:
            self.set_status("")

    def set_status(self, message):
        self.status_label.configure(text=message)

    def set_games(self, games: Sequence[GameEntry]) -> None:
        self._scan_complete = True
        self._scan_error = None
        self.loading_bar.stop()
        self.games = list(games)
        current_keys = {self._game_key(game) for game in self.games}
        if (self._selected_game is not None
                and self._game_key(self._selected_game) not in current_keys):
            self._selected_game = None
            self._hide_details()
        removed_keys = self.card_widgets.keys() - current_keys
        self._visible_card_keys.difference_update(removed_keys)
        for key in removed_keys:
            self.card_widgets.pop(key)["card"].destroy()
        self._search_index = {
            self._game_key(game): " ".join(
                (game.name, game.folder.name, game.executable.name)
            ).casefold()
            for game in self.games
        }
        for game in self.games:
            key = self._game_key(game)
            if key not in self.card_widgets:
                self.card_widgets[key] = self._create_card(key)
            self._update_card(key, game, refresh_icon=True)
        if self._initial_fit_pending:
            self._fit_to_library()
        self._render_cards()

    def set_scan_error(self, message: str) -> None:
        self.set_status(f"Scan failed: {message}")
        if not self._scan_complete:
            self._scan_complete = True
            self._scan_error = message
            self.loading_bar.stop()
            self._render_cards()

    @staticmethod
    def _game_key(game: GameEntry) -> str:
        return str(game.executable).casefold()

    def _on_search_changed(self, *_):
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = self.after(120, self._render_cards)

    def _on_sort_changed(self):
        self._render_cards()

    def _focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)
        return "break"

    def _clear_search(self):
        self.search_var.set("")
        return "break"

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.grid_window, width=event.width)
        if self._layout_after is not None:
            self.after_cancel(self._layout_after)
        self._layout_after = self.after(80, self._render_after_layout)

    def _render_after_layout(self):
        self._layout_after = None
        self._render_cards()

    def _set_details_panel_width(self, window_width):
        panel_width = min(360, max(280, window_width // 5))
        if panel_width == self._details_panel_width:
            return
        self._details_panel_width = panel_width
        self.details_panel.configure(width=panel_width)
        library = self.details_panel.master
        library.grid_columnconfigure(
            2,
            weight=0,
            minsize=panel_width + 12
            if self.details_panel.winfo_manager() == "grid" else 0,
        )
        wraplength = max(180, panel_width - 48)
        if int(self.detail_name.cget("wraplength")) != wraplength:
            self.detail_name.configure(wraplength=wraplength)
        for value in self.detail_values:
            if int(value.cget("wraplength")) != wraplength:
                value.configure(wraplength=wraplength)

    def _on_mousewheel(self, event):
        x = self.canvas.winfo_rootx()
        y = self.canvas.winfo_rooty()
        if (x <= event.x_root < x + self.canvas.winfo_width()
                and y <= event.y_root < y + self.canvas.winfo_height()):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _render_cards(self):
        self._search_after = None
        if not hasattr(self, "grid_frame"):
            return
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        if not self._scan_complete:
            self.empty_state.place_forget()
            height = max(170, self.canvas.winfo_height())
            self._set_grid_size(width, height)
            self.loading_frame.place(relx=0.5, rely=0.5, anchor="center")
            self._queue_scrollbar_update(height)
            return

        self.loading_frame.place_forget()
        query = self.search_var.get().strip().casefold()
        games = [
            game for game in self.games
            if not query or query in self._search_index.get(
                self._game_key(game), "")
        ]
        sort_order = self.sort_var.get()
        if sort_order == "Name (Z-A)":
            games.sort(key=lambda game: game.name.casefold(), reverse=True)
        elif sort_order == "Size (largest)":
            games.sort(key=lambda game: game.size_bytes, reverse=True)
        elif sort_order == "Size (smallest)":
            games.sort(key=lambda game: game.size_bytes)
        else:
            games.sort(key=lambda game: game.name.casefold())

        self.count_label.configure(
            text=(f"Found {len(games)} "
                  f"{'game' if len(games) == 1 else 'games'}"
                  if len(games) == len(self.games)
                  else f"Showing {len(games)} of {len(self.games)} games"))
        if not games:
            if self._scan_error:
                message = self.ui_text["scan_error"]
            elif query:
                message = self.ui_text["empty_search"]
            else:
                message = self.ui_text["empty_library"]
            self.empty_state.configure(text=message)
            self.empty_state.place(relx=0.5, y=48, anchor="n")
            for key in self._visible_card_keys:
                self.card_widgets[key]["card"].place_forget()
            self._visible_card_keys.clear()
            height = max(170, self.canvas.winfo_height())
            self._set_grid_size(width, height)
            self._queue_scrollbar_update(height)
            return

        self.empty_state.place_forget()
        usable_width = max(1, width - CARD_INSET * 2)
        self.target_card_width = min(280, max(220, int(width / 4.2)))
        self.columns = max(
            1, min(9, round((usable_width + CARD_GAP)
                            / (self.target_card_width + CARD_GAP))))
        self.card_width = min(
            MAX_CARD_WIDTH,
            max(MIN_CARD_WIDTH, (usable_width - CARD_GAP
                                * (self.columns - 1)) // self.columns),
        )
        self.card_height = self.icon_size + 168
        rows = math.ceil(len(games) / self.columns)
        height = CARD_INSET + rows * (self.card_height + CARD_GAP)
        self._set_grid_size(width, height)
        visible_keys = set()
        for row in range(rows):
            row_games = games[row * self.columns:(row + 1) * self.columns]
            row_width = (len(row_games) * self.card_width
                         + (len(row_games) - 1) * CARD_GAP)
            start_x = max(0, (width - row_width) // 2)
            y = CARD_INSET + row * (self.card_height + CARD_GAP)
            for column, game in enumerate(row_games):
                key = self._game_key(game)
                visible_keys.add(key)
                card = self.card_widgets[key]["card"]
                card_x = start_x + column * (self.card_width + CARD_GAP)
                if (card.winfo_manager() != "place"
                        or (card.winfo_x(), card.winfo_y(),
                            card.winfo_width(), card.winfo_height())
                        != (card_x, y, self.card_width, self.card_height)):
                    card.place(
                        x=card_x,
                        y=y,
                        width=self.card_width,
                        height=self.card_height,
                    )
                self._update_card_geometry(self.card_widgets[key])
        for key in self._visible_card_keys - visible_keys:
            self.card_widgets[key]["card"].place_forget()
        self._visible_card_keys = visible_keys
        self._queue_scrollbar_update(height)
    def _set_grid_size(self, width: int, height: int) -> None:
        size = (width, height)
        if size == self._grid_size:
            return
        self._grid_size = size
        self.grid_frame.configure(width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def _queue_scrollbar_update(self, content_height):
        if self._scrollbar_after is not None:
            self.after_cancel(self._scrollbar_after)
        self._scrollbar_after = self.after_idle(
            lambda height=content_height: self._update_scrollbar(height))

    def _update_scrollbar(self, content_height):
        self._scrollbar_after = None
        needs_scrollbar = content_height > self.canvas.winfo_height()
        currently_visible = self.scrollbar.winfo_manager() == "grid"
        if needs_scrollbar == currently_visible:
            return
        if needs_scrollbar:
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()
        self.after_idle(self._render_cards)

    def _create_card(self, key: str) -> dict:
        card = tk.Frame(
            self.grid_frame,
            bg=self.colors["card"],
            width=self.card_width,
            height=self.card_height,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        icon_holder = tk.Frame(
            card, bg=self.colors["icon_tile"],
            width=self.icon_size, height=self.icon_size)
        icon_holder.pack(pady=(15, 9))
        icon_holder.pack_propagate(False)
        icon_label = tk.Label(
            icon_holder, bg=self.colors["icon_tile"], borderwidth=0)
        icon_label.pack(fill="both", expand=True)
        name_label = tk.Label(
            card,
            fg=self.colors["text"],
            bg=self.colors["card"],
            wraplength=self.card_width - 24,
            height=2,
            justify="center",
            font=("Segoe UI Semibold", 11),
        )
        name_label.pack(fill="x", padx=10)
        size_label = tk.Label(
            card,
            fg=self.colors["accent"],
            bg=self.colors["badge"],
            padx=10,
            pady=4,
            font=("Segoe UI", 9, "bold"),
        )
        size_label.pack(pady=(5, 8))

        actions = tk.Frame(card, bg=self.colors["card"])
        actions.pack(fill="x", padx=9, side="bottom", pady=(0, 10))
        ttk.Button(
            actions,
            text="Details",
            style="Launcher.TButton",
            command=lambda game_key=key: self._show_details_by_key(game_key),
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(
            actions,
            text="Play",
            style="Accent.TButton",
            command=lambda game_key=key: self._launch_by_key(game_key),
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        def set_card_color(hovered=False):
            selected = (
                self._selected_game is not None
                and self._game_key(self._selected_game) == key
            )
            color = (
                self.colors["card_hover"]
                if hovered or selected else self.colors["card"]
            )
            card.configure(
                bg=color,
                highlightbackground=(
                    self.colors["accent"]
                    if hovered or selected else self.colors["border"]),
            )
            icon_label.configure(bg=self.colors["icon_tile"])
            icon_holder.configure(bg=self.colors["icon_tile"])
            name_label.configure(bg=color)
            actions.configure(bg=color)

        def update_hover(event):
            x, y = event.x_root, event.y_root
            inside = (
                card.winfo_rootx() <= x < card.winfo_rootx() + card.winfo_width()
                and card.winfo_rooty() <= y < card.winfo_rooty() + card.winfo_height()
            )
            set_card_color(inside)

        for widget in (
                card, icon_holder, icon_label, name_label, size_label, actions):
            widget.bind(
                "<Enter>", update_hover)
            widget.bind("<Leave>", update_hover)
        return {
            "card": card,
            "icon": icon_label,
            "icon_holder": icon_holder,
            "name": name_label,
            "size": size_label,
            "actions": actions,
            "set_color": set_card_color,
        }

    def _update_card_geometry(self, widgets: dict) -> None:
        card = widgets["card"]
        if (int(card.cget("width")), int(card.cget("height"))) != (
                self.card_width, self.card_height):
            card.configure(width=self.card_width, height=self.card_height)
        name = widgets["name"]
        wraplength = self.card_width - 24
        if int(name.cget("wraplength")) != wraplength:
            name.configure(wraplength=wraplength)

    def _update_card(
            self, key: str, game: GameEntry,
            refresh_icon: bool = False) -> None:
        widgets = self.card_widgets[key]
        self._update_card_geometry(widgets)
        widgets["name"].configure(text=game.name)
        widgets["size"].configure(text=format_size(game.size_bytes))
        if refresh_icon or widgets.get("icon_size") != self.icon_size:
            try:
                photo = get_icon_image(
                    game.executable, self.icon_size)
            except (OSError, ValueError, tk.TclError):
                log.exception("Unable to load icon for %s", game.executable)
                photo = None
            widgets["icon"].configure(
                image=photo, text="" if photo is not None else "GAME",
                fg=self.colors["accent"], font=("Segoe UI", 10, "bold"))
            widgets["icon"].image = photo
            widgets["icon_size"] = self.icon_size

    def _launch_by_key(self, key: str) -> None:
        game = next(game for game in self.games if self._game_key(game) == key)
        launch_game(game.executable)

    def _show_details_by_key(self, key: str) -> None:
        game = next(game for game in self.games if self._game_key(game) == key)
        self._show_details(game)

    def _build_details_panel(self) -> None:
        header = tk.Frame(self.details_panel, bg=self.colors["surface"])
        header.pack(fill="x", pady=(0, 14))
        tk.Label(
            header, text=self.ui_text["details_heading"],
            fg=self.colors["accent"], bg=self.colors["surface"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="Close", style="Launcher.TButton",
            command=self._hide_details,
        ).pack(side="right")

        identity = tk.Frame(self.details_panel, bg=self.colors["surface"])
        identity.pack(fill="x", pady=(0, 14))
        icon_holder = tk.Frame(
            identity, bg=self.colors["icon_tile"], width=80, height=80)
        icon_holder.pack(side="left", padx=(0, 14))
        icon_holder.pack_propagate(False)
        self.details_icon = tk.Label(
            icon_holder, bg=self.colors["icon_tile"], borderwidth=0)
        self.details_icon.pack(fill="both", expand=True)
        self.details_icon.image = None
        self.detail_name = tk.Label(
            identity, text="", fg=self.colors["text"],
            bg=self.colors["surface"], wraplength=190, height=3,
            justify="left", anchor="w", font=("Segoe UI Semibold", 17),
        )
        self.detail_name.pack(side="left", fill="x", expand=True)
        details_body = tk.Frame(self.details_panel, bg=self.colors["surface"])
        details_body.pack(fill="both", expand=True)
        self.detail_values = []
        for index, heading in enumerate((
                "FOLDER SIZE", "EXECUTABLE SIZE", "MODIFIED",
                "GAME FOLDER", "EXECUTABLE")):
            section = tk.Frame(details_body, bg=self.colors["surface"])
            section.pack(fill="x", pady=(0, 4))
            if index:
                tk.Frame(
                    section, bg=self.colors["border"], height=1,
                ).pack(fill="x", pady=(0, 4))
            tk.Label(
                section,
                text=heading,
                fg=self.colors["muted"],
                bg=self.colors["surface"],
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor="w")
            value = tk.Label(
                section,
                text="",
                fg=self.colors["text"],
                bg=self.colors["surface"],
                wraplength=190,
                justify="left",
                anchor="w",
                font=("Segoe UI", 9),
            )
            value.pack(fill="x", anchor="w", pady=(2, 0))
            self.detail_values.append(value)
        actions = tk.Frame(
            self.details_panel, bg=self.colors["surface"])
        actions.pack(fill="x", side="bottom", pady=(16, 0))
        ttk.Button(
            actions, text="Open folder", style="Launcher.TButton",
            command=self._open_selected_folder,
        ).pack(fill="x", pady=(0, 8))
        ttk.Button(
            actions, text="Play game", style="Accent.TButton",
            command=self._launch_selected_game,
        ).pack(fill="x")
        self._selected_game = None

    def _refresh_card_selection(self) -> None:
        for widgets in self.card_widgets.values():
            widgets["set_color"]()

    def _show_details(self, game: GameEntry) -> None:
        self._selected_game = game
        try:
            executable_stat = game.executable.stat()
        except OSError as exc:
            log.warning("Unable to read executable size for %s: %s",
                        game.executable, exc)
            executable_stat = None
        if self.detail_name.cget("text") != game.name:
            self.detail_name.configure(text=game.name)
        try:
            photo = get_icon_image(
                game.executable, 72)
        except (OSError, ValueError, tk.TclError):
            log.exception("Unable to load details icon for %s",
                          game.executable)
            photo = None
        self.details_icon.configure(
            image=photo, text="" if photo is not None else "GAME",
            fg=self.colors["accent"], font=("Segoe UI", 8, "bold"))
        self.details_icon.image = photo
        details = (
            ("FOLDER SIZE", f"{format_size(game.size_bytes)} (total file size)"),
            ("EXECUTABLE SIZE", format_size(executable_stat.st_size)
             if executable_stat is not None else "Unavailable"),
            ("MODIFIED", datetime.fromtimestamp(executable_stat.st_mtime)
             .strftime("%Y-%m-%d %H:%M")
             if executable_stat is not None else "Unavailable"),
            ("GAME FOLDER", str(game.folder)),
            ("EXECUTABLE", str(game.executable)),
        )
        for value_label, (_, value) in zip(self.detail_values, details):
            value_label.configure(text=value)
        self._refresh_card_selection()
        self._set_details_panel_width(self.winfo_width())
        if self.details_panel.winfo_manager() != "grid":
            library = self.details_panel.master
            library.grid_columnconfigure(
                2, weight=0, minsize=self._details_panel_width + 12)
            self.details_panel.grid(
                row=0, column=2, sticky="nsew", padx=(12, 0), pady=8)
        self.canvas.focus_set()

    def _hide_details(self) -> None:
        self.details_panel.grid_remove()
        self.details_panel.master.grid_columnconfigure(2, minsize=0)
        self._selected_game = None
        self._refresh_card_selection()

    def _open_selected_folder(self) -> None:
        if self._selected_game is not None:
            self._open_folder(self._selected_game.folder)

    def _launch_selected_game(self) -> None:
        if self._selected_game is not None:
            launch_game(self._selected_game.executable)

    def _open_folder(self, folder):
        try:
            subprocess.Popen(["explorer", str(folder)])
        except OSError as exc:
            log.exception("Unable to open game folder %s", folder)
            self.set_status(f"Could not open folder: {exc}")

    def _on_close(self):
        self.loading_bar.stop()
        if self._geometry_after is not None:
            self.after_cancel(self._geometry_after)
        if self._layout_after is not None:
            self.after_cancel(self._layout_after)
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        if self._scrollbar_after is not None:
            self.after_cancel(self._scrollbar_after)
        self._save_settings()
        self.destroy()
