import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    # Paths
    data_zip: Path = Path("100k Sales Link 7 file-20250920T133656Z-1-001.zip")
    storage_dir: Path = Path(".storage")
    sqlite_path: Path = storage_dir / "sales_links.sqlite3"
    chroma_dir: Path = storage_dir / "chroma"
    index_dir: Path = storage_dir / "index"

    # Embeddings / LLM
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    llama_cpp_model: str | None = os.getenv("LLAMA_CPP_MODEL", None)

    # Other
    batch_size: int = 10000


cfg = AppConfig()

# Ensure storage directories exist
cfg.storage_dir.mkdir(parents=True, exist_ok=True)
cfg.chroma_dir.mkdir(parents=True, exist_ok=True)
cfg.index_dir.mkdir(parents=True, exist_ok=True)
