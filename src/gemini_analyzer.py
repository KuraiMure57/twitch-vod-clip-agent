import json
import os
import sys
import time
from pathlib import Path

from google import genai


INPUT_FILE = Path(
    "data/transcriptions/2846005700.json"
)

OUTPUT_DIR = Path(
    "data/analysis"
)

OUTPUT_FILE = (
    OUTPUT_DIR / "2846005700_candidates.json"
)

MODEL_NAME = "gemini-3.6-flash"

# Número aproximado de caracteres enviados a Gemini por bloque.
CHUNK_SIZE = 12000

# Número máximo de reintentos cuando Gemini devuelve un error temporal.
MAX_RETRIES = 4

# Tiempo inicial de espera entre reintentos.
INITIAL_RETRY_DELAY = 10

# Máximo de candidatos que puede devolver cada bloque.
MAX_CANDIDATES_PER_CHUNK = 5


ANALYSIS_PROMPT = """
Eres un analista especializado en contenido para Twitch y clips cortos.

Vas a recibir una parte de la transcripción de un stream de Twitch.

Tu trabajo es identificar momentos que podrían funcionar bien como clips
de Twitch y posteriormente como contenido corto para TikTok.

Busca especialmente:

- momentos graciosos;
- sustos o reacciones fuertes;
- momentos inesperados;
- errores o fails;
- situaciones tensas;
- comentarios espontáneos interesantes;
- momentos de sorpresa;
- interacciones que tengan potencial para entretener;
- momentos con suficiente contexto para entenderse como clip.

IMPORTANTE:

NO inventes acontecimientos que no aparecen en la transcripción.

La transcripción contiene timestamps reales. Utilízalos para localizar
cada momento.

No confundas una frase extraña de Whisper con un acontecimiento real.
Si el texto parece claramente mal transcrito o incomprensible, reduce
la confianza y evita inventar contexto.

Para cada candidato devuelve:

- start: segundo aproximado de inicio;
- end: segundo aproximado de final;
- score: puntuación de 0 a 100;
- category: categoría del momento;
- reason: explicación breve de por qué puede funcionar;
- title: título corto y atractivo;
- confidence: confianza de 0 a 1.

Reglas:

1. No devuelvas momentos que sean simplemente conversación normal.
2. No devuelvas demasiados candidatos.
3. Es mejor devolver pocos candidatos buenos que muchos candidatos mediocres.
4. El momento debe tener un principio y un final razonables.
5. El clip debería poder entenderse por sí mismo.
6. La puntuación debe reflejar el potencial real del momento.
7. Si no existe ningún momento interesante, devuelve una lista vacía.
8. No inventes reacciones, sustos, muertes, persecuciones ni acontecimientos
   que no aparezcan en el texto.
9. No uses información que no aparezca en esta parte de la transcripción.
10. Prioriza momentos realmente interesantes sobre frases simplemente llamativas.

Devuelve ÚNICAMENTE JSON válido con esta estructura:

{
  "candidates": [
    {
      "start": 0,
      "end": 30,
      "score": 85,
      "category": "susto",
      "reason": "Descripción breve.",
      "title": "Título del clip",
      "confidence": 0.92
    }
  ]
}
"""


def load_transcription() -> dict:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Transcription file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def build_transcription_segments(
    transcription: dict,
) -> list[dict]:
    segments = transcription.get(
        "segments",
        [],
    )

    result = []

    for segment in segments:
        start = float(
            segment.get("start", 0)
        )

        end = float(
            segment.get("end", 0)
        )

        text = str(
            segment.get("text", "")
        ).strip()

        if not text:
            continue

        result.append(
            {
                "start": start,
                "end": end,
                "text": text,
            }
        )

    return result


