#!/usr/bin/env python3
"""openTransmit - radio automation / playout system."""

from __future__ import annotations

import random
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


AUDIO_DIR = Path(__file__).parent / "audio"
CATEGORIES = ("music", "ads", "promos", "idents")
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus"}

BG = "#0b0f0c"
PANEL = "#101611"
PANEL2 = "#0d130f"
FG = "#d7e5d9"
DIM = "#718277"
GREEN = "#73ff8a"
CYAN = "#70d7ff"
RED = "#ff7070"
BORDER = "#25352a"


class Player:
    def __init__(self, on_finished):
        self.on_finished = on_finished
        self.process: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.backend = self._find_backend()
        self.output_backend = "PipeWire"
        self.output_device = "default"

    @staticmethod
    def _find_backend():
        for name in ("mpv", "ffplay"):
            path = shutil.which(name)
            if path:
                return path
        return None

    def set_output(self, backend: str, device: str):
        self.output_backend = backend
        self.output_device = device or "default"

    def play(self, path: Path):
        self.stop()
        if not self.backend:
            raise RuntimeError("Install mpv or ffmpeg/ffplay to play audio.")

        if Path(self.backend).name == "mpv":
            command = [
                self.backend, "--no-video", "--really-quiet",
                "--audio-device=" + self._mpv_device(),
                "--", str(path),
            ]
        else:
            command = [
                self.backend, "-nodisp", "-autoexit", "-loglevel", "quiet",
                "-f", "lavfi",
                "-i", "anullsrc",
                str(path),
            ]

        with self.lock:
            self.process = subprocess.Popen(command)

        threading.Thread(target=self._wait, daemon=True).start()

    def _mpv_device(self):
        if self.output_backend == "ALSA":
            return "alsa/" + self.output_device
        if self.output_backend == "PipeWire":
            # mpv's pipewire backend accepts pipewire/<node-name>.
            if self.output_device == "default":
                return "pipewire/"
            return "pipewire/" + self.output_device
        return "auto"

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
        self.geometry("1040x650")
        self.minsize(850, 520)
        self.configure(bg=BG)

        self.queue: list[Path] = []
        self.current: Path | None = None
        self.auto_radio = tk.BooleanVar(value=False)
        self.running = True
        self.backend_var = tk.StringVar(value="PipeWire")
        self.device_var = tk.StringVar(value="default")

        self._setup_fonts()
        self.player = Player(self._playback_finished)
        self._build_ui()
        self.refresh_library()
        self.refresh_outputs()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _setup_fonts(self):
        self.font = ("DejaVu Sans Mono", 10)
        self.small_font = ("DejaVu Sans Mono", 9)
        self.bold_font = ("DejaVu Sans Mono", 10, "bold")
        self.title_font = ("DejaVu Sans Mono", 16, "bold")

    def _label(self, parent, text, fg=FG, font=None):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=fg,
                        font=font or self.font, anchor="w")

    def _frame(self, parent, **kwargs):
        return tk.Frame(parent, bg=kwargs.pop("bg", PANEL), **kwargs)

    def _button(self, parent, text, command, fg=FG, width=None):
        opts = {
            "text": text, "command": command, "bg": PANEL2, "fg": fg,
            "activebackground": BORDER, "activeforeground": GREEN,
            "relief": "flat", "bd": 0, "highlightthickness": 1,
            "highlightbackground": BORDER, "highlightcolor": GREEN,
            "font": self.small_font, "padx": 10, "pady": 6,
            "cursor": "hand2",
        }
        if width:
            opts["width"] = width
        return tk.Button(parent, **opts)

    def _build_ui(self):
        header = self._frame(self, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 8))

        self._label(header, "openTransmit", GREEN, self.title_font).pack(side="left")
        self._label(header, "  // radio automation console", DIM, self.small_font).pack(side="left")
        self._button(header, "[ AUTO RADIO ]", self._auto_changed, GREEN).pack(side="right")
        self.auto_button = header.winfo_children()[-1]

        status = self._frame(self, bg=PANEL2)
        status.pack(fill="x", padx=16, pady=(0, 10))
        self.status_label = self._label(status, "● READY", GREEN, self.bold_font)
        self.status_label.pack(side="left", padx=10, pady=7)
        self.now_playing = self._label(status, "stopped", DIM, self.small_font)
        self.now_playing.pack(side="left", padx=8)

        main = self._frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=16)

        library = self._frame(main)
        library.pack(side="left", fill="both", expand=True, padx=(0, 6))

        queue = self._frame(main)
        queue.pack(side="left", fill="both", expand=True, padx=(6, 0))

        self._label(library, "[ LIBRARY ]", CYAN, self.bold_font).pack(fill="x", padx=10, pady=(10, 6))

        catrow = self._frame(library, bg=PANEL)
        catrow.pack(fill="x", padx=10, pady=(0, 6))
        self._label(catrow, "category:", DIM, self.small_font).pack(side="left", padx=(5, 4))
        self.category = tk.StringVar(value="music")
        self.category_menu = tk.OptionMenu(
            catrow, self.category, *CATEGORIES, command=lambda _x: self.refresh_library()
        )
        self.category_menu.config(
            bg=PANEL2, fg=FG, activebackground=BORDER, activeforeground=GREEN,
            relief="flat", bd=0, highlightthickness=0, font=self.small_font
        )
        self.category_menu["menu"].config(bg=PANEL2, fg=FG, activebackground=BORDER, activeforeground=GREEN)
        self.category_menu.pack(side="left")

        self.library = tk.Listbox(
            library, selectmode=tk.EXTENDED, bg=BG, fg=FG,
            selectbackground=BORDER, selectforeground=GREEN,
            activestyle="none", relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER,
            font=self.small_font
        )
        self.library.pack(fill="both", expand=True, padx=10, pady=4)
        self.library.bind("<Double-Button-1>", lambda _e: self.add_selected())

        libbuttons = self._frame(library)
        libbuttons.pack(fill="x", padx=10, pady=8)
        self._button(libbuttons, "[ refresh ]", self.refresh_library).pack(side="left")
        self._button(libbuttons, "[ add -> ]", self.add_selected, GREEN).pack(side="right")

        self._label(queue, "[ PLAYOUT QUEUE ]", CYAN, self.bold_font).pack(fill="x", padx=10, pady=(10, 6))
        self.queue_list = tk.Listbox(
            queue, bg=BG, fg=FG, selectbackground=BORDER,
            selectforeground=GREEN, activestyle="none", relief="flat",
            bd=0, highlightthickness=1, highlightbackground=BORDER,
            font=self.small_font
        )
        self.queue_list.pack(fill="both", expand=True, padx=10, pady=4)

        qbuttons = self._frame(queue)
        qbuttons.pack(fill="x", padx=10, pady=8)
        self._button(qbuttons, "[ play ]", self.play_selected, GREEN).pack(side="left")
        self._button(qbuttons, "[ remove ]", self.remove_selected).pack(side="left", padx=5)
        self._button(qbuttons, "[ clear ]", self.clear_queue).pack(side="right")

        output = self._frame(self, bg=PANEL2)
        output.pack(fill="x", padx=16, pady=(10, 8))
        self._label(output, "[ OUTPUT ]", CYAN, self.bold_font).grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self._label(output, "backend", DIM, self.small_font).grid(row=1, column=0, padx=(10, 4), pady=(0, 8), sticky="w")
        self.backend_menu = tk.OptionMenu(
            output, self.backend_var, "PipeWire", "ALSA",
            command=lambda _x: self.refresh_outputs()
        )
        self._style_menu(self.backend_menu)
        self.backend_menu.grid(row=1, column=1, pady=(0, 8), sticky="ew")

        self._label(output, "device", DIM, self.small_font).grid(row=1, column=2, padx=(12, 4), pady=(0, 8), sticky="w")
        self.device_menu = tk.OptionMenu(output, self.device_var, "default")
        self._style_menu(self.device_menu)
        self.device_menu.grid(row=1, column=3, pady=(0, 8), sticky="ew")

        self._button(output, "[ refresh devices ]", self.refresh_outputs).grid(
            row=1, column=4, padx=10, pady=(0, 8)
        )
        output.grid_columnconfigure(1, weight=1)
        output.grid_columnconfigure(3, weight=3)

        controls = self._frame(self, bg=BG)
        controls.pack(fill="x", padx=16, pady=(0, 14))
        self._button(controls, "[ stop ]", self.stop, RED).pack(side="right")
        self._button(controls, "[ generate auto queue ]", self.generate_auto_queue, CYAN).pack(side="right", padx=6)

        self._label(self, "  output selection: live  |  playback: mpv/ffplay  |  audio: ./audio/{ads,promos,music,idents}", DIM, self.small_font).pack(
            fill="x", padx=16, pady=(0, 10)
        )

        if not self.player.backend:
            self._set_status("NO PLAYER", RED, "install mpv or ffplay")

    def _style_menu(self, menu):
        menu.config(
            bg=PANEL, fg=FG, activebackground=BORDER, activeforeground=GREEN,
            relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER,
            font=self.small_font
        )
        menu["menu"].config(bg=PANEL2, fg=FG, activebackground=BORDER, activeforeground=GREEN)

    def _set_status(self, status, color, detail=""):
        self.status_label.config(text=f"● {status}", fg=color)
        self.now_playing.config(text=detail)

    def refresh_library(self):
        self.library.delete(0, tk.END)
        folder = AUDIO_DIR / self.category.get()
        folder.mkdir(parents=True, exist_ok=True)
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
                self.library.insert(tk.END, path.name)

    def refresh_outputs(self):
        backend = self.backend_var.get()
        devices = self._pipewire_devices() if backend == "PipeWire" else self._alsa_devices()
        if not devices:
            devices = [("default", "default")]

        menu = self.device_menu["menu"]
        menu.delete(0, "end")
        for value, label in devices:
            menu.add_command(
                label=label,
                command=lambda v=value: self.device_var.set(v)
            )

        values = [value for value, _ in devices]
        if self.device_var.get() not in values:
            self.device_var.set(values[0])

        self.player.set_output(backend, self.device_var.get())

    @staticmethod
    def _pipewire_devices():
        devices = [("default", "default")]
        pactl = shutil.which("pactl")
        if not pactl:
            return devices

        try:
            result = subprocess.run(
                [pactl, "list", "short", "sinks"],
                capture_output=True, text=True, timeout=3, check=False,
            )
        except OSError:
            return devices

        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name = parts[1].strip()
                devices.append((name, name))
        return devices

    @staticmethod
    def _alsa_devices():
        devices = [("default", "default")]
        aplay = shutil.which("aplay")
        if not aplay:
            return devices

        try:
            result = subprocess.run(
                [aplay, "-L"],
                capture_output=True, text=True, timeout=3, check=False,
            )
        except OSError:
            return devices

        seen = {"default"}
        for line in result.stdout.splitlines():
            if not line or line[0].isspace():
                continue
            name = line.strip()
            if name in seen:
                continue
            seen.add(name)
            label = name
            devices.append((name, label))
        return devices

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
        self.player.set_output(self.backend_var.get(), self.device_var.get())
        path = self.queue[index]
        self.current = path
        self._set_status("PLAYING", GREEN, path.name)
        try:
            self.player.play(path)
        except RuntimeError as exc:
            messagebox.showerror("Playback error", str(exc))
            self._set_status("ERROR", RED, str(exc))

    def stop(self):
        self.player.stop()
        self.current = None
        self._set_status("READY", GREEN, "stopped")

    def _playback_finished(self):
        self.after(0, self._next_after_finished)

    def _next_after_finished(self):
        if not self.running:
            return

        if self.queue:
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
            self._set_status("READY", GREEN, "queue empty")

    def _auto_changed(self):
        self.auto_radio.set(not self.auto_radio.get())
        if self.auto_radio.get():
            self.auto_button.config(text="[ AUTO RADIO: ON ]", fg=GREEN)
            if not self.queue:
                self._ensure_auto_item()
                self._play_index(0)
        else:
            self.auto_button.config(text="[ AUTO RADIO ]", fg=FG)

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
