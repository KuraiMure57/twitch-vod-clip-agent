import subprocess
import sys
from pathlib import Path

import yt_dlp


VOD_URL = "https://www.twitch.tv/videos/2846005700"
OUTPUT_DIR = Path("data/vod_test")
OUTPUT_FILE = OUTPUT_DIR / "vod_test.mp4"

TEST_DURATION_SECONDS = 60


def download_vod_segment() -> Path:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_template = str(
        OUTPUT_DIR / "source.%(ext)s"
    )

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": temp_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "download_ranges": lambda info, ydl: [
            {
                "start_time": 0,
                "end_time": TEST_DURATION_SECONDS,
            }
        ],
        "force_keyframes_at_cuts": True,
    }

    print(f"Downloading first {TEST_DURATION_SECONDS} seconds...")
    print(f"VOD: {VOD_URL}")

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([VOD_URL])

    downloaded_files = list(
        OUTPUT_DIR.glob("source.*")
    )

    if not downloaded_files:
        raise RuntimeError(
            "yt-dlp did not produce a downloaded file."
        )

    source_file = downloaded_files[0]

    print(f"Downloaded source: {source_file}")

    convert_to_mp4(source_file)

    if not OUTPUT_FILE.exists():
        raise RuntimeError(
            f"Expected output file was not created: {OUTPUT_FILE}"
        )

    return OUTPUT_FILE


def convert_to_mp4(source_file: Path) -> None:
    print("Converting test segment to MP4...")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_file),
            "-c",
            "copy",
            str(OUTPUT_FILE),
        ],
        check=True,
    )


def inspect_video(video_path: Path) -> None:
    print("Inspecting video with FFprobe...")

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
        video_path = download_vod_segment()

        inspect_video(video_path)

        print()
        print("Twitch VOD download test successful.")
        print(f"Output: {video_path}")

        return 0

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
