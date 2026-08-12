"""Importador guiado de vídeos de Facebook.

Flujo (sin guardar credenciales en ningún sitio):
1. El usuario abre Facebook desde la app y **inicia sesión él mismo** (con su
   2FA normal) en la ventana de la app o en su navegador.
2. En su página de *guardados*, un botón flotante (o un bookmarklet) recopila
   las URLs de los vídeos visibles y las envía al servidor local.
3. Aquí se descargan con `yt-dlp` a la carpeta de vídeos y se escanea de nuevo.

El servidor solo escucha en 127.0.0.1 y las descargas solo se inician con un
clic del usuario en la interfaz de la propia app.
"""
import os
import pathlib
import re
import shutil
import subprocess
import threading
import time

from . import config, database as db, scanner

# JavaScript que recopila los vídeos visibles de la página actual de Facebook.
# Se inyecta en la ventana de la app (botón flotante) y también se ofrece como
# bookmarklet para usar desde el navegador normal.
def build_capture_script(server_url: str) -> str:
    return r"""
(function () {
  if (window.__recetarioFB) return;
  window.__recetarioFB = true;

  function collect() {
    var urls = new Set();
    document.querySelectorAll('video').forEach(function (v) {
      var s = v.currentSrc || v.src;
      if (!s) {
        var src = v.querySelector('source');
        if (src && src.src) s = src.src;
      }
      if (s && s.indexOf('http') === 0) urls.add(s);
    });
    document.querySelectorAll('a[href*="/watch/"], a[href*="/reel/"], a[href*="/videos/"], a[href*="/photo/"]').forEach(function (a) {
      if (a.href && a.href.indexOf('facebook.com') > -1) urls.add(a.href);
    });
    return Array.from(urls);
  }

  function toast(msg) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:80px;right:16px;z-index:2147483647;background:#198754;color:#fff;padding:10px 16px;border-radius:8px;font:14px sans-serif;box-shadow:0 4px 12px rgba(0,0,0,.4);';
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3500);
  }

  function send() {
    var urls = collect();
    if (!urls.length) { toast('No se encontraron vídeos en esta página. Desplázate y vuelve a pulsar.'); return; }
    fetch(%(url)r + '/api/fb/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: urls })
    }).then(function (r) { return r.json(); })
      .then(function (j) { toast('✓ Enviados ' + (j.added || 0) + ' vídeos a Mi Recetario'); })
      .catch(function () { toast('Error al enviar. ¿Está Mi Recetario abierto?'); });
  }

  function goHome() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.go_home) {
      window.pywebview.api.go_home();
    } else {
      location.href = %(url)r + '/?tab=facebook';
    }
  }

  var d = document.createElement('div');
  d.style.cssText = 'position:fixed;bottom:16px;right:16px;z-index:2147483647;display:flex;flex-direction:column;gap:8px;font-family:sans-serif;';
  var b1 = document.createElement('button');
  b1.textContent = '📥 Enviar vídeos a Mi Recetario';
  b1.style.cssText = 'border:0;background:#d97706;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.4);';
  b1.onclick = send;
  var b2 = document.createElement('button');
  b2.textContent = '↩ Volver a Mi Recetario';
  b2.style.cssText = 'border:0;background:#111827;color:#fff;padding:8px 14px;border-radius:8px;font-size:13px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.4);';
  b2.onclick = goHome;
  d.appendChild(b1);
  d.appendChild(b2);
  document.body.appendChild(d);
})();
""" % {"url": server_url}


def bookmarklet(server_url: str) -> str:
    """Versión bookmarklet (para usar desde el navegador normal)."""
    js = build_capture_script(server_url)
    return "javascript:(function(){" + js.replace("\n", "") + "})();"


