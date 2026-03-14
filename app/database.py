"""
database.py — Database initialisation, seed data, and query helpers.

Uses SQLite so the portal can run on any low-cost server or even a
Raspberry Pi without extra dependencies.
"""

import os
import sqlite3
from typing import List, Optional, Tuple

# Default DB path (can be overridden via environment variable for tests)
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "village_jobs.db",
)
DB_PATH: str = os.environ.get("VJP_DB_PATH", _DEFAULT_DB_PATH)

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "db",
    "schema.sql",
)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_SEED_WORKERS: List[Tuple] = [
    # (name, phone, skill, location, is_available, rating)
    ("Ramesh Kumar",    "+919876543210", "tractor mechanic", "Sitapur",   1, 4.8),
    ("Suresh Yadav",    "+919876543211", "tractor mechanic", "Hardoi",    1, 4.5),
    ("Dinesh Singh",    "+919876543212", "tractor mechanic", "Sitapur",   0, 4.2),
    ("Mohan Lal",       "+919876543213", "mason",            "Sitapur",   1, 4.9),
    ("Rajesh Sharma",   "+919876543214", "mason",            "Hardoi",    1, 4.6),
    ("Chotu Mistri",    "+919876543215", "mason",            "Lakhimpur", 1, 4.3),
    ("Anil Plumber",    "+919876543216", "plumber",          "Sitapur",   1, 4.7),
    ("Vijay Nal",       "+919876543217", "plumber",          "Hardoi",    1, 4.4),
    ("Sanjay Bahadur",  "+919876543218", "electrician",      "Sitapur",   1, 4.8),
    ("Pradeep Bijli",   "+919876543219", "electrician",      "Hardoi",    1, 4.5),
    ("Ramu Fasal",      "+919876543220", "harvesting labour","Sitapur",   1, 4.6),
    ("Shyam Khet",      "+919876543221", "harvesting labour","Hardoi",    1, 4.4),
    ("Ghanshyam Das",   "+919876543222", "harvesting labour","Lakhimpur", 1, 4.3),
    ("Bholu Carpenter", "+919876543223", "carpenter",        "Sitapur",   1, 4.7),
    ("Munna Badhai",    "+919876543224", "carpenter",        "Hardoi",    1, 4.5),
    ("Pappu Painter",   "+919876543225", "painter",          "Sitapur",   1, 4.6),
    ("Ravi Rangai",     "+919876543226", "painter",          "Hardoi",    1, 4.3),
    ("Bunty Welding",   "+919876543227", "welder",           "Sitapur",   1, 4.5),
    ("Sonu Iron",       "+919876543228", "welder",           "Hardoi",    1, 4.4),
]

_SEED_ALIASES: List[Tuple[str, str]] = [
    # Canonical skill names map to themselves so direct English terms always work
    ("mason",               "mason"),
    ("tractor mechanic",    "tractor mechanic"),
    ("plumber",             "plumber"),
    ("electrician",         "electrician"),
    ("harvesting labour",   "harvesting labour"),
    ("carpenter",           "carpenter"),
    ("painter",             "painter"),
    ("welder",              "welder"),
    # Hindi / local terms → canonical skill
    ("mistri",              "mason"),
    ("raj mistri",          "mason"),
    ("raj-mistri",          "mason"),
    ("diwaar",              "mason"),
    ("wall",                "mason"),
    ("construction",        "mason"),
    ("nal",                 "plumber"),
    ("paani",               "plumber"),
    ("water pipe",          "plumber"),
    ("bijli",               "electrician"),
    ("electric",            "electrician"),
    ("bijliwala",           "electrician"),
    ("tractor",             "tractor mechanic"),
    ("mechanic",            "tractor mechanic"),
    ("tractor repair",      "tractor mechanic"),
    ("fasal",               "harvesting labour"),
    ("harvest",             "harvesting labour"),
    ("harvesting",          "harvesting labour"),
    ("kaat",                "harvesting labour"),
    ("mazdoor",             "harvesting labour"),
    ("labour",              "harvesting labour"),
    ("laborer",             "harvesting labour"),
    ("badhai",              "carpenter"),
    ("lakdi",               "carpenter"),
    ("wood",                "carpenter"),
    ("paint",               "painter"),
    ("rangai",              "painter"),
    ("welding",             "welder"),
    ("iron",                "welder"),
]

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a sqlite3 connection with row_factory set to Row."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db(db_path: Optional[str] = None) -> None:
    """Create tables (from schema.sql) and populate seed data if empty."""
    conn = get_connection(db_path)
    try:
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())
        conn.commit()
        _seed_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0] == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO workers (name, phone, skill, location, is_available, rating) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            _SEED_WORKERS,
        )
    if conn.execute("SELECT COUNT(*) FROM skill_aliases").fetchone()[0] == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO skill_aliases (alias, skill) VALUES (?, ?)",
            _SEED_ALIASES,
        )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def resolve_skill(keyword: str, db_path: Optional[str] = None) -> Optional[str]:
    """
    Look up *keyword* in skill_aliases.  Returns the canonical skill name
    or None when no match is found.
    """
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT skill FROM skill_aliases WHERE alias = ?",
            (keyword.lower().strip(),),
        ).fetchone()
        return row["skill"] if row else None
    finally:
        conn.close()


def find_workers(
    skill: str,
    location: Optional[str] = None,
    limit: int = 3,
    db_path: Optional[str] = None,
) -> List[sqlite3.Row]:
    """
    Return up to *limit* available workers for *skill*, ordered by rating
    (descending).  If *location* is provided, workers from that location are
    ranked first, but workers from other locations are still included to
    guarantee results when local supply is thin.
    """
    conn = get_connection(db_path)
    try:
        if location:
            rows = conn.execute(
                """
                SELECT name, phone, skill, location, rating
                FROM   workers
                WHERE  skill = ? AND is_available = 1
                ORDER BY
                    CASE WHEN lower(location) = lower(?) THEN 0 ELSE 1 END,
                    rating DESC
                LIMIT ?
                """,
                (skill, location, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT name, phone, skill, location, rating
                FROM   workers
                WHERE  skill = ? AND is_available = 1
                ORDER BY rating DESC
                LIMIT ?
                """,
                (skill, limit),
            ).fetchall()
        return rows
    finally:
        conn.close()


def log_request(
    requester_phone: str,
    raw_message: str,
    parsed_skill: Optional[str],
    response_text: Optional[str],
    db_path: Optional[str] = None,
) -> int:
    """Persist an SMS request log entry and return its row id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO sms_requests (requester_phone, raw_message, parsed_skill, response_text)
            VALUES (?, ?, ?, ?)
            """,
            (requester_phone, raw_message, parsed_skill, response_text),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_skills(db_path: Optional[str] = None) -> List[str]:
    """Return a sorted list of all distinct canonical skills in the DB."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT skill FROM workers ORDER BY skill"
        ).fetchall()
        return [r["skill"] for r in rows]
    finally:
        conn.close()


def set_worker_availability(
    phone: str, is_available: bool, db_path: Optional[str] = None
) -> bool:
    """Toggle a worker's availability. Returns True if a row was updated."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "UPDATE workers SET is_available = ? WHERE phone = ?",
            (1 if is_available else 0, phone),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
