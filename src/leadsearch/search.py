from __future__ import annotations
import sqlite3
from .config import get_settings
from .embedding import encode_texts
from .vector_index import VectorIndex


def hybrid_search(
    query: str, 
    k: int = 20, 
    alpha: float = 0.5, 
    datasets: list[str] | None = None
) -> list[dict[str, any]]:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    # Vector search
    index = VectorIndex.load(settings.index_dir)
    vec_results = []
    if index:
        qvec = encode_texts([query])
        ids, dists = index.search(qvec, k= max(k*5, 100))
        # Convert distances to similarity
        sims = 1 - dists
        for rid, sim in zip(ids, sims, strict=True):
            vec_results.append((int(rid), float(sim)))
    # FTS search
    dataset_filter = (
        f"AND dataset IN ({','.join('?' for _ in datasets)})"
        if datasets 
        else ""
    )
    fts_query = (
        "SELECT id FROM leads WHERE id IN "
        "(SELECT rowid FROM leads_fts WHERE leads_fts MATCH ?) "
        f"{dataset_filter} LIMIT ?"
    )
    fts_rows = conn.execute(
        fts_query,
        ([query] + (datasets or []) + [k * 5]),
    ).fetchall()
    fts_results = [(r[0], 1.0) for r in fts_rows]
    # Merge
    score_map: dict[int, float] = {}
    def add(scores, weight):
        for rank, (rid, s) in enumerate(scores, start=1):
            rr = 1 / rank
            score_map[rid] = score_map.get(rid, 0.0) + weight * (s + rr)
    add(vec_results, alpha)
    add(fts_results, 1 - alpha)
    # Fetch top k rows
    ranked = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:k]
    if not ranked:
        return []
    ids_needed = [r[0] for r in ranked]
    select_query = (
        "SELECT id, dataset, username, name, bio, category, "
        "follower_count, following_count, website, email, phone "
        f"FROM leads WHERE id IN ({','.join('?' for _ in ids_needed)})"
    )
    rows = conn.execute(select_query, ids_needed).fetchall()
    row_map = {r[0]: r for r in rows}
    results = []
    for rid, score in ranked:
        row = row_map.get(rid)
        if not row:
            continue
        results.append({"id": rid, "score": score, **dict(row)})
    return results
