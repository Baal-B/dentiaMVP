import os
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
CHROMA_DIR = os.getenv("CHROMA_DIR", "data/chroma")


@lru_cache(maxsize=1)
def model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def _client():
    return chromadb.PersistentClient(path=CHROMA_DIR)


def collection():
    # cosine distance: score = 1 - distance
    return _client().get_or_create_collection("articles", metadata={"hnsw:space": "cosine"})


# e5 models need these prefixes: "passage: " for documents, "query: " for questions
def embed_passages(texts: list[str]) -> list[list[float]]:
    return model().encode(
        [f"passage: {t}" for t in texts],
        normalize_embeddings=True, batch_size=16, show_progress_bar=False,
    ).tolist()


def embed_query(text: str) -> list[float]:
    return model().encode([f"query: {text}"], normalize_embeddings=True, show_progress_bar=False)[0].tolist()