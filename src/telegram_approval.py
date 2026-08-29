import json
import os
import sys
import time
from pathlib import Path

import requests


TELEGRAM_API_URL = "https://api.telegram.org"

MANIFEST_DIR = Path("data/clips")

APPROVED_DIR = Path("data/telegram_approved")


POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300


def get_config() -> tuple[str, str]:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured."
        )

    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID is not configured."
        )

    return bot_token, chat_id


def find_manifest() -> Path:
    if not MANIFEST_DIR.exists():
        raise FileNotFoundError(
            f"Clips directory not found: {MANIFEST_DIR}"
        )

    manifests = sorted(
        MANIFEST_DIR.glob("*/clips_manifest.json")
    )

    if not manifests:
        raise FileNotFoundError(
            "No clips manifest was found."
        )

    if len(manifests) > 1:
        raise RuntimeError(
            "Multiple clips manifests were found. "
            "Expected exactly one manifest."
        )

    return manifests[0]


def load_manifest(
    manifest_file: Path,
) -> dict:
    with manifest_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise RuntimeError(
            "Clips manifest must contain a JSON object."
        )

    clips = data.get("clips", [])

    if not isinstance(clips, list):
        raise RuntimeError(
            "Manifest 'clips' must be a list."
        )

    return data


def telegram_request(
    bot_token: str,
    method: str,
    payload: dict | None = None,
    files: dict | None = None,
) -> dict:
    url = (
        f"{TELEGRAM_API_URL}/bot"
        f"{bot_token}/{method}"
    )

    response = requests.post(
        url,
        data=payload,
        files=files,
        timeout=120,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    return result


def verify_bot(
    bot_token: str,
) -> None:
    result = telegram_request(
        bot_token,
        "getMe",
    )

    bot = result.get("result", {})

    print(
        "Telegram bot verified:"
    )

    print(
        f"  Username: "
        f"@{bot.get('username', 'unknown')}"
    )

    print(
        f"  Name: "
        f"{bot.get('first_name', 'unknown')}"
    )


def build_caption(
    vod_id: str,
    clip: dict,
) -> str:
    return (
        f"🎬 CLIP DE TWITCH\n\n"
        f"VOD: {vod_id}\n"
        f"Clip #{clip['index']}\n\n"
        f"📌 {clip['title']}\n"
        f"⭐ Score: {clip['score']}\n"
        f"📂 Categoría: {clip['category']}\n"
        f"⏱️ Duración: {clip['duration']}s\n\n"
        f"{clip['reason']}\n\n"
        f"¿Este clip sirve?"
    )


def send_clip(
    bot_token: str,
    chat_id: str,
    vod_id: str,
    clip: dict,
) -> int:
    clip_file = Path(
        clip["file"]
    )

    if not clip_file.exists():
        raise FileNotFoundError(
            f"Clip file not found: {clip_file}"
        )

    caption = build_caption(
        vod_id,
        clip,
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ APROBAR",
                    "callback_data": (
                        f"approve:{vod_id}:"
                        f"{clip['index']}"
                    ),
                },
                {
                    "text": "❌ RECHAZAR",
                    "callback_data": (
                        f"reject:{vod_id}:"
                        f"{clip['index']}"
                    ),
                },
            ]
        ]
    }

    print()
    print(
        f"Sending clip #{clip['index']} "
        f"to Telegram..."
    )

    print(
        f"  File: {clip_file}"
    )

    print(
        f"  Title: {clip['title']}"
    )

    with clip_file.open(
        "rb"
    ) as video_file:
        result = telegram_request(
            bot_token,
            "sendVideo",
            payload={
                "chat_id": chat_id,
                "caption": caption,
                "supports_streaming": "true",
                "reply_markup": json.dumps(
                    keyboard,
                    ensure_ascii=False,
                ),
            },
            files={
                "video": (
                    clip_file.name,
                    video_file,
                    "video/mp4",
                )
            },
        )

    message = result.get(
        "result",
        {},
    )

    message_id = message.get(
        "message_id"
    )

    if not message_id:
        raise RuntimeError(
            "Telegram did not return a message_id."
        )

    print(
        f"  Telegram message ID: "
        f"{message_id}"
    )

    return int(message_id)


def send_all_clips(
    bot_token: str,
    chat_id: str,
    manifest: dict,
) -> dict:
    vod_id = str(
        manifest["vod_id"]
    )

    clips = manifest.get(
        "clips",
        [],
    )

    sent_clips = []

    for clip in clips:
        message_id = send_clip(
            bot_token,
            chat_id,
            vod_id,
            clip,
        )

        sent_clips.append(
            {
                "index": clip["index"],
                "message_id": message_id,
                "status": "pending",
            }
        )

    return {
        "vod_id": vod_id,
        "sent_clips": sent_clips,
    }


