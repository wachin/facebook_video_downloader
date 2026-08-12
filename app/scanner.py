"""Detección de vídeos nuevos y extracción de metadatos (duración, miniatura)."""
import os
import pathlib
import shutil
import subprocess
import threading

from . import config, database as db

VIDEO_EXTS = {
    ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
    ".3gp", ".mpg", ".mpeg", ".ogv", ".flv", ".wmv",
}

_metadata_lock = threading.Lock()


def is_video(path: str | pathlib.Path) -> bool:
    return pathlib.Path(path).suffix.lower() in VIDEO_EXTS


def scan() -> dict:
    """Busca vídeos nuevos en la carpeta vigilada y los da de alta."""
    folder = config.settings.get("watch_folder", "")
    result = {"folder": folder, "exists": False, "total": 0, "new": 0}
    if not folder:
        return result
    fdir = pathlib.Path(folder)
    try:
        fdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return result
    result["exists"] = fdir.is_dir()
    if not result["exists"]:
        return result

    known = db.all_paths()
    for f in sorted(fdir.iterdir()):
        if f.is_file() and is_video(f):
            result["total"] += 1
            path = str(f.resolve())
            if path not in known:
                db.upsert_video(path, f.name)
                result["new"] += 1

    # Metadatos (duración/miniatura) en segundo plano para no bloquear la UI.
    threading.Thread(target=fill_metadata, daemon=True).start()
    return result


def fill_metadata() -> None:
    """Calcula duración y miniatura de los vídeos que aún no las tienen."""
    if not _metadata_lock.acquire(blocking=False):
        return
    try:
        for rec in db.recipes_needing_meta():
            if not os.path.exists(rec["video_path"]):
                continue
            try:
                if not db.get_recipe(rec["id"])["duration"]:
                    dur = probe_duration(rec["video_path"])
                    if dur:
                        db.set_meta(rec["id"], duration=dur)
            except Exception:
                pass
            try:
                if not db.get_recipe(rec["id"])["thumbnail"]:
                    make_thumbnail(rec["id"], rec["video_path"])
            except Exception:
                pass
    finally:
        _metadata_lock.release()


def probe_duration(video_path: str) -> float:
    try:
        import av
        with av.open(video_path) as container:
            return (container.duration or 0) / 1_000_000.0
    except Exception:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 0.0
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                capture_output=True, text=True, timeout=60,
            )
            return float(out.stdout.strip() or 0)
        except Exception:
            return 0.0


def make_thumbnail(rid: int, video_path: str) -> str:
    """Extrae el primer fotograma del vídeo como miniatura JPEG."""
    out = config.THUMBS_DIR / f"thumb_{rid}.jpg"
    try:
        import av
        with av.open(video_path) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            frame = None
            try:
                for f in container.decode(video=0):
                    frame = f
                    break
            except Exception:
                pass
            if frame is None:
                raise RuntimeError("sin fotogramas")
            img = frame.to_image()  # requiere Pillow
            img.thumbnail((640, 640))
            img.save(out, "JPEG", quality=82)
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise
        subprocess.run(
            [ffmpeg, "-y", "-ss", "0", "-i", video_path, "-frames:v", "1",
             "-vf", "scale=640:-1", str(out)],
            capture_output=True, timeout=120, check=True,
        )
    if out.exists():
        db.set_meta(rid, thumbnail=str(out))
        return str(out)
    return ""
