"""Indexing package: exposes the public API for indexing submodules."""

# Re-export commonly used functions/classes so imports like
# `from leadsearching.indexing import build_index` work.
try:
	from .build_index import build_index  # noqa: F401
except Exception as exc:
	raise ImportError("Failed to import 'leadsearching.indexing.build_index'") from exc

__all__ = ["build_index"]