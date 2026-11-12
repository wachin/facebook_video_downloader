"""Pruebas de las rutas de usuario (XDG) y de la migración de datos.

No usan pytest ni tocan los datos reales: cada prueba reimporta `app.config`
con un HOME y unas variables XDG temporales, y apunta `LEGACY_DATA_DIR` a una
carpeta temporal.

Ejecutar desde la raíz del proyecto:

    python3 -m unittest discover -s tests -t .
"""
import contextlib
import importlib
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SLUG = "facebook-collections-downloader"

# Variables que podrían venir del entorno real y alterar las rutas esperadas.
_PATH_ENV_VARS = (
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_VIDEOS_DIR",
    "APPDATA",
    "LOCALAPPDATA",
)


@contextlib.contextmanager
def fresh_config(extra_env=None, prepare=None):
    """Importa `app.config` de cero con HOME y XDG apuntando a un temporal.

    `extra_env` añade variables al entorno y `prepare` crea carpetas en el HOME
    temporal antes de importar (necesario para los valores calculados al
    importar, como DEFAULTS["watch_folder"]).
    """
    saved = sys.modules.pop("app.config", None)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            if prepare is not None:
                prepare(home)
            env = {k: v for k, v in os.environ.items() if k not in _PATH_ENV_VARS}
            env["HOME"] = str(home)
            if extra_env:
                env.update({k: str(v) for k, v in extra_env.items()})
            with mock.patch.dict(os.environ, env, clear=True):
                cfg = importlib.import_module("app.config")
                # Nunca mirar el `data/` real del proyecto.
                cfg.LEGACY_DATA_DIR = home / "legacy" / "data"
                yield cfg, home
                sys.modules.pop("app.config", None)
    finally:
        if saved is not None:
            sys.modules["app.config"] = saved


class XdgPathsTest(unittest.TestCase):
    def test_usa_los_valores_por_defecto_de_xdg(self):
        with fresh_config() as (cfg, home):
            self.assertEqual(cfg.DATA_DIR, home / ".local" / "share" / SLUG)
            self.assertEqual(cfg.CONFIG_DIR, home / ".config" / SLUG)
            self.assertEqual(cfg.CACHE_DIR, home / ".cache" / SLUG)
            self.assertEqual(cfg.THUMBS_DIR, cfg.DATA_DIR / "thumbs")
            self.assertEqual(cfg.DB_FILE, cfg.DATA_DIR / "recipes.db")
            self.assertEqual(cfg.SETTINGS_FILE, cfg.CONFIG_DIR / "settings.json")
            self.assertEqual(cfg.COOKIES_DIR, cfg.DATA_DIR / "cookies")

    def test_respeta_las_variables_xdg(self):
        data = pathlib.Path("/tmp/xdg-datos")
        config = pathlib.Path("/tmp/xdg-ajustes")
        cache = pathlib.Path("/tmp/xdg-cache")
        with fresh_config(
            extra_env={
                "XDG_DATA_HOME": data,
                "XDG_CONFIG_HOME": config,
                "XDG_CACHE_HOME": cache,
            }
        ) as (cfg, _home):
            self.assertEqual(cfg.DATA_DIR, data / SLUG)
            self.assertEqual(cfg.CONFIG_DIR, config / SLUG)
            self.assertEqual(cfg.CACHE_DIR, cache / SLUG)

    def test_ignora_los_valores_xdg_relativos(self):
        with mock.patch.dict(
            os.environ,
            {
                "XDG_DATA_HOME": "datos-relativos",
                "XDG_CONFIG_HOME": "ajustes-relativos",
                "XDG_CACHE_HOME": "./cache-relativa",
            },
        ):
            with fresh_config() as (cfg, home):
                self.assertEqual(cfg.DATA_DIR, home / ".local" / "share" / SLUG)
                self.assertEqual(cfg.CONFIG_DIR, home / ".config" / SLUG)
                self.assertEqual(cfg.CACHE_DIR, home / ".cache" / SLUG)

    def test_ensure_dirs_crea_todas_las_carpetas(self):
        with fresh_config() as (cfg, _home):
            cfg.ensure_dirs()
            for directory in (cfg.DATA_DIR, cfg.CONFIG_DIR, cfg.CACHE_DIR, cfg.THUMBS_DIR):
                self.assertTrue(directory.is_dir(), directory)

    def test_windows_usa_appdata_y_localappdata(self):
        with fresh_config() as (cfg, home):
            roaming = home / "Roaming"
            local = home / "Local"
            with mock.patch.dict(
                os.environ,
                {"APPDATA": str(roaming), "LOCALAPPDATA": str(local)},
            ):
                with mock.patch.object(cfg.sys, "platform", "win32"):
                    data, config, cache = cfg._app_dirs()
            self.assertEqual(data, local / cfg.APP_DISPLAY_NAME)
            self.assertEqual(config, roaming / cfg.APP_DISPLAY_NAME)
            self.assertEqual(cache, local / cfg.APP_DISPLAY_NAME / "cache")

    def test_macos_usa_application_support_y_caches(self):
        with fresh_config() as (cfg, home):
            with mock.patch.object(cfg.sys, "platform", "darwin"):
                data, config, cache = cfg._app_dirs()
            support = home / "Library" / "Application Support" / cfg.APP_DISPLAY_NAME
            self.assertEqual(data, support)
            self.assertEqual(config, support)
            self.assertEqual(cache, home / "Library" / "Caches" / cfg.APP_DISPLAY_NAME)


