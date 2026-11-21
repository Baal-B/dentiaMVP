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

import time

from dentia_rag.embed import embed_texts, load_env, text_key

METADATA_FIELDS = ["doc", "title", "organization", "year", "source_type",
                   "page", "section", "chunk_index", "evidence_type", "doi", "pmid", "url"]


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


def index(args) -> None:
    """For BIG corpora: embed AND save in small batches. Safe for memory, and it resumes.

    It compares a fingerprint (model + text) of every chunk with what is already in the database:
    only new or changed chunks are embedded, and chunks that disappeared are deleted.
    Run it again after an interruption: it continues where it stopped.
    """
    chunks = [json.loads(line) for line in open(args.chunks, encoding="utf-8")]
    collection = get_collection(args.db, args.collection)

    existing: dict[str, str] = {}
    offset = 0
    while True:
        page = collection.get(include=["metadatas"], limit=5000, offset=offset)
        if not page["ids"]:
            break
        for chunk_id, meta in zip(page["ids"], page["metadatas"]):
            existing[chunk_id] = (meta or {}).get("h", "")
        offset += len(page["ids"])

    wanted = {c["id"] for c in chunks}
    stale = [i for i in existing if i not in wanted]
    for start in range(0, len(stale), 500):
        collection.delete(ids=stale[start:start + 500])

    todo = [c for c in chunks if existing.get(c["id"]) != text_key(args.model, c["text"])[:16]]
    print(f"{len(chunks)} chunks | {len(chunks) - len(todo)} already indexed | {len(todo)} to embed "
          f"| {len(stale)} stale removed")
    started, done = time.time(), 0
    for number, start in enumerate(range(0, len(todo), args.batch_size), start=1):
        part = todo[start:start + args.batch_size]
        vectors = embed_texts([c["text"] for c in part], args.model, args.url, batch_size=len(part))
        collection.upsert(
            ids=[c["id"] for c in part],
            documents=[c["text"] for c in part],
            embeddings=vectors,
            metadatas=[{**clean_metadata(c), "h": text_key(args.model, c["text"])[:16]} for c in part])
        done += len(part)
        if number % 10 == 0 or done == len(todo):
            speed = done / max(time.time() - started, 1e-9)
            left = (len(todo) - done) / speed if speed else 0
            print(f"  {done}/{len(todo)} embedded ({speed:.1f} chunks/s, about {left / 60:.0f} min left)")
    print(f"Collection '{args.collection}': {collection.count()} chunks.")


def make_filter(doc=None, org=None, year=None, evidence=None):
    """Build a ChromaDB 'where' filter from the options.
    evidence: one or several evidence types, comma separated (guideline,systematic_review)."""
    conditions = []
    if evidence:
        conditions.append({"evidence_type": {"$in": [e.strip() for e in evidence.split(",") if e.strip()]}})
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
    parser.add_argument("command", choices=["build", "index", "search", "stats"])
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
    parser.add_argument("--evidence", help="filter: evidence type(s), e.g. guideline,systematic_review")
    parser.add_argument("--batch-size", type=int, default=32, help="chunks per request (index): use 64+ on a GPU")
    args = parser.parse_args()

    if args.command == "build":
        build(args)
        return
    if args.command == "index":
        index(args)
        return

    collection = get_collection(args.db, args.collection)
    if args.command == "stats":
        print(f"{collection.count()} chunks in '{args.collection}'")
        docs: dict[str, int] = {}
        for meta in collection.get(include=["metadatas"])["metadatas"]:
            docs[meta["doc"]] = docs.get(meta["doc"], 0) + 1
        kinds: dict[str, int] = {}
        for meta in collection.get(include=["metadatas"])["metadatas"]:
            kinds[meta.get("evidence_type") or "-"] = kinds.get(meta.get("evidence_type") or "-", 0) + 1
        print(f"{len(docs)} documents. Chunks per evidence type: {dict(sorted(kinds.items()))}")
        for doc, n in sorted(docs.items(), key=lambda x: -x[1])[:15]:
            print(f"   {n:>4}  {doc}")
        if len(docs) > 15:
            print(f"   ... and {len(docs) - 15} more documents")
        return

    if not args.question:
        raise SystemExit('Give a question: python -m dentia_rag.store search "your question"')
    hits = search(args.question, collection, args.model, args.url, args.k,
                  make_filter(args.doc, args.org, args.year, args.evidence))
    print(f"Question: {args.question}\n")
    for hit in hits:
        m = hit["meta"]
        print(f"[score {hit['score']:.3f}] {m['doc']} | page {m.get('page')} | id {hit['id']}")
        print("   " + hit["text"][:300].replace("\n", " ") + "...\n")


if __name__ == "__main__":
    main()
