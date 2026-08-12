#!/usr/bin/env python3
"""Mi Recetario — gestor de recetas de cocina en vídeo.

Uso:
    python3 run.py            → ventana nativa (por defecto)
    python3 run.py --web      → abre en el navegador
    python3 run.py --serve    → solo servidor HTTP (para pruebas/API)
"""
import argparse
import socket
import sys
import threading
import time
import webbrowser

from werkzeug.serving import make_server


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def keep_alive() -> None:
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Mi Recetario")
    parser.add_argument("--web", action="store_true",
                        help="Abrir en el navegador en lugar de la ventana nativa")
    parser.add_argument("--serve", action="store_true",
                        help="Solo servidor HTTP sin interfaz (modo pruebas)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None,
                        help="Puerto (por defecto: uno libre automático)")
    args = parser.parse_args()

    from app.server import create_app

    app = create_app()
    port = args.port or free_port()
    server = make_server(args.host, port, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = f"http://{args.host}:{port}/"
    print(f"🍲 Mi Recetario disponible en {url}")

    if args.serve:
        print("Modo servidor. Ctrl+C para salir.")
        keep_alive()
        return

    if args.web:
        webbrowser.open(url)
        keep_alive()
        return

    # Ventana nativa de escritorio.
    try:
        import webview
        from app.window import Api
    except ImportError:
        print("pywebview no está instalado. Abriendo en el navegador…")
        webbrowser.open(url)
        keep_alive()
        return

    webview.create_window(
        "Mi Recetario",
        url,
        width=1320,
        height=860,
        min_size=(980, 620),
        js_api=Api(app_url=url),
        background_color="#171009",
    )
    webview.start()


if __name__ == "__main__":
    sys.exit(main())
