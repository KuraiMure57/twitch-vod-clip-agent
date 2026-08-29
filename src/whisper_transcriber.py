```python
import json
import sys
from pathlib import Path

import whisper


INPUT_DIR = Path(
    "data/vods"
)

OUTPUT_DIR = Path(
    "data/transcriptions"
)

MODEL_NAME = "small"


def find_vod() -> Path:
    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"VOD directory not found: {INPUT_DIR}"
        )

    vod_files = sorted(
        INPUT_DIR.glob("*.mp4")
    )

    if not vod_files:
        raise FileNotFoundError(
            f"No MP4 VOD found in {INPUT_DIR}"
        )

    if len(vod_files) > 1:
        print(
            f"Multiple VOD files found: "
            f"{len(vod_files)}"
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
        f"Loading Whisper model: "
        f"{MODEL_NAME}"
    )

    model = whisper.load_model(
        MODEL_NAME
    )

    print(
        f"Transcribing: {input_video}"
    )

    result = model.transcribe(
        str(input_video),
        language="es",
        fp16=False,
        verbose=True,
    )

    output = {
        "vod_id": vod_id,
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
    print()
    print("Transcription:")
    print(output["text"])

    return output_file


def main() -> int:
    try:
        input_video = find_vod()

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
    raise SystemExit(
        main()
    )
```
