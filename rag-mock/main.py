import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

load_dotenv()
from store import collection, embed_query, model  # noqa: E402  (after load_dotenv so env vars apply)
import hmac
from fastapi import FastAPI, Header, HTTPException   # extend your existing fastapi import
from ingest import add_articles


MIN_SCORE = float(os.getenv("MIN_SCORE", "0.80"))
ADMIN_KEY = os.getenv("RAG_ADMIN_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    model()        # load the embedding model once, so the first request is not slow
    collection()
    yield


app = FastAPI(title="RAG service (Chroma)", version="1.0", lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=3, ge=1, le=10)
    language: str | None = None                      # accepted for contract compatibility, unused
    min_score: float | None = Field(default=None, ge=0, le=1)   # override the threshold (for calibration)


class SearchResult(BaseModel):
    id: str
    title: str
    authors: str
    journal: str
    year: int | None
    doi: str | None
    url: str
    passage: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    insufficient_evidence: bool


class IngestRequest(BaseModel):
    articles: list[dict]



@app.get("/health")
def health():
    return {"status": "ok", "mock": False, "chunks": collection().count(), "min_score": MIN_SCORE}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    col = collection()
    total = col.count()
    if total == 0:
        return SearchResponse(query=req.query, results=[], insufficient_evidence=True)

    threshold = MIN_SCORE if req.min_score is None else req.min_score
    res = col.query(
        query_embeddings=[embed_query(req.query)],
        n_results=min(total, req.top_k * 4),
        include=["documents", "metadatas", "distances"],
    )

    results, seen = [], set()
    # sorted by distance, so the first hit per article is its best chunk
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        score = 1 - dist
        if meta["pmid"] in seen or score < threshold:
            continue
        seen.add(meta["pmid"])
        results.append(SearchResult(
            id=f'{meta["pmid"]}:{meta["chunk"]}',
            title=meta["title"],
            authors=meta["authors"],
            journal=meta["journal"],
            year=meta["year"] or None,
            doi=meta["doi"] or None,
            url=meta["url"],
            passage=doc,
            score=round(score, 3),
        ))
        if len(results) == req.top_k:
            break

    return SearchResponse(query=req.query, results=results, insufficient_evidence=len(results) == 0)

@app.post("/ingest")
def ingest_articles(body: IngestRequest, x_admin_key: str | None = Header(default=None)):
    """Used by scrape.py to add new articles while the service is running."""
    if not ADMIN_KEY or not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(403, "Forbidden")
    return {"chunks_added": add_articles(collection(), body.articles)}