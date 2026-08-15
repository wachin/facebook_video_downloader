"""Puente con la ventana nativa (pywebview).

Los métodos de esta clase quedan disponibles en el frontend como
`window.pywebview.api.<método>()` cuando la app corre en modo ventana nativa.
"""
import os
import subprocess
import threading
import time
import webbrowser

import webview

from . import fb

FB_URL = "https://www.facebook.com/saved/"

# Retraso antes de navegar (segundos). La página de la app registra un
# callback en el puente de pywebview cuando el frontend llama a un método API;
# si la ventana cambia de URL en ese mismo instante, el callback se pierde y
# pywebview lanza JavascriptException. Un pequeño retraso permite que el valor
# de retorno llegue al frontend antes de empezar la navegación.
NAV_DELAY = 1.0

# Periodo del vigilante de Facebook (segundos). Facebook es una SPA: sus
# navegaciones internas (login → guardados, cambiar de colección, etc.) no
# disparan el evento `loaded` de pywebview, así que un hilo comprueba de vez en
# cuando si la ventana sigue en una página de Facebook y re-inyecta el botón.
# El script inyectado es idempotente (no duplica el botón), así que inyectar
# repetido es inocuo.
FB_WATCHDOG_PERIOD = 2.0


class Api:
    def __init__(self, app_url: str = "http://127.0.0.1:8000/") -> None:
        self.app_url = app_url.rstrip("/") + "/"
        self._injector_armed = False
        self._watchdog_started = False

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
        """Abre Facebook (página de guardados) en la propia ventana.

        No navega de forma síncrona: devuelve `True` de inmediato (para que
        pywebview entregue el valor de retorno al frontend de la app) y la
        navegación se lanza desde un hilo con un pequeño retraso.
        """
        try:
            window = webview.windows[0]
            self._arm_injector(window)
            threading.Thread(
                target=self._navigate_later, args=(window, FB_URL), daemon=True
            ).start()
            return True
        except Exception:
            webbrowser.open(FB_URL)
            return False

    def go_home(self) -> None:
        """Vuelve a la interfaz de Mi Recetario (desde la página de Facebook)."""
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
        """Inyecta el botón de captura en la página de Facebook actual.

        Solo actúa si la ventana está mostrando una página de Facebook; si está
        en la propia app no hace nada (evita inyectar el botón en la interfaz).
        """
        try:
            window = webview.windows[0]
            url = window.get_current_url() or ""
            if "facebook.com" not in url:
                return False
            window.run_js(fb.build_capture_script(self.app_url.rstrip("/")))
            return True
        except Exception:
            return False

    # ------------------------------------------------------ interno

    def _navigate_later(self, window, url: str) -> None:
        """Espera un instante y navega, dejando tiempo a pywebview para
        entregar el valor de retorno de la llamada API que originó la
        navegación (evita JavascriptException por callback perdido)."""
        time.sleep(NAV_DELAY)
        try:
            window.load_url(url)
        except Exception:
            pass

    def _arm_injector(self, window) -> None:
        """Registra una sola vez la inyección del botón flotante.

        Se escucha el evento `loaded` de pywebview, que se dispara justo cuando
        una página termina de cargar y el puente JS ya está inyectado (por eso
        `document.body` existe y no hay errores de `null`). Además se arranca un
        vigilante que re-inyecta el botón mientras la ventana esté en Facebook,
        porque las navegaciones internas de la SPA no disparan `loaded`.
        """
        if self._injector_armed:
            return
        self._injector_armed = True
        window.events.loaded += self._on_page_loaded
        self._start_watchdog()

    def _start_watchdog(self) -> None:
        """Hilo daemon que, mientras la ventana esté en una página de Facebook,
        re-inyecta el script del botón cada FB_WATCHDOG_PERIOD segundos.

        Cubre los casos que el evento `loaded` no ve: navegación interna de la
        SPA de Facebook y botón borrado por React (el script además se
        auto-repara solo con su setInterval). El script es idempotente, así que
        re-inyectarlo no duplica nada.
        """
        if self._watchdog_started:
            return
        self._watchdog_started = True

        def run() -> None:
            while True:
                time.sleep(FB_WATCHDOG_PERIOD)
                try:
                    window = webview.windows[0]
                except Exception:
                    continue
                try:
                    url = window.get_current_url() or ""
                except Exception:
                    continue
                if "facebook.com" not in url:
                    continue
                try:
                    window.run_js(fb.build_capture_script(self.app_url.rstrip("/")))
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _on_page_loaded(self, window) -> None:
        """Callback del evento `loaded`: inyecta el botón si es una página de
        Facebook, y no hace nada en la propia app."""
        try:
            url = window.get_current_url() or ""
        except Exception:
            return
        if "facebook.com" not in url:
            return
        try:
            window.run_js(fb.build_capture_script(self.app_url.rstrip("/")))
        except Exception:
            pass
