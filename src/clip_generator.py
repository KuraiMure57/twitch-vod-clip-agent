import json
import subprocess
import sys
from pathlib import Path


VOD_DIR = Path(
    "data/vods"
)

CANDIDATES_DIR = Path(
    "data/filtered_candidates"
)

OUTPUT_DIR = Path(
    "data/clips"
)


def find_vod() -> Path:
    if not VOD_DIR.exists():
        raise FileNotFoundError(
            f"VOD directory not found: {VOD_DIR}"
        )

    files = sorted(
        VOD_DIR.glob("*.mp4")
    )

    if not files:
        raise FileNotFoundError(
            f"No VOD MP4 found in {VOD_DIR}"
        )

    return files[0]


def find_candidates_file() -> Path:
    if not CANDIDATES_DIR.exists():
        raise FileNotFoundError(
            "Filtered candidates directory not found: "
            f"{CANDIDATES_DIR}"
        )

    files = sorted(
        CANDIDATES_DIR.glob("*_selected.json")
    )

    if not files:
        raise FileNotFoundError(
            "No filtered candidates file found in "
            f"{CANDIDATES_DIR}"
        )

    return files[0]


def load_candidates(
    input_file: Path,
) -> list[dict]:
    with input_file.open(
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
            "Filtered 'candidates' must be a list."
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

    start = float(
        candidate["start"]
    )

    end = float(
        candidate["end"]
    )

    if start < 0:
        raise RuntimeError(
            f"Candidate #{index} has a negative start."
        )

    if end <= start:
        raise RuntimeError(
            f"Candidate #{index} has invalid timestamps: "
            f"{start} -> {end}."
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
    vod_file: Path,
    output_dir: Path,
) -> Path:
    start = float(
        candidate["start"]
    )

    end = float(
        candidate["end"]
    )

    duration = end - start

    score = int(
        float(candidate["score"])
    )

    category = sanitize_filename(
        str(candidate["category"])
    )

    output_file = (
        output_dir
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
            str(vod_file),
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

        vod_file = find_vod()

        candidates_file = (
            find_candidates_file()
        )

        candidates = load_candidates(
            candidates_file
        )

        vod_id = vod_file.stem

        output_dir = (
            OUTPUT_DIR / vod_id
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            f"VOD: {vod_file}"
        )

        print(
            f"Candidates: "
            f"{candidates_file}"
        )

        print(
            f"Candidates received: "
            f"{len(candidates)}"
        )

        if not candidates:
            print()
            print(
                "No selected candidates."
            )
            print(
                "No clips will be generated."
            )
            return 0

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
                vod_file,
                output_dir,
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
            output_dir
            / "clips_manifest.json"
        )

        with manifest_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                {
                    "vod_id": vod_id,
                    "vod": str(vod_file),
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
            f"{output_dir}"
        )
        print(
            f"Manifest: "
            f"{manifest_file}"
        )
        print(
            "========================================="
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
