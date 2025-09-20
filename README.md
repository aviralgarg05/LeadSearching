# LeadSearching

End-to-end local search over a 100k-row sales links dataset using Python, SQLite FTS, LlamaIndex with HuggingFace embeddings + Chroma, and a simple Streamlit UI.

## ✅ System Status
**FULLY OPERATIONAL** - Perfect searching with complete structured data!

- ✅ **Data Ingested**: 21,489 contact records with full metadata
- ✅ **Vector Index Built**: Semantic search with sentence transformers
- ✅ **Perfect Search Results**: Returns complete contact info (name, company, email, title, location, etc.)
- ✅ **Data Quality**: Verified - minimal nulls, valid URLs, comprehensive coverage
- ✅ **CLI & API**: Working search interface with structured output

## What this provides
- Ingestion from the provided zip (Excel inside) into a local SQLite database
- Full-text search fallback via SQLite FTS5
- Vector search via LlamaIndex + Chroma with local embeddings (no cloud calls)
- **Structured contact results** with complete information (name, company, domain, email, title, city, phone)
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

2) Put your zip in the project root:
`100k Sales Link 7 file-20250920T133656Z-1-001.zip`

3) (Optional) Set env vars in `.env` if desired:
- `EMBEDDING_MODEL` (default: sentence-transformers/all-MiniLM-L6-v2)
- `LLAMA_CPP_MODEL` path to a local GGUF model to enable local LLM

## Usage

CLI - **Recommended for testing**
```bash
# Data pipeline
python cli.py ingest      # parse Excel in zip -> SQLite
python cli.py index       # build Chroma vector index

# Search with structured results
python cli.py query "senior software engineer munich" --k 5
python cli.py query "machine learning bmw" --k 3
python cli.py query "sales manager frankfurt" --k 5
```

Streamlit UI
```bash
streamlit run app.py
```

## Example Search Results
```
Query: "senior software engineer munich"
Results:
1. Federico Miroballo - Magneti Marelli GmbH (luxoft.com)
   Software Architect | Greater Munich Metropolitan Area
   Email: fmiroballo@luxoft.com | Score: 0.525

2. Mohamed kamal Abozeid - BMW Group (bmwgroup.com)
   Software Architect | Greater Munich Metropolitan Area
   Email: mohamed-kamalabozeid@bmwgroup.com | Score: 0.516
```

## Storage
- SQLite/Chroma/index files are stored under `.storage/`
- Large files and models are git-ignored

## Notes
- The ingestion heuristics try to detect title/url/description column names. Adjust in `leadsearching/ingest_excel.py` if needed for your specific sheet.
- Search returns complete contact information including: name, company, domain, email, job title, city, phone numbers, and relevance scores.