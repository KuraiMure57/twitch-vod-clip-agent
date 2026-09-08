import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests


TELEGRAM_API_URL = "https://api.telegram.org"

MANIFEST_DIR = Path("data/clips")
APPROVED_DIR = Path("data/telegram_approved")
TELEGRAM_TEMP_DIR = Path("data/telegram_temp")

TELEGRAM_LONG_POLL_SECONDS = 30

TELEGRAM_MAX_VIDEO_SIZE_MB = 45
TELEGRAM_MAX_VIDEO_SIZE_BYTES = (
    TELEGRAM_MAX_VIDEO_SIZE_MB * 1024 * 1024
)

TELEGRAM_UPLOAD_RETRY_INITIAL_SECONDS = 5
TELEGRAM_UPLOAD_RETRY_MAX_SECONDS = 60


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


def find_all_manifests() -> list[Path]:
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

    return manifests


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

    bot = result.get(
        "result",
        {},
    )

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


def is_reward_code_clip(
    clip: dict,
) -> bool:
    value = clip.get(
        "is_reward_code",
        False,
    )

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "si",
            "sí",
        }

    return bool(value)


def get_reward_code(
    clip: dict,
) -> str | None:
    possible_fields = (
        "reward_code",
        "code",
        "redeem_code",
        "promo_code",
    )

    for field in possible_fields:
        value = clip.get(field)

        if value is None:
            continue

        if not isinstance(value, str):
            value = str(value)

        value = value.strip()

        if value:
            return value

    return None


def build_reward_code_caption(
    vod_id: str,
    clip: dict,
) -> str:
    reward_code = get_reward_code(
        clip
    )

    title = clip.get(
        "title",
        "Código de recompensa",
    )

    reason = clip.get(
        "reason",
        "",
    )

    lines = [
        "🎁 CÓDIGO DE RECOMPENSA",
        "",
        f"📌 {title}",
        "",
    ]

    if reward_code:
        lines.extend(
            [
                "🎟️ Código:",
                f"`{reward_code}`",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "🎟️ Código de recompensa detectado en este clip.",
                "",
            ]
        )

    lines.extend(
        [
            "⚠️ Canjéalo cuanto antes por si caduca.",
            "",
            f"VOD: {vod_id}",
            f"Clip #{clip.get('index', '?')}",
            f"⏱️ Duración: {clip.get('duration', '?')}s",
        ]
    )

    if reason:
        lines.extend(
            [
                "",
                reason,
            ]
        )

    lines.extend(
        [
            "",
            "¿Este clip sirve?",
        ]
    )

    return "\n".join(lines)


def build_normal_caption(
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


def build_caption(
    vod_id: str,
    clip: dict,
) -> str:
    if is_reward_code_clip(clip):
        return build_reward_code_caption(
            vod_id,
            clip,
        )

    return build_normal_caption(
        vod_id,
        clip,
    )


def get_video_duration(
    video_file: Path,
) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_file),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    duration_text = result.stdout.strip()

    if not duration_text:
        raise RuntimeError(
            f"Could not determine video duration: "
            f"{video_file}"
        )

    duration = float(duration_text)

    if duration <= 0:
        raise RuntimeError(
            f"Invalid video duration: "
            f"{video_file}"
        )

    return duration


