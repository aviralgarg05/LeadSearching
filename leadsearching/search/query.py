from __future__ import annotations
from typing import List, Dict, Any

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

from ..core.config import cfg
from ..core.db import get_conn, search_fts, get_row


class SearchEngine:
    def __init__(self) -> None:
        client = chromadb.PersistentClient(path=str(cfg.chroma_dir))
        collection = client.get_or_create_collection(name="sales_links")
        self.vs = ChromaVectorStore(chroma_collection=collection, collection_name="sales_links")
        self.embed = HuggingFaceEmbedding(model_name=cfg.embedding_model)
        self.index = VectorStoreIndex.from_vector_store(self.vs, embed_model=self.embed)

    def query(self, q: str, k: int = 20) -> List[Dict[str, Any]]:
        try:
            retriever = self.index.as_retriever(similarity_top_k=k)
            nodes = retriever.retrieve(q)
            items: List[Dict[str, Any]] = []
            conn = get_conn(cfg.sqlite_path)
            for sn in nodes:
                md = getattr(sn.node, "metadata", {}) or {}
                row_id = md.get("id")
                structured = None
                if row_id is not None:
                    structured = get_row(conn, int(row_id))
                if structured:
                    attrs = structured.get("attributes", {}) or {}
                    items.append({
                        "name": (attrs.get("first_name", "") + " " + attrs.get("last_name", "")).strip() or None,
                        "email": attrs.get("email_first") or attrs.get("email"),
                        "company": attrs.get("company_name") or attrs.get("company"),
                        "domain": attrs.get("company_domain"),
                        "title": attrs.get("job_title") or structured.get("title"),
                        "city": attrs.get("city"),
                        "phone": attrs.get("phone"),
                        "company_phone": attrs.get("company_phone"),
                        "url": structured.get("url"),
                        "score": getattr(sn, "score", None),
                    })
                else:
                    items.append({
                        "title": md.get("title"),
                        "url": md.get("url"),
                        "text": sn.node.get_content(),
                        "score": getattr(sn, "score", None),
                    })
            if items:
                return items
        except Exception:
            # Vector index may not be built yet
            pass

        # Fallback to SQLite FTS
        conn = get_conn(cfg.sqlite_path)
        rows = search_fts(conn, q, limit=k)
        items: List[Dict[str, Any]] = []
        for r in rows:
            structured = get_row(conn, int(r["id"]))
            attrs = (structured or {}).get("attributes", {})
            items.append({
                "name": (attrs.get("first_name", "") + " " + attrs.get("last_name", "")).strip() or None,
                "email": attrs.get("email_first") or attrs.get("email"),
                "company": attrs.get("company_name") or attrs.get("company"),
                "domain": attrs.get("company_domain"),
                "title": attrs.get("job_title") or structured.get("title") if structured else r.get("title"),
                "city": attrs.get("city"),
                "phone": attrs.get("phone"),
                "company_phone": attrs.get("company_phone"),
                "url": structured.get("url") if structured else r.get("url"),
                "score": None,
            })
        return items