class VideosDirTest(unittest.TestCase):
    def test_usa_la_variable_xdg_videos_dir(self):
        with fresh_config() as (cfg, home):
            videos = home / "Vídeos"
            videos.mkdir()
            with mock.patch.dict(os.environ, {"XDG_VIDEOS_DIR": str(videos)}):
                self.assertEqual(cfg.default_videos_dir(), videos)
                self.assertEqual(cfg.default_watch_folder(), str(videos / cfg.APP_FOLDER_NAME))

    def test_lee_user_dirs_para_el_nombre_localizado(self):
        with fresh_config() as (cfg, home):
            videos = home / "Vídeos"
            videos.mkdir()
            config_home = home / ".config"
            config_home.mkdir()
            (config_home / "user-dirs.dirs").write_text(
                'XDG_VIDEOS_DIR="$HOME/Vídeos"\n', encoding="utf-8"
            )
            self.assertEqual(cfg.default_videos_dir(), videos)

    def test_busca_nombres_localizados_antes_que_videos(self):
        with fresh_config() as (cfg, home):
            (home / "Videos").mkdir()
            localized = home / "Vídeos"
            localized.mkdir()
            self.assertEqual(cfg.default_videos_dir(), localized)


class MigrationTest(unittest.TestCase):
    def _legacy_tree(self, home: pathlib.Path) -> pathlib.Path:
        legacy = home / "legacy" / "data"
        (legacy / "thumbs").mkdir(parents=True)
        (legacy / "cookies").mkdir()
        (legacy / "webview").mkdir()
        (legacy / "cert").mkdir()
        (legacy / "recipes.db").write_bytes(b"db")
        (legacy / "thumbs" / "video.jpg").write_bytes(b"jpg")
        (legacy / "cookies" / "fb_cookies.txt").write_text("cookies", encoding="utf-8")
        (legacy / "webview" / "Cache").write_bytes(b"perfil")
        (legacy / "cert" / "cert.pem").write_text("pem", encoding="utf-8")
        (legacy / "settings.json").write_text(
            json.dumps({"whisper_model": "base"}), encoding="utf-8"
        )
        return legacy

    def test_mueve_los_datos_a_sus_carpetas_correctas(self):
        with fresh_config() as (cfg, home):
            legacy = self._legacy_tree(home)
            cfg.load()

            self.assertEqual((cfg.DATA_DIR / "recipes.db").read_bytes(), b"db")
            self.assertEqual((cfg.THUMBS_DIR / "video.jpg").read_bytes(), b"jpg")
            self.assertEqual(
                (cfg.COOKIES_DIR / "fb_cookies.txt").read_text(encoding="utf-8"),
                "cookies",
            )
            self.assertEqual((cfg.DATA_DIR / "webview" / "Cache").read_bytes(), b"perfil")
            self.assertTrue((cfg.CONFIG_DIR / "settings.json").is_file())
            self.assertTrue((cfg.CACHE_DIR / "cert" / "cert.pem").is_file())
            # Los ajustes migrados se cargan en este mismo arranque.
            self.assertEqual(cfg.settings["whisper_model"], "base")
            self.assertFalse(legacy.exists(), "la carpeta antigua vacía debe borrarse")

    def test_no_sobrescribe_lo_que_ya_existe(self):
        with fresh_config() as (cfg, home):
            legacy = self._legacy_tree(home)
            cfg.DATA_DIR.mkdir(parents=True)
            cfg.CONFIG_DIR.mkdir(parents=True)
            cfg.CACHE_DIR.mkdir(parents=True)
            (cfg.DATA_DIR / "recipes.db").write_bytes(b"nuevo")
            (cfg.CONFIG_DIR / "settings.json").write_text(
                json.dumps({"whisper_model": "small"}), encoding="utf-8"
            )

            cfg.load()

            self.assertEqual((cfg.DATA_DIR / "recipes.db").read_bytes(), b"nuevo")
            self.assertEqual(cfg.settings["whisper_model"], "small")
            # Lo que no se pudo mover sigue en la carpeta antigua.
            self.assertEqual((legacy / "recipes.db").read_bytes(), b"db")
            self.assertTrue((legacy / "settings.json").is_file())
            self.assertTrue((cfg.THUMBS_DIR / "video.jpg").is_file())
            self.assertTrue(legacy.is_dir())

    def test_no_hace_nada_si_la_carpeta_antigua_no_existe(self):
        with fresh_config() as (cfg, _home):
            cfg.load()
            self.assertTrue(cfg.DATA_DIR.is_dir())
            self.assertFalse(cfg.LEGACY_DATA_DIR.exists())

    def test_no_migra_si_la_carpeta_antigua_es_la_de_datos(self):
        with fresh_config() as (cfg, _home):
            cfg.DATA_DIR.mkdir(parents=True)
            marker = cfg.DATA_DIR / "recipes.db"
            marker.write_bytes(b"db")
            cfg.LEGACY_DATA_DIR = cfg.DATA_DIR
            cfg.load()
            self.assertEqual(marker.read_bytes(), b"db")
            self.assertTrue(marker.is_file())


