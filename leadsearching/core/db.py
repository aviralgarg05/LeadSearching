from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Dict, Any


def get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    
    # Main table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            row_hash TEXT UNIQUE,
            title TEXT,
            url TEXT,
            description TEXT,
            source_sheet TEXT,
            raw_json TEXT
        );
        """
    )
    
    # Attributes table for structured data
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_link_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            key TEXT,
            value TEXT,
            FOREIGN KEY (link_id) REFERENCES sales_links (id) ON DELETE CASCADE
        );
        """
    )
    
    # Index for fast attribute lookup
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_link_attributes_link_id 
        ON sales_link_attributes (link_id);
        """
    )
    
    # FTS table
    cur.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS sales_links_fts USING fts5(
            title, description, url, content='sales_links', content_rowid='id'
        );
        """
    )
    
    # Metadata table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_links_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    
    conn.commit()


def quick_check(conn: sqlite3.Connection) -> bool:
    """Check if the database is not corrupted."""
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA quick_check;")
        result = cur.fetchone()
        return result and result[0] == "ok"
    except Exception:
        return False


def upsert_rows(conn: sqlite3.Connection, rows: List[Dict[str, Any]]) -> int:
    cur = conn.cursor()
    inserted = 0
    
    for r in rows:
        # Insert main record
        cur.execute(
            """
            INSERT OR IGNORE INTO sales_links (row_hash, title, url, description, source_sheet, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
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
            link_id = cur.lastrowid
            
            # Insert attributes
            attrs = r.get("attrs", {})
            for key, value in attrs.items():
                if value is not None:
                    cur.execute(
                        """
                        INSERT INTO sales_link_attributes (link_id, key, value)
                        VALUES (?, ?, ?)
                        """,
                        (link_id, key, str(value))
                    )
    
    conn.commit()
    return inserted


def search_fts(conn: sqlite3.Connection, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        "SELECT rowid AS id, rank FROM sales_links_fts WHERE sales_links_fts MATCH ? ORDER BY rank LIMIT ?",
        (query, limit),
    )
    return [dict(r) for r in cur.fetchall()]


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