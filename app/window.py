"""Puente con la ventana nativa (pywebview).

Los métodos de esta clase quedan disponibles en el frontend como
`window.pywebview.api.<método>()` cuando la app corre en modo ventana nativa.

Facebook se abre en una **segunda ventana** independiente: Facebook Collections Downloader se
queda abierto en su propia ventana para que puedas ver el progreso de las
descargas mientras navegas por Facebook. Ambas ventanas comparten el MISMO
objeto Api (se pasa `js_api=self` a las dos), así que el canal nativo de WebKit
(`jsBridge`) de la ventana de Facebook llama a los mismos métodos
(`capture_urls`, `go_home`…).

El botón flotante que se inyecta en las páginas de Facebook envía los vídeos
por el **canal nativo de WebKit** (`jsBridge`, el puente interno de pywebview
registrado al crear cada ventana), que llega directo a Python sin pasar por
HTTP. Es la única vía que el Content-Security-Policy de Facebook no bloquea
(prohíbe el fetch hacia 127.0.0.1).
"""
import importlib
import os
import subprocess
import threading
import time
import webbrowser

import webview

from . import config, database as db, fb

FB_URL = "https://www.facebook.com/saved/"

# Retraso antes de navegar (segundos). La página de la app registra un
# callback en el puente de pywebview cuando el frontend llama a un método API;
# si la ventana cambia de URL en ese mismo instante, el callback se pierde y
# pywebview lanza JavascriptException. Un pequeño retraso permite que el valor
# de retorno llegue al frontend antes de empezar la navegación.
NAV_DELAY = 1.0


