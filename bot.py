import json
import os
import time
import urllib.parse
import urllib.request

# Variables de entorno indispensables y funciones iniciales del bot (configuración, envío de mensajes a Telegram y verificación de estado del pipeline en GitHub).
def is_pipeline_running():
    """Verifica si el pipeline test.yml ya está en curso."""
    try:
        url = f"https://github.com{REPO_FULL}/actions/workflows/test.yml/runs?per_page=20"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for r in data.get("workflow_runs", []):
                if r.get("status") in {"queued", "in_progress", "waiting", "requested", "pending"}:
                    return True
            return False
    except Exception as e:
        print(f"Error comprobando pipeline: {e}")
        return False
def get_latest_run_status():
    """Consulta el estado del último workflow ejecutado."""
    # ... código para consultar el estado del workflow en GitHub Actions ...
    pass

def launch_pipeline():
    """Lanza el workflow test.yml de GitHub Actions."""
    # ... código para realizar la petición POST y lanzar el pipeline ...
    pass
def main_polling_loop():
    """Bucle infinito que consulta la API de Telegram cada 4 segundos."""
    offset = None
    print("🤖 Escuchando comandos en Telegram...")
    while True:
        try:
            url = f"https://telegram.org{BOT_TOKEN}/getUpdates?timeout=10"
            if offset:
                url += f"&offset={offset}"
            req = urllib.request.Request(url, timeout=15)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                time.sleep(4)
                continue
            updates = data.get("result", [])
            for update in updates:
                update_id = update.get("update_id")
                if update_id:
                    offset = update_id + 1
                message = update.get("message")
                if not message:
                    continue
                chat_id = str(message.get("chat", {}).get("id", ""))
                if chat_id != CHAT_ID:
                    continue
                text = message.get("text", "").strip().lower()
                if text.startswith("/start"):
                    if is_pipeline_running():
                        send_telegram_message("🟢 El Proyecto 2 ya está procesando un VOD.\nNo se ha iniciado otro proceso.")
                    else:
                        if launch_pipeline():
                            send_telegram_message("🚀 Procesamiento iniciado.\nEl Proyecto 2 comenzará a descargar y analizar el último VOD.\nTe avisaré cuando termine.")
                        else:
                            send_telegram_message("❌ Error: No se pudo lanzar el pipeline de GitHub.")
                elif text.startswith("/estado"):
                    status_msg = get_latest_run_status()
                    send_telegram_message(status_msg)
                elif text.startswith("/help"):
                    send_telegram_message("📖 Comandos disponibles:\n\n/start → Inicia un nuevo procesamiento.\n/estado → Consulta el estado del procesamiento.\n/help → Muestra este menú.")
        except Exception as e:
            print(f"Error en el bucle principal: {e}")
        time.sleep(4)

if __name__ == "__main__":
    main_polling_loop()
