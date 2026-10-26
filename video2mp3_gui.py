#!/usr/bin/env python3
"""Simple desktop GUI for video2mp3: paste a URL, pick options, click Download.

Run with:  python video2mp3_gui.py
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core import download_mp3

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video to MP3")
        self.geometry("620x460")
        self.resizable(True, True)

        self._msg_queue: "queue.Queue[tuple]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._last_output_dir = DEFAULT_OUTPUT_DIR
        self._last_mp3_path: str | None = None

        self._build_widgets()
        self.after(100, self._poll_queue)

    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}

        url_frame = ttk.Frame(self)
        url_frame.pack(fill="x", **pad)
        ttk.Label(url_frame, text="Video URL:").pack(anchor="w")
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.pack(fill="x", pady=(4, 0))
        self.url_entry.focus()

        opts_frame = ttk.Frame(self)
        opts_frame.pack(fill="x", **pad)

        out_frame = ttk.Frame(opts_frame)
        out_frame.pack(fill="x")
        ttk.Label(out_frame, text="Output folder:").pack(side="left")
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.output_entry = ttk.Entry(out_frame, textvariable=self.output_var)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(out_frame, text="Browse...", command=self._browse_folder).pack(side="left")

        row2 = ttk.Frame(opts_frame)
        row2.pack(fill="x", pady=(8, 0))
        ttk.Label(row2, text="Quality (kbps):").pack(side="left")
        self.quality_var = tk.StringVar(value="192")
        quality_box = ttk.Combobox(row2, textvariable=self.quality_var, values=["128", "192", "256", "320"], width=6, state="readonly")
        quality_box.pack(side="left", padx=(6, 20))

        self.poster_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Embed thumbnail as poster/cover art", variable=self.poster_var).pack(side="left", padx=(0, 20))

        self.keep_video_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Also keep original video file", variable=self.keep_video_var).pack(side="left")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", **pad)
        self.download_btn = ttk.Button(btn_frame, text="Download MP3", command=self._start_download)
        self.download_btn.pack(side="left")
        self.open_folder_btn = ttk.Button(btn_frame, text="Open output folder", command=self._open_output_folder, state="disabled")
        self.open_folder_btn.pack(side="left", padx=(10, 0))

        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor="w", pady=(4, 0))

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, **pad)
        ttk.Label(log_frame, text="Log:").pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(log_frame, height=10, state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True, pady=(4, 0))

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.output_var.get() or ".")
        if folder:
            self.output_var.set(folder)

    def _open_output_folder(self) -> None:
        folder = self._last_output_dir
        if os.path.isdir(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])

    def _append_log(self, msg: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _start_download(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please paste a video URL first.")
            return
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("Busy", "A download is already in progress.")
            return

        output_dir = self.output_var.get().strip() or DEFAULT_OUTPUT_DIR
        quality = self.quality_var.get()
        keep_video = self.keep_video_var.get()
        embed_thumbnail = self.poster_var.get()

        self._last_output_dir = output_dir
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress["value"] = 0
        self.status_var.set("Starting...")
        self.download_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        def progress_callback(pct, speed, eta, stage):
            self._msg_queue.put(("progress", pct, speed, eta, stage))

        def log_callback(msg):
            self._msg_queue.put(("log", msg))

        def worker():
            try:
                mp3_path = download_mp3(
                    url,
                    output_dir=output_dir,
                    quality=quality,
                    keep_video=keep_video,
                    embed_thumbnail=embed_thumbnail,
                    progress_callback=progress_callback,
                    log_callback=log_callback,
                )
                self._msg_queue.put(("done", mp3_path))
            except Exception as exc:
                self._msg_queue.put(("error", str(exc)))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._msg_queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, pct, speed, eta, stage = item
                    if stage == "downloading":
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                        self.progress["value"] = pct
                        speed_str = f"{speed / 1024 / 1024:.2f} MiB/s" if speed else "?"
                        eta_str = f"{eta}s" if eta is not None else "?"
                        self.status_var.set(f"Downloading: {pct:.1f}%  ({speed_str}, ETA {eta_str})")
                    elif stage == "processing":
                        self.progress.configure(mode="indeterminate")
                        self.progress.start(12)
                        self.status_var.set("Converting to MP3 / embedding poster... (can take a while for long videos, still working)")
                elif kind == "log":
                    self._append_log(item[1])
                elif kind == "done":
                    mp3_path = item[1]
                    self._last_mp3_path = mp3_path
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.progress["value"] = 100
                    self.status_var.set(f"Done (100%): {mp3_path}")
                    self._append_log(f"Saved: {mp3_path}")
                    self.download_btn.configure(state="normal")
                    self.open_folder_btn.configure(state="normal")
                    messagebox.showinfo("Download complete", f"Saved MP3 to:\n{mp3_path}")
                elif kind == "error":
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.status_var.set("Failed")
                    self._append_log(f"ERROR: {item[1]}")
                    self.download_btn.configure(state="normal")
                    messagebox.showerror("Download failed", item[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


if __name__ == "__main__":
    app = App()
    app.mainloop()
