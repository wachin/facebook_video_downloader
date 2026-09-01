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

# JavaScript que recopila los vídeos de la página actual de Facebook.
# Se inyecta en la ventana de la app (botón flotante) y también se ofrece como
# bookmarklet para usar desde el navegador normal.
#
# Diseño "auto-curativo": Facebook (SPA de React) elimina los nodos del DOM que
# no conoce al re-renderizar, así que un setInterval comprueba cada 1.5 s si el
# botón sigue en la página y, si no, lo vuelve a crear. Así el botón sobrevive
# a la navegación interna de Facebook (login, colecciones, etc.).
#
# Botones:
#  - «⬇️ Descargar toda la colección»: hace auto-scroll por la colección
#    (Facebook carga más vídeos al llegar abajo), recopila todas las URLs y las
#    envía con `download: true` para que el servidor arranque yt-dlp con toda
#    la colección de una vez.
#  - «📥 Enviar vídeos visibles»: solo los vídeos actualmente en pantalla.
#  - «↩ Cerrar Facebook»: cierra la ventana de Facebook (Facebook Collections Downloader sigue
#    abierto en su propia ventana).
def build_capture_script(server_url: str) -> str:
    return r"""
(function () {
  // Este script se inyecta como *user script* de WebKit, que se ejecuta en
  // TODAS las páginas (también en la propia app). Solo debe actuar en
  // Facebook, así que salimos en cualquier otro sitio.
  if (location.hostname.indexOf('facebook.com') < 0) return;

  // Facebook impone un Content-Security-Policy sin 'unsafe-eval', así que
  // pywebview no consigue inyectar su puente JS (window.pywebview) en estas
  // páginas. No importa para ENVIAR (el canal nativo jsBridge está registrado
  // en la propia ventana), pero pywebview intenta entregar el valor de retorno
  // con window.pywebview._returnValuesCallbacks y falla con un traceback.
  // Este stub hace que esa entrega sea un no-op silencioso y, además, construye
  // window.pywebview.api reenviando cada llamada por jsBridge (así el botón
  // «↩ Cerrar Facebook» puede hablar con Python).
  if (!window.pywebview || !window.pywebview._returnValuesCallbacks) {
    var _noop = function () {};
    window.pywebview = window.pywebview || {};
    window.pywebview._returnValuesCallbacks = new Proxy({}, {
      get: function () { return new Proxy({}, { get: function () { return _noop; } }); }
    });
    if (!window.pywebview.api) {
      window.pywebview.api = new Proxy({}, {
        get: function (_, name) {
          return function () {
            var args = [].slice.call(arguments);
            if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jsBridge) {
              window.webkit.messageHandlers.jsBridge.postMessage(JSON.stringify({
                funcName: String(name),
                params: args,
                id: 'c' + Date.now() + '_' + Math.floor(Math.random() * 1e6)
              }));
            }
            return Promise.resolve();
          };
        }
      });
    }
  }

  // Id único del contenedor del botón. Se usa para saber si el botón sigue en
  // el DOM (si no, es que React lo borró y hay que recrearlo).
  var BTN_ID = '__recetario_fb_btn';
  var RUNNING = false;   // ¿una recopilación de colección está en curso?

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
    document.querySelectorAll('a[href*="/watch/"], a[href*="/reel/"], a[href*="/videos/"], a[href*="/photo/"], a[href*="fb.watch"]').forEach(function (a) {
      if (a.href && a.href.indexOf('facebook.com') > -1) urls.add(a.href);
    });
    return Array.from(urls);
  }

  function toast(msg, err) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:80px;right:16px;z-index:2147483647;background:' + (err ? '#dc3545' : '#198754') + ';color:#fff;padding:10px 16px;border-radius:8px;font:14px sans-serif;box-shadow:0 4px 12px rgba(0,0,0,.4);';
    if (document.body) document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 4200);
  }

  // Caja de estado de la recopilación (progreso + botón Detener).
  function statusBox() {
    var st = document.getElementById('__recetario_fb_status');
    if (!st) {
      st = document.createElement('div');
      st.id = '__recetario_fb_status';
      st.style.cssText = 'position:fixed;bottom:150px;right:16px;z-index:2147483647;display:none;align-items:center;gap:10px;background:#0b1220;color:#fff;padding:10px 14px;border-radius:8px;font:13px sans-serif;box-shadow:0 4px 12px rgba(0,0,0,.5);';
      var txt = document.createElement('span');
      txt.id = '__recetario_fb_status_text';
      var stop = document.createElement('button');
      stop.textContent = 'Detener';
      stop.style.cssText = 'border:0;background:#e05252;color:#fff;border-radius:6px;padding:4px 10px;font:12px sans-serif;cursor:pointer;';
      st.appendChild(txt);
      st.appendChild(stop);
      if (document.body) document.body.appendChild(st);
    }
    return st;
  }

  function send(urls, download) {
    if (!urls.length) { toast('No se encontraron vídeos en esta página. Desplázate y vuelve a pulsar.', true); return; }
    var n = urls.length;
    var msg = '✓ ' + n + ' vídeo' + (n === 1 ? '' : 's') +
      (download ? ' — ¡descargando la colección! El progreso está en Facebook Collections Downloader' : ' enviado' + (n === 1 ? '' : 's') + ' a Facebook Collections Downloader');

    // 1) Canal nativo (ventana de la app): el mensaje va DIRECTO a Python por
    // el puente de WebKit (script message handler 'jsBridge' de pywebview,
    // registrado al crear la ventana), sin pasar por HTTP. Facebook impone un
    // Content-Security-Policy que bloquea el fetch hacia 127.0.0.1 (solo
    // permite ws://localhost), así que esta es la vía fiable: ni CSP, ni
    // CORS, ni el contenido mixto pueden bloquearla.
    if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jsBridge) {
      window.webkit.messageHandlers.jsBridge.postMessage(JSON.stringify({
        funcName: 'capture_urls',
        params: [urls, !!download],
        id: 'c' + Date.now()
      }));
      toast(msg);
      return;
    }
    // 2) Puente clásico de pywebview (si la página lo tiene disponible).
    if (window.pywebview && window.pywebview.api && window.pywebview.api.capture_urls) {
      window.pywebview.api.capture_urls(urls, !!download);
      toast(msg);
      return;
    }
    // 3) Último recurso: fetch normal (bookmarklet en navegador externo).
    // Ojo: el CSP de Facebook también bloquea este fetch en navegadores
    // externos; el flujo recomendado es la ventana nativa de la app.
    fetch(%(url)r + '/api/fb/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: urls, download: !!download })
    }).then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.download && !j.download.ok) { toast(j.download.message, true); return; }
        if (j.added) {
          toast('✓ ' + j.added + ' vídeo' + (j.added === 1 ? '' : 's') +
            (j.download && j.download.ok ? ' — ¡descargando la colección!' : ' enviado' + (j.added === 1 ? '' : 's') + ' a Facebook Collections Downloader'));
        } else {
          toast('Sin vídeos nuevos (ya estaban capturados).');
        }
      })
      .catch(function () { toast('Error al enviar. ¿Está Facebook Collections Downloader abierto?', true); });
  }

  // Baja el scroll de la ventana (y, si no funciona, del contenedor interno
  // más alto) para que Facebook cargue los siguientes vídeos de la colección.
  // En Facebook de escritorio el scroll es de la ventana; el contenedor
  // interno es el plan B para páginas con scroll propio (se cachea para no
  // volver a escanear todos los divs en cada vuelta).
  var innerScroll = null;
  function scrollDown() {
    var before = window.scrollY;
    var se = document.scrollingElement || document.documentElement;
    se.scrollTop = se.scrollHeight;
    window.scrollTo(0, se.scrollHeight);
    if (Math.abs(window.scrollY - before) < 10) {
      if (!innerScroll) {
        var best = null, bestH = 0;
        var divs = document.querySelectorAll('div');
        for (var i = 0; i < divs.length; i++) {
          var d = divs[i];
          if (d.scrollHeight - d.clientHeight > 200 && d.scrollHeight > bestH) {
            bestH = d.scrollHeight;
            best = d;
          }
        }
        innerScroll = best;
      }
      if (innerScroll) innerScroll.scrollTop = innerScroll.scrollHeight;
    }
  }

  // Recopila TODA la colección: baja el scroll repetidamente y junta las URLs
  // de los vídeos. Termina cuando no aparecen vídeos nuevos tras varios
  // intentos (o al pulsar Detener), y entonces envía todo con `download: true`.
  function downloadCollection() {
    if (RUNNING) { toast('Ya se está recopilando la colección…'); return; }
    RUNNING = true;
    var found = new Set();
    var emptyRounds = 0;
    var rounds = 0;
    var stopped = false;
    var MAX_ROUNDS = 60;    // ~2 minutos como máximo
    var MAX_VIDEOS = 500;   // tope de seguridad

    var st = statusBox();
    var txt = document.getElementById('__recetario_fb_status_text');
    var stopBtn = st.querySelector('button');
    st.style.display = 'flex';
    txt.textContent = 'Recopilando colección… 0 vídeos';
    stopBtn.onclick = function () { stopped = true; txt.textContent = 'Deteniendo…'; };

    function update() {
      txt.textContent = 'Recopilando colección… ' + found.size + ' vídeo' + (found.size === 1 ? '' : 's');
    }
    function finish() {
      RUNNING = false;
      st.style.display = 'none';
      if (!found.size) { toast('No se encontraron vídeos en esta colección.'); return; }
      send(Array.from(found), true);
    }

    function grab() { collect().forEach(function (u) { found.add(u); }); }

    grab();
    scrollDown();
    var timer = setInterval(function () {
      if (stopped) { clearInterval(timer); finish(); return; }
      rounds++;
      if (rounds >= MAX_ROUNDS || found.size >= MAX_VIDEOS) { clearInterval(timer); finish(); return; }
      var before = found.size;
      grab();
      if (found.size > before) {
        emptyRounds = 0;
        update();
      } else {
        emptyRounds++;
        if (emptyRounds >= 4) { clearInterval(timer); finish(); return; }
      }
      scrollDown();
    }, 1800);
  }

  function goHome() {
    // Dentro de la ventana de la app, el canal nativo jsBridge está disponible:
    // cerramos la ventana de Facebook (Facebook Collections Downloader sigue abierto). En un
    // navegador externo (bookmarklet) navegamos a la app como respaldo.
    if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jsBridge) {
      window.pywebview.api.go_home();
    } else {
      location.href = %(url)r + '/?tab=facebook';
    }
  }

  // Crea el panel de botones si no está ya en la página. Idempotente: si
  // existe, no hace nada. Se llama al inyectar y desde el vigilante interno
  // cada 1.5 s.
  function ensureButton() {
    if (!document.body) return;             // la página aún carga; reintentará
    if (document.getElementById(BTN_ID)) return;
    var d = document.createElement('div');
    d.id = BTN_ID;
    d.style.cssText = 'position:fixed;bottom:16px;right:16px;z-index:2147483647;display:flex;flex-direction:column;gap:8px;font-family:sans-serif;';
    var b1 = document.createElement('button');
    b1.textContent = '⬇️ Descargar toda la colección';
    b1.style.cssText = 'border:0;background:#d97706;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.4);';
    b1.onclick = downloadCollection;
    var b2 = document.createElement('button');
    b2.textContent = '📥 Enviar vídeos visibles';
    b2.style.cssText = 'border:0;background:#4b5563;color:#fff;padding:8px 14px;border-radius:8px;font-size:12.5px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.4);';
    b2.onclick = function () { send(collect(), false); };
    var b3 = document.createElement('button');
    b3.textContent = '↩ Cerrar Facebook';
    b3.style.cssText = 'border:0;background:#111827;color:#fff;padding:8px 14px;border-radius:8px;font-size:13px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.4);';
    b3.onclick = goHome;
    d.appendChild(b1);
    d.appendChild(b2);
    d.appendChild(b3);
    document.body.appendChild(d);
  }

  // Arranca una sola vez el vigilante que re-crea el botón si React lo borra.
  if (!window.__recetarioFBInterval) {
    window.__recetarioFBInterval = setInterval(ensureButton, 1500);
  }
  ensureButton();
})();
""" % {"url": server_url}


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