def run_ffmpeg_compression(
    input_file: Path,
    output_file: Path,
    video_bitrate_kbps: int,
    scale_filter: str,
) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_file),
            "-vf",
            scale_filter,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-b:v",
            f"{video_bitrate_kbps}k",
            "-maxrate",
            f"{video_bitrate_kbps}k",
            "-bufsize",
            f"{video_bitrate_kbps * 2}k",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(output_file),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def compress_clip_for_telegram(
    clip_file: Path,
) -> Path:
    TELEGRAM_TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        TELEGRAM_TEMP_DIR
        / f"{clip_file.stem}_telegram.mp4"
    )

    duration = get_video_duration(
        clip_file
    )

    target_size_bytes = (
        42 * 1024 * 1024
    )

    target_size_bits = (
        target_size_bytes * 8
    )

    audio_bitrate_kbps = 96

    total_bitrate_kbps = (
        target_size_bits
        / duration
        / 1000
    )

    video_bitrate_kbps = max(
        400,
        int(
            total_bitrate_kbps
            - audio_bitrate_kbps
        ),
    )

    if video_bitrate_kbps < 1200:
        scale_filter = (
            "scale=w=1280:h=720:"
            "force_original_aspect_ratio=decrease,"
            "pad=ceil(iw/2)*2:ceil(ih/2)*2"
        )
    else:
        scale_filter = (
            "scale=ceil(iw/2)*2:"
            "ceil(ih/2)*2"
        )

    run_ffmpeg_compression(
        clip_file,
        output_file,
        video_bitrate_kbps,
        scale_filter,
    )

    if not output_file.exists():
        raise RuntimeError(
            "Telegram compression did not produce "
            f"an output file: {output_file}"
        )

    output_size = output_file.stat().st_size

    if output_size <= TELEGRAM_MAX_VIDEO_SIZE_BYTES:
        return output_file

    second_output = (
        TELEGRAM_TEMP_DIR
        / f"{clip_file.stem}_telegram_small.mp4"
    )

    second_target_size_bytes = (
        38 * 1024 * 1024
    )

    second_target_bits = (
        second_target_size_bytes * 8
    )

    second_total_bitrate_kbps = (
        second_target_bits
        / duration
        / 1000
    )

    second_video_bitrate_kbps = max(
        350,
        int(
            second_total_bitrate_kbps
            - audio_bitrate_kbps
        ),
    )

    second_scale_filter = (
        "scale=w=1280:h=720:"
        "force_original_aspect_ratio=decrease,"
        "pad=ceil(iw/2)*2:ceil(ih/2)*2"
    )

    run_ffmpeg_compression(
        clip_file,
        second_output,
        second_video_bitrate_kbps,
        second_scale_filter,
    )

    if not second_output.exists():
        raise RuntimeError(
            "Second Telegram compression failed."
        )

    second_size = second_output.stat().st_size

    if second_size > TELEGRAM_MAX_VIDEO_SIZE_BYTES:
        raise RuntimeError(
            "Unable to compress clip below "
            f"{TELEGRAM_MAX_VIDEO_SIZE_MB} MB: "
            f"{clip_file}"
        )

    return second_output


def prepare_clip_for_telegram(
    clip_file: Path,
) -> Path:
    if (
        clip_file.stat().st_size
        <= TELEGRAM_MAX_VIDEO_SIZE_BYTES
    ):
        return clip_file

    return compress_clip_for_telegram(
        clip_file
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

    telegram_file = prepare_clip_for_telegram(
        clip_file
    )

    retry_delay = (
        TELEGRAM_UPLOAD_RETRY_INITIAL_SECONDS
    )

    attempt = 0

    while True:
        attempt += 1

        print(
            f"Telegram upload attempt #{attempt}"
        )

        try:
            with telegram_file.open(
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
                            telegram_file.name,
                            video_file,
                            "video/mp4",
                        )
                    },
                )

            message_id = (
                result
                .get("result", {})
                .get("message_id")
            )

            if not message_id:
                raise RuntimeError(
                    "Telegram did not return a message_id."
                )

            return int(message_id)

        except (
            requests.Timeout,
            requests.ConnectionError,
            TimeoutError,
            ConnectionResetError,
            ConnectionAbortedError,
        ) as exc:
            print(
                "Telegram upload connection error: "
                f"{exc}"
            )

            print(
                f"Retrying in {retry_delay} seconds..."
            )

            time.sleep(
                retry_delay
            )

            retry_delay = min(
                retry_delay * 2,
                TELEGRAM_UPLOAD_RETRY_MAX_SECONDS,
            )


def send_status_message(
    bot_token: str,
    chat_id: str,
    vod_id: str,
    clips: list[dict],
) -> None:
    count = len(clips)

    telegram_request(
        bot_token,
        "sendMessage",
        payload={
            "chat_id": chat_id,
            "text": (
                "📤 Iniciando envío de clips\n\n"
                f"Se van a enviar {count} "
                "vídeos para revisión"
            ),
        },
    )


def get_updates(
    bot_token: str,
    offset: int | None = None,
) -> list[dict]:
    payload = {
        "timeout": TELEGRAM_LONG_POLL_SECONDS,
        "allowed_updates": json.dumps(
            ["callback_query"]
        ),
    }

    if offset is not None:
        payload["offset"] = offset

    result = telegram_request(
        bot_token,
        "getUpdates",
        payload=payload,
    )

    return result.get(
        "result",
        [],
    )


def answer_callback_query(
    bot_token: str,
    callback_query_id: str,
) -> None:
    telegram_request(
        bot_token,
        "answerCallbackQuery",
        payload={
            "callback_query_id": callback_query_id,
        },
    )


