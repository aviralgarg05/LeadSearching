from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class AppConfig:
    # Paths
    project_root: Path
    data_zip: Path
    storage_dir: Path
    sqlite_path: Path
    chroma_dir: Path
    index_dir: Path
    
    # Model settings
    embedding_model: str
    llama_cpp_model: str | None

    def __post_init__(self):
        # Ensure directories exist
        self.storage_dir.mkdir(exist_ok=True, parents=True)
        self.chroma_dir.mkdir(exist_ok=True, parents=True)
        self.index_dir.mkdir(exist_ok=True, parents=True)


def _create_config() -> AppConfig:
    project_root = Path(__file__).parent.parent.parent

    # Allow overriding storage directory and data zip via environment variables
    storage_dir_env = os.getenv("STORAGE_DIR")
    storage_dir = Path(storage_dir_env) if storage_dir_env else (project_root / ".storage")

    # Default sample dataset in repo; can be overridden with DATA_ZIP
    default_zip = project_root / "100k Sales Link 7 file-20250920T133656Z-1-001.zip"
    data_zip_env = os.getenv("DATA_ZIP")
    data_zip = Path(data_zip_env) if data_zip_env else default_zip
    
    return AppConfig(
        project_root=project_root,
        data_zip=data_zip,
        storage_dir=storage_dir,
        sqlite_path=storage_dir / "sales_links.db",
        chroma_dir=storage_dir / "chroma",
        index_dir=storage_dir / "index",
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        llama_cpp_model=os.getenv("LLAMA_CPP_MODEL"),
    )


cfg = _create_config()