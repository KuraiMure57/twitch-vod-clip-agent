```python
import json
import subprocess
import sys
from pathlib import Path


INPUT_CANDIDATES_FILE = Path(
    "data/analysis/2846005700_candidates.json"
)

INPUT_VOD_FILE = Path(
    "data/vods/2846005700.mp4"
)

OUTPUT_DIR = Path(
    "data/clips"
)


def load_candidates() -> list[dict]:
    if not INPUT_CANDIDATES_FILE.exists():
        raise FileNotFoundError(
            "Gemini candidates file not found: "
            f"{INPUT_CANDIDATES_FILE}"
        )

    with INPUT_CANDIDATES_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    candidates = data.get(
        "candidates",
        [],
    )

    if not isinstance(
        candidates,
        list,
    ):
        raise RuntimeError(
            "Gemini 'candidates' must be a list."
        )

    return candidates


def validate_candidate(
    candidate: dict,
    index: int,
) -> None:
    required_fields = [
        "start",
        "end",
        "score",
        "category",
        "reason",
        "title",
        "confidence",
    ]

    for field in required_fields:
        if field not in candidate:
            raise RuntimeError(
                f"Candidate #{index} is missing "
                f"field '{field}'."
            )

    try:
        start = float(candidate["start"])
        end = float(candidate["end"])
        score = float(candidate["score"])
        confidence = float(candidate["confidence"])
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise RuntimeError(
            f"Candidate #{index} contains invalid "
            "numeric values."
        ) from exc

    if start < 0:
        raise RuntimeError(
            f"Candidate #{index} has a negative start."
        )

    if end <= start:
        raise RuntimeError(
            f"Candidate #{index} has invalid timestamps: "
            f"{start} -> {end}."
        )

    if not 0 <= score <= 100:
        raise RuntimeError(
            f"Candidate #{index} has invalid score: "
            f"{score}."
        )

    if not 0 <= confidence <= 1:
        raise RuntimeError(
            f"Candidate #{index} has invalid confidence: "
            f"{confidence}."
        )


def sanitize_filename(
    text: str,
) -> str:
    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "-_"
    )

    sanitized = "".join(
        character
        if character in allowed
        else "_"
        for character in text
    )

    sanitized = sanitized.strip("_")

    if not sanitized:
        return "clip"

    return sanitized[:80]


def generate_clip(
    candidate: dict,
    index: int,
) -> Path:
    start = float(candidate["start"])
    end = float(candidate["end"])

    duration = end - start

    score = int(
        float(candidate["score"])
    )

    category = sanitize_filename(
        str(candidate["category"])
    )

    output_file = (
        OUTPUT_DIR
        / (
            f"clip_{index:02d}"
            f"_{start:.2f}_{end:.2f}"
            f"_score_{score}"
            f"_{category}.mp4"
        )
    )

    print()
    print(
        f"Generating clip #{index}"
    )
    print(
        f"  Start: {start:.2f}s"
    )
    print(
        f"  End: {end:.2f}s"
    )
    print(
        f"  Duration: {duration:.2f}s"
    )
    print(
        f"  Score: {score}"
    )
    print(
        f"  Category: "
        f"{candidate['category']}"
    )
    print(
        f"  Title: "
        f"{candidate['title']}"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(INPUT_VOD_FILE),
            "-t",
            str(duration),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_file),
        ],
        check=True,
    )

    if not output_file.exists():
        raise RuntimeError(
            "FFmpeg did not create the expected "
            f"clip file: {output_file}"
        )

    return output_file


def main() -> int:
    try:
        print(
            "========================================="
        )
        print(
            "Clip generation"
        )
        print(
            "========================================="
        )

        if not INPUT_VOD_FILE.exists():
            raise FileNotFoundError(
                "Complete VOD file not found: "
                f"{INPUT_VOD_FILE}"
            )

        candidates = load_candidates()

        print(
            f"Candidates received: "
            f"{len(candidates)}"
        )

        if not candidates:
            print(
                "No candidates were found."
            )
            print(
                "No clips will be generated."
            )
            return 0

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        generated_clips = []

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            validate_candidate(
                candidate,
                index,
            )

            output_file = generate_clip(
                candidate,
                index,
            )

            generated_clips.append(
                {
                    "index": index,
                    "file": str(output_file),
                    "start": float(
                        candidate["start"]
                    ),
                    "end": float(
                        candidate["end"]
                    ),
                    "duration": round(
                        float(candidate["end"])
                        - float(candidate["start"]),
                        2,
                    ),
                    "score": float(
                        candidate["score"]
                    ),
                    "category": candidate[
                        "category"
                    ],
                    "title": candidate[
                        "title"
                    ],
                    "reason": candidate[
                        "reason"
                    ],
                    "confidence": float(
                        candidate["confidence"]
                    ),
                }
            )

        manifest_file = (
            OUTPUT_DIR / "clips_manifest.json"
        )

        with manifest_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                {
                    "vod": str(
                        INPUT_VOD_FILE
                    ),
                    "clips": generated_clips,
                },
                file,
                indent=2,
                ensure_ascii=False,
            )

        print()
        print(
            "========================================="
        )
        print(
            "Clip generation completed."
        )
        print(
            f"Clips generated: "
            f"{len(generated_clips)}"
        )
        print(
            f"Output directory: "
            f"{OUTPUT_DIR}"
        )
        print(
            f"Manifest: "
            f"{manifest_file}"
        )
        print(
            "========================================="
        )

        for clip in generated_clips:
            print()
            print(
                f"Clip #{clip['index']}"
            )
            print(
                f"  File: "
                f"{clip['file']}"
            )
            print(
                f"  Duration: "
                f"{clip['duration']}s"
            )
            print(
                f"  Score: "
                f"{clip['score']}"
            )
            print(
                f"  Title: "
                f"{clip['title']}"
            )

        return 0

    except subprocess.CalledProcessError as exc:
        print(
            "ERROR: FFmpeg failed.",
            file=sys.stderr,
        )
        print(
            f"Exit code: {exc.returncode}",
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
```