def copy_approved_clip(
    vod_id: str,
    clip_index: int,
    clip: dict,
) -> Path:
    source_file = Path(
        clip["file"]
    )

    if not source_file.exists():
        raise FileNotFoundError(
            f"Approved clip source file not found: "
            f"{source_file}"
        )

    APPROVED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        APPROVED_DIR
        / f"{vod_id}_clip_{clip_index}.mp4"
    )

    subprocess.run(
        [
            "cp",
            str(source_file),
            str(output_file),
        ],
        check=True,
    )

    return output_file


def edit_telegram_message(
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
            "message_id": message_id,
            "caption": text,
        },
    )

    try:
        telegram_request(
            bot_token,
            "editMessageReplyMarkup",
            payload={
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": json.dumps(
                    {
                        "inline_keyboard": []
                    }
                ),
            },
        )
    except Exception as exc:
        print(
            "Could not remove Telegram keyboard: "
            f"{exc}"
        )


def build_reviewed_caption(
    vod_id: str,
    clip: dict,
    status: str,
) -> str:
    base_caption = build_caption(
        vod_id,
        clip,
    )

    if status == "approved":
        return (
            "✅ APROBADO\n\n"
            + base_caption
        )

    return (
        "❌ RECHAZADO\n\n"
        + base_caption
    )


def write_approval_files(
    vod_id: str,
    states: dict[int, dict],
) -> None:
    APPROVED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    approved_clips = []
    rejected_clips = []

    for state in states.values():
        clip = state["clip"]
        status = state["status"]

        if status == "approved":
            approved_clips.append(
                {
                    **clip,
                    "file": str(
                        state["approved_file"]
                    ),
                    "status": "approved",
                }
            )

        elif status == "rejected":
            rejected_clips.append(
                {
                    **clip,
                    "status": "rejected",
                }
            )

    output = {
        "vod_id": vod_id,
        "approved_clips": approved_clips,
        "rejected_clips": rejected_clips,
        "approved_count": len(
            approved_clips
        ),
        "rejected_count": len(
            rejected_clips
        ),
        "total_clips": len(states),
    }

    output_file = (
        APPROVED_DIR
        / f"{vod_id}_approved.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Approval result written to: "
        f"{output_file}"
    )


