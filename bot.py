import json
import os
import time
import urllib.parse
import urllib.request

# Variables de entorno
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GH_TOKEN = os.environ.get("CROSS_REPO_TOKEN")
REPO_FULL = os.environ.get("GITHUB_REPOSITORY", "KuraiMure57/twitch-vod-clip-agent")

if not BOT_TOKEN or not CHAT_ID or not GH_TOKEN:
    print("❌ ERROR: Faltan variables de entorno esenciales.")
    exit(1)

print("🚀 Bot iniciado correctamente en la nube. Escuchando 24/7...")

def send_telegram_message(text):
    """Envía un mensaje de texto plano al chat autorizado de Telegram."""
    try:
        url = f"https://telegram.org{BOT_TOKEN}/sendMessage"
        payload = json.dumps({"chat_id": CHAT_ID, "text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("ok", False)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")
        return False
def is_pipeline_running():
    """Comprueba si el pipeline test.yml ya está ejecutándose en GitHub."""
    # Realiza una petición a la API de GitHub para verificar si hay ejecuciones activas (queued, in_progress, etc.)
    # Puedes encontrar el código completo de esta función en los documentos referenciados.
    pass

def get_latest_run_status():
    """Consulta cómo terminó el último flujo ejecutado."""
    # Consulta el último estado del workflow y devuelve un mensaje formateado según el resultado (éxito, fallo, en proceso).
    # Puedes encontrar el código completo de esta función en los documentos referenciados.
    pass

def launch_pipeline():
    """Lanza el workflow test.yml de GitHub Actions."""
    # Realiza una petición POST a la API de GitHub para despachar el workflow en la rama principal.
    # Puedes encontrar el código completo de esta función en los documentos referenciados.
    pass
def main_polling_loop():
    """Bucle infinito que consulta la API de Telegram cada 5 segundos."""
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
                time.sleep(5)
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
