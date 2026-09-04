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

# Dejamos margen respecto al límite de Telegram.
TELEGRAM_MAX_VIDEO_SIZE_MB = 45
TELEGRAM_MAX_VIDEO_SIZE_BYTES = (
    TELEGRAM_MAX_VIDEO_SIZE_MB * 1024 * 1024
)

# Reintentos de subida ante errores temporales de red.
# No existe límite de intentos.
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


# CAMBIO AQUÍ: Ahora devuelve una lista con todos los manifiestos ordenados
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

    # Objetivo de aproximadamente 42 MB para dejar
    # margen de seguridad al límite de Telegram.
    target_size_bytes = (
        42 * 1024 * 1024
    )

    target_size_bits = (
        target_size_bytes * 8
    )

    # Reservamos bitrate para el audio.
    audio_bitrate_kbps = 96

    total_bitrate_kbps = (
        target_size_bits
        / duration
        / 1000
    )

    video_bitrate_kbps = (
        total_bitrate_kbps
        - audio_bitrate_kbps
    )

    # Evitamos bitrates absurdamente bajos.
    video_bitrate_kbps = max(
        400,
        int(video_bitrate_kbps),
    )

    print()
    print(
        "Clip exceeds Telegram upload limit."
    )

    print(
        f"  Original: "
        f"{clip_file.stat().st_size / 1024 / 1024:.2f} MB"
    )

    print(
        f"  Duration: "
        f"{duration:.2f}s"
    )

    print(
        f"  Target video bitrate: "
        f"{video_bitrate_kbps} kbps"
    )

    print(
        f"  Output: "
        f"{output_file}"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(clip_file),
            "-vf",
            "scale=w=1280:h=720:force_original_aspect_ratio=decrease,"
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
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
            f"{audio_bitrate_kbps}k",
            "-movflags",
            "+faststart",
            str(output_file),
        ],
        check=True,
    )

    if not output_file.exists():
        raise RuntimeError(
            "Telegram compression did not produce "
            f"an output file: {output_file}"
        )

    output_size = output_file.stat().st_size

    print(
        f"  Compressed size: "
        f"{output_size / 1024 / 1024:.2f} MB"
    )

    if output_size > TELEGRAM_MAX_VIDEO_SIZE_BYTES:
        print(
            "  Compressed file is still too large."
        )

        second_output = (
            TELEGRAM_TEMP_DIR
            / f"{clip_file.stem}_telegram_small.mp4"
        )

        second_target_size_bytes = (
            35 * 1024 * 1024
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
            300,
            int(
                second_total_bitrate_kbps
                - audio_bitrate_kbps
            ),
        )

        print(
            f"  Second video bitrate: "
            f"{second_video_bitrate_kbps} kbps"
        )

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(clip_file),
                "-vf",
                "scale=w=960:h=540:force_original_aspect_ratio=decrease,"
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-b:v",
                f"{second_video_bitrate_kbps}k",
                "-maxrate",
                f"{second_video_bitrate_kbps}k",
                "-bufsize",
                f"{second_video_bitrate_kbps * 2}k",
                "-c:a",
                "aac",
                "-b:a",
                f"{audio_bitrate_kbps}k",
                "-movflags",
                "+faststart",
                str(second_output),
            ],
            check=True,
        )

        if not second_output.exists():
            raise RuntimeError(
                "Second Telegram compression failed."
            )

        second_size = (
            second_output.stat().st_size
        )

        print(
            f"  Second compressed size: "
            f"{second_size / 1024 / 1024:.2f} MB"
        )

        if second_size > TELEGRAM_MAX_VIDEO_SIZE_BYTES:
            raise RuntimeError(
                "Unable to compress clip below "
                f"{TELEGRAM_MAX_VIDEO_SIZE_MB} MB: "
                f"{clip_file}"
            )

        return second_output

    return output_file


