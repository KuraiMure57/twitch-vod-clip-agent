import os
import sys

import requests


TWITCH_API_URL = "https://api.twitch.tv/helix"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"

CHANNEL_NAME = "kuraimure57"


def get_access_token() -> str:
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError("Twitch credentials are not configured.")

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
            "Twitch OAuth response did not contain an access token."
        )

    return access_token


def get_user(access_token: str) -> dict:
    client_id = os.getenv("TWITCH_CLIENT_ID")

    response = requests.get(
        f"{TWITCH_API_URL}/users",
        headers={
            "Client-ID": client_id,
            "Authorization": f"Bearer {access_token}",
        },
        params={"login": CHANNEL_NAME},
        timeout=30,
    )

    response.raise_for_status()

    data = response.json().get("data", [])

    if not data:
        raise RuntimeError(
            f"Twitch channel '{CHANNEL_NAME}' was not found."
        )

    return data[0]


def get_latest_vod(access_token: str, user_id: str) -> dict | None:
    client_id = os.getenv("TWITCH_CLIENT_ID")

    response = requests.get(
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

    response.raise_for_status()

    vods = response.json().get("data", [])

    if not vods:
        return None

    return vods[0]


def main() -> int:
    try:
        access_token = get_access_token()

        user = get_user(access_token)

        print("Twitch channel found.")
        print(f"Channel: {user['display_name']}")
        print(f"User ID: {user['id']}")
        print(f"Login: {user['login']}")
        print()

        vod = get_latest_vod(
            access_token,
            user["id"],
        )

        if vod is None:
            print("No VODs were found.")
            return 0

        print("Latest VOD:")
        print(f"  ID: {vod['id']}")
        print(f"  Title: {vod['title']}")
        print(f"  Created: {vod['created_at']}")
        print(f"  Duration: {vod['duration']}")
        print(f"  Views: {vod['view_count']}")
        print(f"  URL: {vod['url']}")

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
