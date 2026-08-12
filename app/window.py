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


class Api:
    def __init__(self, app_url: str = "http://127.0.0.1:8000/") -> None:
        self.app_url = app_url.rstrip("/") + "/"
        self._injecting = False

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
        """Abre Facebook (página de guardados). En la ventana nativa navega
        la propia ventana e inyecta un botón flotante; fuera de ella abre el
        navegador normal (ahí se usa el bookmarklet)."""
        try:
            window = webview.windows[0]
            window.load_url(FB_URL)
            self._watch_facebook(window)
            return True
        except Exception:
            webbrowser.open(FB_URL)
            return False

    def go_home(self) -> None:
        """Vuelve a la interfaz de Mi Recetario (desde la página de Facebook)."""
        try:
            webview.windows[0].load_url(self.app_url + "?tab=facebook")
        except Exception:
            webbrowser.open(self.app_url + "?tab=facebook")

    def capture_now(self) -> bool:
        """Ejecuta la captura de vídeos en la página de Facebook actual."""
        try:
            window = webview.windows[0]
            js = fb.build_capture_script(self.app_url.rstrip("/"))
            window.evaluate_js(js)
            return True
        except Exception:
            return False

    # ------------------------------------------------------ interno

    def _watch_facebook(self, window) -> None:
        """Hilo que inyecta el botón flotante en cuanto la ventana está en una
        página de Facebook, y que se detiene al volver a la app."""
        if self._injecting:
            return
        self._injecting = True

        def loop() -> None:
            try:
                last_url = ""
                while True:
                    try:
                        url = window.get_current_url() or ""
                    except Exception:
                        break
                    if "facebook.com" in url:
                        # Facebook es una SPA: cada navegación completa recarga
                        # la página y se pierde el botón, así que se reinyecta
                        # siempre que cambie la URL.
                        if url != last_url:
                            try:
                                window.evaluate_js(
                                    fb.build_capture_script(self.app_url.rstrip("/"))
                                )
                                last_url = url
                            except Exception:
                                pass  # página aún cargando; se reintenta en 2s
                    else:
                        # De vuelta en la app: no hace falta seguir vigilando.
                        if url and url.startswith(self.app_url):
                            break
                    time.sleep(2)
            finally:
                self._injecting = False

        threading.Thread(target=loop, daemon=True).start()
