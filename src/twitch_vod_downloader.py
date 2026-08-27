import os
import subprocess
import sys
from pathlib import Path

import requests
import yt_dlp

from vod_state import (
    is_vod_processed,
    mark_vod_as_processed,
)


TWITCH_API_URL = "https://api.twitch.tv/helix"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"

CHANNEL_NAME = "kuraimure57"

OUTPUT_DIR = Path("data/vods")


def get_access_token() -> str:
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Twitch credentials are not configured."
        )

    response = requests.post(
        TWITCH_TOKEN_URL,
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    access_token = data.get("access_token")

    if not access_token:
        raise RuntimeError(
            "Twitch OAuth response did not contain "
            "an access token."
        )

    return access_token


def get_latest_vod(access_token: str) -> dict:
    client_id = os.getenv("TWITCH_CLIENT_ID")

    user_response = requests.get(
        f"{TWITCH_API_URL}/users",
        headers={
            "Client-ID": client_id,
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "login": CHANNEL_NAME,
        },
        timeout=30,
    )

    user_response.raise_for_status()

    users = user_response.json().get(
        "data",
        [],
    )

    if not users:
        raise RuntimeError(
            f"Twitch channel '{CHANNEL_NAME}' "
            "was not found."
        )

    user_id = users[0]["id"]

    vod_response = requests.get(
        f"{TWITCH_API_URL}/videos",
        headers={
            "Client-ID": client_id,
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "user_id": user_id,
            "type": "archive",
            "first": 1,
        },
        timeout=30,
    )

    vod_response.raise_for_status()

    vods = vod_response.json().get(
        "data",
        [],
    )

    if not vods:
        raise RuntimeError(
            "No Twitch VODs were found."
        )

    return vods[0]


def download_vod(vod: dict) -> Path:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vod_url = vod["url"]
    vod_id = str(vod["id"])

    output_file = (
        OUTPUT_DIR / f"{vod_id}.mp4"
    )

    temp_template = (
        OUTPUT_DIR / f"{vod_id}_source.%(ext)s"
    )

    if output_file.exists():
        print(
            f"VOD file already exists: "
            f"{output_file}"
        )

        return output_file

    print(
        f"Selected VOD: {vod_id}"
    )

    print(
        f"Title: {vod['title']}"
    )

    print(
        f"Duration: {vod.get('duration', 'unknown')}"
    )

    print(
        f"URL: {vod_url}"
    )

    print()

    print(
        "Downloading complete VOD..."
    )

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(temp_template),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([vod_url])

    source_files = list(
        OUTPUT_DIR.glob(
            f"{vod_id}_source.*"
        )
    )

    if not source_files:
        raise RuntimeError(
            "yt-dlp did not produce a downloaded file."
        )

    source_file = source_files[0]

    print()
    print(
        f"Downloaded source: {source_file}"
    )

    print(
        "Converting complete VOD to MP4..."
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_file),
            "-c",
            "copy",
            str(output_file),
        ],
        check=True,
    )

    if not output_file.exists():
        raise RuntimeError(
            "Expected output file was not created: "
            f"{output_file}"
        )

    print()
    print(
        f"Complete VOD available at: "
        f"{output_file}"
    )

    return output_file


def inspect_video(video_path: Path) -> None:
    print(
        "Inspecting complete VOD with FFprobe..."
    )

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

    print()
    print(
        "FFprobe result:"
    )
    print(
        result.stdout
    )


def main() -> int:
    try:
        access_token = get_access_token()

        vod = get_latest_vod(
            access_token
        )

        vod_id = str(
            vod["id"]
        )

        force_download = (
            os.getenv(
                "FORCE_VOD_DOWNLOAD",
                "",
            ).lower()
            == "true"
        )

        print(
            f"Checking whether VOD {vod_id} "
            "has already been processed..."
        )

        if is_vod_processed(vod_id):
            print()

            if not force_download:
                print(
                    f"VOD {vod_id} has already "
                    "been processed."
                )

                print(
                    "No download is necessary."
                )

                return 0

            print(
                f"VOD {vod_id} has already "
                "been processed."
            )

            print(
                "FORCE_VOD_DOWNLOAD=true"
            )

            print(
                "Forcing complete VOD download "
                "without changing VOD state."
            )

            print()

        else:
            print()
            print(
                f"VOD {vod_id} has NOT been processed."
            )

            print(
                "Proceeding with complete VOD download..."
            )

            print()

        video_path = download_vod(
            vod
        )

        inspect_video(
            video_path
        )

        print()

        if force_download:
            print(
                "Forced complete VOD download completed."
            )

            print(
                "Processed VOD state was NOT modified."
            )

        else:
            mark_vod_as_processed(
                vod_id
            )

            print(
                "VOD state persistence successful."
            )

        print()
        print(
            f"VOD ID: {vod_id}"
        )

        print(
            f"Output: {video_path}"
        )

        return 0

    except requests.HTTPError as exc:
        print(
            f"Twitch API error: {exc}",
            file=sys.stderr,
        )

        if exc.response is not None:
            print(
                f"Response: {exc.response.text}",
                file=sys.stderr,
            )

        return 1

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
