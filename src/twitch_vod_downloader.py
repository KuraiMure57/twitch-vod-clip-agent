import os
import subprocess
import sys
from pathlib import Path

import yt_dlp


OUTPUT_DIR = Path("data/vods")


def get_latest_vod_url() -> str:
    """
    Get the latest VOD URL using the Twitch API module.
    """

    import twitch_vods

    # This function is intentionally kept separate from the
    # downloader so the Twitch API logic remains reusable.
    access_token = twitch_vods.get_access_token()
    user = twitch_vods.get_user(access_token)
    vod = twitch_vods.get_latest_vod(
        access_token,
        user["id"],
    )

    if vod is None:
        raise RuntimeError("No Twitch VODs were found.")

    print(f"Selected VOD: {vod['id']}")
    print(f"Title: {vod['title']}")
    print(f"URL: {vod['url']}")

    return vod["url"]


def download_vod(vod_url: str) -> Path:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_template = str(
        OUTPUT_DIR / "%(id)s.%(ext)s"
    )

    options = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }

    print("Starting VOD download...")

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            vod_url,
            download=True,
        )

        downloaded_path = Path(
            ydl.prepare_filename(info)
        )

    mp4_path = downloaded_path.with_suffix(".mp4")

    if not mp4_path.exists():
        raise RuntimeError(
            f"Downloaded video was not found: {mp4_path}"
        )

    print(f"VOD downloaded successfully: {mp4_path}")

    return mp4_path


def inspect_video(video_path: Path) -> None:
    print("Inspecting downloaded video with FFprobe...")

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-of",
            "default=noprint_wrappers=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    print("FFprobe result:")
    print(result.stdout)


def main() -> int:
    try:
        vod_url = get_latest_vod_url()

        video_path = download_vod(vod_url)

        inspect_video(video_path)

        return 0

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