def prepare_clip_for_telegram(
    clip_file: Path,
) -> Path:
    file_size = clip_file.stat().st_size

    file_size_mb = (
        file_size / 1024 / 1024
    )

    print(
        f"  File size: "
        f"{file_size_mb:.2f} MB"
    )

    if file_size <= TELEGRAM_MAX_VIDEO_SIZE_BYTES:
        print(
            "  Size is within Telegram limit."
        )

        return clip_file

    print(
        f"  Size exceeds "
        f"{TELEGRAM_MAX_VIDEO_SIZE_MB} MB."
    )

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

    telegram_file = prepare_clip_for_telegram(
        clip_file
    )

    if telegram_file != clip_file:
        print(
            f"  Telegram upload file: "
            f"{telegram_file}"
        )

    retry_delay = (
        TELEGRAM_UPLOAD_RETRY_INITIAL_SECONDS
    )

    attempt = 0

    while True:
        attempt += 1

        print()
        print(
            f"  Telegram upload attempt #{attempt}"
        )

        try:
            # El archivo debe abrirse de nuevo en cada intento.
            # Si una subida se corta, no reutilizamos el
            # file object anterior.
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

        except (
            requests.Timeout,
            requests.ConnectionError,
            TimeoutError,
            ConnectionResetError,
            ConnectionAbortedError,
        ) as exc:
            print()
            print(
                "  Telegram upload connection error."
            )

            print(
                f"  Error: {exc}"
            )

            print(
                f"  Retrying in "
                f"{retry_delay} seconds..."
            )

            time.sleep(
                retry_delay
            )

            retry_delay = min(
                retry_delay * 2,
                TELEGRAM_UPLOAD_RETRY_MAX_SECONDS,
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

    # =====================================================
    # AVISO INICIAL ANTES DE ENVIAR EL PRIMER CLIP
    # =====================================================

    print()
    print("📤 Iniciando envío de clips")
    print(
        f"Se van a enviar {len(clips)} vídeos para revisión."
    )

    telegram_request(
        bot_token,
        "sendMessage",
        payload={
            "chat_id": chat_id,
            "text": (
                "📤 Iniciando envío de clips\n"
                f"Se van a enviar {len(clips)} vídeos para revisión"
            ),
        },
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


# NUEVA FUNCIÓN COMODÍN: Asegura la creación del JSON final que GitHub Actions necesita validar
def save_final_approved_json(vod_id: str, approved_clips: list) -> Path:
    APPROVED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_file = APPROVED_DIR / f"{vod_id}_approved.json"
    
    # Estructura limpia requerida por los pasos subsiguientes
    final_data = {
        "vod_id": vod_id,
        "approved_clips": approved_clips,
        "timestamp": time.time()
    }
    
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(final_data, file, indent=2, ensure_ascii=False)
        
    print(f"📁 Archivo final de éxitos generado con éxito: {output_file}")
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
        "No approval timeout is configured."
    )

    print(
        "The workflow will continue only "
        "after every clip is reviewed."
    )

    pending = {
        int(item["index"]): item
        for item in state["sent_clips"]
    }

    approved = []
    rejected = []

    update_id = None

    while pending:
        params = {
            "timeout": TELEGRAM_LONG_POLL_SECONDS,
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

        print(
            f"Waiting for Telegram updates... "
            f"Pending clips: {len(pending)}"
        )

        try:
            response = requests.get(
                url,
                params=params,
                timeout=TELEGRAM_LONG_POLL_SECONDS + 10,
            )

            response.raise_for_status()

            result = response.json()

        except requests.RequestException as exc:
            print(
                "Telegram polling error. "
                "Retrying instead of stopping the workflow:"
            )
            print(
                f"  {exc}"
            )
            continue

        except ValueError as exc:
            print(
                "Telegram returned invalid JSON. "
                "Retrying instead of stopping the workflow:"
            )
            print(
                f"  {exc}"
            )
            continue

        if not result.get("ok"):
            print(
                "Telegram getUpdates returned an error. "
                "Retrying instead of stopping the workflow:"
            )
            print(
                f"  {result}"
            )
            continue

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
                {},
            )

            callback_chat_id = str(
                callback_chat.get(
                    "id",
                    "",
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

            if action not in (
                "approve",
                "reject",
            ):
                continue

            if clip_index not in pending:
                print(
                    f"Ignoring callback for "
                    f"already processed clip #{clip_index}."
                )
                continue

            # Sacamos el clip de pending inmediatamente.
            # Esto evita procesar dos veces el mismo botón.
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

                decision_text = (
                    "🎬 CLIP DE TWITCH\n\n"
                    "✅ APROBADO\n\n"
                    "Este clip pasará al "
                    "siguiente paso."
                )

                callback_text = (
                    "✅ Clip aprobado."
                )

                print(
                    f"Clip #{clip_index} "
                    "APPROVED"
                )

            else:
                item["status"] = "rejected"
                rejected.append(item)

                decision_text = (
                    "🎬 CLIP DE TWITCH\n\n"
                    "❌ RECHAZADO"
                )

                callback_text = (
                    "❌ Clip rechazado."
                )

                print(
                    f"Clip #{clip_index} "
                    "REJECTED"
                )

            # Guardamos SIEMPRE la decisión antes de
            # hacer cualquier otra operación de Telegram.
            state["approved"] = approved
            state["rejected"] = rejected
            state["pending"] = list(
                pending.values()
            )

            try:
                save_pending_state(
                    state
                )

                print(
                    f"  Decision for clip "
                    f"#{clip_index} saved."
                )

            except Exception as exc:
                # La decisión ya está en memoria y
                # continuamos procesando las demás.
                print(
                    "WARNING: Could not save "
                    "Telegram approval state:"
                )
                print(
                    f"  {exc}"
                )

            # Confirmamos el botón de Telegram.
            # Si falla, NO detenemos el workflow.
            try:
                answer_callback(
                    bot_token,
                    callback["id"],
                    callback_text,
                )

            except Exception as exc:
                print(
                    f"WARNING: Could not answer "
                    f"callback for clip #{clip_index}:"
                )
                print(
                    f"  {exc}"
                )

            # Actualizamos el mensaje.
            # Si falla, NO detenemos el workflow.
            try:
                update_message(
                    bot_token,
                    chat_id,
                    message_id,
                    decision_text,
                )

            except Exception as exc:
                print(
                    f"WARNING: Could not update "
                    f"Telegram message for clip #{clip_index}:"
                )
                print(
                    f"  {exc}"
                )

        if not pending:
            print()
            print(
                "All clips have been reviewed."
            )

    state["approved"] = approved
    state["rejected"] = rejected
    state["pending"] = list(
        pending.values()
    )

    state["completed"] = (
        len(state["pending"]) == 0
    )

    # Guardado final.
    try:
        save_pending_state(
            state
        )
    except Exception as exc:
        print(
            "WARNING: Final Telegram state "
            "could not be saved:"
        )
        print(
            f"  {exc}"
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


# CAMBIO AQUÍ: Ahora procesa dinámicamente todos los manifiestos en bucle
def main() -> int:
    try:
        print(
            "========================================="
        )
        print(
            "Telegram Clip Approval (Multi-VOD Loop)"
        )
        print(
            "========================================="
        )

        bot_token, chat_id = get_config()

        # Obtenemos la lista con todas las carpetas de vídeos
        manifest_files = find_all_manifests()
        print(f"📚 Se encontraron {len(manifest_files)} vídeos listos para procesar.")

        verify_bot(bot_token)

        # Procesamos cada vídeo de forma secuencial, uno detrás de otro
        for manifest_file in manifest_files:
            manifest = load_manifest(manifest_file)
            vod_id = str(manifest["vod_id"])
            clips = manifest.get("clips", [])

            print()
            print(f"🎬 PROCESANDO VOD ID: {vod_id}")
            print(f"   Ruta manifiesto: {manifest_file}")
            print(f"   Clips para revisar: {len(clips)}")

            if not clips:
                print("   ⚠️ No hay clips para enviar en este vídeo. Pasando al siguiente.")
                continue

            # Envia los clips de este vídeo concreto
            state = send_all_clips(
                bot_token,
                chat_id,
                manifest,
            )

            pending_file = save_pending_state(state)
            print(f"   Pendientes guardados en: {pending_file}")

            # Se detiene aquí a escuchar Telegram hasta que votes TODOS los clips de ESTE vídeo
            final_state = poll_for_approvals(
                bot_token,
                chat_id,
                state,
            )

            result_file = save_approval_result(final_state)
            
            # Forzamos la creación del archivo esperado por GitHub Actions
            save_final_approved_json(vod_id, final_state.get("approved", []))

            print()
            print(f"✅ VOD {vod_id} completado con éxito.")
            print(f"   Aprobados: {len(final_state['approved'])} | Rechazados: {len(final_state['rejected'])}")
            print(f"   Resultado guardado en: {result_file}")
            print("=========================================")

        print("\n🎉 ¡Todos los vídeos y clips en cola han sido revisados correctamente!")
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


# DISPARADOR DE EJECUCIÓN PRINCIPAL
if __name__ == "__main__":
    raise SystemExit(
        main()
    )
