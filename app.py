import os
import sys
import logging

# Ensure modern SQLite on platforms with old sqlite3 (e.g., Streamlit Cloud)
try:
    import sqlite3  # noqa: F401
    import pysqlite3 as _pysqlite3  # type: ignore
    sys.modules["sqlite3"] = _pysqlite3
except Exception:
    # If pysqlite3 isn't available locally, continue; it's included in cloud requirements.
    pass

import streamlit as st
import pandas as pd

from leadsearching.ingest_excel import ingest_zip
from leadsearching.indexing.build_index import build_index
from leadsearching.search.query import SearchEngine
from leadsearching.core.config import cfg

"""Streamlit app for lead search with clean, tabular results."""

# Reduce noisy third‑party logs and telemetry
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
# Disable Chroma telemetry to fix telemetry warnings
os.environ.setdefault("CHROMA_CLIENT_TELEMETRY", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
# Some libs respect this for warning suppression; adjust as needed
os.environ.setdefault("PYTHONWARNINGS", "ignore")

logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)

st.set_page_config(page_title="Lead Search", page_icon="🔎", layout="wide")

st.title("🔎 Lead Search")

with st.sidebar:
    st.header("Setup")
    st.write("Data zip:", str(cfg.data_zip))
    st.write("Storage:", str(cfg.storage_dir))

    # Lightweight readiness checks
    try:
        import sqlite3
        conn = sqlite3.connect(cfg.sqlite_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM sales_links")
        row_count = cur.fetchone()[0]
        conn.close()
    except Exception:
        row_count = 0
    st.caption(f"SQLite rows: {row_count}")
    index_built = (cfg.index_dir / "BUILT").exists()
    st.caption(f"Vector index built: {'yes' if index_built else 'no'}")
    fast_start = st.toggle("Fast start (sample only)", value=True, help="Quickly ingest a small sample and build a small index so the app is usable immediately. You can run full ingest/index later.")
    sample_size = 200_000 if fast_start else None
    index_limit = 150_000 if fast_start else None

    if st.button("1) Ingest into SQLite"):
        with st.spinner("Ingesting... this may take a few minutes"):
            inserted = ingest_zip(cfg.data_zip, limit_rows=sample_size)
        st.success(f"Inserted {inserted} new rows into {cfg.sqlite_path}")
        st.rerun()

    if st.button("2) Build Vector Index"):
        with st.spinner("Building vector index..."):
            build_index(persist=True, limit=index_limit)
        st.success("Vector index built.")
        st.rerun()

st.divider()

# Cache the SearchEngine to avoid recreating on every search
@st.cache_resource
def get_search_engine():
    """Create and cache the SearchEngine instance"""
    return SearchEngine()

q = st.text_input("Enter your query", placeholder="e.g., senior software engineer munich")

col1, col2 = st.columns([1,1])
with col1:
    top_k = st.slider("Top K", 5, 50, 20)
with col2:
    _ = st.write("")

if st.button("Search") and q:
    se = get_search_engine()
    with st.spinner("Searching..."):
        results = se.query(q, k=top_k)
    st.subheader("Results")
    if not results:
        st.info("No results found yet. Make sure you've ingested data and built the index.")
    else:
        # Build a tabular view of results
        rows = []
        for i, r in enumerate(results, start=1):
            rows.append({
                "rank": i,
                "name": r.get("name"),
                "title": r.get("title"),
                "company": r.get("company"),
                "domain": r.get("domain"),
                "city": r.get("city"),
                "email": r.get("email"),
                "phone": r.get("phone"),
                "company_phone": r.get("company_phone"),
                "score": r.get("score"),
                "url": r.get("url"),
            })

        df = pd.DataFrame(rows)
        cols = ["rank", "name", "title", "company", "domain", "city", "email", "phone", "company_phone", "score", "url"]
        df = df.reindex(columns=cols)

        st.dataframe(df, width="stretch")
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", data=csv, file_name="leadsearch_results.csv", mime="text/csv")
else:
    st.info("Enter a search query and click Search to find contacts.")
