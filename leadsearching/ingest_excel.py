from __future__ import annotations
import zipfile
import json
import hashlib
from pathlib import Path
from typing import Generator, Dict, Any, Iterable

import pandas as pd

from .core.config import cfg
from .core.db import (
    get_conn,
    init_db,
    upsert_rows,
    quick_check,
    set_bulk_ingest_pragmas,
    drop_attribute_index,
    create_attribute_index,
)


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


def _yield_rows_from_csv(csv_bytes: bytes, source_sheet: str, sep: str = ",", chunksize: int = 100_000) -> Iterable[Dict[str, Any]]:
    """Stream rows from CSV/TSV content using pandas chunks for memory efficiency."""
    import io
    for chunk in pd.read_csv(io.BytesIO(csv_bytes), sep=sep, chunksize=chunksize):
        if chunk.empty:
            continue
        chunk.columns = chunk.columns.str.strip().str.lower()
        for _, row in chunk.iterrows():
            d = {}
            for col, val in row.items():
                if pd.isna(val):
                    continue
                d[col] = str(val).strip()
            if not d:
                continue
            url = d.get("url") or d.get("link") or d.get("linkedin_url") or ""
            title = d.get("job_title") or d.get("title") or d.get("position") or ""
            desc = d.get("description") or d.get("company_name") or ""
            record = {
                "title": title or None,
                "url": url,
                "description": desc or None,
                "source_sheet": source_sheet,
                "raw_json": json.dumps(d, ensure_ascii=False),
                "attrs": {k: v for k, v in d.items() if k not in ("title", "url", "description", "source_sheet")},
            }
            record["row_hash"] = _row_hash(record)
            yield record


def ingest_zip(zip_path: Path = cfg.data_zip, limit_rows: int | None = None, drop_index_during_ingest: bool = True) -> int:
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

    # Speed up bulk ingest
    set_bulk_ingest_pragmas(conn)
    if drop_index_during_ingest:
        drop_attribute_index(conn)

    with zipfile.ZipFile(zip_path, "r") as zf:
        count_inserted = 0
        processed = 0
        for name in zf.namelist():
            lower = name.lower()
            if not lower.endswith((".xlsx", ".xls", ".csv", ".tsv")):
                continue
            with zf.open(name) as f:
                content = f.read()

            if lower.endswith((".xlsx", ".xls")):
                row_iter = _yield_rows_from_excel(content, source_sheet=name)
            else:
                sep = "\t" if lower.endswith(".tsv") else ","
                row_iter = _yield_rows_from_csv(content, source_sheet=name, sep=sep)

            batch: list[Dict[str, Any]] = []
            BATCH_SIZE = 50_000
            for rec in row_iter:
                if limit_rows is not None and processed >= limit_rows:
                    break
                batch.append(rec)
                processed += 1
                if len(batch) >= BATCH_SIZE:
                    count_inserted += upsert_rows(conn, batch)
                    batch.clear()
            if batch:
                count_inserted += upsert_rows(conn, batch)

    # Recreate attribute index after bulk insert
    if drop_index_during_ingest:
        create_attribute_index(conn)
    return count_inserted