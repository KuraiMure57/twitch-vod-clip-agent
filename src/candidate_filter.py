import json
import sys
from pathlib import Path


INPUT_DIR = Path(
    "data/analysis"
)

OUTPUT_DIR = Path(
    "data/filtered_candidates"
)

MIN_SCORE = 70
MIN_DURATION = 15
MAX_DURATION = 180

REWARD_CODE_KEYWORDS = (
    "código",
    "codigo",
    "code",
    "canjear",
    "canje",
    "recompensa",
    "reward",
    "redeem",
    "coupon",
    "cupón",
    "cupon",
    "promocode",
    "promo code",
)


def find_analysis_file() -> Path:
    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Analysis directory not found: "
            f"{INPUT_DIR}"
        )

    files = sorted(
        INPUT_DIR.glob("*_candidates.json")
    )

    if not files:
        raise FileNotFoundError(
            f"No Gemini candidates file found in "
            f"{INPUT_DIR}"
        )

    if len(files) > 1:
        raise RuntimeError(
            "Multiple Gemini candidates files found in "
            f"{INPUT_DIR}. Expected exactly one analysis file."
        )

    return files[0]


def load_candidates(
    input_file: Path,
) -> dict:
    with input_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def is_reward_code_candidate(
    candidate: dict,
) -> bool:
    explicit_flag = candidate.get(
        "is_reward_code",
        False,
    )

    if explicit_flag is True:
        return True

    searchable_text = " ".join(
        str(candidate.get(field, ""))
        for field in (
            "category",
            "reason",
            "title",
        )
    ).lower()

    return any(
        keyword in searchable_text
        for keyword in REWARD_CODE_KEYWORDS
    )


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
        start = float(
            candidate["start"]
        )

        end = float(
            candidate["end"]
        )

        score = float(
            candidate["score"]
        )

        confidence = float(
            candidate["confidence"]
        )

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
            f"Candidate #{index} has invalid "
            f"timestamps: {start} -> {end}."
        )

    if not 0 <= score <= 100:
        raise RuntimeError(
            f"Candidate #{index} has invalid "
            f"score: {score}."
        )

    if not 0 <= confidence <= 1:
        raise RuntimeError(
            f"Candidate #{index} has invalid "
            f"confidence: {confidence}."
        )


def filter_candidates(
    candidates: list[dict],
) -> tuple[list[dict], dict]:

    selected = []

    rejected_score = 0
    rejected_duration = 0
    selected_reward_codes = 0

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        validate_candidate(
            candidate,
            index,
        )

        start = float(
            candidate["start"]
        )

        end = float(
            candidate["end"]
        )

        score = float(
            candidate["score"]
        )

        duration = end - start

        reward_code = is_reward_code_candidate(
            candidate
        )

        # Los códigos de recompensa tienen
        # prioridad especial.
        #
        # No se descartan por score bajo ni por
        # durar menos de MIN_DURATION.
        #
        # El único límite que mantienen es el
        # máximo de MAX_DURATION para que el clip
        # siga siendo válido para TikTok.
        if reward_code:
            if duration > MAX_DURATION:
                rejected_duration += 1
                continue

            normalized_candidate = dict(
                candidate
            )

            normalized_candidate[
                "is_reward_code"
            ] = True

            selected_reward_codes += 1

        else:
            if score < MIN_SCORE:
                rejected_score += 1
                continue

            if (
                duration < MIN_DURATION
                or duration > MAX_DURATION
            ):
                rejected_duration += 1
                continue

            normalized_candidate = dict(
                candidate
            )

            normalized_candidate[
                "is_reward_code"
            ] = False

        normalized_candidate["start"] = round(
            start,
            2,
        )

        normalized_candidate["end"] = round(
            end,
            2,
        )

        normalized_candidate["score"] = round(
            score,
            2,
        )

        normalized_candidate["confidence"] = round(
            float(candidate["confidence"]),
            3,
        )

        normalized_candidate["duration"] = round(
            duration,
            2,
        )

        selected.append(
            normalized_candidate
        )

    # Los códigos de recompensa aparecen primero.
    # Dentro de cada grupo, se mantiene el orden
    # por score descendente.
    selected.sort(
        key=lambda candidate: (
            candidate.get(
                "is_reward_code",
                False,
            ),
            candidate["score"],
        ),
        reverse=True,
    )

    statistics = {
        "total_candidates": len(candidates),
        "selected_candidates": len(selected),
        "selected_reward_codes": selected_reward_codes,
        "rejected_by_score": rejected_score,
        "rejected_by_duration": rejected_duration,
        "minimum_score": MIN_SCORE,
        "minimum_duration": MIN_DURATION,
        "maximum_duration": MAX_DURATION,
    }

    return selected, statistics


def save_result(
    selected: list[dict],
    statistics: dict,
    output_file: Path,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = {
        "statistics": statistics,
        "candidates": selected,
    }

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main() -> int:
    try:
        input_file = find_analysis_file()

        data = load_candidates(
            input_file
        )

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

        vod_id = input_file.name.replace(
            "_candidates.json",
            "",
        )

        output_file = (
            OUTPUT_DIR
            / f"{vod_id}_selected.json"
        )

        print(
            f"VOD ID: {vod_id}"
        )

        print(
            f"Analysis file: "
            f"{input_file}"
        )

        print(
            f"Gemini candidates received: "
            f"{len(candidates)}"
        )

        print(
            f"Minimum score: {MIN_SCORE}"
        )

        print(
            f"Allowed duration: "
            f"{MIN_DURATION}-{MAX_DURATION} seconds"
        )

        print(
            "Reward-code exception: enabled"
        )

        selected, statistics = filter_candidates(
            candidates
        )

        save_result(
            selected,
            statistics,
            output_file,
        )

        print()
        print(
            "Candidate filtering completed."
        )

        print(
            f"Total candidates: "
            f"{statistics['total_candidates']}"
        )

        print(
            f"Selected candidates: "
            f"{statistics['selected_candidates']}"
        )

        print(
            f"Selected reward-code candidates: "
            f"{statistics['selected_reward_codes']}"
        )

        print(
            f"Rejected by score: "
            f"{statistics['rejected_by_score']}"
        )

        print(
            f"Rejected by duration: "
            f"{statistics['rejected_by_duration']}"
        )

        print(
            f"Output: {output_file}"
        )

        for index, candidate in enumerate(
            selected,
            start=1,
        ):
            print()
            print(
                f"Selected candidate #{index}"
            )

            print(
                f"  Start: "
                f"{candidate['start']}"
            )

            print(
                f"  End: "
                f"{candidate['end']}"
            )

            print(
                f"  Duration: "
                f"{candidate['duration']}s"
            )

            print(
                f"  Score: "
                f"{candidate['score']}"
            )

            print(
                f"  Category: "
                f"{candidate['category']}"
            )

            print(
                f"  Reward code: "
                f"{candidate['is_reward_code']}"
            )

            print(
                f"  Title: "
                f"{candidate['title']}"
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
