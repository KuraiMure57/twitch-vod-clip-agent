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

MAX_RETRIES = 3

RETRY_DELAYS = [
    10,
    30,
    60,
]


ANALYSIS_PROMPT = """
Eres un analista especializado en contenido para Twitch y clips cortos.

Vas a recibir la transcripción COMPLETA de un stream de Twitch.

Tu trabajo es identificar únicamente los momentos que tengan potencial real
para convertirse en clips de Twitch y posteriormente en vídeos cortos para
TikTok.

La transcripción contiene timestamps reales de los segmentos de Whisper.

Busca especialmente:

- sustos;
- reacciones fuertes;
- momentos graciosos;
- momentos inesperados;
- fails;
- errores;
- situaciones tensas;
- persecuciones;
- muertes;
- victorias;
- descubrimientos;
- comentarios espontáneos interesantes;
- frases especialmente graciosas;
- interacciones entretenidas;
- situaciones que puedan generar curiosidad;
- momentos con una reacción clara del streamer;
- momentos que tengan contexto suficiente para funcionar como clip.

IMPORTANTE:

La transcripción puede contener errores de reconocimiento de voz.

No debes interpretar literalmente palabras claramente deformadas por Whisper
si el contexto de los segmentos cercanos permite entender lo que realmente
está ocurriendo.

Sin embargo:

NO inventes acontecimientos.

NO supongas que ha ocurrido un susto, una muerte, una persecución, una
victoria o cualquier otro acontecimiento si la transcripción no proporciona
evidencia suficiente.

Utiliza siempre los timestamps de los segmentos proporcionados.

El candidato debe cubrir el momento interesante completo.

Cuando sea posible, incluye unos segundos de contexto antes del momento
principal y unos segundos después para que el clip tenga sentido.

Duración recomendada:

- mínimo aproximado: 15 segundos;
- máximo aproximado: 90 segundos.

No es necesario utilizar exactamente esos límites si hacerlo perjudica
claramente el contexto del momento.

Prioridad:

1. Momentos claramente entretenidos.
2. Momentos con una reacción fuerte.
3. Momentos inesperados.
4. Momentos tensos o de suspense.
5. Momentos graciosos.
6. Momentos con potencial para TikTok.

NO devuelvas:

- saludos;
- introducciones normales;
- explicaciones rutinarias;
- conversaciones normales;
- comentarios sin interés;
- información sobre drops salvo que exista un momento realmente entretenido
  asociado a ellos;
- fragmentos cuyo único interés sea que el streamer está hablando.

Es mejor devolver pocos candidatos buenos que muchos candidatos mediocres.

Como regla general, devuelve como máximo 10 candidatos.

Cada candidato debe contener:

- start: segundo aproximado de inicio;
- end: segundo aproximado de final;
- score: puntuación de 0 a 100;
- category: categoría del momento;
- reason: explicación breve de por qué puede funcionar;
- title: título corto y atractivo en español;
- confidence: confianza de 0 a 1.

La puntuación debe representar el potencial real del momento como clip.

Orientación de puntuación:

90-100:
Momento excepcional, muy entretenido o con gran potencial viral.

80-89:
Muy buen momento, claramente recomendable.

70-79:
Buen candidato, aunque no excepcional.

60-69:
Interesante pero probablemente no merece convertirse en clip.

0-59:
No debería seleccionarse como clip.

IMPORTANTE:

Si no existe ningún momento suficientemente interesante, devuelve:

{
  "candidates": []
}

Devuelve ÚNICAMENTE JSON válido con esta estructura:

{
  "candidates": [
    {
      "start": 2420,
      "end": 2470,
      "score": 85,
      "category": "tensión",
      "reason": "El fantasma aparece mientras el jugador intenta esconderse y genera una situación de tensión clara.",
      "title": "Pasó por delante de nosotros 🫣",
      "confidence": 0.91
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


def is_retryable_error(
    exc: Exception,
) -> bool:
    error_text = str(exc).upper()

    retryable_markers = [
        "503",
        "UNAVAILABLE",
        "429",
        "RESOURCE_EXHAUSTED",
        "500",
        "502",
        "INTERNAL",
        "DEADLINE_EXCEEDED",
        "TIMEOUT",
    ]

    return any(
        marker in error_text
        for marker in retryable_markers
    )


def request_gemini(
    client: genai.Client,
    prompt: str,
):
    last_exception = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        print(
            f"Gemini request attempt "
            f"{attempt}/{MAX_RETRIES}..."
        )

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )

            return response

        except Exception as exc:
            last_exception = exc

            print(
                f"Gemini request failed: {exc}",
                file=sys.stderr,
            )

            if not is_retryable_error(exc):
                raise

            if attempt >= MAX_RETRIES:
                print(
                    "Maximum Gemini retry attempts reached.",
                    file=sys.stderr,
                )
                raise

            delay = RETRY_DELAYS[
                attempt - 1
            ]

            print(
                f"Temporary Gemini error detected."
                f" Retrying in {delay} seconds..."
            )

            time.sleep(delay)

    if last_exception is not None:
        raise last_exception

    raise RuntimeError(
        "Gemini request failed without an exception."
    )


def analyze_transcription(
    transcription_text: str,
) -> dict:
    client = get_gemini_client()

    prompt = (
        ANALYSIS_PROMPT
        + "\n\nTRANSCRIPCIÓN COMPLETA:\n\n"
        + transcription_text
    )

    print(
        f"Sending transcription to Gemini "
        f"using {MODEL_NAME}..."
    )

    response = request_gemini(
        client,
        prompt,
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

    if len(candidates) > 10:
        raise RuntimeError(
            "Gemini returned more than 10 candidates."
        )

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


def save_result(
    result: dict,
) -> None:
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
            f"VOD ID: "
            f"{transcription.get('video', 'unknown')}"
        )

        print(
            f"Transcription file: "
            f"{INPUT_FILE}"
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