def save_pending_state(
    state: dict,
) -> Path:
    APPROVED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vod_id = str(
        state["vod_id"]
    )

    output_file = (
        APPROVED_DIR
        / f"{vod_id}_telegram_state.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_file


def answer_callback(
    bot_token: str,
    callback_id: str,
    text: str,
) -> None:
    telegram_request(
        bot_token,
        "answerCallbackQuery",
        payload={
            "callback_query_id": callback_id,
            "text": text,
        },
    )


def update_message(
    bot_token: str,
    chat_id: str,
    message_id: int,
    text: str,
) -> None:
    telegram_request(
        bot_token,
        "editMessageCaption",
        payload={
            "chat_id": chat_id,
            "message_id": str(message_id),
            "caption": text,
        },
    )


def poll_for_approvals(
    bot_token: str,
    chat_id: str,
    state: dict,
) -> dict:
    print()
    print(
        "Waiting for Telegram approvals..."
    )

    print(
        f"Polling timeout: "
        f"{POLL_TIMEOUT_SECONDS}s"
    )

    started_at = time.time()

    update_id = None

    pending = {
        int(item["index"]): item
        for item in state["sent_clips"]
    }

    approved = []
    rejected = []

    while (
        time.time() - started_at
        < POLL_TIMEOUT_SECONDS
    ):
        params = {
            "timeout": 10,
            "allowed_updates": json.dumps(
                ["callback_query"]
            ),
        }

        if update_id is not None:
            params["offset"] = update_id

        url = (
            f"{TELEGRAM_API_URL}/bot"
            f"{bot_token}/getUpdates"
        )

        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        response.raise_for_status()

        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(
                f"Telegram getUpdates error: "
                f"{result}"
            )

        updates = result.get(
            "result",
            [],
        )

        for update in updates:
            update_id = (
                update["update_id"] + 1
            )

            callback = update.get(
                "callback_query"
            )

            if not callback:
                continue

            callback_data = callback.get(
                "data",
                "",
            )

            callback_message = callback.get(
                "message",
                {},
            )

            callback_chat = callback_message.get(
                "chat",
                {}
            )

            callback_chat_id = str(
                callback_chat.get(
                    "id",
                    ""
                )
            )

            if callback_chat_id != str(
                chat_id
            ):
                continue

            parts = callback_data.split(
                ":"
            )

            if len(parts) != 3:
                continue

            action = parts[0]
            vod_id = parts[1]

            try:
                clip_index = int(
                    parts[2]
                )
            except ValueError:
                continue

            if (
                action not in (
                    "approve",
                    "reject",
                )
            ):
                continue

            if clip_index not in pending:
                continue

            item = pending.pop(
                clip_index
            )

            item["vod_id"] = vod_id

            message_id = int(
                item["message_id"]
            )

            if action == "approve":
                item["status"] = "approved"
                approved.append(item)

                answer_callback(
                    bot_token,
                    callback["id"],
                    "✅ Clip aprobado.",
                )

                update_message(
                    bot_token,
                    chat_id,
                    message_id,
                    "🎬 CLIP DE TWITCH\n\n"
                    "✅ APROBADO\n\n"
                    "Este clip pasará al "
                    "siguiente paso.",
                )

                print(
                    f"Clip #{clip_index} "
                    "APPROVED"
                )

            else:
                item["status"] = "rejected"
                rejected.append(item)

                answer_callback(
                    bot_token,
                    callback["id"],
                    "❌ Clip rechazado.",
                )

                update_message(
                    bot_token,
                    chat_id,
                    message_id,
                    "🎬 CLIP DE TWITCH\n\n"
                    "❌ RECHAZADO",
                )

                print(
                    f"Clip #{clip_index} "
                    "REJECTED"
                )

        if not pending:
            print()
            print(
                "All clips have been reviewed."
            )
            break

    state["approved"] = approved
    state["rejected"] = rejected
    state["pending"] = list(
        pending.values()
    )

    state["completed"] = (
        len(state["pending"]) == 0
    )

    return state


def save_approval_result(
    state: dict,
) -> Path:
    APPROVED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vod_id = str(
        state["vod_id"]
    )

    output_file = (
        APPROVED_DIR
        / f"{vod_id}_approved.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_file


def main() -> int:
    try:
        print(
            "========================================="
        )
        print(
            "Telegram Clip Approval"
        )
        print(
            "========================================="
        )

        bot_token, chat_id = get_config()

        manifest_file = find_manifest()

        manifest = load_manifest(
            manifest_file
        )

        vod_id = str(
            manifest["vod_id"]
        )

        clips = manifest.get(
            "clips",
            [],
        )

        print(
            f"VOD ID: {vod_id}"
        )

        print(
            f"Manifest: {manifest_file}"
        )

        print(
            f"Clips to review: "
            f"{len(clips)}"
        )

        if not clips:
            print()
            print(
                "No clips to send."
            )

            return 0

        verify_bot(
            bot_token
        )

        state = send_all_clips(
            bot_token,
            chat_id,
            manifest,
        )

        pending_file = save_pending_state(
            state
        )

        print()
        print(
            f"Pending state saved: "
            f"{pending_file}"
        )

        final_state = poll_for_approvals(
            bot_token,
            chat_id,
            state,
        )

        result_file = save_approval_result(
            final_state
        )

        print()
        print(
            "========================================="
        )

        print(
            "Telegram approval completed."
        )

        print(
            f"Approved: "
            f"{len(final_state['approved'])}"
        )

        print(
            f"Rejected: "
            f"{len(final_state['rejected'])}"
        )

        print(
            f"Pending: "
            f"{len(final_state['pending'])}"
        )

        print(
            f"Output: {result_file}"
        )

        print(
            "========================================="
        )

        return 0

    except requests.RequestException as exc:
        print(
            f"Telegram HTTP error: {exc}",
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
    raise SystemExit(
        main()
    )
