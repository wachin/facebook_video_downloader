#!/usr/bin/env python3
"""Mi Recetario — gestor de recetas de cocina en vídeo.

Uso:
    python3 run.py            → ventana nativa (por defecto)
    python3 run.py --web      → abre en el navegador
    python3 run.py --serve    → solo servidor HTTP (para pruebas/API)

En modo ventana nativa la app se sirve por **HTTPS local** (certificado
autofirmado). Es necesario: la página de Facebook es HTTPS y WebKitGTK
bloquea los *fetch* desde HTTPS hacia http://127.0.0.1 (contenido mixto), así
que la captura de vídeos fallaría. Con HTTPS local el envío desde Facebook a
la app ya no es contenido mixto. El certificado se genera una vez con openssl
y se guarda en data/cert/.
"""
import argparse
import pathlib
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from werkzeug.serving import make_server


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ensure_cert(data_dir: pathlib.Path):
    """Genera (o reutiliza) un certificado autofirmado para 127.0.0.1.

    Devuelve (ruta_cert, ruta_key) o None si openssl no está disponible o
    falla (en ese caso la app sigue funcionando, pero solo por HTTP).
    """
    cert_dir = data_dir / "cert"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert = cert_dir / "cert.pem"
    key = cert_dir / "key.pem"
    if cert.exists() and key.exists():
        return cert, key
    try:
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", str(key), "-out", str(cert),
                "-days", "3650", "-subj", "/CN=127.0.0.1",
                "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost",
            ],
            check=True, capture_output=True, timeout=30,
        )
        return cert, key
    except Exception:
        return None


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

    # HTTPS local solo en modo ventana nativa (el modo donde se captura desde
    # Facebook). En --web/--serve se mantiene HTTP: en el navegador normal
    # (Chrome/Firefox) el acceso a http://127.0.0.1 desde páginas HTTPS está
    # permitido, y un certificado autofirmado daría avisos de seguridad.
    cert = None
    if not args.web and not args.serve:
        from app.config import DATA_DIR

        cert = ensure_cert(DATA_DIR)

    if cert:
        import ssl

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert[0]), str(cert[1]))
        server = make_server(args.host, port, app, threaded=True, ssl_context=ctx)
        url = f"https://127.0.0.1:{port}/"
        print(f"🍲 Mi Recetario disponible en {url} (HTTPS local)")
    else:
        server = make_server(args.host, port, app, threaded=True)
        url = f"http://{args.host}:{port}/"
        print(f"🍲 Mi Recetario disponible en {url}")
        if not args.web and not args.serve:
            print("⚠ Aviso: no se pudo activar HTTPS local (¿falta openssl?). "
                  "La captura desde Facebook no funcionará.")
    threading.Thread(target=server.serve_forever, daemon=True).start()

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
        from app.config import DATA_DIR
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
    # private_mode=False: pywebview conserva cookies y datos de sitios (la
    # sesión de Facebook sobrevive al cerrar la app). Sin esto, el contexto de
    # WebKit es efímero y pide credenciales en cada arranque. Los datos se
    # guardan en data/webview/ (carpeta del proyecto).
    # IGNORE_SSL_ERRORS: la app se sirve por HTTPS con certificado autofirmado;
    # sin esto WebKit mostraría un aviso de seguridad en cada arranque.
    webview.settings["IGNORE_SSL_ERRORS"] = True
    webview.start(
        private_mode=False,
        storage_path=str(DATA_DIR / "webview"),
    )


if __name__ == "__main__":
    sys.exit(main())
