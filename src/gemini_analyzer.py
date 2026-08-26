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
Eres un analista de streams de Twitch especializado en encontrar
momentos que puedan convertirse en clips.

Vas a recibir una transcripción automática de Whisper con timestamps.

IMPORTANTE:
La transcripción puede contener errores graves de reconocimiento.
Puede haber palabras incorrectas, frases incompletas, palabras
inventadas, repeticiones o texto extraño.

NO intentes corregir la transcripción.
NO descartes un posible momento simplemente porque el texto sea raro.

Tu tarea en esta fase es hacer una PRIMERA DETECCIÓN AMPLIA de momentos
que MEREZCA LA PENA REVISAR posteriormente.

Busca cualquier cambio o situación potencialmente interesante, como:

- una reacción;
- una sorpresa;
- una exclamación;
- un susto;
- una frase graciosa;
- un fail;
- una situación absurda;
- frustración;
- celebración;
- tensión;
- descubrimiento;
- comentario espontáneo;
- repetición extraña;
- cambio repentino en la conversación;
- una frase que pueda tener contexto de gameplay;
- cualquier momento que pueda tener potencial para un clip.

NO necesitas estar seguro de que sea viral.

Es preferible incluir un posible candidato dudoso antes que perder un
momento potencialmente bueno.

NO inventes acontecimientos.

Los candidatos deben basarse únicamente en el texto y timestamps
proporcionados.

DURACIÓN:

Los candidatos deben tener entre 15 y 60 segundos siempre que sea
posible.

Incluye contexto suficiente para que el momento pueda entenderse.

No cortes una frase importante.

TIMESTAMPS:

Utiliza los timestamps de los segmentos.

El start debe comenzar cerca del inicio del momento interesante.

El end debe terminar cuando la situación haya terminado o cuando
exista suficiente contexto.

PUNTUACIÓN:

La puntuación representa POTENCIAL, no certeza.

90-100 = potencial excepcional
80-89 = potencial alto
70-79 = potencial moderado
60-69 = posible candidato
0-59 = no devolver

En esta fase puedes devolver candidatos desde 60 puntos.

CONFIDENCE:

Indica cuánto confías en que realmente exista un momento interesante.

No confundas confidence con score.

Un momento puede tener:
- score alto pero confidence bajo si parece muy interesante pero la
  transcripción es difícil de entender.
- score moderado y confidence alto si sabes exactamente qué está
  ocurriendo pero no parece especialmente espectacular.

REGLAS:

1. NO devuelvas conversación completamente plana si no existe ninguna
   señal de interés.

2. Si hay cualquier señal razonable de reacción, sorpresa, humor,
   gameplay, tensión o situación inesperada, considérala candidata.

3. No seas excesivamente conservador.

4. No agrupes automáticamente todo el vídeo.

5. Un candidato puede solaparse ligeramente con otro si representan
   posibles momentos diferentes.

6. Máximo 5 candidatos.

7. Si solo existe un posible momento, devuelve ese momento aunque la
   confianza no sea alta.

8. No devuelvas una lista vacía simplemente porque la transcripción
   tenga errores.

Para cada candidato devuelve:

- start
- end
- score
- category
- reason
- title
- confidence

Categorías:

- susto
- reacción
- sorpresa
- fail
- humor
- tensión
- celebración
- descubrimiento
- momento_inesperado
- comentario
- gameplay
- otro

Devuelve ÚNICAMENTE JSON válido.

Formato:

{
  "candidates": [
    {
      "start": 10,
      "end": 30,
      "score": 72,
      "category": "reacción",
      "reason": "Existe un cambio repentino en la conversación que podría corresponder a una reacción.",
      "title": "¿Pero qué acaba de pasar?",
      "confidence": 0.55
    }
  ]
}

Si después de revisar TODA la transcripción no existe absolutamente
ninguna señal que pueda justificar un candidato, devuelve:

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
