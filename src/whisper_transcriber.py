import json
import sys
from pathlib import Path

import whisper


INPUT_DIR = Path(
    "data/vods"
)

OUTPUT_DIR = Path(
    "data/transcriptions"
)

MODEL_NAME = "small"


def find_vod() -> Path:
    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"VOD directory not found: {INPUT_DIR}"
        )

    vod_files = sorted(
        INPUT_DIR.glob("*.mp4")
    )

    if not vod_files:
        raise FileNotFoundError(
            f"No MP4 VOD found in {INPUT_DIR}"
        )

    if len(vod_files) > 1:
        raise RuntimeError(
            "Multiple VOD files found in "
            f"{INPUT_DIR}. Expected exactly one VOD."
        )

    return vod_files[0]


def transcribe_video(
    input_video: Path,
) -> Path:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vod_id = input_video.stem

    output_file = (
        OUTPUT_DIR / f"{vod_id}.json"
    )

    print(
        f"VOD ID: {vod_id}"
    )

    print(
        f"Loading Whisper model: "
        f"{MODEL_NAME}"
    )

    model = whisper.load_model(
        MODEL_NAME
    )

    print(
        f"Transcribing: {input_video}"
    )

    # =====================================================================
    # 1. PARÁMETROS BLINDADOS PARA WHISPER ORIGINAL DE OPENAI
    # =====================================================================
    result = model.transcribe(
        str(input_video),
        language="es",                  # Fuerza el idioma español nativo
        fp16=False,                     # Evita errores de precisión en CPU de GitHub
        verbose=True,
        beam_size=3,                    # Reduce la carga de memoria RAM en GitHub
        temperature=(0.0, 0.2, 0.4),    # Ajusta la creatividad si hay estática o música
        compression_ratio_threshold=2.4 # Frena bucles infinitos de texto basura repetitivo
    )

    text_final = result.get("text", "")

    # =====================================================================
    # 2. FILTRO UNIVERSAL ANTIALUCINACIÓN ANTES DE GUARDAR
    # =====================================================================
    texto_limpio = text_final.strip()
    palabras = texto_limpio.split()

    letras_unicas = set(texto_limpio.replace(" ", "").upper())
    palabras_unicas = set(palabras)
    ratio_repeticion = len(palabras_unicas) / max(1, len(palabras))

    es_basura = False

    # Condición A: El texto es largo pero usa menos de 3 letras distintas (ej: "YYYYYYY")
    if len(texto_limpio) > 10 and len(letras_unicas) <= 2:
        es_basura = True

    # Condición B: Repite tanto la misma palabra que no hay variedad (ej: "Thanks for watching...")
    elif len(palabras) > 10 and ratio_repeticion < 0.15:
        es_basura = True

    if es_basura:
        print("\n⚠️ ERROR CRÍTICO: Se ha detectado una transcripción corrupta o en bucle infinito.")
        print("Forzando la creación de un manifiesto vacío para notificar correctamente a Telegram.")
        
        # Escribimos el manifiesto vacío en la carpeta de clips para activar la alerta del bot
        clips_dir = Path(f"data/clips/{vod_id}")
        clips_dir.mkdir(parents=True, exist_ok=True)
        
        with open(clips_dir / "clips_manifest.json", "w", encoding="utf-8") as f:
            json.dump({"vod_id": vod_id, "clips": []}, f)
            
        print("✅ Manifiesto vacío generado. Abortando pipeline de forma segura.")
        sys.exit(0) # Salimos limpiamente para que continúe el flujo hacia el script de Telegram

    # Si el texto es válido, continúa el flujo normal de tu script original:
    output = {
        "vod_id": vod_id,
        "video": str(input_video),
        "model": MODEL_NAME,
        "language": result.get(
            "language",
            "unknown",
        ),
        "text": text_final,
        "segments": result.get(
            "segments",
            [],
        ),
    }

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        "Whisper transcription completed."
    )
    print(
        f"Output: {output_file}"
    )
    print(
        f"Detected language: "
        f"{output['language']}"
    )
    print(
        f"Segments: "
        f"{len(output['segments'])}"
    )
    print()
    print("Transcription:")
    print(output["text"])

    return output_file


def main() -> int:
    try:
        input_video = find_vod()

        transcribe_video(
            input_video
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
