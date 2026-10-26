#!/usr/bin/env python3
"""Download a video (YouTube or any yt-dlp-supported site) and convert it to MP3,
embedding the video's thumbnail as cover art (poster) by default.

Works for very long videos (10h+) since yt-dlp streams/downloads in chunks and
ffmpeg extracts audio without loading the whole file into memory.

Usage:
    python video2mp3.py <url> [-o OUTPUT_DIR] [-q QUALITY] [--keep-video] [--no-poster]

Examples:
    python video2mp3.py "https://youtu.be/JCKBaJDRMw4"
    python video2mp3.py "https://youtu.be/JCKBaJDRMw4?si=iLcX6oGQTRXNmu9D" -o downloads -q 192
"""

import argparse
import os
import sys

from core import download_mp3

# Windows consoles often use a legacy codepage that can't encode emoji/CJK
# characters in video titles; replace instead of crashing after the file is saved.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")


def _print_progress(pct, speed, eta, stage):
    if stage == "downloading":
        speed_str = f"{speed / 1024 / 1024:.2f} MiB/s" if speed else "?"
        eta_str = f"{eta}s" if eta is not None else "?"
        print(f"\r  downloading: {pct:5.1f}%  speed={speed_str}  eta={eta_str}   ", end="", flush=True)
    elif stage == "processing":
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a video and convert it to MP3 with embedded poster art.")
    parser.add_argument("url", help="Video URL (YouTube or any yt-dlp-supported site)")
    parser.add_argument("-o", "--output-dir", default=".", help="Output directory (default: current directory)")
    parser.add_argument("-q", "--quality", default="192", help="MP3 bitrate in kbps, e.g. 128/192/320 (default: 192)")
    parser.add_argument("--keep-video", action="store_true", help="Also keep the original downloaded video/audio file")
    parser.add_argument("--no-poster", action="store_true", help="Don't embed the video thumbnail as MP3 cover art")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Fetching: {args.url}")
    mp3_path = download_mp3(
        args.url,
        output_dir=args.output_dir,
        quality=args.quality,
        keep_video=args.keep_video,
        embed_thumbnail=not args.no_poster,
        progress_callback=_print_progress,
        log_callback=lambda msg: print(f"  {msg}"),
    )
    print(f"\nDone. Saved MP3 to: {mp3_path}")


if __name__ == "__main__":
    main()
