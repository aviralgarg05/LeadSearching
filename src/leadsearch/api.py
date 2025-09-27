from __future__ import annotations
from fastapi import FastAPI, Query
from pydantic import BaseModel

from .search import hybrid_search

app = FastAPI(title="LeadSearch API")


class SearchResponse(BaseModel):
    id: int
    score: float
    dataset: str | None = None
    username: str | None = None
    name: str | None = None
    bio: str | None = None
    category: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None


@app.get("/search", response_model=list[SearchResponse])
def search(
    q: str = Query(..., description="Query string"), 
    k: int = 20, 
    alpha: float = 0.5, 
    datasets: str | None = None
):
    ds_list = [d.strip() for d in datasets.split(",") if d.strip()] if datasets else None
    return hybrid_search(q, k=k, alpha=alpha, datasets=ds_list)
