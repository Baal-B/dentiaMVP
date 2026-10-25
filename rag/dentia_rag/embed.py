"""
STEP 2 - EMBEDDINGS: turn every chunk into a vector (a list of numbers).

Why? A computer cannot compare the MEANING of two texts. An embedding model turns
a text into ~1000 numbers. Texts with a similar meaning get similar vectors, so we can
find the chunks closest to a question even if they share few words.

We use the model bge-m3 through Ollama (it must be running: `ollama pull bge-m3`).
Only the Python standard library is needed (no extra install).

What this file does:
    1. reads data/processed/chunks.jsonl (Step 1),
    2. asks Ollama for one vector per chunk, in small batches,
    3. saves them to data/processed/embeddings.jsonl (a CACHE: a second run only
       embeds the new or changed chunks, so it is fast),
    4. optional --demo "question": shows the 5 closest chunks (semantic search by hand).

Run it:
    python -m dentia_rag.embed
    python -m dentia_rag.embed --demo "How do I test if a tooth pulp is vital?"
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path: str = ".env") -> None:
    """Read KEY=VALUE lines of .env into os.environ (existing variables win)."""
    file = Path(path)
    if not file.exists():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def embed_texts(texts: list[str], model: str, url: str, batch_size: int = 16,
                retries: int = 3) -> list[list[float]]:
    """Ask Ollama for one vector per text. Returns the vectors in the same order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        payload = json.dumps({"model": model, "input": batch}).encode("utf-8")
        request = urllib.request.Request(
            url.rstrip("/") + "/api/embed", data=payload,
            headers={"Content-Type": "application/json"})
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt == retries:
                    raise SystemExit(
                        f"Cannot reach Ollama at {url} ({error}).\n"
                        f"Is Ollama running? Is the model installed (ollama pull {model})?")
                time.sleep(2 * attempt)
        embeddings = result.get("embeddings", [])
        if len(embeddings) != len(batch):
            raise SystemExit(f"Ollama returned {len(embeddings)} vectors for {len(batch)} texts.")
        vectors.extend(embeddings)
    return vectors


def cosine(a: list[float], b: list[float]) -> float:
    """Similarity of two vectors: 1 = same direction (same meaning), 0 = unrelated."""
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def text_key(model: str, text: str) -> str:
    """Fingerprint of (model, text): if the text or the model changes, we embed again."""
    return hashlib.sha1(f"{model}\n{text}".encode("utf-8")).hexdigest()


def load_cache(path: Path) -> dict:
    cache = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            cache[row["id"]] = row
    return cache


def embed_chunks(chunks: list[dict], model: str, url: str, cache_path: Path,
                 batch_size: int = 16) -> dict[str, list[float]]:
    """Return {chunk_id: vector}. Uses and updates the cache file."""
    cache = load_cache(cache_path)
    todo = [c for c in chunks
            if c["id"] not in cache or cache[c["id"]]["key"] != text_key(model, c["text"])]
    print(f"{len(chunks)} chunks | {len(chunks) - len(todo)} already in cache | {len(todo)} to embed")

    started = time.time()
    for start in range(0, len(todo), batch_size * 4):
        part = todo[start:start + batch_size * 4]
        vectors = embed_texts([c["text"] for c in part], model, url, batch_size)
        for chunk, vector in zip(part, vectors):
            cache[chunk["id"]] = {"id": chunk["id"], "key": text_key(model, chunk["text"]),
                                  "vector": [round(v, 6) for v in vector]}
        done = min(start + batch_size * 4, len(todo))
        print(f"  embedded {done}/{len(todo)}  ({time.time() - started:.0f}s)")
        # save after every part: if you stop (Ctrl+C), nothing is lost
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            for row in cache.values():
                f.write(json.dumps(row) + "\n")

    return {c["id"]: cache[c["id"]]["vector"] for c in chunks}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env()
    parser = argparse.ArgumentParser(description="Step 2: embed the chunks with Ollama")
    parser.add_argument("--chunks", default="data/processed/chunks.jsonl")
    parser.add_argument("--out", default="data/processed/embeddings.jsonl")
    parser.add_argument("--model", default=os.environ.get("EMBEDDING_MODEL", "bge-m3"))
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--demo", help="a question: show the 5 closest chunks")
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    if "/" in args.model:
        raise SystemExit(f"'{args.model}' looks like a Hugging Face name. For Ollama use: "
                         "EMBEDDING_MODEL=bge-m3 (edit your .env file).")

    chunks = [json.loads(line) for line in open(args.chunks, encoding="utf-8")]
    vectors = embed_chunks(chunks, args.model, args.url, Path(args.out), args.batch_size)
    dim = len(next(iter(vectors.values())))
    print(f"\nDone: {len(vectors)} vectors of {dim} numbers. Saved in {args.out}")

    if args.demo:
        question_vector = embed_texts([args.demo], args.model, args.url)[0]
        scored = sorted(((cosine(question_vector, vectors[c["id"]]), c) for c in chunks),
                        key=lambda pair: pair[0], reverse=True)
        print(f"\nQuestion: {args.demo}\nThe {args.top} closest chunks:\n")
        for score, c in scored[:args.top]:
            print(f"[score {score:.3f}] {c['doc']} | page {c['page']}")
            print("   " + c["text"][:300].replace("\n", " ") + "...\n")


if __name__ == "__main__":
    main()