def wait_for_approvals(
    bot_token: str,
    chat_id: str,
    vod_id: str,
    states: dict[int, dict],
) -> None:
    pending = {
        index
        for index, state in states.items()
        if state["status"] == "pending"
    }

    if not pending:
        write_approval_files(
            vod_id,
            states,
        )
        return

    print()
    print(
        "Waiting for Telegram approvals..."
    )
    print(
        "No approval timeout is configured."
    )
    print(
        "The workflow will continue only after "
        "every clip is reviewed."
    )

    offset = None

    while pending:
        print(
            "Waiting for Telegram updates... "
            f"Pending clips: {len(pending)}"
        )

        try:
            updates = get_updates(
                bot_token,
                offset,
            )

            for update in updates:
                update_id = update.get(
                    "update_id"
                )

                if update_id is not None:
                    offset = update_id + 1

                callback_query = update.get(
                    "callback_query"
                )

                if not callback_query:
                    continue

                message = callback_query.get(
                    "message",
                    {},
                )

                callback_chat_id = str(
                    message
                    .get("chat", {})
                    .get("id", "")
                )

                if callback_chat_id != str(
                    chat_id
                ):
                    continue

                data = callback_query.get(
                    "data",
                    "",
                )

                parts = data.split(":")

                if len(parts) != 3:
                    continue

                action = parts[0]
                callback_vod_id = parts[1]

                if callback_vod_id != vod_id:
                    continue

                try:
                    clip_index = int(parts[2])
                except ValueError:
                    continue

                if clip_index not in pending:
                    continue

                if action not in {
                    "approve",
                    "reject",
                }:
                    continue

                callback_id = callback_query.get(
                    "id"
                )

                if callback_id:
                    answer_callback_query(
                        bot_token,
                        callback_id,
                    )

                state = states[
                    clip_index
                ]

                clip = state["clip"]

                if action == "approve":
                    approved_file = (
                        copy_approved_clip(
                            vod_id,
                            clip_index,
                            clip,
                        )
                    )

                    state["status"] = "approved"
                    state["approved_file"] = (
                        approved_file
                    )

                    reviewed_caption = (
                        build_reviewed_caption(
                            vod_id,
                            clip,
                            "approved",
                        )
                    )

                    print(
                        f"✅ Clip #{clip_index} approved."
                    )

                else:
                    state["status"] = "rejected"
                    state["approved_file"] = None

                    reviewed_caption = (
                        build_reviewed_caption(
                            vod_id,
                            clip,
                            "rejected",
                        )
                    )

                    print(
                        f"❌ Clip #{clip_index} rejected."
                    )

                try:
                    edit_telegram_message(
                        bot_token,
                        chat_id,
                        state["message_id"],
                        reviewed_caption,
                    )
                except Exception as exc:
                    print(
                        "Could not update Telegram "
                        f"message: {exc}"
                    )

                pending.remove(
                    clip_index
                )

                print(
                    "Remaining pending clips: "
                    f"{len(pending)}"
                )

            if pending:
                continue

        except (
            requests.Timeout,
            requests.ConnectionError,
            TimeoutError,
            ConnectionResetError,
            ConnectionAbortedError,
        ) as exc:
            print(
                "Telegram listener connection error: "
                f"{exc}"
            )

            print(
                "Retrying..."
            )

            time.sleep(5)

        except Exception as exc:
            print(
                "Telegram approval listener error: "
                f"{exc}"
            )

            time.sleep(5)

    write_approval_files(
        vod_id,
        states,
    )

    print()
    print(
        "All Telegram clips have been reviewed."
    )


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

    if not isinstance(clips, list):
        raise RuntimeError(
            "Manifest 'clips' must be a list."
        )

    if not clips:
        telegram_request(
            bot_token,
            "sendMessage",
            payload={
                "chat_id": chat_id,
                "text": (
                    "🔎 Análisis completado\n\n"
                    "No se han generado clips válidos "
                    "para revisar en Telegram."
                ),
            },
        )

        return {
            "vod_id": vod_id,
            "sent": [],
            "sent_count": 0,
            "failed": [],
            "failed_count": 0,
        }

    send_status_message(
        bot_token,
        chat_id,
        vod_id,
        clips,
    )

    sent = []
    failed = []
    states = {}

    for clip in clips:
        if not isinstance(clip, dict):
            continue

        try:
            message_id = send_clip(
                bot_token,
                chat_id,
                vod_id,
                clip,
            )

            clip_index = int(
                clip["index"]
            )

            states[clip_index] = {
                "clip": clip,
                "message_id": message_id,
                "status": "pending",
                "approved_file": None,
            }

            sent.append(
                {
                    "index": clip_index,
                    "message_id": message_id,
                }
            )

        except Exception as exc:
            print(
                f"Failed to send clip "
                f"#{clip.get('index', '?')}: "
                f"{exc}"
            )

            failed.append(
                {
                    "index": clip.get("index"),
                    "error": str(exc),
                }
            )

    if failed:
        print(
            f"{len(failed)} clips could not be sent."
        )

    if not states:
        raise RuntimeError(
            "No clips could be sent to Telegram."
        )

    wait_for_approvals(
        bot_token,
        chat_id,
        vod_id,
        states,
    )

    result = {
        "vod_id": vod_id,
        "sent": sent,
        "sent_count": len(sent),
        "failed": failed,
        "failed_count": len(failed),
    }

    result_file = (
        APPROVED_DIR
        / f"{vod_id}_telegram_send_result.json"
    )

    APPROVED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with result_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return result


def main() -> int:
    try:
        bot_token, chat_id = get_config()

        verify_bot(
            bot_token
        )

        manifests = find_all_manifests()

        total_sent = 0
        total_failed = 0

        for manifest_file in manifests:
            print()
            print(
                "Processing manifest:"
            )

            print(
                f"  {manifest_file}"
            )

            manifest = load_manifest(
                manifest_file
            )

            result = send_all_clips(
                bot_token,
                chat_id,
                manifest,
            )

            total_sent += result[
                "sent_count"
            ]

            total_failed += result[
                "failed_count"
            ]

        print()
        print(
            "All manifests processed."
        )

        print(
            f"  Total sent: {total_sent}"
        )

        print(
            f"  Total failed: {total_failed}"
        )

        return 0

    except KeyboardInterrupt:
        print()
        print(
            "Telegram approval stopped."
        )

        return 130

    except Exception as exc:
        print()
        print(
            f"Telegram approval failed: {exc}"
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )
