#!/usr/bin/env python3
from __future__ import annotations
import argparse


def main():
    ap = argparse.ArgumentParser(description="LeadSearching CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_ingest = sub.add_parser("ingest", help="Ingest Excel/CSV/TSV inside zip into SQLite")
    sp_ingest.add_argument("--limit-rows", type=int, default=None, help="Limit rows to ingest for a fast start")

    sp_index = sub.add_parser("index", help="Build vector index (Chroma)")
    sp_index.add_argument("--limit", type=int, default=None, help="Limit number of rows to index for a fast start")
    sub.add_parser("reset-db", help="Delete SQLite and vector index to start fresh")

    sp = sub.add_parser("query", help="Query the index/FTS")
    sp.add_argument("q", help="Query text")
    sp.add_argument("--k", type=int, default=10)

    args = ap.parse_args()

    if args.cmd == "ingest":
        # Lazy imports to avoid loading heavy deps on CLI help
        from leadsearching.ingest_excel import ingest_zip
        from leadsearching.core.config import cfg

        n = ingest_zip(cfg.data_zip, limit_rows=args.limit_rows)
        print(f"Inserted {n} rows")
    elif args.cmd == "index":
        # Lazy import heavy index builder
        from leadsearching.indexing.build_index import build_index

        build_index(persist=True, limit=args.limit)
        print("Index built.")
    elif args.cmd == "reset-db":
        # Remove SQLite DB and Chroma persistence
        from leadsearching.core.config import cfg

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
        # Disable telemetry for CLI usage
        import os
        os.environ.setdefault("CHROMA_CLIENT_TELEMETRY", "false")
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        
        # Lazy import search engine to avoid startup overhead on help
        from leadsearching.search.query import SearchEngine

        se = SearchEngine()
        res = se.query(args.q, k=args.k)
        if not res:
            print("No results found.")
        else:
            for i, r in enumerate(res, 1):
                name = r.get("name", "N/A")
                company = r.get("company", "N/A")
                title = r.get("title", "N/A")
                email = r.get("email", "N/A")
                city = r.get("city", "N/A")
                score = r.get("score")
                
                print(f"{i}. {name} - {company}")
                print(f"   {title} | {city}")
                print(f"   Email: {email}")
                if score is not None:
                    print(f"   Score: {score:.3f}")
                print()


if __name__ == "__main__":
    main()