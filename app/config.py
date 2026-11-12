"""Configuración de la aplicación: rutas y ajustes persistentes.

Las rutas siguen la convención de cada sistema, no la carpeta del proyecto:

- Linux (XDG): datos en $XDG_DATA_HOME, ajustes en $XDG_CONFIG_HOME y
  caché (certificado) en $XDG_CACHE_HOME, con los valores por defecto de la
  especificación (~/.local/share, ~/.config, ~/.cache).
- Windows: datos y caché en %LOCALAPPDATA%; ajustes en %APPDATA%.
- macOS: datos y ajustes en ~/Library/Application Support; caché en
  ~/Library/Caches.

Una instalación anterior (que guardaba todo en `data/` junto al código) se
migra automáticamente al arrancar.
"""
import json
import os
import pathlib
import shutil
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

# Identidad de la app para las carpetas de usuario.
APP_SLUG = "facebook-collections-downloader"
APP_DISPLAY_NAME = "Facebook Collections Downloader"


def _absolute_env(name: str) -> pathlib.Path | None:
    """Valor de una variable de entorno que debe ser una ruta absoluta.

    La especificación XDG exige ignorar los valores relativos.
    """
    value = os.environ.get(name)
    if not value:
        return None
    path = pathlib.Path(os.path.expanduser(value))
    return path if path.is_absolute() else None