def find_ytdlp() -> str | None:
    """Localiza el binario de yt-dlp (instalado por apt, pipx o pip)."""
    found = shutil.which("yt-dlp")
    if found:
        return found
    for candidate in (
        pathlib.Path.home() / ".local" / "bin" / "yt-dlp",
        pathlib.Path("/usr/local/bin/yt-dlp"),
        pathlib.Path("/usr/bin/yt-dlp"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


class _Cancelled(Exception):
    """Descarga interrumpida por el usuario."""


class FbDownloader:
    """Cola de descargas con yt-dlp (una a la vez, con progreso por vídeo)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: dict | None = None

    def start(self, ids: list[int]) -> tuple[bool, str]:
        items = [db.fb_get(i) for i in ids if db.fb_get(i)]
        with self._lock:
            if self._job and self._job["running"]:
                return False, "Ya hay una descarga en curso."
            if not items:
                return False, "Selecciona al menos un vídeo."
            job = {
                "running": True,
                "cancelled": False,
                "items": [
                    {
                        "url": it["url"],
                        "kind": it["kind"],
                        "title": it["title"] or "Vídeo de Facebook",
                        "status": "queued",
                        "progress": 0.0,
                        "error": "",
                        "filename": "",
                    }
                    for it in items
                ],
            }
            self._job = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return True, f"Descargando {len(job['items'])} vídeo(s)…"

    def status(self) -> dict:
        with self._lock:
            if not self._job:
                return {"running": False, "items": []}
            return {"running": self._job["running"], "items": list(self._job["items"])}

    def cancel(self) -> bool:
        with self._lock:
            if self._job and self._job["running"]:
                self._job["cancelled"] = True
                return True
        return False

    # ------------------------------------------------------------ interno

    def _run(self, job: dict) -> None:
        try:
            for item in job["items"]:
                if job["cancelled"]:
                    item["status"] = "cancelled"
                    continue
                item["status"] = "downloading"
                item["progress"] = 0.0
                item["error"] = ""
                try:
                    out = self._download(job, item)
                    item["status"] = "done"
                    item["filename"] = out
                except _Cancelled:
                    item["status"] = "cancelled"
                except Exception as exc:  # noqa: BLE001
                    item["status"] = "error"
                    item["error"] = str(exc)[:300]
            if not job["cancelled"]:
                # Los vídeos nuevos quedan listos en la Biblioteca.
                scanner.scan()
        finally:
            with self._lock:
                job["running"] = False

    def _download(self, job: dict, item: dict) -> str:
        url = item["url"]
        if not url.startswith(("http://", "https://")):
            raise RuntimeError("URL no válida: solo se admiten enlaces http(s).")
        ytdlp = find_ytdlp()
        if not ytdlp:
            raise RuntimeError(
                "No se encuentra yt-dlp. Instálalo con: sudo apt install yt-dlp"
            )
        folder = config.settings.get("watch_folder", "")
        if not folder:
            raise RuntimeError("Define primero la carpeta de vídeos en Ajustes.")
        os.makedirs(folder, exist_ok=True)
        cmd = [
            ytdlp,
            "--no-playlist",
            "--no-warnings",
            "--newline",
            "--retries", "3",
            "--print", "after_move:filepath",
            "-o", os.path.join(folder, "%(title).80s [%(id)s].%(ext)s"),
            url,
        ]
        # yt-dlp es Python: con salida a tubería almacena en búfer y el
        # progreso no llega en vivo. PYTHONUNBUFFERED fuerza el volcado.
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=env,
        )

        # Vigilante: aplica la cancelación aunque yt-dlp no emita líneas de
        # progreso (su salida por tubería puede ir en búfer y no llegar al
        # bucle de lectura). Al morir el proceso, el bucle recibe EOF.
        def watchdog() -> None:
            while proc.poll() is None:
                if job["cancelled"]:
                    proc.terminate()
                    return
                time.sleep(0.3)

        threading.Thread(target=watchdog, daemon=True).start()

        assert proc.stdout is not None
        final = ""
        for line in proc.stdout:
            match = re.search(r"\[download\]\s+([\d.]+)%", line)
            if match:
                item["progress"] = min(99.0, float(match.group(1)))
            line = line.strip()
            if line and not line.startswith("["):
                final = line  # --print after_move:filepath
        proc.wait()
        if proc.returncode == 0:
            item["progress"] = 100.0
            return os.path.basename(final) if final else ""
        if job["cancelled"]:
            raise _Cancelled()
        raise RuntimeError(f"yt-dlp falló (código {proc.returncode}). Revisa la URL.")


downloader = FbDownloader()
