import json
import os
import sys
from pathlib import Path

from google import genai


INPUT_FILE = Path(
    "data/transcriptions/2846005700_test.json"
)

OUTPUT_DIR = Path(
    "data/analysis"
)

OUTPUT_FILE = (
    OUTPUT_DIR / "2846005700_candidates.json"
)

MODEL_NAME = "gemini-2.5-flash"


ANALYSIS_PROMPT = """
Eres un analista especializado en contenido para Twitch y clips cortos.

Vas a recibir la transcripción de un stream de Twitch.

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
- momentos que tengan contexto suficiente para entenderse como clip.

NO inventes acontecimientos que no aparecen en la transcripción.

Utiliza los timestamps de los segmentos para localizar cada momento.

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


def build_transcription_text(
    transcription: dict,
) -> str:
    segments = transcription.get(
        "segments",
        [],
    )

    lines = []

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

        lines.append(
            f"[{start:.2f} - {end:.2f}] {text}"
        )

    return "\n".join(lines)


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


def analyze_transcription(
    transcription_text: str,
) -> dict:
    client = get_gemini_client()

    prompt = (
        ANALYSIS_PROMPT
        + "\n\nTRANSCRIPCIÓN:\n\n"
        + transcription_text
    )

    print(
        f"Sending transcription to Gemini "
        f"using {MODEL_NAME}..."
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


def validate_candidates(
    result: dict,
) -> None:
    candidates = result["candidates"]

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
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

        score = float(
            candidate["score"]
        )

        confidence = float(
            candidate["confidence"]
        )

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


def save_result(result: dict) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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

        transcription_text = (
            build_transcription_text(
                transcription
            )
        )

        if not transcription_text.strip():
            raise RuntimeError(
                "The transcription contains no text."
            )

        print(
            f"Transcription segments: "
            f"{len(transcription.get('segments', []))}"
        )

        print(
            f"Transcription characters: "
            f"{len(transcription_text)}"
        )

        result = analyze_transcription(
            transcription_text
        )

        validate_candidates(
            result
        )

        save_result(
            result
        )

        candidates = result[
            "candidates"
        ]

        print()
        print(
            "Gemini analysis completed."
        )
        print(
            f"Candidates found: "
            f"{len(candidates)}"
        )
        print(
            f"Output: {OUTPUT_FILE}"
        )
        print()

        for index, candidate in enumerate(
            candidates,
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
                f"  Reason: "
                f"{candidate['reason']}"
            )
            print(
                f"  Confidence: "
                f"{candidate['confidence']}"
            )
            print()

        return 0

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
