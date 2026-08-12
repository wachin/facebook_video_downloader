"""Servicio de transcripción local con faster-whisper.

Los trabajos se ejecutan en hilos y se serializan (una transcripción a la vez)
para no saturar la CPU. El progreso se guarda en la base de datos y la UI lo
consulta por polling.
"""
import os
import threading

from . import config, database as db

_serial_lock = threading.Lock()  # una transcripción a la vez


class TranscriptionManager:
    def __init__(self) -> None:
        self._model = None
        self._model_spec = None
        self._jobs: dict[int, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------- API

    def start(self, recipe_id: int) -> tuple[bool, str]:
        with self._lock:
            if recipe_id in self._jobs:
                return False, "Ya hay una transcripción en curso para este vídeo."
            recipe = db.get_recipe(recipe_id)
            if not recipe:
                return False, "Receta no encontrada."
            if not os.path.exists(recipe["video_path"]):
                return False, "No se encuentra el archivo de vídeo."
            job = {"recipe_id": recipe_id, "cancelled": False, "thread": None}
            self._jobs[recipe_id] = job
        thread = threading.Thread(
            target=self._run, args=(recipe_id, recipe["video_path"]), daemon=True
        )
        job["thread"] = thread
        thread.start()
        return True, "Transcripción iniciada."

    def cancel(self, recipe_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(recipe_id)
            if job:
                job["cancelled"] = True
                return True
        return False

    def active(self) -> list[dict]:
        with self._lock:
            return [{"recipe_id": rid} for rid in self._jobs]

    # ------------------------------------------------------------- interno

    def _ensure_model(self, name: str, threads: int):
        spec = (name, threads)
        if self._model is None or self._model_spec != spec:
            self._model = None
            from faster_whisper import WhisperModel
            # int8 = 4x más rápido y con menos memoria en CPU.
            self._model = WhisperModel(name, device="cpu", compute_type="int8",
                                       cpu_threads=threads)
            self._model_spec = spec
        return self._model

    def _run(self, recipe_id: int, video_path: str) -> None:
        job = self._jobs.get(recipe_id)
        settings = config.settings
        db.set_progress(recipe_id, "transcribing", 0)
        try:
            # Carga del modelo bajo el candado: evita que dos hilos descarguen
            # o carguen el modelo a la vez (primera ejecución puede tardar).
            with _serial_lock:
                if job and job["cancelled"]:
                    self._abort(recipe_id)
                    return
                model = self._ensure_model(
                    settings["whisper_model"], int(settings["cpu_threads"])
                )
                # Si pidieron cancelar mientras se descargaba/cargaba el
                # modelo (primera ejecución), respetarlo antes de transcribir.
                if job and job["cancelled"]:
                    self._abort(recipe_id)
                    return
                segments, info = model.transcribe(
                    video_path,
                    language=settings.get("language") or None,
                    vad_filter=bool(settings.get("vad", True)),
                    beam_size=5,
                )
                parts: list[str] = []
                duration = info.duration or 0
                last_progress = -1.0
                for segment in segments:
                    if job and job["cancelled"]:
                        self._abort(recipe_id)
                        return
                    text = segment.text.strip()
                    if text:
                        parts.append(text)
                    if duration:
                        progress = min(98.9, segment.end / duration * 100)
                        if progress - last_progress >= 1.0:
                            last_progress = progress
                            db.set_progress(recipe_id, "transcribing", progress)
                            # Vista previa del texto en tiempo real.
                            db.set_transcript(recipe_id, "\n".join(parts))
                if job and job["cancelled"]:
                    self._abort(recipe_id)
                    return
                transcript = "\n".join(parts)
                db.set_transcript(recipe_id, transcript)
                db.set_progress(recipe_id, "done", 100)
        except Exception as exc:  # noqa: BLE001 — cualquier fallo → estado error
            db.set_progress(recipe_id, "error", 0, error=str(exc)[:600])
        finally:
            with self._lock:
                self._jobs.pop(recipe_id, None)

    @staticmethod
    def _abort(recipe_id: int) -> None:
        """Cancelación: la receta vuelve a pendiente para poder reintentarla."""
        db.set_progress(recipe_id, "pending", 0)


manager = TranscriptionManager()
