"""Internationalization (i18n) module.

Loads Qt Linguist .ts translation files (XML) and provides a ``tr()``
function for the backend.  The frontend uses the ``/api/translations``
endpoint instead (see ``app/server.py``).

Usage in backend code::

    from .i18n import tr
    msg = tr("MainWindow", "Transcription started.")
"""

import pathlib
import threading
import xml.etree.ElementTree as ET

LOCALE_DIR = pathlib.Path(__file__).resolve().parent.parent / "locale"

# { "es": { ("Context", "source"): "translation", … }, … }
_cache: dict[str, dict[tuple[str, str], str]] = {}
_lock = threading.Lock()


def _load(lang: str) -> dict[tuple[str, str], str]:
    """Parse a ``.ts`` file and return a ``(context, source) → translation`` map."""
    ts_path = LOCALE_DIR / f"{lang}.ts"
    if not ts_path.is_file():
        return {}
    try:
        tree = ET.parse(ts_path)
    except ET.ParseError:
        return {}
    result: dict[tuple[str, str], str] = {}
    for context_el in tree.iter("context"):
        ctx_name = (context_el.findtext("name") or "").strip()
        for msg_el in context_el.iter("message"):
            src = (msg_el.findtext("source") or "").strip()
            trans_el = msg_el.find("translation")
            if trans_el is None:
                continue
            # Skip empty or unfinished translations (type="unfinished")
            trans_text = (trans_el.text or "").strip()
            typ = trans_el.get("type", "")
            if not trans_text or typ == "unfinished":
                continue
            result[(ctx_name, src)] = trans_text
    return result


def _get_map(lang: str) -> dict[tuple[str, str], str]:
    with _lock:
        if lang not in _cache:
            _cache[lang] = _load(lang)
        return _cache[lang]


def tr(context: str, source: str, lang: str | None = None) -> str:
    """Return the translation for *source* in *context*.

    Falls back to the English source string when no translation is found.
    """
    from . import config

    if lang is None:
        lang = config.settings.get("language", "en") or "en"
    # English is the source language — return as-is
    if lang == "en":
        return source
    mapping = _get_map(lang)
    return mapping.get((context, source), source)


def available_languages() -> list[dict]:
    """Return languages that have a ``.ts`` file in ``locale/``."""
    langs = []
    for p in sorted(LOCALE_DIR.glob("*.ts")):
        code = p.stem  # e.g. "es"
        langs.append({"code": code, "name": _LANG_NAMES.get(code, code)})
    return langs


def reload(lang: str | None = None) -> None:
    """Clear cached translations so they are re-read from disk."""
    with _lock:
        if lang:
            _cache.pop(lang, None)
        else:
            _cache.clear()


# Human-readable language names (ISO 639-1 → name)
_LANG_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "pt": "Português",
    "it": "Italiano",
    "ca": "Català",
    "gl": "Galego",
    "eu": "Euskara",
    "ru": "Русский",
    "ja": "日本語",
    "zh": "中文",
    "ko": "한국어",
    "ar": "العربية",
    "hi": "हिन्दी",
    "tr": "Türkçe",
    "nl": "Nederlands",
    "pl": "Polski",
    "sv": "Svenska",
    "no": "Norsk",
    "da": "Dansk",
    "fi": "Suomi",
    "cs": "Čeština",
    "sk": "Slovenčina",
    "hu": "Magyar",
    "ro": "Română",
    "el": "Ελληνικά",
    "uk": "Українська",
    "th": "ไทย",
    "vi": "Tiếng Việt",
    "id": "Bahasa Indonesia",
    "ms": "Bahasa Melayu",
    "sw": "Kiswahili",
    "he": "עברית",
    "fa": "فارسی",
    "bn": "বাংলা",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "ur": "اردو",
    "sr": "Српски",
    "hr": "Hrvatski",
    "bg": "Български",
    "lt": "Lietuvių",
    "lv": "Latviešu",
    "et": "Eesti",
    "sl": "Slovenščina",
    "sq": "Shqip",
    "is": "Íslenska",
    "ka": "ქართული",
    "hy": "Հայերեն",
    "kk": "Қазақ",
    "uz": "O'zbek",
    "az": "Azərbaycan",
    "af": "Afrikaans",
    "sw": "Kiswahili",
    "tl": "Tagalog",
    "ha": "Hausa",
    "yo": "Yorùbá",
    "so": "Soomaali",
    "am": "አማርኛ",
    "ne": "नेपाली",
    "si": "සිංහල",
    "my": "မြန်မာ",
    "km": "ភាសាខ្មែរ",
    "lo": "ລາວ",
    "mn": "Монгол",
    "bo": "བོད་སྐད",
}