def _app_dirs() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Devuelve (datos, ajustes, caché) según el sistema operativo."""
    home = pathlib.Path.home()
    if sys.platform.startswith("win"):
        roaming = _absolute_env("APPDATA") or home / "AppData" / "Roaming"
        local = _absolute_env("LOCALAPPDATA") or home / "AppData" / "Local"
        data = local / APP_DISPLAY_NAME
        return data, roaming / APP_DISPLAY_NAME, data / "cache"
    if sys.platform == "darwin":
        support = home / "Library" / "Application Support" / APP_DISPLAY_NAME
        return support, support, home / "Library" / "Caches" / APP_DISPLAY_NAME
    data_home = _absolute_env("XDG_DATA_HOME") or home / ".local" / "share"
    config_home = _absolute_env("XDG_CONFIG_HOME") or home / ".config"
    cache_home = _absolute_env("XDG_CACHE_HOME") or home / ".cache"
    return (data_home / APP_SLUG, config_home / APP_SLUG, cache_home / APP_SLUG)


DATA_DIR, CONFIG_DIR, CACHE_DIR = _app_dirs()
THUMBS_DIR = DATA_DIR / "thumbs"
DB_FILE = DATA_DIR / "recipes.db"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
COOKIES_DIR = DATA_DIR / "cookies"

# Instalaciones anteriores guardaban todo dentro del proyecto.
LEGACY_DATA_DIR = BASE_DIR / "data"

# Subcarpeta propia de la app dentro de la carpeta de vídeos del sistema.
APP_FOLDER_NAME = "Recetas"

# Valor que usaban las versiones anteriores en todos los sistemas. Se migra
# al arrancar para no seguir creando ~/Videos cuando el sistema usa otro
# nombre (p. ej. ~/Vídeos en español).
_LEGACY_WATCH_FOLDER = pathlib.Path.home() / "Videos" / APP_FOLDER_NAME


def _linux_videos_dir() -> pathlib.Path | None:
    """Carpeta de vídeos según el estándar XDG (respeta el idioma del sistema).

    El nombre real de la carpeta (Videos, Vídeos, Vidéos, Videos…) lo decide
    el escritorio y se guarda en user-dirs.dirs. Se consulta primero la
    variable de entorno y después ese archivo.
    """
    home = pathlib.Path.home()

    env = os.environ.get("XDG_VIDEOS_DIR")
    if env:
        path = pathlib.Path(os.path.expanduser(os.path.expandvars(env)))
        if path.is_absolute() and path != home:
            return path

    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = pathlib.Path(config_home) if config_home else home / ".config"
    try:
        with open(base / "user-dirs.dirs", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("XDG_VIDEOS_DIR="):
                    continue
                value = line.split("=", 1)[1].strip().strip('"')
                value = value.replace("$HOME", str(home))
                path = pathlib.Path(os.path.expanduser(os.path.expandvars(value)))
                # XDG_VIDEOS_DIR="$HOME/" significa "sin carpeta de vídeos".
                if path.is_absolute() and path != home:
                    return path
                return None
    except OSError:
        pass
    return None


def _windows_videos_dir() -> pathlib.Path | None:
    """Carpeta de vídeos de Windows vía la API de carpetas conocidas.

    Es la forma correcta porque puede estar redirigida (OneDrive, otra
    unidad) y porque el nombre mostrado cambia con el idioma, pero consultar
    la API evita adivinar.
    """
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        # FOLDERID_Videos {18989B1D-99B5-455B-841C-AB7C74E4DDFC}
        folder_id = _GUID.from_buffer_copy(
            uuid.UUID("18989B1D-99B5-455B-841C-AB7C74E4DDFC").bytes_le
        )
        path_ptr = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(path_ptr)
        )
        if result == 0 and path_ptr.value:
            value = path_ptr.value
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
            return pathlib.Path(value)
    except Exception:
        pass
    return None


def _macos_videos_dir() -> pathlib.Path | None:
    home = pathlib.Path.home()
    for name in ("Movies", "Videos"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home / "Movies"


def default_videos_dir() -> pathlib.Path:
    """Carpeta de vídeos del sistema, sin importar el idioma ni la plataforma."""
    home = pathlib.Path.home()
    if sys.platform.startswith("win"):
        return _windows_videos_dir() or home / "Videos"
    if sys.platform == "darwin":
        return _macos_videos_dir()
    linux_dir = _linux_videos_dir()
    if linux_dir is not None:
        return linux_dir
    # Sin configuración XDG: buscar nombres habituales antes de crear "Videos".
    # Los localizados van primero porque, si existe el genérico creado por
    # versiones antiguas de la app, el del escritorio es el que importa.
    for name in ("Vídeos", "Vidéos", "Video", "Filme", "Videot", "Videa",
                 "Wideo", "Videos"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home / "Videos"


def default_watch_folder() -> str:
    return str(default_videos_dir() / APP_FOLDER_NAME)


DEFAULTS = {
    # Carpeta donde dejas los vídeos descargados de Facebook.
    "watch_folder": default_watch_folder(),
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
    for directory in (DATA_DIR, CONFIG_DIR, CACHE_DIR, THUMBS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _migrate_legacy_data() -> None:
    """Mueve los datos de una instalación antigua (`data/` del proyecto).

    No sobrescribe nada: si el destino ya existe, el archivo se deja donde
    estaba. Solo borra la carpeta antigua si queda vacía.
    """
    if LEGACY_DATA_DIR == DATA_DIR or not LEGACY_DATA_DIR.is_dir():
        return
    # settings.json y el certificado tienen su propia carpeta; el resto
    # (base de datos, miniaturas, cookies, perfil del webview) son datos.
    destinations = {"settings.json": CONFIG_DIR, "cert": CACHE_DIR}
    try:
        entries = list(LEGACY_DATA_DIR.iterdir())
    except OSError:
        return
    for entry in entries:
        target_dir = destinations.get(entry.name, DATA_DIR)
        target = target_dir / entry.name
        if target.exists():
            continue
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(target))
        except OSError:
            continue
    try:
        LEGACY_DATA_DIR.rmdir()  # solo si quedó vacía
    except OSError:
        pass


def _migrate_watch_folder() -> None:
    """Cambia el antiguo valor fijo `~/Videos/Recetas` por el real del sistema.

    Solo actúa si el ajuste coincide exactamente con el valor que generaba la
    app por defecto; una carpeta elegida a mano no se toca.
    """
    current = settings.get("watch_folder") or ""
    if not current:
        return
    try:
        if pathlib.Path(current).expanduser() != _LEGACY_WATCH_FOLDER:
            return
    except (OSError, ValueError):
        return
    new_default = DEFAULTS["watch_folder"]
    if pathlib.Path(new_default) == _LEGACY_WATCH_FOLDER:
        return
    settings["watch_folder"] = new_default
    try:
        save()
    except OSError:
        pass


def load() -> dict:
    """Carga los ajustes desde disco (mezclando con los valores por defecto)."""
    _migrate_legacy_data()
    ensure_dirs()
    settings.clear()
    settings.update(DEFAULTS)
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, encoding="utf-8") as fh:
                settings.update(json.load(fh))
    except Exception:
        pass
    _migrate_watch_folder()
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
