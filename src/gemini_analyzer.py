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

MODEL_NAME = "gemini-3.6-flash"


ANALYSIS_PROMPT = """
Eres un analista especializado en contenido para Twitch y clips cortos.

Vas a recibir la transcripción de un stream de Twitch realizada
automáticamente mediante Whisper.

Tu objetivo es identificar ÚNICAMENTE momentos que tengan un potencial
real para convertirse en clips de Twitch y posteriormente en vídeos
cortos para TikTok.

IMPORTANTE:
La transcripción puede contener errores de reconocimiento de voz.
Puede haber palabras inventadas, frases incoherentes, idiomas mezclados,
repeticiones o fragmentos mal interpretados.

NO debes interpretar una transcripción incoherente como si describiera
un acontecimiento real.

Busca especialmente:

- sustos;
- reacciones fuertes;
- gritos o exclamaciones claramente relevantes;
- momentos graciosos;
- fails;
- errores del jugador;
- situaciones inesperadas;
- situaciones tensas;
- comentarios espontáneos interesantes;
- descubrimientos o sorpresas;
- interacciones entretenidas;
- momentos con una reacción emocional clara;
- momentos que tengan contexto suficiente para funcionar como clip.

REGLAS IMPORTANTES:

1. NO inventes acontecimientos que no aparecen en la transcripción.

2. NO asumas que una frase incoherente describe algo que ocurrió en el
   juego.

3. Si una parte de la transcripción parece claramente un error de
   Whisper, ignórala como evidencia de un momento interesante.

4. Una frase aislada o una exclamación genérica NO es suficiente para
   crear un candidato.

5. Una frase como "muy bien", "qué le vamos a hacer", "hostia",
   "madre mía", etc. no debe convertirse automáticamente en un clip.
   Necesita contexto y una reacción significativa.

6. Las repeticiones causadas probablemente por Whisper no deben
   considerarse múltiples momentos.

7. Si no puedes determinar razonablemente por qué el momento sería
   entretenido basándote en el texto disponible, NO lo selecciones.

8. Es preferible devolver cero candidatos antes que devolver un
   candidato mediocre.

9. No devuelvas demasiados candidatos. Selecciona únicamente los
   momentos con potencial real.

10. Cada candidato debe tener un principio y un final razonables.

11. El clip debería poder entenderse por sí mismo siempre que sea
    posible.

12. La puntuación debe reflejar el potencial REAL del momento:

    - 90-100: momento excepcional, muy buen candidato.
    - 80-89: momento claramente bueno.
    - 70-79: momento interesante y potencialmente válido.
    - 60-69: dudoso, normalmente NO debería seleccionarse.
    - menos de 60: NO seleccionar.

13. La confianza representa cuánto confías en que el momento realmente
    corresponde a algo interesante y no a un error de transcripción.

14. Si la transcripción disponible es demasiado mala para identificar
    momentos con confianza, devuelve una lista vacía.

15. No utilices el título del clip para inventar contexto que no aparece
    en la transcripción.

16. Los timestamps deben proceder de los segmentos proporcionados.

Para cada candidato devuelve:

- start: segundo aproximado de inicio;
- end: segundo aproximado de final;
- score: puntuación de 0 a 100;
- category: categoría del momento;
- reason: explicación breve basada exclusivamente en la transcripción;
- title: título corto y atractivo;
- confidence: confianza de 0 a 1.

Devuelve ÚNICAMENTE JSON válido con esta estructura:

{
  "candidates": [
    {
      "start": 0,
      "end": 30,
      "score": 85,
      "category": "reacción",
      "reason": "Descripción breve basada en la transcripción.",
      "title": "Título del clip",
      "confidence": 0.90
    }
  ]
}

Si no encuentras ningún momento suficientemente bueno:

{
  "candidates": []
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
