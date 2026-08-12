"""Servidor HTTP local: API REST + interfaz web + medios con soporte Range."""
import mimetypes
import os
import pathlib
import re

from flask import Flask, Response, abort, jsonify, request, send_file

from . import config, database as db, scanner
from .transcription import manager

VIDEO_MIME = {
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".avi": "video/x-msvideo", ".m4v": "video/mp4",
    ".3gp": "video/3gpp", ".ogg": "video/ogg", ".ogv": "video/ogg",
}

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def create_app() -> Flask:
    config.load()
    db.conn()  # inicializa esquema
    scanner.scan()  # alta inicial de vídeos

    app = Flask(__name__, static_folder=str(config.WEB_DIR), static_url_path="")

    # ------------------------------------------------------------- utilidades

    def media_response(path: str, mime: str) -> Response:
        """Sirve un archivo local con soporte de peticiones Range (necesario
        para poder hacer seek en el reproductor de vídeo)."""
        size = os.path.getsize(path)
        range_header = request.headers.get("Range")
        if range_header:
            match = _RANGE_RE.match(range_header)
            if match:
                start_s, end_s = match.groups()
                try:
                    if start_s == "":
                        # suffix range: bytes=-N  → últimos N bytes
                        suffix = int(end_s)
                        start = max(0, size - suffix)
                        end = size - 1
                    else:
                        start = int(start_s)
                        end = int(end_s) if end_s else size - 1
                        end = min(end, size - 1)
                    if start >= size or start > end:
                        return Response(status=416, headers={"Content-Range": f"bytes */{size}"})
                    fh = open(path, "rb")
                    fh.seek(start)
                    resp = Response(fh, status=206, mimetype=mime, direct_passthrough=True)
                    resp.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
                    resp.headers["Content-Length"] = str(end - start + 1)
                    resp.headers["Accept-Ranges"] = "bytes"
                    return resp
                except (ValueError, OSError):
                    pass
        resp = send_file(path, mimetype=mime, conditional=True)
        resp.headers["Accept-Ranges"] = "bytes"
        return resp

    def json_error(message: str, code: int = 400):
        return jsonify({"error": message}), code

    # ------------------------------------------------------------- ajustes

    @app.get("/api/settings")
    def get_settings():
        return jsonify(config.settings)

    @app.post("/api/settings")
    def save_settings():
        data = request.get_json(silent=True) or {}
        changed = config.update(data)
        if "watch_folder" in changed:
            scanner.scan()
        return jsonify(config.settings)

    # ------------------------------------------------------------- vídeos

    @app.post("/api/rescan")
    def rescan():
        return jsonify(scanner.scan())

    @app.post("/api/import")
    def import_videos():
        """Importa vídeos arrastrados/soltados copiándolos a la carpeta vigilada."""
        folder = config.settings.get("watch_folder", "")
        if not folder:
            return json_error("Define primero la carpeta de vídeos en Ajustes.", 400)
        os.makedirs(folder, exist_ok=True)
        files = request.files.getlist("files")
        saved = []
        for f in files:
            name = pathlib.Path(f.filename or "video.mp4").name
            dest = pathlib.Path(folder) / name
            try:
                f.save(str(dest))
                saved.append(name)
            except OSError as exc:
                return json_error(f"No se pudo guardar {name}: {exc}", 500)
        result = scanner.scan()
        result["saved"] = saved
        return jsonify(result)

    # ------------------------------------------------------------- recetas

    @app.get("/api/recipes")
    def list_recipes():
        return jsonify(db.list_recipes(
            search=request.args.get("search", ""),
            category=request.args.get("category", ""),
            tag=request.args.get("tag", ""),
        ))

    @app.get("/api/recipes/<int:rid>")
    def get_recipe(rid):
        recipe = db.get_recipe(rid)
        return jsonify(recipe) if recipe else json_error("Receta no encontrada.", 404)

    @app.post("/api/recipes/<int:rid>")
    def update_recipe(rid):
        if not db.get_recipe(rid):
            return json_error("Receta no encontrada.", 404)
        data = request.get_json(silent=True) or {}
        return jsonify(db.update_recipe(rid, data))

    @app.delete("/api/recipes/<int:rid>")
    def delete_recipe(rid):
        recipe = db.get_recipe(rid)
        if not recipe:
            return json_error("Receta no encontrada.", 404)
        delete_file = request.args.get("delete_file") == "1"
        if delete_file and recipe["file_exists"]:
            try:
                os.remove(recipe["video_path"])
            except OSError as exc:
                return json_error(f"No se pudo borrar el vídeo: {exc}", 500)
        db.delete_recipe(rid)
        return jsonify({"ok": True})

    # ------------------------------------------------------------- transcripción

    @app.post("/api/recipes/<int:rid>/transcribe")
    def transcribe(rid):
        ok, message = manager.start(rid)
        return (jsonify({"ok": ok, "message": message}) if ok
                else json_error(message, 409))

    @app.post("/api/transcription/cancel/<int:rid>")
    def cancel_transcription(rid):
        return jsonify({"ok": manager.cancel(rid)})

    @app.get("/api/transcription/jobs")
    def transcription_jobs():
        return jsonify(manager.active())

    # ------------------------------------------------------------- estadísticas

    @app.get("/api/stats")
    def get_stats():
        return jsonify(db.stats())

    @app.get("/api/categories")
    def get_categories():
        return jsonify(db.categories())

    # ------------------------------------------------------------- medios

    @app.get("/media/video/<int:rid>")
    def media_video(rid):
        recipe = db.get_recipe(rid)
        if not recipe or not recipe["file_exists"]:
            abort(404)
        path = recipe["video_path"]
        mime = VIDEO_MIME.get(pathlib.Path(path).suffix.lower()) or \
            mimetypes.guess_type(path)[0] or "application/octet-stream"
        return media_response(path, mime)

    @app.get("/media/thumb/<int:rid>")
    def media_thumb(rid):
        recipe = db.get_recipe(rid)
        if recipe and recipe["thumbnail"] and os.path.exists(recipe["thumbnail"]):
            return send_file(recipe["thumbnail"], mimetype="image/jpeg", conditional=True)
        abort(404)

    @app.post("/api/recipes/<int:rid>/thumbnail")
    def regen_thumbnail(rid):
        recipe = db.get_recipe(rid)
        if not recipe:
            return json_error("Receta no encontrada.", 404)
        if not recipe["file_exists"]:
            return json_error("No se encuentra el archivo de vídeo.", 400)
        path = scanner.make_thumbnail(rid, recipe["video_path"])
        return jsonify({"ok": bool(path), "thumbnail": path})

    # ------------------------------------------------------------- exportación

    @app.get("/api/export/<int:rid>")
    def export_recipe(rid):
        recipe = db.get_recipe(rid)
        if not recipe:
            return json_error("Receta no encontrada.", 404)
        md = to_markdown(recipe)
        filename = re.sub(r"[^\w\-]+", "_", recipe["title"] or recipe["file_name"]) or "receta"
        return Response(
            md, mimetype="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}.md"},
        )

    @app.get("/")
    def index():
        return send_file(str(config.WEB_DIR / "index.html"))

    return app