def write_cookies_netscape(cookies, path) -> int:
    """Escribe cookies (listas de `SimpleCookie` de pywebview, como las devuelve
    `window.get_cookies()`) en formato Netscape, el que espera
    `yt-dlp --cookies`. Devuelve cuántas cookies se escribieron.

    Las colecciones guardadas de Facebook son privadas: sus vídeos solo se
    descargan con la sesión iniciada, y yt-dlp necesita estas cookies para
    poder descargarlos (no ve el navegador).
    """
    lines = ["# Netscape HTTP Cookie File", "# Generado por Facebook Collections Downloader", ""]
    written = 0
    for cookie in cookies:
        try:
            for name, morsel in cookie.items():
                domain = str(morsel.get("domain") or "")
                if not domain:
                    continue
                if not domain.startswith("."):
                    domain = "." + domain
                cookie_path = str(morsel.get("path") or "/")
                secure = "TRUE" if str(morsel.get("secure") or "").lower() == "true" else "FALSE"
                expires = morsel.get("expires")
                try:
                    exp = int(expires) if expires else 0
                except (TypeError, ValueError):
                    exp = 0
                lines.append(
                    f"{domain}\tTRUE\t{cookie_path}\t{secure}\t{exp}\t{name}\t{morsel.value}"
                )
                written += 1
        except Exception:
            continue
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


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
        # Cookies de la sesión de Facebook: necesarias para descargar los
        # vídeos de colecciones privadas (guardados). Se exportan desde el
        # webview en cada captura (ver Api.capture_urls en app/window.py).
        cookies_file = config.DATA_DIR / "cookies" / "fb_cookies.txt"
        if cookies_file.exists():
            cmd += ["--cookies", str(cookies_file)]
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
