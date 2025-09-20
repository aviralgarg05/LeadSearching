import streamlit as st
import pandas as pd

from leadsearching.ingest_excel import ingest_zip
from leadsearching.indexing.build_index import build_index
from leadsearching.search.query import SearchEngine
from leadsearching.core.config import cfg

st.set_page_config(page_title="Lead Search", page_icon="🔎", layout="wide")

st.title("🔎 Lead Search (100k Sales Links)")

with st.sidebar:
    st.header("Setup")
    st.write("Data zip:", str(cfg.data_zip))
    if st.button("1) Ingest into SQLite"):
        with st.spinner("Ingesting... this may take a few minutes"):
            inserted = ingest_zip(cfg.data_zip)
        st.success(f"Inserted {inserted} new rows into {cfg.sqlite_path}")

    if st.button("2) Build Vector Index"):
        with st.spinner("Building vector index..."):
            build_index(persist=True)
        st.success("Vector index built.")

st.divider()
q = st.text_input("Enter your query", placeholder="e.g., CRM tool for small businesses with free tier")
col1, col2 = st.columns([1,1])
with col1:
    top_k = st.slider("Top K", 5, 50, 20)
with col2:
    _ = st.write("")

if st.button("Search") and q:
    se = SearchEngine()
    with st.spinner("Searching..."):
        results = se.query(q, k=top_k)
    st.subheader("Results")
    if not results:
        st.info("No results found yet. Make sure you've ingested data and built the index.")
    else:
        # Normalize results into a table-friendly structure
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

        # Ensure consistent column order
        cols = ["rank", "name", "title", "company", "domain", "city", "email", "phone", "company_phone", "score", "url"]
        df = df.reindex(columns=cols)

        st.subheader("Results (tabular)")
        st.dataframe(df, use_container_width=True)

        # Provide CSV download
        csv = df.to_csv(index=False)
        st.download_button(label="Download CSV", data=csv, file_name="leadsearch_results.csv", mime="text/csv")