def create_chunks(
    segments: list[dict],
) -> list[str]:
    chunks = []
    current_lines = []
    current_length = 0

    for segment in segments:
        line = (
            f"[{segment['start']:.2f} - "
            f"{segment['end']:.2f}] "
            f"{segment['text']}"
        )

        line_length = len(line) + 1

        if (
            current_lines
            and current_length + line_length > CHUNK_SIZE
        ):
            chunks.append(
                "\n".join(current_lines)
            )

            current_lines = []
            current_length = 0

        current_lines.append(line)
        current_length += line_length

    if current_lines:
        chunks.append(
            "\n".join(current_lines)
        )

    return chunks


def get_gemini_client() -> genai.Client:
    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    return genai.Client(
        api_key=api_key
    )


def request_gemini(
    client: genai.Client,
    prompt: str,
    chunk_number: int,
) -> dict:
    delay = INITIAL_RETRY_DELAY

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            print(
                f"Gemini request for chunk "
                f"{chunk_number} "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )

            if not response.text:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            try:
                result = json.loads(
                    response.text
                )
            except json.JSONDecodeError as exc:
                print(
                    "Gemini raw response:",
                    file=sys.stderr,
                )

                print(
                    response.text,
                    file=sys.stderr,
                )

                raise RuntimeError(
                    "Gemini did not return valid JSON."
                ) from exc

            if "candidates" not in result:
                raise RuntimeError(
                    "Gemini response does not contain "
                    "the 'candidates' field."
                )

            if not isinstance(
                result["candidates"],
                list,
            ):
                raise RuntimeError(
                    "Gemini 'candidates' must be a list."
                )

            return result

        except Exception as exc:
            error_text = str(exc)

            print(
                f"Gemini request failed: {error_text}",
                file=sys.stderr,
            )

            is_temporary_error = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
                or "429" in error_text
            )

            if (
                not is_temporary_error
                or attempt >= MAX_RETRIES
            ):
                raise

            print(
                f"Temporary Gemini error. "
                f"Waiting {delay} seconds before retry..."
            )

            time.sleep(delay)

            delay *= 2

    raise RuntimeError(
        f"Gemini request failed after "
        f"{MAX_RETRIES} attempts."
    )


def analyze_chunk(
    client: genai.Client,
    chunk: str,
    chunk_number: int,
    total_chunks: int,
) -> list[dict]:
    prompt = (
        ANALYSIS_PROMPT
        + "\n\n"
        + f"ESTA ES LA PARTE {chunk_number} "
        + f"DE {total_chunks} DE LA TRANSCRIPCIÓN:\n\n"
        + chunk
    )

    result = request_gemini(
        client,
        prompt,
        chunk_number,
    )

    candidates = result.get(
        "candidates",
        [],
    )

    if len(candidates) > MAX_CANDIDATES_PER_CHUNK:
        candidates = candidates[
            :MAX_CANDIDATES_PER_CHUNK
        ]

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
            f"Candidate #{index} contains "
            f"invalid numeric values."
        ) from exc

    if start < 0:
        raise RuntimeError(
            f"Candidate #{index} has "
            f"a negative start."
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


def validate_candidates(
    candidates: list[dict],
) -> None:
    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        validate_candidate(
            candidate,
            index,
        )


def normalize_candidates(
    candidates: list[dict],
) -> list[dict]:
    normalized = []

    for candidate in candidates:
        normalized_candidate = dict(
            candidate
        )

        normalized_candidate["start"] = round(
            float(candidate["start"]),
            2,
        )

        normalized_candidate["end"] = round(
            float(candidate["end"]),
            2,
        )

        normalized_candidate["score"] = round(
            float(candidate["score"]),
            2,
        )

        normalized_candidate["confidence"] = round(
            float(candidate["confidence"]),
            3,
        )

        normalized_candidate["duration"] = round(
            (
                normalized_candidate["end"]
                - normalized_candidate["start"]
            ),
            2,
        )

        normalized.append(
            normalized_candidate
        )

    return normalized


def remove_duplicate_candidates(
    candidates: list[dict],
) -> list[dict]:
    if not candidates:
        return []

    candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["confidence"],
        ),
        reverse=True,
    )

    selected = []

    for candidate in candidates:
        duplicate = False

        for existing in selected:
            start_difference = abs(
                candidate["start"]
                - existing["start"]
            )

            end_difference = abs(
                candidate["end"]
                - existing["end"]
            )

            if (
                start_difference < 10
                and end_difference < 10
            ):
                duplicate = True
                break

        if not duplicate:
            selected.append(
                candidate
            )

    selected.sort(
        key=lambda candidate: candidate["score"],
        reverse=True,
    )

    return selected


