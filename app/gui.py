from __future__ import annotations

import tkinter as tk
from tkinter import ttk

try:
    from .library import get_track_rows, search_track_rows
except ImportError:  # pragma: no cover - fallback for direct execution
    from library import get_track_rows, search_track_rows


class DJPlusGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DJPlus")
        self.root.geometry("1100x700")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.build_ui()
        self.load_library()

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        ttk.Label(main, text="DJPlus", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )

        search_frame = ttk.Frame(main)
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 10))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Buscar:").grid(row=0, column=0, padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<Return>", self.on_search)

        ttk.Button(search_frame, text="Buscar", command=self.on_search).grid(row=0, column=2, padx=(8, 0))

        left = ttk.Frame(main)
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        ttk.Label(left, text="Biblioteca").grid(row=0, column=0, sticky="w")
        self.library_list = ttk.Treeview(left, columns=("artist", "title", "duration"), show="headings", height=18)
        self.library_list.heading("artist", text="Artista")
        self.library_list.heading("title", text="Título")
        self.library_list.heading("duration", text="Duración")
        self.library_list.column("artist", width=220, anchor="w")
        self.library_list.column("title", width=300, anchor="w")
        self.library_list.column("duration", width=90, anchor="center")
        self.library_list.grid(row=1, column=0, sticky="nsew")
        self.library_list.bind("<<TreeviewSelect>>", self.on_select_track)

        right = ttk.Frame(main)
        right.grid(row=2, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(right, text="Detalles").grid(row=0, column=0, sticky="w")
        self.detail_text = tk.Text(right, height=12, wrap="word")
        self.detail_text.grid(row=1, column=0, sticky="nsew", pady=(6, 10))

        ttk.Label(right, text="Crates").grid(row=2, column=0, sticky="w")
        self.crates_list = tk.Listbox(right, height=8)
        self.crates_list.grid(row=3, column=0, sticky="nsew")
        self.crates_list.insert(0, "Crate 1")
        self.crates_list.insert(1, "Crate 2")

        bottom = ttk.Frame(main)
        bottom.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, text="Reproductor básico: play / pause / next").grid(row=0, column=0, sticky="w")

    def load_library(self) -> None:
        self.library_list.delete(*self.library_list.get_children())
        tracks = get_track_rows(limit=200)
        for track in tracks:
            duration = f"{track.duration:.2f}s" if track.duration else "-"
            self.library_list.insert(
                "",
                "end",
                values=(track.artist, track.title, duration),
                iid=str(track.id),
            )

    def on_search(self, event=None) -> None:
        query = self.search_var.get().strip()
        self.library_list.delete(*self.library_list.get_children())
        if not query:
            self.load_library()
            return

        tracks = search_track_rows(query)
        for track in tracks:
            duration = f"{track.duration:.2f}s" if track.duration else "-"
            self.library_list.insert(
                "",
                "end",
                values=(track.artist, track.title, duration),
                iid=str(track.id),
            )

    def on_select_track(self, event=None) -> None:
        selection = self.library_list.selection()
        if not selection:
            return
        item_id = selection[0]
        values = self.library_list.item(item_id, "values")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(
            tk.END,
            f"Artista: {values[0]}\n"
            f"Título: {values[1]}\n"
            f"Duración: {values[2]}\n"
            f"\nEsta pista está lista para ser añadida a un crate o a un reproductor futuro.",
        )


def launch_gui() -> None:
    root = tk.Tk()
    DJPlusGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
