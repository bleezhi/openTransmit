#!/usr/bin/env python3
"""openTransmit - simple Tk radio automation / playout system."""

from __future__ import annotations

import random
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

AUDIO_DIR = Path(__file__).parent / "audio"
CATEGORIES = ("music", "ads", "promos", "idents")
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus"}


class Player:
    def __init__(self, on_finished):
        self.on_finished = on_finished
        self.process: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.backend = self._find_backend()

    @staticmethod
    def _find_backend():
        for name in ("mpv", "ffplay"):
            path = shutil.which(name)
            if path:
                return path
        return None

    def play(self, path: Path):
        self.stop()
        if not self.backend:
            raise RuntimeError("Install mpv or ffmpeg/ffplay to play audio.")

        if Path(self.backend).name == "mpv":
            command = [
                self.backend, "--no-video", "--really-quiet",
                "--", str(path)
            ]
        else:
            command = [
                self.backend, "-nodisp", "-autoexit", "-loglevel", "quiet",
                str(path)
            ]

        with self.lock:
            self.process = subprocess.Popen(command)

        threading.Thread(target=self._wait, daemon=True).start()

    def _wait(self):
        with self.lock:
            process = self.process
        if process:
            process.wait()
        self.on_finished()

    def stop(self):
        with self.lock:
            process = self.process
            self.process = None
        if process and process.poll() is None:
            process.terminate()


class OpenTransmit(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("openTransmit")
        self.geometry("900x560")
        self.minsize(760, 460)

        self.queue: list[Path] = []
        self.current: Path | None = None
        self.auto_radio = tk.BooleanVar(value=False)
        self.running = True

        self.player = Player(self._playback_finished)

        self._build_ui()
        self.refresh_library()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="openTransmit", font=("TkDefaultFont", 18, "bold")).pack(side="left")
        ttk.Checkbutton(
            top, text="Auto Radio", variable=self.auto_radio,
            command=self._auto_changed
        ).pack(side="right")

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        library_frame = ttk.Labelframe(main, text="Library", padding=8)
        queue_frame = ttk.Labelframe(main, text="Queue", padding=8)
        main.add(library_frame, weight=1)
        main.add(queue_frame, weight=1)

        self.category = tk.StringVar(value="music")
        ttk.Combobox(
            library_frame, textvariable=self.category,
            values=CATEGORIES, state="readonly"
        ).pack(fill="x", pady=(0, 8))
        self.library = tk.Listbox(library_frame, selectmode=tk.EXTENDED)
        self.library.pack(fill="both", expand=True)
        self.library.bind("<Double-Button-1>", lambda _e: self.add_selected())

        lib_buttons = ttk.Frame(library_frame)
        lib_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(lib_buttons, text="Refresh", command=self.refresh_library).pack(side="left")
        ttk.Button(lib_buttons, text="Add →", command=self.add_selected).pack(side="right")

        self.queue_list = tk.Listbox(queue_frame)
        self.queue_list.pack(fill="both", expand=True)

        q_buttons = ttk.Frame(queue_frame)
        q_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(q_buttons, text="Play selected", command=self.play_selected).pack(side="left")
        ttk.Button(q_buttons, text="Remove", command=self.remove_selected).pack(side="left", padx=5)
        ttk.Button(q_buttons, text="Clear", command=self.clear_queue).pack(side="right")

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")

        self.now_playing = ttk.Label(bottom, text="Stopped")
        self.now_playing.pack(side="left")

        ttk.Button(bottom, text="Stop", command=self.stop).pack(side="right")
        ttk.Button(bottom, text="Generate Auto Queue", command=self.generate_auto_queue).pack(
            side="right", padx=5
        )

        if not self.player.backend:
            self.now_playing.config(text="No player found — install mpv or ffplay")

    def refresh_library(self):
        self.library.delete(0, tk.END)
        folder = AUDIO_DIR / self.category.get()
        folder.mkdir(parents=True, exist_ok=True)
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
                self.library.insert(tk.END, path.name)

    def add_selected(self):
        folder = AUDIO_DIR / self.category.get()
        for index in self.library.curselection():
            path = folder / self.library.get(index)
            if path.exists():
                self.queue.append(path)
                self.queue_list.insert(tk.END, f"[{self.category.get()}] {path.name}")

    def remove_selected(self):
        for index in reversed(self.queue_list.curselection()):
            self.queue.pop(index)
            self.queue_list.delete(index)

    def clear_queue(self):
        self.queue.clear()
        self.queue_list.delete(0, tk.END)

    def play_selected(self):
        selection = self.queue_list.curselection()
        if not selection:
            if self.queue:
                self._play_index(0)
            return
        self._play_index(selection[0])

    def _play_index(self, index: int):
        if not (0 <= index < len(self.queue)):
            return
        path = self.queue[index]
        self.current = path
        self.now_playing.config(text=f"Now playing: {path.name}")
        try:
            self.player.play(path)
        except RuntimeError as exc:
            messagebox.showerror("Playback error", str(exc))

    def stop(self):
        self.player.stop()
        self.current = None
        self.now_playing.config(text="Stopped")

    def _playback_finished(self):
        self.after(0, self._next_after_finished)

    def _next_after_finished(self):
        if not self.running:
            return

        if self.queue:
            # Remove the item that just finished, then continue.
            try:
                index = self.queue.index(self.current) if self.current else 0
            except ValueError:
                index = 0

            if 0 <= index < len(self.queue):
                self.queue.pop(index)
                self.queue_list.delete(index)

        self.current = None

        if self.auto_radio.get():
            self._ensure_auto_item()

        if self.queue:
            self._play_index(0)
        else:
            self.now_playing.config(text="Queue empty")

    def _auto_changed(self):
        if self.auto_radio.get() and not self.queue:
            self._ensure_auto_item()
            self._play_index(0)

    def generate_auto_queue(self):
        self._ensure_auto_item(count=8)

    def _ensure_auto_item(self, count=1):
        music = self._files("music")
        ads = self._files("ads")
        promos = self._files("promos")
        idents = self._files("idents")

        if not music:
            messagebox.showwarning("Auto Radio", "Put at least one audio file in audio/music/.")
            return

        # A small rolling clock: mostly music, with occasional station elements.
        for _ in range(count):
            roll = random.random()
            if roll < 0.15 and ads:
                path = random.choice(ads)
            elif roll < 0.23 and promos:
                path = random.choice(promos)
            elif roll < 0.30 and idents:
                path = random.choice(idents)
            else:
                path = random.choice(music)

            self.queue.append(path)
            self.queue_list.insert(tk.END, f"[{path.parent.name}] {path.name}")

    @staticmethod
    def _files(category: str) -> list[Path]:
        folder = AUDIO_DIR / category
        folder.mkdir(parents=True, exist_ok=True)
        return [
            p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
        ]

    def close(self):
        self.running = False
        self.player.stop()
        self.destroy()


if __name__ == "__main__":
    OpenTransmit().mainloop()
