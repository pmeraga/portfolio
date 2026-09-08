import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("SF_INDEX_DB", "index.db")

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with open(_SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
