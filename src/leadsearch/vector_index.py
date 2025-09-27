from __future__ import annotations
import json
from pathlib import Path

import numpy as np
from .config import get_settings


class VectorIndex:
    def __init__(self, dim: int):
        self.dim = dim
        self.ids: list[int] = []
        self._index = None
        self.backend = "faiss" if get_settings().use_faiss else "hnsw"

    @property
    def size(self):
        return len(self.ids)

    def _ensure_index(self):
        if self._index is not None:
            return
        if self.backend == "faiss":
            import faiss  # type: ignore

            quantizer = faiss.IndexHNSWFlat(self.dim, 32)
            self._index = faiss.IndexIVFFlat(quantizer, self.dim, 4096)
            # will train lazily
        else:
            import hnswlib

            self._index = hnswlib.Index(space="cosine", dim=self.dim)
            self._index.init_index(max_elements=10_000, ef_construction=200, M=32)

    def add(self, vectors: np.ndarray, ids: np.ndarray):
        self._ensure_index()
        if self.backend == "faiss":
            import faiss  # type: ignore

            idx = self._index
            if not idx.is_trained:
                idx.train(vectors.astype("float32"))
            idx.add(vectors.astype("float32"))
        else:
            index = self._index
            if index.get_current_count() + len(vectors) > index.get_max_elements():
                index.resize_index(index.get_current_count() + len(vectors) + 10_000)
            index.add_items(vectors.astype("float32"), ids)
        self.ids.extend(ids.tolist())

    def search(self, query_vec: np.ndarray, k: int = 20) -> tuple[np.ndarray, np.ndarray]:
        self._ensure_index()
        if self.backend == "faiss":
            import faiss  # type: ignore

            distances, indices = self._index.search(query_vec.astype("float32"), k)
            return indices[0], distances[0]
        else:
            labels, distances = self._index.knn_query(query_vec.astype("float32"), k=k)
            return labels[0], distances[0]

    def save(self, dir_path: Path):
        dir_path.mkdir(parents=True, exist_ok=True)
        meta = {"dim": self.dim, "backend": self.backend, "count": self.size}
        (dir_path / "meta.json").write_text(json.dumps(meta, indent=2))
        np.save(dir_path / "id_mapping.npy", np.array(self.ids, dtype=np.int64))
        if self.backend == "faiss":
            import faiss  # type: ignore

            faiss.write_index(self._index, str(dir_path / "vectors.faiss"))
        else:
            self._index.save_index(str(dir_path / "hnsw.bin"))

    @classmethod
    def load(cls, dir_path: Path) -> VectorIndex | None:
        meta_file = dir_path / "meta.json"
        if not meta_file.exists():
            return None
        meta = json.loads(meta_file.read_text())
        inst = cls(meta["dim"])  # type: ignore
        inst.backend = meta.get("backend", "faiss")
        ids = np.load(dir_path / "id_mapping.npy")
        inst.ids = ids.tolist()
        inst._ensure_index()
        if inst.backend == "faiss":
            import faiss  # type: ignore

            inst._index = faiss.read_index(str(dir_path / "vectors.faiss"))
        else:
            import hnswlib

            inst._index = hnswlib.Index(space="cosine", dim=inst.dim)
            inst._index.load_index(str(dir_path / "hnsw.bin"))
        return inst
