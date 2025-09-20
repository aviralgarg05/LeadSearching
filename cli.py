#!/usr/bin/env python3
from __future__ import annotations
import argparse

from leadsearching.ingest_excel import ingest_zip
from leadsearching.indexing.build_index import build_index
from leadsearching.search.query import SearchEngine
from leadsearching.core.config import cfg


def main():
    ap = argparse.ArgumentParser(description="LeadSearching CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="Ingest Excel inside zip into SQLite")
    sub.add_parser("index", help="Build vector index (Chroma)")
    sub.add_parser("reset-db", help="Delete SQLite and vector index to start fresh")

    sp = sub.add_parser("query", help="Query the index/FTS")
    sp.add_argument("q", help="Query text")
    sp.add_argument("--k", type=int, default=10)

    args = ap.parse_args()

    if args.cmd == "ingest":
        n = ingest_zip(cfg.data_zip)
        print(f"Inserted {n} rows")
    elif args.cmd == "index":
        build_index(persist=True)
        print("Index built.")
    elif args.cmd == "reset-db":
        # Remove SQLite DB and Chroma persistence
        try:
            cfg.sqlite_path.unlink(missing_ok=True)
        except Exception:
            pass
        # Remove Chroma dir marker files
        if cfg.chroma_dir.exists():
            import shutil
            try:
                shutil.rmtree(cfg.chroma_dir)
            except Exception:
                # Try to remove individual files
                for p in cfg.chroma_dir.rglob("*"):
                    try:
                        if p.is_file():
                            p.unlink()
                    except Exception:
                        pass
        print("Storage reset. Re-run ingest and index.")
    elif args.cmd == "query":
        se = SearchEngine()
        res = se.query(args.q, k=args.k)
        for r in res:
            print(r)


if __name__ == "__main__":
    main()