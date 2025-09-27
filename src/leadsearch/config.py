import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    db_path: Path = Path(os.getenv("LS_DB_PATH", "data/index.db"))
    index_dir: Path = Path(os.getenv("LS_INDEX_DIR", "data/index"))
    embed_model: str = os.getenv("LS_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    batch_size: int = int(os.getenv("LS_BATCH_SIZE", "5000"))
    max_workers: int = int(os.getenv("LS_MAX_WORKERS", "2"))
    use_faiss: bool = os.getenv("LS_USE_FAISS", "1") != "0"
    vector_fp16: bool = os.getenv("LS_VECTOR_FP16", "1") != "0"
    flush_every: int = int(os.getenv("LS_FLUSH_EVERY", "1"))  # batches per vector index flush


def get_settings() -> Settings:
    s = Settings()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    s.index_dir.mkdir(parents=True, exist_ok=True)
    return s
