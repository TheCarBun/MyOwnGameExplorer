from collections.abc import Callable, Sequence
import json
import math
import pathlib
import subprocess
import tkinter as tk
from tkinter import ttk

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
SORT_OPTIONS = (
    "Name (A-Z)",
    "Name (Z-A)",
    "Size (largest)",
    "Size (smallest)",
)
CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config.json"


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


class GameLauncherWindow(tk.Tk):
    def __init__(
            self, games: Sequence[GameEntry],
            on_refresh: Callable[[], None]) -> None:
        super().__init__()
        self.title("Arcade - Game Launcher")
        self.configure(bg=BG)
        self.games = []
        self.on_refresh = on_refresh
        self.card_widgets = {}
        self._search_index = {}
        self._visible_card_keys = set()
        self.columns = 1
        self.target_card_width = TARGET_CARD_WIDTH
        self.card_width = TARGET_CARD_WIDTH
        self.card_height = 252
        self.icon_size = 96
        self._geometry_after = None
        self._expected_window_size = None
        self._layout_after = None
        self._search_after = None
        self._scrollbar_after = None
        self._grid_size = None
        self._details_panel_width = None
        self._scan_complete = False
        self._scan_error = None
        self._initial_fit_pending = True
        self._settings = self._load_settings()
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
            background="#2a3746",
            foreground=TEXT,
            borderwidth=0,
            padding=(12, 8),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Launcher.TButton",
            background=[("active", "#35485b"), ("disabled", "#202a36")],
            foreground=[("disabled", MUTED)],
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#10221d",
            borderwidth=0,
            padding=(12, 8),
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#83ebc7")])
        style.configure(
            "Launcher.TCombobox",
            fieldbackground=SURFACE,
            background=SURFACE,
            foreground=TEXT,
            arrowcolor=ACCENT,
            padding=8,
        )
        style.map(
            "Launcher.TCombobox",
            fieldbackground=[("readonly", SURFACE), ("focus", SURFACE)],
            foreground=[("readonly", TEXT), ("focus", TEXT)],
            selectbackground=[("readonly", SURFACE)],
            selectforeground=[("readonly", TEXT)],
        )
        self.option_add("*TCombobox*Listbox.background", SURFACE)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", "#35485b")
        self.option_add("*TCombobox*Listbox.selectForeground", TEXT)
        style.configure(
            "Launcher.TEntry",
            fieldbackground=SURFACE,
            foreground=TEXT,
            insertcolor=TEXT,
            padding=10,
        )
        style.configure(
            "Launcher.Vertical.TScrollbar",
            background=SURFACE,
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=MUTED,
        )
        style.configure(
            "Launcher.Horizontal.TProgressbar",
            troughcolor=SURFACE,
            background=ACCENT,
            borderwidth=0,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    def _build_layout(self):
        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=26, pady=(22, 16))

        header = tk.Frame(content, bg=BG)
        header.pack(fill="x", pady=(0, 20))
        title_block = tk.Frame(header, bg=BG)
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_block,
            text="Your library",
            fg=TEXT,
            bg=BG,
            font=("Segoe UI Semibold", 25),
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="All your games, ready when you are.",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))
        self.refresh_button = ttk.Button(
            header,
            text="Refresh library",
            style="Launcher.TButton",
            command=self.on_refresh,
        )
        self.refresh_button.pack(side="right", anchor="center")

        toolbar = tk.Frame(content, bg=BG)
        toolbar.pack(fill="x", pady=(0, 16))
        search_wrap = tk.Frame(toolbar, bg=SURFACE, padx=2, pady=2)
        search_wrap.pack(side="left", fill="x", expand=True, padx=(0, 16))
        tk.Label(
            search_wrap, text="⌕", fg=ACCENT, bg=SURFACE,
            font=("Segoe UI", 16),
        ).pack(side="left", padx=(10, 4))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_wrap,
            textvariable=self.search_var,
            style="Launcher.TEntry",
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_entry.bind("<Escape>", lambda *_: self._clear_search())
        self.sort_var = tk.StringVar(
            value=self._settings.get("sort_order", SORT_OPTIONS[0]))
        tk.Label(
            toolbar, text="SORT BY", fg=MUTED, bg=BG,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 8))
        self.sort_box = ttk.Combobox(
            toolbar,
            textvariable=self.sort_var,
            values=SORT_OPTIONS,
            state="readonly",
            width=17,
            style="Launcher.TCombobox",
        )
        self.sort_box.pack(side="left")
        self.sort_box.bind(
            "<<ComboboxSelected>>", lambda *_: self._on_sort_changed())

        library = tk.Frame(content, bg=BG)
        library.pack(fill="both", expand=True)
        library.grid_rowconfigure(0, weight=1)
        library.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(library, bg=BG, highlightthickness=0,
                                borderwidth=0)
        self.scrollbar = ttk.Scrollbar(
            library,
            orient="vertical",
            command=self.canvas.yview,
            style="Launcher.Vertical.TScrollbar",
        )
        self.grid_frame = tk.Frame(self.canvas, bg=BG)
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
            bg=SURFACE,
            highlightthickness=1,
            highlightbackground="#34475b",
            padx=22,
            pady=20,
        )
        self.details_panel.grid_propagate(False)
        library.grid_columnconfigure(2, weight=0, minsize=0)
        library.grid_columnconfigure(1, weight=0, minsize=0)
        self._build_details_panel()
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        footer = tk.Frame(content, bg=BG)
        footer.pack(fill="x", pady=(12, 0))
        self.status_label = tk.Label(
            footer,
            text="Loading your library...",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
        )
        self.status_label.pack(side="left")
        self.count_label = tk.Label(
            footer, text="", fg=MUTED, bg=BG, font=("Segoe UI", 9))
        self.count_label.pack(side="right")
        self.empty_state = tk.Label(
            self.grid_frame,
            text="",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 12),
        )
        self.empty_state.place_forget()
        self.loading_frame = tk.Frame(self.grid_frame, bg=BG)
        tk.Label(
            self.loading_frame,
            text="Finding your games",
            fg=TEXT,
            bg=BG,
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

    def _load_settings(self):
        try:
            settings = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            log.exception("Unable to read UI settings from %s", CONFIG_PATH)
            return {}

        if not isinstance(settings, dict):
            log.warning("Invalid UI settings in %s; using defaults", CONFIG_PATH)
            return {}
        size = settings.get("window_size")
        if (isinstance(size, list) and len(size) == 2
                and all(type(value) is int and value > 0 for value in size)):
            settings["window_size"] = size
        else:
            settings.pop("window_size", None)
        if settings.get("sort_order") not in SORT_OPTIONS:
            settings.pop("sort_order", None)
        return settings

    def _save_settings(self):
        self._geometry_after = None
        size = [self.winfo_width(), self.winfo_height()]
        if min(size) <= 1:
            return
        if self._expected_window_size == tuple(size):
            return
        settings = {"window_size": size, "sort_order": self.sort_var.get()}
        temporary_path = CONFIG_PATH.with_suffix(".json.tmp")
        try:
            temporary_path.write_text(
                json.dumps(settings, indent=2), encoding="utf-8")
            temporary_path.replace(CONFIG_PATH)
            self._expected_window_size = tuple(size)
        except OSError:
            log.exception("Unable to save UI settings to %s", CONFIG_PATH)

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
            text="Scanning..." if scanning else "Refresh library",
        )
        if scanning:
            self.set_status("Scanning your game folders...")

    def set_status(self, message):
        self.status_label.configure(text=message)

    def set_games(self, games: Sequence[GameEntry]) -> None:
        self._scan_complete = True
        self._scan_error = None
        self.loading_bar.stop()
        self.games = list(games)
        current_keys = {self._game_key(game) for game in self.games}
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
            text=f"{len(games)} of {len(self.games)} games")
        if not games:
            if self._scan_error:
                message = "Could not load games. Check the game folder and try again."
            elif query:
                message = "No games match your search."
            else:
                message = "No games found. Check your game folder and refresh."
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
        self.card_height = self.icon_size + 156
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
            bg=CARD_BG,
            width=self.card_width,
            height=self.card_height,
            highlightthickness=1,
            highlightbackground="#293747",
        )
        icon_holder = tk.Frame(
            card, bg="#273342", width=self.icon_size, height=self.icon_size)
        icon_holder.pack(pady=(12, 8))
        icon_holder.pack_propagate(False)
        icon_label = tk.Label(icon_holder, bg="#273342", borderwidth=0)
        icon_label.pack(fill="both", expand=True)
        name_label = tk.Label(
            card,
            fg=TEXT,
            bg=CARD_BG,
            wraplength=self.card_width - 24,
            height=2,
            justify="center",
            font=("Segoe UI Semibold", 10),
        )
        name_label.pack(fill="x", padx=10)
        size_label = tk.Label(
            card,
            fg=ACCENT,
            bg="#203b38",
            padx=9,
            pady=3,
            font=("Segoe UI", 8, "bold"),
        )
        size_label.pack(pady=(5, 8))

        actions = tk.Frame(card, bg=CARD_BG)
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

        def set_card_color(color):
            card.configure(bg=color, highlightbackground="#3b5368")
            icon_label.configure(bg="#273342")
            name_label.configure(bg=color)
            actions.configure(bg=color)

        for widget in (card, icon_label, name_label, size_label, actions):
            widget.bind("<Enter>", lambda *_: set_card_color(CARD_HOVER))
            widget.bind("<Leave>", lambda *_: set_card_color(CARD_BG))
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
                photo = get_icon_image(game.executable, self.icon_size)
            except (OSError, ValueError, tk.TclError):
                log.exception("Unable to load icon for %s", game.executable)
                photo = None
            widgets["icon"].configure(
                image=photo, text="" if photo is not None else "GAME",
                fg=ACCENT, font=("Segoe UI", 10, "bold"))
            widgets["icon"].image = photo
            widgets["icon_size"] = self.icon_size

    def _launch_by_key(self, key: str) -> None:
        game = next(game for game in self.games if self._game_key(game) == key)
        launch_game(game.executable)

    def _show_details_by_key(self, key: str) -> None:
        game = next(game for game in self.games if self._game_key(game) == key)
        self._show_details(game)

    def _build_details_panel(self) -> None:
        header = tk.Frame(self.details_panel, bg=SURFACE)
        header.pack(fill="x", pady=(0, 18))
        tk.Label(
            header, text="GAME DETAILS", fg=ACCENT, bg=SURFACE,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="Close", style="Launcher.TButton",
            command=self._hide_details,
        ).pack(side="right")

        self.detail_name = tk.Label(
            self.details_panel, text="", fg=TEXT, bg=SURFACE,
            wraplength=290, height=2, justify="left", anchor="nw",
            font=("Segoe UI Semibold", 18),
        )
        self.detail_name.pack(fill="x", pady=(0, 20))
        self.details_text = tk.Text(
            self.details_panel,
            height=12,
            wrap="word",
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#35485b",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 9),
            padx=0,
            pady=0,
            state="disabled",
        )
        self.details_text.tag_configure(
            "heading", foreground=MUTED, font=("Segoe UI", 8, "bold"))
        self.details_text.pack(fill="x", anchor="nw")
        self._details_content = ""
        actions = tk.Frame(self.details_panel, bg=SURFACE)
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

    def _show_details(self, game: GameEntry) -> None:
        self._selected_game = game
        if self.detail_name.cget("text") != game.name:
            self.detail_name.configure(text=game.name)
        try:
            executable_size = game.executable.stat().st_size
        except OSError as exc:
            log.warning("Unable to read executable size for %s: %s",
                        game.executable, exc)
            executable_size = None
        details = (
            ("FOLDER SIZE", f"{format_size(game.size_bytes)} (total file size)"),
            ("EXECUTABLE SIZE", format_size(executable_size)
             if executable_size is not None else "Unavailable"),
            ("GAME FOLDER", str(game.folder)),
            ("EXECUTABLE", str(game.executable)),
        )
        content = "\n\n".join(
            f"{heading}\n{value}" for heading, value in details) + "\n"
        if content != self._details_content:
            self.details_text.configure(state="normal")
            self.details_text.replace("1.0", "end", content)
            self.details_text.tag_remove("heading", "1.0", "end")
            offset = 0
            for heading, value in details:
                start = f"1.0 + {offset} chars"
                end = f"1.0 + {offset + len(heading)} chars"
                self.details_text.tag_add("heading", start, end)
                offset += len(heading) + 1 + len(value) + 2
            self.details_text.configure(state="disabled")
            self._details_content = content
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
