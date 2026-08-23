import os
import sys

import requests


TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"


def get_twitch_access_token() -> str:
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id:
        raise RuntimeError("TWITCH_CLIENT_ID is not configured.")

    if not client_secret:
        raise RuntimeError("TWITCH_CLIENT_SECRET is not configured.")

    response = requests.post(
        TWITCH_TOKEN_URL,
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Twitch OAuth failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    access_token = data.get("access_token")

    if not access_token:
        raise RuntimeError(
            "Twitch OAuth response did not contain an access token."
        )

    return access_token


def validate_twitch_access_token(access_token: str) -> dict:
    response = requests.get(
        TWITCH_VALIDATE_URL,
        headers={"Authorization": f"OAuth {access_token}"},
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Twitch token validation failed "
            f"({response.status_code}): {response.text}"
        )

    return response.json()


def main() -> int:
    try:
        access_token = get_twitch_access_token()
        validation = validate_twitch_access_token(access_token)

        print("Twitch authentication successful.")
        print(f"Client ID: {validation.get('client_id')}")
        print(f"Scopes: {validation.get('scopes', [])}")
        print(f"Expires in: {validation.get('expires_in')} seconds")

        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
