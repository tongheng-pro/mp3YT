"""Shared download/convert logic used by both the CLI (video2mp3.py) and the GUI (video2mp3_gui.py)."""

import os
import shutil

import yt_dlp


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


class _YdlLogger:
    """Routes yt-dlp's internal log lines to a user-supplied log_callback."""

    def __init__(self, log_callback):
        self._log = log_callback

    def debug(self, msg):
        # yt-dlp prefixes some info messages with '[debug] ' even on the debug channel.
        if msg.startswith("[debug] "):
            return
        self._log(msg)

    def info(self, msg):
        self._log(msg)

    def warning(self, msg):
        self._log(f"WARNING: {msg}")

    def error(self, msg):
        self._log(f"ERROR: {msg}")


def download_mp3(
    url: str,
    output_dir: str = ".",
    quality: str = "192",
    keep_video: bool = False,
    embed_thumbnail: bool = True,
    progress_callback=None,
    log_callback=None,
) -> str:
    """Download `url` and convert it to an MP3.

    progress_callback(pct: float, speed: float|None, eta: int|None, stage: str) -> None
    log_callback(message: str) -> None

    Returns the path to the resulting MP3 file.
    """
    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg first (e.g. `winget install ffmpeg`).")

    os.makedirs(output_dir, exist_ok=True)

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed")
            eta = d.get("eta")
            if total and progress_callback:
                pct = downloaded / total * 100
                progress_callback(pct, speed, eta, "downloading")
        elif status == "finished":
            log("Download finished, post-processing (audio extraction / thumbnail)...")
            if progress_callback:
                progress_callback(100.0, None, None, "processing")

    postprocessors = [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality},
    ]
    if embed_thumbnail:
        postprocessors.append({"key": "EmbedThumbnail"})

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "postprocessors": postprocessors,
        "writethumbnail": embed_thumbnail,
        "keepvideo": keep_video,
        "progress_hooks": [hook],
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "continuedl": True,
        "ffmpeg_location": ffmpeg_path,
        "quiet": True,
        "no_warnings": True,
        "logger": _YdlLogger(log_callback) if log_callback else None,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "audio")
        duration = info.get("duration")
        if duration and log_callback:
            h, rem = divmod(int(duration), 3600)
            m, s = divmod(rem, 60)
            log(f"Source duration: {h:02d}:{m:02d}:{s:02d}")
        return os.path.join(output_dir, f"{title}.mp3")
