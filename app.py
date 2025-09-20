import streamlit as st

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
q = st.text_input("Enter your query", placeholder="e.g., senior software engineer munich")

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
        for i, r in enumerate(results, start=1):
            with st.container(border=True):
                name = r.get("name") or "N/A"
                company = r.get("company") or "N/A"
                domain = r.get("domain") or "N/A"
                title = r.get("title") or "N/A"
                city = r.get("city") or "N/A"
                email = r.get("email") or "N/A"
                url = r.get("url")
                score = r.get("score")
                
                st.markdown(f"**{i}. {name}**")
                st.write(f"**Company:** {company} ({domain})")
                st.write(f"**Title:** {title}")
                st.write(f"**Location:** {city}")
                st.write(f"**Email:** {email}")
                if url:
                    st.write(f"**LinkedIn:** {url}")
                if score:
                    st.caption(f"Relevance Score: {score:.3f}")
else:
    st.info("Enter a search query and click Search to find contacts.")