class Api:
    def __init__(self, app_url: str = "http://127.0.0.1:8000/") -> None:
        self.app_url = app_url.rstrip("/") + "/"
        # Ventana de Facebook (segunda ventana). Facebook Collections Downloader vive en su propia
        # ventana y nunca se cierra al abrir Facebook.
        self._fb_window: webview.Window | None = None
        self._fb_opening = False   # evita abrir dos ventanas con clics seguidos
        # Conjuntos de uids: el inyector y el user script se arman POR VENTANA.
        self._injector_armed: set = set()
        self._user_script_windows: set = set()

    # ------------------------------------------------------ utilidades

    def pick_folder(self) -> str | None:
        """Abre el diálogo nativo para elegir la carpeta de vídeos."""
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(webview.FOLDER_DIALOG)
            return result[0] if result else None
        except Exception:
            return None

    def reveal_in_file_manager(self, path: str) -> bool:
        """Abre la carpeta del archivo en el gestor de archivos del sistema."""
        try:
            if not path or not os.path.exists(path):
                return False
            target = os.path.dirname(path) if os.path.isfile(path) else path
            subprocess.Popen(["xdg-open", target])
            return True
        except Exception:
            return False

    # ------------------------------------------------------ Facebook

    def open_facebook(self) -> bool:
        """Abre Facebook en una ventana NUEVA, sin cerrar Facebook Collections Downloader.

        Devuelve `True` de inmediato (para que pywebview entregue el valor de
        retorno al frontend de la app) y la apertura se lanza desde un hilo:
        se crea la ventana de Facebook, se le instala el user script y se
        navega a la página de guardados.
        """
        try:
            win = self._fb_window
            if win is not None and not win.events.closed.is_set():
                # La ventana de Facebook ya existe: solo la llevamos de nuevo a
                # la página de guardados (por si el usuario navegó a otro sitio).
                threading.Thread(
                    target=self._navigate_later, args=(win, FB_URL), daemon=True
                ).start()
                return True
            if self._fb_opening:
                return True  # ya se está abriendo (evita ventanas duplicadas)
            self._fb_opening = True
            threading.Thread(target=self._open_fb_window, daemon=True).start()
            return True
        except Exception:
            webbrowser.open(FB_URL)
            return False

    def go_home(self) -> None:
        """Cierra la ventana de Facebook; Facebook Collections Downloader sigue abierto.

        El botón «↩ Cerrar Facebook» de la página de Facebook la invoca por el
        canal nativo jsBridge. Si no hay ventana de Facebook (modo navegador),
        vuelve a la pestaña de Facebook de la app como respaldo.
        """
        win = self._fb_window
        self._fb_window = None
        if win is not None and not win.events.closed.is_set():
            threading.Thread(
                target=self._close_fb_window_later, args=(win,), daemon=True
            ).start()
            return
        try:
            window = webview.windows[0]
            threading.Thread(
                target=self._navigate_later,
                args=(window, self.app_url + "?tab=facebook"),
                daemon=True,
            ).start()
        except Exception:
            webbrowser.open(self.app_url + "?tab=facebook")

    def capture_now(self) -> bool:
        """Garantiza que el botón flotante esté armado en la ventana de Facebook.

        La inyección ya es automática (user script de WebKit en cada página de
        Facebook + auto-reparación interna del propio script), así que este
        método solo se asegura de que el mecanismo esté activo.
        """
        win = self._fb_window
        if win is None or win.events.closed.is_set():
            return False
        try:
            self._arm_injector(win)
            return True
        except Exception:
            return False

    def capture_urls(self, urls, download: bool = False) -> dict:
        """Recibe las URLs capturadas desde una página de Facebook.

        Llega por el canal nativo de WebKit (`jsBridge`, el puente interno de
        pywebview que está registrado en la propia ventana), nunca por HTTP,
        así que no lo bloquean ni el CSP de Facebook ni el contenido mixto.
        Con `download: true` arranca yt-dlp con los vídeos recién capturados y
        refresca las cookies de la sesión (necesarias para las colecciones
        privadas).
        """
        urls = [u for u in (urls or []) if isinstance(u, str)]
        before = {r["id"] for r in db.fb_list()}
        added = db.fb_add_urls(urls)
        result = {"ok": True, "added": added}
        if download:
            ids = [r["id"] for r in db.fb_list() if r["id"] not in before]
            if ids:
                self._refresh_cookies()
                ok, message = fb.downloader.start(ids)
                result["download"] = {"ok": ok, "message": message}
        return result

    def _refresh_cookies(self) -> None:
        """Exporta las cookies de la sesión de Facebook (la página actual del
        webview) a un archivo Netscape para que yt-dlp pueda descargar los
        vídeos privados de las colecciones guardadas."""
        try:
            win = self._fb_window
            if win is None or win.events.closed.is_set():
                win = webview.windows[0]
            cookies = win.get_cookies()
            path = config.DATA_DIR / "cookies" / "fb_cookies.txt"
            written = fb.write_cookies_netscape(cookies, path)
            print(f"[Facebook] cookies de sesión exportadas ({written})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[Facebook] aviso: no se pudieron exportar las cookies: {exc}", flush=True)

    # ------------------------------------------------------ interno

    def _open_fb_window(self) -> None:
        """Crea la ventana de Facebook (desde un hilo, tras entregar el valor de
        retorno) y la deja lista: user script instalado + navegación a la
        página de guardados.

        La ventana se crea con `js_api=self` (el MISMO Api que la ventana de la
        app): así el canal nativo jsBridge de esta ventana llama a los mismos
        métodos (capture_urls, go_home…).
        """
        try:
            win = webview.create_window(
                "Facebook — Facebook Collections Downloader",
                self.app_url,
                js_api=self,
                width=1280,
                height=820,
                min_size=(900, 600),
                background_color="#171009",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[Facebook] no se pudo abrir la ventana: {exc}", flush=True)
            webbrowser.open(FB_URL)
            self._fb_opening = False
            return
        if win is None:
            self._fb_opening = False
            return
        self._fb_window = win
        # El BrowserView (con el WebView dentro) se crea con glib.idle_add, así
        # que esperamos a que exista antes de instalar el user script.
        gtk_platform = None
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                gtk_platform = importlib.import_module("webview.platforms.gtk")
                if gtk_platform.BrowserView.instances.get(win.uid) is not None:
                    break
            except Exception:
                pass
            time.sleep(0.1)
        if gtk_platform is None or gtk_platform.BrowserView.instances.get(win.uid) is None:
            print("[Facebook] aviso: no se pudo armar la ventana de Facebook", flush=True)
            self._fb_opening = False
            return
        self._fb_opening = False
        self._arm_injector(win)
        # Esperamos a que el user script quede instalado antes de navegar a
        # Facebook (debe ejecutarse al cargar la página).
        deadline = time.time() + 5
        while time.time() < deadline and win.uid not in self._user_script_windows:
            time.sleep(0.05)
        try:
            from gi.repository import GLib

            GLib.idle_add(win.load_url, FB_URL)
        except Exception:
            try:
                win.load_url(FB_URL)
            except Exception:
                pass

    def _close_fb_window_later(self, win) -> None:
        """Espera un instante (para que pywebview entregue el valor de retorno de
        la llamada que originó el cierre) y destruye la ventana de Facebook."""
        time.sleep(0.8)
        try:
            win.destroy()
        except Exception:
            pass

    def _navigate_later(self, window, url: str) -> None:
        """Espera un instante y navega, dejando tiempo a pywebview para
        entregar el valor de retorno de la llamada API que originó la
        navegación (evita JavascriptException por callback perdido).

        `load_url` toca WebKitGTK, que solo es seguro desde el hilo principal:
        se programa con `GLib.idle_add` (igual que hace el propio pywebview)
        para evitar cierres/segfaults con páginas pesadas.
        """
        time.sleep(NAV_DELAY)
        try:
            from gi.repository import GLib

            GLib.idle_add(window.load_url, url)
        except Exception:
            try:
                window.load_url(url)
            except Exception:
                pass

    def _arm_injector(self, window) -> None:
        """Activa la inyección del botón flotante en una ventana (una sola vez).

        El mecanismo es el **user script de WebKit**: el script se registra
        para ejecutarse en CADA página que cargue la ventana y, gracias al
        guard interno, solo actúa en Facebook. Cubre todas las cargas completas
        de página (login, colecciones, etc.); dentro de la SPA el propio script
        se auto-repara con su setInterval si React borra el botón.

        No se usa `run_js` ni el evento `loaded` de pywebview: en esta versión
        de pywebview, `run_js` trunca los scripts con caracteres no ASCII
        (pasa `len()` como si fueran bytes) y genera errores en la terminal.
        """
        if window.uid in self._injector_armed:
            return
        self._injector_armed.add(window.uid)
        # La instalación toca WebKitGTK (UserScript + add_script), que solo es
        # seguro desde el hilo principal; este método se invoca desde el hilo
        # del puente jsBridge, así que se programa con GLib.idle_add.
        try:
            from gi.repository import GLib

            GLib.idle_add(self._install_user_script, window)
        except Exception:
            self._install_user_script(window)

    def _install_user_script(self, window) -> None:
        """Registra el script de captura como *user script* de WebKit.

        Se ejecuta en document-start de cada página que cargue la ventana (con
        el guard de `build_capture_script` solo actúa en Facebook). Así el
        botón aparece aunque `run_js` o el puente de pywebview fallen en
        Facebook, que es donde antes se rompía.

        El WebKitWebView no está en `window.gui` (que es el módulo GTK de
        pywebview) sino en `BrowserView.instances[uid].webview`; se accede con
        importlib para no forzar la carga de la plataforma GTK en el import.
        """
        if window.uid in self._user_script_windows:
            return
        try:
            gtk_platform = importlib.import_module("webview.platforms.gtk")
            bview = gtk_platform.BrowserView.instances.get(window.uid)
            if bview is None:
                print("[Facebook] aviso: vista WebKit no encontrada", flush=True)
                return
            widget = bview.webview
            manager = widget.get_user_content_manager()
            script = gtk_platform.webkit.UserScript.new(
                fb.build_capture_script(self.app_url.rstrip("/")),
                gtk_platform.webkit.UserContentInjectedFrames.TOP_FRAME,
                gtk_platform.webkit.UserScriptInjectionTime.START,
                [],
                [],
            )
            manager.add_script(script)
            self._user_script_windows.add(window.uid)
            print(f"[Facebook] user script instalado (ventana {window.uid})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[Facebook] aviso: no se pudo instalar el user script: {exc}", flush=True)


