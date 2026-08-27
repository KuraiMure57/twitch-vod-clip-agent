import json
import sys
from pathlib import Path

import whisper


VOD_DIR = Path(
    "data/vods"
)

OUTPUT_DIR = Path(
    "data/transcriptions"
)

MODEL_NAME = "small"

INITIAL_PROMPT = """
Transcripción en español de un stream de Twitch de videojuegos.
El hablante puede utilizar lenguaje coloquial, nombres de videojuegos,
personajes, objetos, enemigos, habilidades, drops, clips, gameplay
y terminología habitual de videojuegos.
"""


def find_vod() -> Path:
    vod_files = sorted(
        VOD_DIR.glob("*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not vod_files:
        raise FileNotFoundError(
            f"No MP4 VOD files found in: {VOD_DIR}"
        )

    return vod_files[0]


def transcribe_video(
    input_video: Path,
) -> Path:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vod_id = input_video.stem

    output_file = (
        OUTPUT_DIR / f"{vod_id}.json"
    )

    print(
        f"Loading Whisper model: {MODEL_NAME}"
    )

    model = whisper.load_model(
        MODEL_NAME
    )

    print()
    print(
        f"Transcribing complete VOD:"
    )

    print(
        input_video
    )

    print()

    result = model.transcribe(
        str(input_video),
        language="es",
        task="transcribe",
        fp16=False,
        verbose=True,
        temperature=0,
        condition_on_previous_text=False,
        initial_prompt=INITIAL_PROMPT,
    )

    output = {
        "video": str(input_video),
        "model": MODEL_NAME,
        "language": result.get(
            "language",
            "unknown",
        ),
        "text": result.get(
            "text",
            "",
        ),
        "segments": result.get(
            "segments",
            [],
        ),
    }

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        "Whisper transcription completed."
    )

    print(
        f"Output: {output_file}"
    )

    print(
        f"Detected language: "
        f"{output['language']}"
    )

    print(
        f"Segments: "
        f"{len(output['segments'])}"
    )

    print(
        f"Characters: "
        f"{len(output['text'])}"
    )

    print()

    return output_file


def main() -> int:
    try:
        input_video = find_vod()

        print(
            f"Selected VOD for transcription: "
            f"{input_video}"
        )

        transcribe_video(
            input_video
        )

        return 0

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
