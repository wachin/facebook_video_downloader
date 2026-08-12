"""Puente con la ventana nativa (pywebview).

Los métodos de esta clase quedan disponibles en el frontend como
`window.pywebview.api.<método>()` cuando la app corre en modo ventana nativa.
"""
import os
import subprocess

import webview


class Api:
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
