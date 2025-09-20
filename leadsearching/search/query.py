from __future__ import annotations
from typing import List, Dict, Any
from functools import lru_cache
import os
import sys

# Ensure modern SQLite on platforms with old sqlite3 (e.g., Streamlit Cloud)
try:
    import sqlite3  # noqa: F401
    import pysqlite3 as _pysqlite3  # type: ignore
    sys.modules["sqlite3"] = _pysqlite3
except Exception:
    # If pysqlite3 isn't available locally, continue; it's included in cloud requirements.
    pass

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

from ..core.config import cfg
from ..core.db import get_conn, search_fts, get_row

# Disable Chroma telemetry
os.environ.setdefault("CHROMA_CLIENT_TELEMETRY", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


class SearchEngine:
    def __init__(self) -> None:
        # Disable telemetry for this client instance
        client = chromadb.PersistentClient(
            path=str(cfg.chroma_dir),
            settings=chromadb.config.Settings(anonymized_telemetry=False)
        )
        collection = client.get_or_create_collection(name="sales_links")
        self.vs = ChromaVectorStore(chroma_collection=collection, collection_name="sales_links")
        self.embed = HuggingFaceEmbedding(model_name=cfg.embedding_model)
        self.index = VectorStoreIndex.from_vector_store(self.vs, embed_model=self.embed)
        # Cache database connection
        self._conn = None

    @property
    def conn(self):
        """Cached database connection"""
        if self._conn is None:
            self._conn = get_conn(cfg.sqlite_path)
        return self._conn

    @lru_cache(maxsize=100)
    def _get_rows_batch(self, row_ids_tuple: tuple) -> Dict[int, Dict]:
        """Batch fetch rows for better performance"""
        if not row_ids_tuple:
            return {}
        
        placeholders = ','.join('?' * len(row_ids_tuple))
        cur = self.conn.cursor()
        
        # Get main records
        cur.execute(f"SELECT * FROM sales_links WHERE id IN ({placeholders})", row_ids_tuple)
        main_rows = {row[0]: dict(row) for row in cur.fetchall()}
        
        # Get attributes for all rows at once
        cur.execute(f"""
            SELECT link_id, key, value 
            FROM sales_link_attributes 
            WHERE link_id IN ({placeholders})
        """, row_ids_tuple)
        
        # Group attributes by link_id
        attributes_by_id = {}
        for link_id, key, value in cur.fetchall():
            if link_id not in attributes_by_id:
                attributes_by_id[link_id] = {}
            attributes_by_id[link_id][key] = value
        
        # Combine main records with attributes
        result = {}
        for row_id in row_ids_tuple:
            if row_id in main_rows:
                main_rows[row_id]["attributes"] = attributes_by_id.get(row_id, {})
                result[row_id] = main_rows[row_id]
        
        return result

    def _format_result(self, structured: Dict, score: float = None) -> Dict[str, Any]:
        """Format a single result for consistent output"""
        attrs = structured.get("attributes", {}) or {}
        return {
            "name": (attrs.get("first_name", "") + " " + attrs.get("last_name", "")).strip() or None,
            "email": attrs.get("email_first") or attrs.get("email"),
            "company": attrs.get("company_name") or attrs.get("company"),
            "domain": attrs.get("company_domain"),
            "title": attrs.get("job_title") or structured.get("title"),
            "city": attrs.get("city"),
            "phone": attrs.get("phone"),
            "company_phone": attrs.get("company_phone"),
            "url": structured.get("url"),
            "score": score,
        }

    def _vector_search(self, q: str, k: int) -> List[Dict[str, Any]]:
        """Perform vector search and return formatted results"""
        try:
            retriever = self.index.as_retriever(similarity_top_k=k)
            nodes = retriever.retrieve(q)
            
            # Extract row IDs
            row_ids = []
            node_metadata = []
            for sn in nodes:
                md = getattr(sn.node, "metadata", {}) or {}
                row_id = md.get("id")
                if row_id is not None:
                    row_ids.append(int(row_id))
                    node_metadata.append((sn, md))
            
            if not row_ids:
                return []
            
            # Batch fetch all required rows
            structured_data = self._get_rows_batch(tuple(row_ids))
            
            # Format results
            items = []
            for sn, md in node_metadata:
                row_id = int(md.get("id"))
                if row_id in structured_data:
                    score = getattr(sn, "score", None)
                    items.append(self._format_result(structured_data[row_id], score))
                else:
                    # Fallback for missing data
                    items.append({
                        "title": md.get("title"),
                        "url": md.get("url"),
                        "text": sn.node.get_content(),
                        "score": getattr(sn, "score", None),
                    })
            
            return items
        except Exception:
            # Vector index may not be built yet
            return []

    def _fts_search(self, q: str, k: int) -> List[Dict[str, Any]]:
        """Perform FTS search and return formatted results"""
        rows = search_fts(self.conn, q, limit=k)
        if not rows:
            return []
        
        # Extract row IDs and batch fetch
        row_ids = tuple(int(r["id"]) for r in rows)
        structured_data = self._get_rows_batch(row_ids)
        
        # Format results
        items = []
        for r in rows:
            row_id = int(r["id"])
            if row_id in structured_data:
                items.append(self._format_result(structured_data[row_id]))
            else:
                # Fallback for missing data
                items.append({
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "score": None,
                })
        
        return items

    def query(self, q: str, k: int = 20) -> List[Dict[str, Any]]:
        """Search for contacts using vector search with FTS fallback"""
        # Try vector search first
        items = self._vector_search(q, k)
        if items:
            return items
        
        # Fallback to FTS
        return self._fts_search(q, k)
