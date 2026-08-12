"""Capa de persistencia en SQLite."""
import json
import os
import re
import sqlite3
import threading
import time
import unicodedata

from . import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    transcript TEXT NOT NULL DEFAULT '',
    ingredients TEXT NOT NULL DEFAULT '[]',
    steps TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    duration REAL NOT NULL DEFAULT 0,
    thumbnail TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_recipes_status ON recipes(status);
CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);

CREATE TABLE IF NOT EXISTS fb_captured (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL DEFAULT 'video',
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);
"""

_SEP_RE = re.compile(r"[\s_\-\.]+")


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.ensure_dirs()
        _conn = sqlite3.connect(str(config.DB_FILE), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        # Los trabajos interrumpidos al cerrar la app vuelven a "pendiente".
        _conn.execute("UPDATE recipes SET status='pending', progress=0 WHERE status='transcribing'")
        _conn.commit()
    return _conn


def _fold(text: str) -> str:
    """Normaliza el texto para búsquedas sin distinguir tildes ni mayúsculas."""
    return "".join(
        c for c in unicodedata.normalize("NFD", (text or "").lower())
        if unicodedata.category(c) != "Mn"
    )


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("tags", "ingredients", "steps"):
        try:
            d[key] = json.loads(d[key] or "[]")
        except Exception:
            d[key] = []
    d["file_exists"] = os.path.exists(d.get("video_path") or "")
    return d


def pretty_title(file_name: str) -> str:
    """Convierte 'receta_pollo-al_limon_01.mp4' en 'Receta Pollo Al Limon 01'."""
    stem = os.path.splitext(file_name)[0]
    parts = [p for p in _SEP_RE.split(stem.strip()) if p]
    title = " ".join(parts).strip()
    return title[:120] or stem


# ---------------------------------------------------------------- escritura

def upsert_video(video_path: str, file_name: str) -> int:
    """Inserta el vídeo si es nuevo; si ya existe, devuelve su id."""
    with _lock:
        c = conn()
        row = c.execute("SELECT id FROM recipes WHERE video_path=?", (video_path,)).fetchone()
        if row:
            c.execute("UPDATE recipes SET file_name=? WHERE id=?", (file_name, row["id"]))
            c.commit()
            return row["id"]
        now = _now()
        c.execute(
            "INSERT INTO recipes (video_path, file_name, title, created_at, updated_at) VALUES (?,?,?,?,?)",
            (video_path, file_name, pretty_title(file_name), now, now),
        )
        c.commit()
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_recipe(rid: int, data: dict) -> dict:
    allowed = {"title", "category", "tags", "transcript", "ingredients", "steps", "notes"}
    fields, values = [], []
    for key in allowed:
        if key in data:
            value = data[key]
            if key in ("tags", "ingredients", "steps"):
                value = json.dumps(value or [], ensure_ascii=False)
            fields.append(f"{key}=?")
            values.append(value)
    if fields:
        values.append(_now())
        with _lock:
            conn().execute(f"UPDATE recipes SET {', '.join(fields)}, updated_at=? WHERE id=?", (*values, rid))
            conn().commit()
    return get_recipe(rid)


def set_progress(rid: int, status: str, progress: float, error: str = "") -> None:
    with _lock:
        conn().execute(
            "UPDATE recipes SET status=?, progress=?, error=?, updated_at=? WHERE id=?",
            (status, float(progress), error, _now(), rid),
        )
        conn().commit()


def set_transcript(rid: int, text: str) -> None:
    with _lock:
        conn().execute("UPDATE recipes SET transcript=?, updated_at=? WHERE id=?", (text, _now(), rid))
        conn().commit()


def set_meta(rid: int, duration: float | None = None, thumbnail: str | None = None) -> None:
    """Actualiza solo los campos de metadatos indicados (sin pisar el resto)."""
    fields, values = [], []
    if duration is not None:
        fields.append("duration=?")
        values.append(float(duration))
    if thumbnail is not None:
        fields.append("thumbnail=?")
        values.append(thumbnail)
    if not fields:
        return
    values.append(rid)
    with _lock:
        conn().execute(f"UPDATE recipes SET {', '.join(fields)} WHERE id=?", values)
        conn().commit()


def delete_recipe(rid: int) -> bool:
    rec = get_recipe(rid)
    if not rec:
        return False
    thumb = rec.get("thumbnail")
    if thumb and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except OSError:
            pass
    with _lock:
        conn().execute("DELETE FROM recipes WHERE id=?", (rid,))
        conn().commit()
    return True


# ---------------------------------------------------------------- lectura

def get_recipe(rid: int) -> dict | None:
    with _lock:
        row = conn().execute("SELECT * FROM recipes WHERE id=?", (rid,)).fetchone()
    return row_to_dict(row) if row else None


def list_recipes(search: str = "", category: str = "", tag: str = "") -> list:
    with _lock:
        rows = conn().execute(
            "SELECT * FROM recipes ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    out = [row_to_dict(r) for r in rows]
    if search:
        needle = _fold(search)
        out = [
            r for r in out
            if needle in _fold(f"{r['title']} {r['file_name']} {r['transcript']} {r['category']} "
                              f"{' '.join(r['tags'])}")
        ]
    if category:
        out = [r for r in out if r["category"].lower() == category.lower()]
    if tag:
        out = [r for r in out if any(t.lower() == tag.lower() for t in r["tags"])]
    return out


def all_paths() -> set:
    with _lock:
        rows = conn().execute("SELECT video_path FROM recipes").fetchall()
    return {r["video_path"] for r in rows}


def recipes_needing_meta() -> list:
    with _lock:
        rows = conn().execute(
            "SELECT id, video_path FROM recipes WHERE duration = 0 OR thumbnail = ''"
        ).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    with _lock:
        rows = conn().execute("SELECT status, COUNT(*) AS n FROM recipes GROUP BY status").fetchall()
    s = {"total": 0, "done": 0, "pending": 0, "transcribing": 0, "error": 0}
    for r in rows:
        key = r["status"] if r["status"] in s else "pending"
        s[key] = r["n"]
        s["total"] += r["n"]
    return s


def categories() -> list:
    with _lock:
        rows = conn().execute(
            "SELECT category, COUNT(*) AS n FROM recipes WHERE category <> '' "
            "GROUP BY category ORDER BY n DESC, category COLLATE NOCASE"
        ).fetchall()
    return [{"name": r["category"], "count": r["n"]} for r in rows]


# ------------------------------------------------------ captura de Facebook

def fb_add_urls(urls: list[str]) -> int:
    """Registra URLs capturadas de Facebook (sin duplicados). Devuelve cuántas
    se añadieron nuevas."""
    now = _now()
    added = 0
    with _lock:
        c = conn()
        for url in urls:
            url = (url or "").strip()
            if not url.startswith("http"):
                continue
            exists = c.execute("SELECT 1 FROM fb_captured WHERE url=?", (url,)).fetchone()
            if exists:
                continue
            kind = "video" if ("fbcdn" in url or ".mp4" in url) else "link"
            c.execute(
                "INSERT INTO fb_captured (url, kind, title, created_at) VALUES (?,?,?,?)",
                (url, kind, _fb_title(url), now),
            )
            added += 1
        c.commit()
    return added


def _fb_title(url: str) -> str:
    """Intenta dar un nombre humano a la URL capturada."""
    return "Vídeo de Facebook"


def fb_list() -> list:
    with _lock:
        rows = conn().execute(
            "SELECT * FROM fb_captured ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def fb_get(fid: int) -> dict | None:
    with _lock:
        row = conn().execute("SELECT * FROM fb_captured WHERE id=?", (fid,)).fetchone()
    return dict(row) if row else None


def fb_delete(fid: int) -> bool:
    with _lock:
        cur = conn().execute("DELETE FROM fb_captured WHERE id=?", (fid,))
        conn().commit()
    return cur.rowcount > 0


def fb_clear() -> int:
    with _lock:
        cur = conn().execute("DELETE FROM fb_captured")
        conn().commit()
    return cur.rowcount
