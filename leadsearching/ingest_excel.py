from __future__ import annotations
import zipfile
import json
import hashlib
from pathlib import Path
from typing import Generator, Dict, Any

import pandas as pd

from .core.config import cfg
from .core.db import get_conn, init_db, upsert_rows, quick_check


def _row_hash(record: Dict[str, Any]) -> str:
    """Create a hash for deduplication."""
    content = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def _yield_rows_from_excel(excel_bytes: bytes, source_sheet: str) -> Generator[Dict[str, Any], None, None]:
    """Extract structured rows from Excel bytes."""
    try:
        df = pd.read_excel(excel_bytes, engine="openpyxl")
    except Exception:
        return
    
    if df.empty:
        return
    
    # Convert column names to lowercase for easier matching
    df.columns = df.columns.str.strip().str.lower()
    
    # Heuristic column mapping based on common patterns
    for _, row in df.iterrows():
        d = {}
        for col, val in row.items():
            if pd.isna(val):
                continue
            d[col] = str(val).strip()
        
        if not d:
            continue
            
        # Extract core fields with heuristics
        url = d.get("url") or d.get("link") or d.get("linkedin_url") or ""
        title = d.get("job_title") or d.get("title") or d.get("position") or ""
        desc = d.get("description") or d.get("company_name") or ""
        
        record = {
            "title": title or None,
            "url": url,
            "description": desc or None,
            "source_sheet": source_sheet,
            "raw_json": json.dumps(d, ensure_ascii=False),
            # Store non-core columns as attributes for later faceting/filtering
            "attrs": {k: v for k, v in d.items() if k not in ("title", "url", "description", "source_sheet")},
        }
        record["row_hash"] = _row_hash(record)
        yield record


def ingest_zip(zip_path: Path = cfg.data_zip) -> int:
    conn = get_conn(cfg.sqlite_path)
    try:
        init_db(conn)
        if not quick_check(conn):
            raise RuntimeError("SQLite quick_check failed; DB appears corrupted")
    except Exception:
        # Attempt to recreate the DB from scratch
        try:
            conn.close()
        except Exception:
            pass
        try:
            cfg.sqlite_path.unlink(missing_ok=True)
        except Exception:
            pass
        conn = get_conn(cfg.sqlite_path)
        init_db(conn)

    with zipfile.ZipFile(zip_path, "r") as zf:
        count_inserted = 0
        for name in zf.namelist():
            if not name.lower().endswith((".xlsx", ".xls")):
                continue
            with zf.open(name) as f:
                xbytes = f.read()
            rows = list(_yield_rows_from_excel(xbytes, source_sheet=name))
            count_inserted += upsert_rows(conn, rows)
    return count_inserted