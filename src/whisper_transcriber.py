import json
import sys
from pathlib import Path

import whisper


INPUT_VIDEO = Path(
    "data/vod_test/2846005700_test.mp4"
)

OUTPUT_DIR = Path(
    "data/transcriptions"
)

OUTPUT_FILE = (
    OUTPUT_DIR / "2846005700_test.json"
)

MODEL_NAME = "base"


def transcribe_video() -> None:
    if not INPUT_VIDEO.exists():
        raise FileNotFoundError(
            f"Input video not found: {INPUT_VIDEO}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Loading Whisper model: {MODEL_NAME}"
    )

    model = whisper.load_model(
        MODEL_NAME
    )

    print(
        f"Transcribing: {INPUT_VIDEO}"
    )

    result = model.transcribe(
        str(INPUT_VIDEO),
        language="es",
        fp16=False,
        verbose=True,
    )

    output = {
        "video": str(INPUT_VIDEO),
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

    with OUTPUT_FILE.open(
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
        f"Output: {OUTPUT_FILE}"
    )
    print(
        f"Detected language: "
        f"{output['language']}"
    )
    print(
        f"Segments: "
        f"{len(output['segments'])}"
    )
    print()
    print("Transcription:")
    print(output["text"])


def main() -> int:
    try:
        transcribe_video()
        return 0

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
