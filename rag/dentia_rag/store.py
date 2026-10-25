"""
STEP 3 - VECTOR STORE: save the chunks and their vectors in ChromaDB.

Why a vector database? It keeps, for every chunk: the text, the vector, and the
METADATA (document, page, organization, year...). It finds the closest vectors fast,
and it can FILTER ("only documents of the ADA", "only year 2023"). It is saved on disk
(folder chroma_db/), so we embed only once.

Two commands:
    python -m dentia_rag.store build      # chunks + embeddings.jsonl -> ChromaDB
    python -m dentia_rag.store search "your question" --k 5 [--doc FILE] [--org TEXT] [--year 2023]

Rules we follow:
    - the chunk id (for example 3rd-molar...pdf#p65#c1) is the ID in the database,
    - "build" uses upsert: running it twice does not create duplicates,
    - chunks that are not in chunks.jsonl any more (for example you excluded a page)
      are deleted from the database, so the database always matches your corpus.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import chromadb

from dentia_rag.embed import embed_texts, load_env

METADATA_FIELDS = ["doc", "title", "organization", "year", "source_type",
                   "page", "section", "chunk_index"]


def get_collection(path: str, name: str):
    """Open (or create) the collection. 'cosine' = the distance we use (0 = identical)."""
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection(name=name, configuration={"hnsw": {"space": "cosine"}})


def clean_metadata(chunk: dict) -> dict:
    """ChromaDB accepts only str / int / float / bool. We drop empty values."""
    meta = {}
    for key in METADATA_FIELDS:
        value = chunk.get(key)
        if value is None or value == "":
            continue
        if key == "year":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        meta[key] = value
    return meta


def build(args) -> None:
    chunks = [json.loads(line) for line in open(args.chunks, encoding="utf-8")]
    vectors = {}
    for line in open(args.embeddings, encoding="utf-8"):
        row = json.loads(line)
        vectors[row["id"]] = row["vector"]
    missing = [c["id"] for c in chunks if c["id"] not in vectors]
    if missing:
        raise SystemExit(f"{len(missing)} chunks have no vector. Run first: python -m dentia_rag.embed")

    collection = get_collection(args.db, args.collection)

    # 1. delete what is not in the corpus any more
    wanted = {c["id"] for c in chunks}
    old_ids = collection.get(include=[])["ids"]
    stale = [i for i in old_ids if i not in wanted]
    for start in range(0, len(stale), 500):
        collection.delete(ids=stale[start:start + 500])

    # 2. add or update, in batches
    for start in range(0, len(chunks), 256):
        part = chunks[start:start + 256]
        collection.upsert(
            ids=[c["id"] for c in part],
            documents=[c["text"] for c in part],
            embeddings=[vectors[c["id"]] for c in part],
            metadatas=[clean_metadata(c) for c in part],
        )
    print(f"Collection '{args.collection}' in '{args.db}': {collection.count()} chunks "
          f"({len(stale)} stale removed).")


def make_filter(doc=None, org=None, year=None):
    """Build a ChromaDB 'where' filter from the options."""
    conditions = []
    if doc:
        conditions.append({"doc": doc})
    if org:
        conditions.append({"organization": org})
    if year:
        conditions.append({"year": int(year)})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def search(question: str, collection, model: str, url: str, k: int = 5, where=None) -> list[dict]:
    """The question -> its vector -> the k closest chunks. Returns a list of dicts."""
    vector = embed_texts([question], model, url)[0]
    result = collection.query(query_embeddings=[vector], n_results=k, where=where,
                              include=["documents", "metadatas", "distances"])
    hits = []
    for chunk_id, text, meta, distance in zip(result["ids"][0], result["documents"][0],
                                              result["metadatas"][0], result["distances"][0]):
        hits.append({"id": chunk_id, "text": text, "meta": meta,
                     "score": 1 - distance})          # cosine similarity: higher = closer
    return hits


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env()
    parser = argparse.ArgumentParser(description="Step 3: ChromaDB vector store")
    parser.add_argument("command", choices=["build", "search", "stats"])
    parser.add_argument("question", nargs="?", help="for 'search'")
    parser.add_argument("--chunks", default="data/processed/chunks.jsonl")
    parser.add_argument("--embeddings", default="data/processed/embeddings.jsonl")
    parser.add_argument("--db", default=os.environ.get("CHROMA_PATH", "chroma_db"))
    parser.add_argument("--collection", default=os.environ.get("COLLECTION_NAME", "denti_documents"))
    parser.add_argument("--model", default=os.environ.get("EMBEDDING_MODEL", "bge-m3"))
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--doc", help="filter: exact file name")
    parser.add_argument("--org", help="filter: exact organization name")
    parser.add_argument("--year", help="filter: year")
    args = parser.parse_args()

    if args.command == "build":
        build(args)
        return

    collection = get_collection(args.db, args.collection)
    if args.command == "stats":
        print(f"{collection.count()} chunks in '{args.collection}'")
        docs: dict[str, int] = {}
        for meta in collection.get(include=["metadatas"])["metadatas"]:
            docs[meta["doc"]] = docs.get(meta["doc"], 0) + 1
        for doc, n in sorted(docs.items()):
            print(f"   {n:>4}  {doc}")
        return

    if not args.question:
        raise SystemExit('Give a question: python -m dentia_rag.store search "your question"')
    hits = search(args.question, collection, args.model, args.url, args.k,
                  make_filter(args.doc, args.org, args.year))
    print(f"Question: {args.question}\n")
    for hit in hits:
        m = hit["meta"]
        print(f"[score {hit['score']:.3f}] {m['doc']} | page {m.get('page')} | id {hit['id']}")
        print("   " + hit["text"][:300].replace("\n", " ") + "...\n")


if __name__ == "__main__":
    main()
