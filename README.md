# LeadSearching

End-to-end local search over a 100k-row sales links dataset using Python, SQLite FTS, LlamaIndex with HuggingFace embeddings + Chroma, and a simple Streamlit UI.

## What this provides
- Ingestion from the provided zip (Excel inside) into a local SQLite database
- Full-text search fallback via SQLite FTS5
- Vector search via LlamaIndex + Chroma with local embeddings (no cloud calls)
- Optional local LLM (llama.cpp) for future RAG enhancements
- Streamlit UI for quick testing, and a small CLI for automation

## Setup
1) Create a virtual environment and install deps
```
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

2) Put your zip in the project root (already present):
`100k Sales Link 7 file-20250920T133656Z-1-001.zip`

3) (Optional) Set env vars in `.env` if desired:
- `EMBEDDING_MODEL` (default: sentence-transformers/all-MiniLM-L6-v2)
- `LLAMA_CPP_MODEL` path to a local GGUF model to enable local LLM

## Usage

CLI
```
python cli.py ingest      # parse Excel in zip -> SQLite
python cli.py index       # build Chroma vector index
python cli.py query "crm for small business"
```

### Example Queries
Try these sample queries to test the search functionality:
- "email marketing tools for startups"
- "project management software free"
- "sales automation platforms"
- "customer relationship management open source"

Streamlit
```
streamlit run app.py
```

## Storage
- SQLite/Chroma/index files are stored under `.storage/`
- Large files and models are git-ignored

## Notes
- The ingestion heuristics try to detect title/url/description column names. Adjust in `leadsearching/ingest_excel.py` if needed for your specific sheet.
