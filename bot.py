import json
import os
import time
import urllib.parse
import urllib.request
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ============================================================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GH_TOKEN = os.environ.get("CROSS_REPO_TOKEN")
REPO_FULL = os.environ.get("GITHUB_REPOSITORY", "KuraiMure57/twitch-vod-clip-agent")

if not BOT_TOKEN or not CHAT_ID or not GH_TOKEN:
    print("❌ ERROR: Faltan variables de entorno esenciales.")
    exit(1)

# ============================================================
# SERVIDOR WEB FALSO PARA ENGAÑAR A RENDER (PLAN GRATUITO)
# ============================================================
class FakeServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass # Silenciar logs en la consola

def run_fake_server():
    port = 10000
    server = HTTPServer(("0.0.0.0", port), FakeServer)

    print(f"🌍 Servidor web falso escuchando en el puerto {port}")
    server.serve_forever()

# ============================================================
# FUNCIONES DE CONEXIÓN CON GITHUB ACTIONS
# ============================================================
def send_telegram_message(text):
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
    try:
        url = f"https://github.com{REPO_FULL}/actions/workflows/test.yml/runs?per_page=1"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            runs = data.get("workflow_runs", [])
            if not runs:
                return "ℹ️ No se encontraron ejecuciones previas del pipeline."
            last_run = runs[0]
            status = last_run.get("status")
            conclusion = last_run.get("conclusion")
            url_web = last_run.get("html_url")
            if status in {"queued", "in_progress", "waiting"}:
                return f"🟢 Estado: El pipeline está EN EJECUCIÓN actualmente.\nSíguelo aquí: {url_web}"
            if conclusion == "success":
                return "✅ Estado: El último pipeline finalizó con ÉXITO."
            if conclusion == "failure":
                return f"❌ Estado: El último pipeline FALLÓ.\nRevisa los logs aquí: {url_web}"
            return f"ℹ️ Estado: {status} | Conclusión: {conclusion}"
    except Exception as e:
        return f"⚠️ Error al consultar el estado en GitHub: {e}"

def launch_pipeline():
    try:
        url = f"https://github.com{REPO_FULL}/actions/workflows/test.yml/dispatches"
        payload = json.dumps({"ref": "main"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.getcode() == 204
    except Exception as e:
        print(f"Error lanzando pipeline: {e}")
        return False

# ============================================================
# BUCLE PRINCIPAL DE ESCUCHA DE TELEGRAM (POLLING)
# ============================================================
def main_polling_loop():
    offset = None
    threading.Thread(target=run_fake_server, daemon=True).start()
    print("🚀 Bot iniciado correctamente en la nube. Escuchando 24/7...")
    
    while True:
        try:
            url = f"https://telegram.org{BOT_TOKEN}/getUpdates?timeout=10"
            if offset:
                url += f"&offset={offset}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
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
    import threading
    threading.Thread(target=run_fake_server, daemon=True).start()
    main_polling_loop()
