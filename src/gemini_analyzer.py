import json
import os
import sys
from pathlib import Path

from google import genai


INPUT_DIR = Path(
    "data/transcriptions"
)

OUTPUT_DIR = Path(
    "data/analysis"
)

MODEL_NAME = "gemini-3.6-flash"


ANALYSIS_PROMPT = """
Eres un analista especializado en contenido para Twitch
y clips cortos para TikTok.

Vas a recibir la transcripción completa de un stream de Twitch.

Tu trabajo es identificar los momentos que realmente tienen
potencial para convertirse en clips.

Busca especialmente:

- momentos graciosos;
- sustos;
- reacciones fuertes;
- momentos inesperados;
- errores o fails;
- situaciones tensas;
- comentarios espontáneos interesantes;
- sorpresas;
- situaciones absurdas;
- interacciones entretenidas;
- momentos con potencial viral;
- momentos que tengan contexto suficiente para entenderse
  como clip independiente.

NO inventes acontecimientos.

La transcripción puede contener errores de reconocimiento de voz.
Tenlo en cuenta antes de decidir que una frase es graciosa.

No consideres interesante una frase únicamente porque la
transcripción parezca absurda.

Utiliza los timestamps de los segmentos.

Para cada candidato devuelve:

- start: segundo aproximado de inicio;
- end: segundo aproximado de final;
- score: puntuación de 0 a 100;
- category: categoría;
- reason: explicación breve;
- title: título corto y atractivo;
- confidence: confianza de 0 a 1.

Reglas importantes:

1. No devuelvas conversación normal.
2. No devuelvas introducciones normales.
3. No devuelvas explicaciones rutinarias del juego.
4. No devuelvas simplemente información sobre drops.
5. No confundas errores de Whisper con momentos graciosos.
6. No inventes contexto visual que no aparece en la información.
7. Es mejor devolver pocos candidatos buenos que muchos malos.
8. Un candidato debe tener un principio y un final razonables.
9. El clip debe poder entenderse razonablemente por sí mismo.
10. Prioriza momentos con reacción, sorpresa, tensión,
    humor o algo claramente interesante.
11. Si no existe ningún momento suficientemente bueno,
    devuelve una lista vacía.
12. No fuerces candidatos para llenar una cantidad determinada.
13. Solo considera candidatos con potencial real de clip.

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


def find_transcription() -> Path:
    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Transcription directory not found: "
            f"{INPUT_DIR}"
        )

    files = sorted(
        INPUT_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            f"No transcription JSON files found "
            f"in {INPUT_DIR}"
        )

    return files[0]


def load_transcription(
    input_file: Path,
) -> dict:

    with input_file.open(
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
            segment.get(
                "start",
                0,
            )
        )

        end = float(
            segment.get(
                "end",
                0,
            )
        )

        text = str(
            segment.get(
                "text",
                "",
            )
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
                f"Candidate #{index} has "
                "a negative start."
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


def save_result(
    result: dict,
    output_file: Path,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        input_file = find_transcription()

        transcription = load_transcription(
            input_file
        )

        transcription_text = (
            build_transcription_text(
                transcription
            )
        )

        if not transcription_text.strip():
            raise RuntimeError(
                "The transcription contains no text."
            )

        vod_id = transcription.get(
            "vod_id",
            input_file.stem,
        )

        output_file = (
            OUTPUT_DIR
            / f"{vod_id}_candidates.json"
        )

        print(
            f"Transcription file: "
            f"{input_file}"
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
            result,
            output_file,
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
            f"Output: {output_file}"
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
