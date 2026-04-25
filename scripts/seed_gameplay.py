#!/usr/bin/env python3
"""One-time script to download gameplay clips from YouTube and upload to GCS.

Usage:
    uv run python scripts/seed_gameplay.py
"""

import sys
import tempfile
from pathlib import Path

import yt_dlp
from google.cloud import storage

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))
from smartscroll.config import get_settings

CLIPS = [
    {"url": "https://www.youtube.com/watch?v=zZ7AimPACzc", "name": "subway_surfers_1.mp4"},
    {"url": "https://www.youtube.com/watch?v=s600FYgI5-s", "name": "minecraft_parkour_1.mp4"},
    {"url": "https://www.youtube.com/watch?v=0ikEJppc9qQ", "name": "minecraft_parkour_2.mp4"},
    {"url": "https://www.youtube.com/watch?v=FHkeRqGnNQk", "name": "minecraft_parkour_3.mp4"},
]


def download_clip(url: str, tmp_dir: Path) -> Path:
    ydl_opts = {
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best[height<=1080]",
        "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return tmp_dir / f"{info['id']}.mp4"


def main() -> None:
    settings = get_settings()
    client = storage.Client()
    bucket = client.bucket(settings.gcs_bucket_gameplay)

    existing = {b.name for b in client.list_blobs(settings.gcs_bucket_gameplay)}
    print(f"Bucket gs://{settings.gcs_bucket_gameplay} has {len(existing)} existing clips.\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for clip in CLIPS:
            name = clip["name"]

            print(f"[download] {name}")
            try:
                local_file = download_clip(clip["url"], tmp)
            except Exception as e:
                print(f"[error] download failed for {name}: {e}")
                continue

            print(f"[upload] {name} ({local_file.stat().st_size / 1_000_000:.1f} MB)")
            blob = bucket.blob(name)
            blob.upload_from_filename(str(local_file), content_type="video/mp4")
            print(f"  → gs://{settings.gcs_bucket_gameplay}/{name}\n")

    print("Done.")


if __name__ == "__main__":
    main()
