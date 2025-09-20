from __future__ import annotations
from pathlib import Path
import json

from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

from ..core.config import cfg
from ..core.db import get_conn


def fetch_rows(limit: int | None = None):
    conn = get_conn(cfg.sqlite_path)
    cur = conn.cursor()
    q = "SELECT id, title, url, description, raw_json FROM sales_links ORDER BY id"
    if limit:
        q += " LIMIT ?"
        cur.execute(q, (limit,))
    else:
        cur.execute(q)
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        yield dict(zip(cols, row))


def build_index(persist: bool = True) -> VectorStoreIndex:
    client = chromadb.PersistentClient(path=str(cfg.chroma_dir))
    collection = client.get_or_create_collection(name="sales_links")
    vs = ChromaVectorStore(chroma_collection=collection, collection_name="sales_links")

    embed_model = HuggingFaceEmbedding(model_name=cfg.embedding_model)

    docs: list[Document] = []
    for r in fetch_rows():
        # Parse raw_json to gather attributes for richer context
        try:
            raw = json.loads(r.get("raw_json") or "{}")
        except Exception:
            raw = {}
        name = " ".join([str(raw.get("first_name", "")).strip(), str(raw.get("last_name", "")).strip()]).strip()
        email = raw.get("email_first") or raw.get("email")
        company = raw.get("company_name") or raw.get("company")
        domain = raw.get("company_domain")
        title = raw.get("job_title") or r.get("title")
        city = raw.get("city")
        phone = raw.get("phone")
        cphone = raw.get("company_phone")
        url = r.get("url")

        lines = []
        if name:
            lines.append(f"Name: {name}")
        if email:
            lines.append(f"Email: {email}")
        if company:
            lines.append(f"Company: {company}")
        if domain:
            lines.append(f"Domain: {domain}")
        if title:
            lines.append(f"Title: {title}")
        if city:
            lines.append(f"City: {city}")
        if phone:
            lines.append(f"Phone: {phone}")
        if cphone:
            lines.append(f"Company Phone: {cphone}")
        if url:
            lines.append(f"URL: {url}")
        # Also add original simple fields
        if r.get("description"):
            lines.append(f"Description: {r['description']}")
        text = "\n".join([ln for ln in lines if ln]) or json.dumps(r, ensure_ascii=False)

        meta = {"id": r["id"], "url": url, "title": title or r.get("title")}
        docs.append(Document(text=text, metadata=meta))

    storage_context = StorageContext.from_defaults(vector_store=vs)
    index = VectorStoreIndex.from_documents(docs, storage_context=storage_context, embed_model=embed_model)

    if persist:
        # Chroma persists automatically; keep a flag file
        Path(cfg.index_dir).mkdir(exist_ok=True, parents=True)
        Path(cfg.index_dir / "BUILT").write_text("ok")
    return index


if __name__ == "__main__":
    idx = build_index()
    print("Index built and persisted.")
