import tkinter as tk
from tkinter import ttk

from icons import get_icon_image
from runner import launch_game

from logger import get_logger

log = get_logger("gui")


BG = "#1e1e1e"
CARD_BG = "#2b2b2b"


class GameLauncherWindow(tk.Tk):
    def __init__(self, games, columns=5, icon_size=128):
        super().__init__()
        self.title("Game Launcher")
        self.geometry("1000x700")
        self.configure(bg=BG)

        self.games = games
        self.columns = columns
        self.icon_size = icon_size
        self.images = []  # keeps PhotoImage references alive

        self._build_scroll_area()
        self._build_cards()

    def _build_scroll_area(self):
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=self.canvas.yview)

        self.grid_frame = tk.Frame(self.canvas, bg=BG)
        self.grid_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_cards(self):
        log.info("Building %d cards", len(self.games))
        for index, (name, exe_path) in enumerate(self.games):
            photo = get_icon_image(exe_path, self.icon_size)
            self.images.append(photo)

            card = tk.Frame(self.grid_frame, bg=CARD_BG,
                            padx=10, pady=10, cursor="hand2")
            card.grid(row=index // self.columns, column=index %
                      self.columns, padx=8, pady=8)

            icon_label = tk.Label(card, image=photo, bg=CARD_BG)
            name_label = tk.Label(
                card, text=name, fg="white", bg=CARD_BG, wraplength=self.icon_size
            )
            icon_label.pack()
            name_label.pack()

            # Make the whole card clickable, not just the icon
            for widget in (card, icon_label, name_label):
                widget.bind("<Button-1>", lambda e, p=exe_path: launch_game(p))
