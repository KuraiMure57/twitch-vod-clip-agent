import json
from pathlib import Path


STATE_FILE = Path("data/processed_vods.json")


def load_processed_vods() -> list[str]:
    if not STATE_FILE.exists():
        return []

    with STATE_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    processed_vods = data.get("processed_vods", [])

    return [str(vod_id) for vod_id in processed_vods]


def is_vod_processed(vod_id: str) -> bool:
    processed_vods = load_processed_vods()

    return str(vod_id) in processed_vods


def mark_vod_as_processed(vod_id: str) -> None:
    processed_vods = load_processed_vods()

    vod_id = str(vod_id)

    if vod_id not in processed_vods:
        processed_vods.append(vod_id)

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with STATE_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "processed_vods": processed_vods,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    print("Processed VOD state module is working.")

    processed = load_processed_vods()

    print(
        f"Processed VODs: {len(processed)}"
    )

    for vod_id in processed:
        print(f"  - {vod_id}")