class WatchFolderMigrationTest(unittest.TestCase):
    def _write_settings(self, cfg, value: str) -> None:
        cfg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg.SETTINGS_FILE.write_text(
            json.dumps({"watch_folder": value}), encoding="utf-8"
        )

    def test_cambia_el_antiguo_valor_por_defecto(self):
        localized = pathlib.Path("Vídeos")

        def prepare(home):
            (home / localized).mkdir()

        with fresh_config(prepare=prepare) as (cfg, home):
            old = home / "Videos" / cfg.APP_FOLDER_NAME
            self._write_settings(cfg, str(old))

            cfg.load()

            self.assertEqual(
                cfg.settings["watch_folder"],
                str(home / localized / cfg.APP_FOLDER_NAME),
            )
            saved = json.loads(cfg.SETTINGS_FILE.read_text(encoding="utf-8"))
            self.assertEqual(saved["watch_folder"], cfg.settings["watch_folder"])

    def test_respeta_una_carpeta_elegida_a_mano(self):
        with fresh_config() as (cfg, home):
            (home / "Vídeos").mkdir()
            custom = home / "Mis recetas"
            self._write_settings(cfg, str(custom))

            cfg.load()

            self.assertEqual(cfg.settings["watch_folder"], str(custom))


if __name__ == "__main__":
    unittest.main()
