from __future__ import annotations
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path


SCHEMA = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    """CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY, dataset TEXT, username TEXT, name TEXT, bio TEXT, 
        category TEXT, follower_count INT, following_count INT, website TEXT, 
        email TEXT, phone TEXT, text_concat TEXT
    );""",
    """CREATE VIRTUAL TABLE IF NOT EXISTS leads_fts USING fts5(
        username, name, bio, category, website, email, phone, content=''
    );""",
    """CREATE TABLE IF NOT EXISTS processed_files(
        dataset TEXT, file_name TEXT PRIMARY KEY, row_count INT, completed_at TEXT
    );""",
    "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);",
]


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    with conn:
        for stmt in SCHEMA:
            conn.execute(stmt)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        conn.execute("BEGIN")
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def bulk_insert_leads(conn: sqlite3.Connection, rows: Iterable[tuple]):
    conn.executemany(
        """INSERT INTO leads(
            dataset, username, name, bio, category, follower_count, 
            following_count, website, email, phone, text_concat
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )


def bulk_insert_fts(conn: sqlite3.Connection, fts_rows: Iterable[tuple]):
    conn.executemany(
        """INSERT INTO leads_fts(
            rowid, username, name, bio, category, website, email, phone
        ) VALUES (last_insert_rowid(),?,?,?,?,?,?,?)""",
        fts_rows,
    )
