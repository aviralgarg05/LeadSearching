"""Indexing package public API.

Exports selected symbols lazily to avoid importing heavy dependencies
on module import. Accessing ``build_index`` will import the underlying
implementation from ``leadsearching.indexing.build_index`` on first use.
"""

__all__ = ["build_index"]

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    # Eager import only for type checkers and static analysis tools.
    from .build_index import build_index as build_index


def __getattr__(name: str) -> Any:  # pragma: no cover - behavior validated via tests
    if name == "build_index":
        # Lazy wrapper to defer heavy imports until actually called
        def _build_index_proxy(*args, **kwargs):
            try:
                from .build_index import build_index as _impl
            except Exception as e:
                raise ImportError("Failed to import 'leadsearching.indexing.build_index'") from e
            return _impl(*args, **kwargs)

        globals()["build_index"] = _build_index_proxy
        return _build_index_proxy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")