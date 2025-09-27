# Architecture Overview

## Goals
- Efficient multi-dataset ingestion (8M CSV shards + 100k XLSX) with minimal RAM.
- Immediate lexical search availability while vectors build.
- Modular, resumable pipeline with transparent status.
- Support natural language queries via semantic embeddings + hybrid fusion.

## Components
| Module | Responsibility |
|--------|----------------|
| `config.py` | Load environment & defaults. |
| `progress.py` | Emit + persist progress heartbeat JSON. |
| `db.py` | SQLite connection + schema migrations + FTS helpers. |
| `embedding.py` | Lazy singleton embedding model + encode batches (fp16). |
| `vector_index.py` | ANN abstraction (FAISS or HNSW) create/add/search/save/load. |
| `ingest.py` | Streaming ZIP member reader, CSV/XLSX row normalization, batching, insertion, embedding. |
| `search.py` | Query parsing, vector + FTS retrieval, fusion. |
| `cli.py` | Typer-like (plain argparse) CLI commands. |
| `api.py` | FastAPI app exposing /search endpoint. |

## Data Model

SQLite tables:
```
leads(
  id INTEGER PRIMARY KEY,
  dataset TEXT NOT NULL,
  username TEXT, name TEXT, bio TEXT, category TEXT,
  follower_count INT, following_count INT,
  website TEXT, email TEXT, phone TEXT,
  text_concat TEXT
)

-- FTS virtual table (contentless for space efficiency)
leads_fts(username, name, bio, category, website, email, phone)

processed_files(dataset TEXT, file_name TEXT PRIMARY KEY, row_count INT, completed_at TEXT)
meta(key TEXT PRIMARY KEY, value TEXT)
```

## Vector Index Files
Stored under `LS_INDEX_DIR`:
- `vectors.faiss` (or `hnsw.bin`)
- `id_mapping.npy` (NumPy array of row ids aligned with vector order)
- `meta.json`

## Ingestion Flow
1. Open ZIP -> enumerate target members (pattern filter).
2. For each file not yet in `processed_files`:
   - Stream rows (CSV: python csv reader with proper quoting; XLSX: openpyxl row iterator) -> normalize.
   - Collect rows in batch (size `B`).
   - Insert into `leads` + `leads_fts` (FTS uses parameterized insert).
   - Build embedding for new rows (unless `--no-vectors`).
   - Append embeddings to ANN index (deferred create until first batch).
   - Update status JSON.
3. Mark file complete; commit.

Resumable because `processed_files` prevents re-processing & vector index grows append-only.

## Query Flow
1. Receive user query string.
2. Generate embedding.
3. ANN search top `k_vec` (default 200) -> candidate ids + distances.
4. FTS search across selected datasets (limit `k_fts` default 200) using quoted user query.
5. Normalize scores; combine by id using weighted sum + reciprocal rank fallback.
6. Fetch rows (SELECT ... WHERE id IN (...)).
7. Return JSON sorted by hybrid score.

## Performance Considerations
- Batched inserts inside a transaction keep SQLite fast.
- FTS5 with contentless table reduces duplication.
- Float16 storage halves memory of vectors; FAISS supports adding FP16 -> internally converts if needed.
- Option to delay embedding (lexical-first) when memory constrained.

## Failure & Reliability
- Status file updated after each committed batch (idempotent writes).
- Partial batch crash safe: either committed entirely or retried.
- Vector index persisted after each batch to avoid large redo on restart (configurable flush interval).

## Security & PII
The dataset contains potential emails & phone numbers; system avoids logging raw PII beyond necessary debug counts.

## Extensions
- Add filtering (category, min follower count) via SQL WHERE.
- Add re-ranking cross-encoder for top 50 results (future optional dependency).