def save_result(
    candidates: list[dict],
    statistics: dict,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = {
        "statistics": statistics,
        "candidates": candidates,
    }

    with OUTPUT_FILE.open(
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
        transcription = load_transcription()

        segments = build_transcription_segments(
            transcription
        )

        if not segments:
            raise RuntimeError(
                "The transcription contains no usable segments."
            )

        chunks = create_chunks(
            segments
        )

        print(
            f"Transcription segments: "
            f"{len(segments)}"
        )

        print(
            f"Transcription characters: "
            f"{sum(len(segment['text']) for segment in segments)}"
        )

        print(
            f"Chunk size: "
            f"{CHUNK_SIZE} characters"
        )

        print(
            f"Chunks created: "
            f"{len(chunks)}"
        )

        print(
            f"Gemini model: "
            f"{MODEL_NAME}"
        )

        client = get_gemini_client()

        all_candidates = []

        failed_chunks = []

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            print()
            print(
                "========================================="
            )

            print(
                f"Processing Gemini chunk "
                f"{index}/{len(chunks)}"
            )

            print(
                f"Chunk characters: "
                f"{len(chunk)}"
            )

            print(
                "========================================="
            )

            try:
                candidates = analyze_chunk(
                    client,
                    chunk,
                    index,
                    len(chunks),
                )

                validate_candidates(
                    candidates
                )

                all_candidates.extend(
                    candidates
                )

                print(
                    f"Candidates found in chunk "
                    f"{index}: "
                    f"{len(candidates)}"
                )

            except Exception as exc:
                print(
                    f"ERROR processing chunk "
                    f"{index}: {exc}",
                    file=sys.stderr,
                )

                failed_chunks.append(
                    index
                )

            if index < len(chunks):
                print(
                    "Waiting before next Gemini request..."
                )

                time.sleep(3)

        normalized_candidates = (
            normalize_candidates(
                all_candidates
            )
        )

        deduplicated_candidates = (
            remove_duplicate_candidates(
                normalized_candidates
            )
        )

        statistics = {
            "transcription_segments": len(
                segments
            ),
            "chunks": len(chunks),
            "failed_chunks": failed_chunks,
            "raw_candidates": len(
                all_candidates
            ),
            "final_candidates": len(
                deduplicated_candidates
            ),
            "model": MODEL_NAME,
            "chunk_size": CHUNK_SIZE,
        }

        save_result(
            deduplicated_candidates,
            statistics,
        )

        print()
        print(
            "========================================="
        )

        print(
            "Gemini analysis completed."
        )

        print(
            "========================================="
        )

        print(
            f"Chunks processed: "
            f"{len(chunks) - len(failed_chunks)}"
        )

        print(
            f"Failed chunks: "
            f"{len(failed_chunks)}"
        )

        print(
            f"Raw candidates: "
            f"{len(all_candidates)}"
        )

        print(
            f"Final candidates: "
            f"{len(deduplicated_candidates)}"
        )

        print(
            f"Output: {OUTPUT_FILE}"
        )

        print()

        for index, candidate in enumerate(
            deduplicated_candidates,
            start=1,
        ):
            print(
                f"Candidate #{index}"
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
                f"  Title: "
                f"{candidate['title']}"
            )

            print(
                f"  Confidence: "
                f"{candidate['confidence']}"
            )

            print()

        if failed_chunks:
            print(
                "WARNING: Some Gemini chunks failed:"
            )

            print(
                failed_chunks
            )

            print(
                "The available candidates were "
                "saved successfully."
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
