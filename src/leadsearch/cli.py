from __future__ import annotations
import argparse
import json
from pathlib import Path

from .ingest import ingest
from .search import hybrid_search


def _handle_ingest(args):
    """Handle ingest command."""
    ingest(
        Path(args.zip), 
        args.pattern, 
        args.dataset, 
        limit=args.limit, 
        no_vectors=args.no_vectors
    )


def _handle_search(args):
    """Handle search command."""
    datasets = None
    if args.datasets:
        datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    
    res = hybrid_search(args.query, k=args.k, alpha=args.alpha, datasets=datasets)
    
    if args.explain:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        for r in res:
            score = r['score']
            username = r.get('username') or ''
            name = r.get('name') or ''
            dataset = r.get('dataset')
            print(f"{score:.4f}\t{username}\t{name}\t{dataset}")


def _handle_api(args):
    """Handle API command."""
    try:
        import uvicorn
        from .api import app
        uvicorn.run(app, host=args.host, port=args.port)
    except ImportError:
        print("FastAPI/uvicorn not installed. Install with: pip install fastapi uvicorn")


def _handle_status(args):
    """Handle status command."""
    path = Path("data/status.json")
    if not path.exists():
        print("No status file yet")
        return
    print(path.read_text())


def main():
    parser = argparse.ArgumentParser("leadsearch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Ingest command
    p_ing = sub.add_parser("ingest", help="Ingest a dataset from within a ZIP archive")
    p_ing.add_argument("--zip", required=True, help="Path to zip archive")
    p_ing.add_argument(
        "--pattern", 
        required=True, 
        help="Glob pattern inside zip (e.g. '8 MILLION LEADS/*.csv')"
    )
    p_ing.add_argument("--dataset", required=True, help="Dataset identifier")
    p_ing.add_argument("--limit", type=int, help="Row limit for dry runs")
    p_ing.add_argument(
        "--no-vectors", 
        action="store_true", 
        help="Skip vector embedding (lexical only)"
    )

    # Search command
    p_search = sub.add_parser("search", help="Run a hybrid search query")
    p_search.add_argument("query", help="Query text")
    p_search.add_argument("--k", type=int, default=20)
    p_search.add_argument("--alpha", type=float, default=0.5)
    p_search.add_argument("--datasets", help="Comma separated dataset ids")
    p_search.add_argument("--explain", action="store_true")

    # API command
    p_api = sub.add_parser("api", help="Run FastAPI server")
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8000)

    # Status command
    sub.add_parser("status", help="Show last ingestion status JSON")

    args = parser.parse_args()
    
    # Route to handlers
    handlers = {
        "ingest": _handle_ingest,
        "search": _handle_search,
        "api": _handle_api,
        "status": _handle_status,
    }
    
    handler = handlers.get(args.cmd)
    if handler:
        handler(args)


if __name__ == "__main__":  # pragma: no cover
    main()
