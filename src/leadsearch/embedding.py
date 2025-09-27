from __future__ import annotations
from .config import get_settings

_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(get_settings().embed_model)
    return _MODEL


def encode_texts(texts: list[str]):
    model = get_model()
    emb = model.encode(
        texts, 
        show_progress_bar=False, 
        batch_size=64, 
        convert_to_numpy=True, 
        normalize_embeddings=True
    )
    if get_settings().vector_fp16:
        emb = emb.astype("float16")
    return emb
