from __future__ import annotations
import io
import json
import hashlib
import zipfile
from pathlib import Path
from typing import Iterator, Dict, Any

import pandas as pd

from .core.config import cfg
from .core.db import get_conn, init_db, upsert_rows, quick_check


def _row_hash(obj: Dict[str, Any]) -> str:
    m = hashlib.sha256()
    m.update(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return m.hexdigest()


def _yield_rows_from_excel(xlsx_bytes: bytes, source_sheet: str | None = None) -> Iterator[Dict[str, Any]]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes))
    # Normalize column names
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Heuristics: find likely fields
    title_cols = [c for c in df.columns if c in ("title", "name", "company", "product", "sales_link_name")]
    url_cols = [c for c in df.columns if "url" in c or "link" in c]
    desc_cols = [c for c in df.columns if c in ("description", "details", "notes", "summary")]

    for _, row in df.iterrows():
        d_raw = row.to_dict()
        d = {k: (None if pd.isna(v) else str(v)) for k, v in d_raw.items()}
        title = next((d.get(c) for c in title_cols if d.get(c)), None)
        url = next((d.get(c) for c in url_cols if d.get(c)), None)
        desc = next((d.get(c) for c in desc_cols if d.get(c)), None)

        record = {
            "title": title,
            "url": url,
            "description": desc,
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


if __name__ == "__main__":
    inserted = ingest_zip()
    print(f"Inserted {inserted} new rows into {cfg.sqlite_path}")
