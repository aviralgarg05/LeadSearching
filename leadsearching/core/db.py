from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping, Any


def get_conn(sqlite_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(sqlite_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS sales_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_hash TEXT UNIQUE,
    title TEXT,
    url TEXT,
    description TEXT,
    source_sheet TEXT,
    raw_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS sales_links_fts USING fts5(
    title, description, url, content='sales_links', content_rowid='id'
);

CREATE TABLE IF NOT EXISTS sales_links_meta (
    id INTEGER PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales_link_attributes (
    link_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (link_id, key),
    FOREIGN KEY (link_id) REFERENCES sales_links(id) ON DELETE CASCADE
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def quick_check(conn: sqlite3.Connection) -> bool:
    try:
        cur = conn.execute("PRAGMA quick_check;")
        row = cur.fetchone()
        return bool(row and row[0] == "ok")
    except sqlite3.DatabaseError:
        return False


def upsert_rows(conn: sqlite3.Connection, rows: Iterable[Mapping[str, Any]]) -> int:
    cur = conn.cursor()
    inserted = 0
    for r in rows:
        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO sales_links(row_hash, title, url, description, source_sheet, raw_json)
                VALUES(?,?,?,?,?,?)
                """,
                (
                    r.get("row_hash"),
                    r.get("title"),
                    r.get("url"),
                    r.get("description"),
                    r.get("source_sheet"),
                    r.get("raw_json"),
                ),
            )
            if cur.rowcount:
                inserted += 1
            # fetch link id and upsert attributes if provided
            cur.execute("SELECT id FROM sales_links WHERE row_hash=?", (r.get("row_hash"),))
            rowid = cur.fetchone()[0]
            attrs = r.get("attrs") or {}
            if isinstance(attrs, dict):
                for k, v in attrs.items():
                    cur.execute(
                        "INSERT OR REPLACE INTO sales_link_attributes(link_id, key, value) VALUES(?,?,?)",
                        (rowid, str(k), None if v is None else str(v)),
                    )
        except sqlite3.IntegrityError:
            pass
    conn.commit()

    # Rebuild FTS from base table by recreating the virtual table to avoid corruption issues
    recreate_fts(conn)
    cur.execute(
        "INSERT INTO sales_links_fts(rowid, title, description, url) SELECT id, title, description, url FROM sales_links;"
    )
    conn.commit()
    return inserted


def search_fts(conn: sqlite3.Connection, q: str, limit: int = 20):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, s.title, s.url, s.description
        FROM sales_links_fts f
        JOIN sales_links s ON s.id = f.rowid
        WHERE sales_links_fts MATCH ?
        LIMIT ?
        """,
        (q, limit),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_row(conn: sqlite3.Connection, row_id: int) -> dict | None:
    cur = conn.cursor()
    cur.execute("SELECT * FROM sales_links WHERE id=?", (row_id,))
    r = cur.fetchone()
    if not r:
        return None
    cols = [d[0] for d in cur.description]
    row = dict(zip(cols, r))
    # attributes
    cur.execute("SELECT key, value FROM sales_link_attributes WHERE link_id=?", (row_id,))
    row["attributes"] = dict(cur.fetchall())
    return row


def recreate_fts(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    try:
        cur.execute("DROP TABLE IF EXISTS sales_links_fts;")
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS sales_links_fts USING fts5(
                title, description, url, content='sales_links', content_rowid='id'
            );
            """
        )
        conn.commit()
    except sqlite3.OperationalError:
        # Probably no FTS5 available; continue without FTS support
        conn.rollback()
