import os
import sys
import logging
from pathlib import Path

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

st.title("🔎 Lead Search (100k Sales Links)")

# Helpers for zip sourcing on Cloud
def _ensure_storage_dir() -> Path:
    p = Path(".storage")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_uploaded_zip(uploaded_file) -> Path:
    storage = _ensure_storage_dir()
    name = uploaded_file.name or "uploaded.zip"
    # Light sanitization
    safe_name = name.replace("/", "_").replace("\\", "_")
    dest = storage / safe_name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


def _download_zip(url: str) -> Path:
    import requests
    storage = _ensure_storage_dir()
    dest = storage / "downloaded.zip"
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return dest


with st.sidebar:
    st.header("Setup")

    default_zip = Path(cfg.data_zip)
    default_exists = default_zip.exists()
    st.caption(f"Default zip path: {default_zip} {'(found)' if default_exists else '(missing)'}")

    uploaded = st.file_uploader("Upload data zip", type=["zip"], accept_multiple_files=False, key="uploaded_zip")
    url_default = os.getenv("DATA_ZIP_URL", "")
    zip_url = st.text_input("Or provide a zip URL (optional)", value=url_default)

    if st.button("1) Ingest into SQLite"):
        try:
            zip_path: Path | None = None
            if uploaded is not None:
                zip_path = _save_uploaded_zip(uploaded)
            elif zip_url.strip():
                zip_path = _download_zip(zip_url.strip())
            elif default_exists:
                zip_path = default_zip

            if not zip_path or not zip_path.exists():
                st.error("No data zip available. Upload a zip or provide DATA_ZIP_URL, or place the zip at the default path.")
            else:
                with st.spinner("Ingesting... this may take a few minutes"):
                    inserted = ingest_zip(zip_path)
                st.success(f"Inserted {inserted} new rows into {cfg.sqlite_path}")
        except Exception as e:
            st.exception(e)

    if st.button("2) Build Vector Index"):
        try:
            with st.spinner("Building vector index..."):
                build_index(persist=True)
            st.success("Vector index built.")
        except Exception as e:
            st.exception(e)

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