def to_markdown(recipe: dict) -> str:
    minutes = int(recipe["duration"] // 60) if recipe["duration"] else 0
    seconds = int(recipe["duration"] % 60) if recipe["duration"] else 0
    lines = [f"# {recipe['title'] or recipe['file_name']}"]
    lines.append("")
    if recipe["category"]:
        lines.append(f"- **Categoría:** {recipe['category']}")
    if recipe["tags"]:
        lines.append(f"- **Etiquetas:** {', '.join(recipe['tags'])}")
    lines.append(f"- **Fuente:** {recipe['file_name']}")
    if recipe["duration"]:
        lines.append(f"- **Duración:** {minutes:02d}:{seconds:02d}")
    lines.append("")
    if recipe["ingredients"]:
        lines.append("## Ingredientes")
        lines.append("")
        lines += [f"- {item}" for item in recipe["ingredients"]]
        lines.append("")
    if recipe["steps"]:
        lines.append("## Pasos")
        lines.append("")
        lines += [f"{i}. {step}" for i, step in enumerate(recipe["steps"], 1)]
        lines.append("")
    if recipe["notes"]:
        lines.append("## Notas")
        lines.append("")
        lines.append(recipe["notes"])
        lines.append("")
    if recipe["transcript"]:
        lines.append("## Transcripción del vídeo")
        lines.append("")
        lines.append(recipe["transcript"])
        lines.append("")
    return "\n".join(lines)
