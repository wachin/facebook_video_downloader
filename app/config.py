"""Configuración de la aplicación: rutas y ajustes persistentes."""
import json
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
THUMBS_DIR = DATA_DIR / "thumbs"
DB_FILE = DATA_DIR / "recipes.db"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    # Carpeta donde dejas los vídeos descargados de Facebook.
    "watch_folder": str(pathlib.Path.home() / "Videos" / "Recetas"),
    # Modelo de Whisper: tiny | base | small | medium  (a mayor tamaño, más
    # preciso pero más lento. "small" es un buen equilibrio en CPU).
    "whisper_model": "small",
    # Idioma de la transcripción: "auto" (detectar) o cualquier código ISO de
    # Whisper (es, en, pt, fr, it, de, ca, ru, ja... 99 idiomas en total).
    "language": "es",
    # Hilos de CPU para la transcripción.
    "cpu_threads": 4,
    # Filtrar silencios y música de fondo (recomendado para vídeos de cocina).
    "vad": True,
}

settings: dict = {}


def ensure_dirs() -> None:
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    """Carga los ajustes desde disco (mezclando con los valores por defecto)."""
    ensure_dirs()
    settings.clear()
    settings.update(DEFAULTS)
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, encoding="utf-8") as fh:
                settings.update(json.load(fh))
    except Exception:
        pass
    return settings


def save() -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)


def update(data: dict) -> list:
    """Actualiza los ajustes recibidos y devuelve las claves modificadas."""
    changed = []
    for key, value in data.items():
        if key in DEFAULTS and value != settings.get(key):
            settings[key] = value
            changed.append(key)
    if changed:
        save()
    return changed
