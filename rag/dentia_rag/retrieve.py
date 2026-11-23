"""
STEP 4 - RETRIEVAL: from a question to the best passages, ready for the language model.

store.search() returns the k closest chunks, relevant or not. retrieve() adds the rules
that make the result safe and useful:
    1. take a larger POOL of candidates (default 20),
    2. drop the ones below a MINIMUM SCORE (so an off-topic question returns nothing),
    3. keep at most N chunks per page (so one page cannot fill all the places),
    4. return the best K, each with a citation label like "[1]" and "title, p.25".

If the result is empty, the answer step must say "I did not find this in the documents".

Use it in code:
    from dentia_rag.retrieve import retrieve, format_context
    hits = retrieve("How do I test pulp vitality?", k=5)
    prompt_context = format_context(hits)

Test it:
    python -m dentia_rag.retrieve "How do I test pulp vitality?" --k 5
    python -m dentia_rag.retrieve "recette de gateau" --show-all       # nothing passes
"""

import argparse
import os
import sys

from dentia_rag.embed import load_env
from dentia_rag.store import get_collection, make_filter, search

DEFAULT_MIN_SCORE = 0.50     # tuned later with the evaluation (Step 7)

# Evidence hierarchy: when two passages are about equally close to the question, the one from a
# guideline should come before a single study. The bonus ONLY changes the ORDER; the minimum
# score is still checked on the real cosine score. Turn it off with boost=False to compare.
EVIDENCE_BONUS = {"guideline": 0.04, "systematic_review": 0.03, "rct": 0.01, "review": 0.01,
                  "article": 0.0, "case_report": -0.01}


def retrieve(question: str, k: int = 5, min_score: float = DEFAULT_MIN_SCORE, pool: int = 20,
             max_per_page: int = 2, where=None, collection=None,
             model: str | None = None, url: str | None = None, boost: bool | None = None, extra_queries: list[str] | None = None) -> list[dict]:
    """Return up to k relevant chunks, best first. May return an empty list."""
    load_env()
    if boost is None:                                        # default ON; RAG_BOOST=0 turns it off
        boost = os.environ.get("RAG_BOOST", "1") != "0"
    model = model or os.environ.get("EMBEDDING_MODEL", "bge-m3")
    url = url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
    if collection is None:
        collection = get_collection(os.environ.get("CHROMA_PATH", "chroma_db"),
                                    os.environ.get("COLLECTION_NAME", "denti_documents"))

    candidates = search(question, collection, model, url, max(pool, k), where)
    if extra_queries:                  # e.g. the English translation of a French question
        best = {h["id"]: h for h in candidates}
        for extra in extra_queries:
            for h in search(extra, collection, model, url, max(pool, k), where):
                if h["id"] not in best or h["score"] > best[h["id"]]["score"]:
                    best[h["id"]] = h  # keep the best score of the same chunk
        candidates = list(best.values())
    for hit in candidates:
        bonus = EVIDENCE_BONUS.get(hit["meta"].get("evidence_type") or "", 0.0) if boost else 0.0
        hit["rank_score"] = hit["score"] + bonus
    candidates.sort(key=lambda h: h["rank_score"], reverse=True)

    selected, per_page = [], {}
    for hit in candidates:
        if hit["score"] < min_score:
            continue                                         # real cosine score under the minimum
        page_key = (hit["meta"].get("doc"), hit["meta"].get("page"))
        if per_page.get(page_key, 0) >= max_per_page:
            continue
        per_page[page_key] = per_page.get(page_key, 0) + 1
        selected.append(hit)
        if len(selected) == k:
            break

    for rank, hit in enumerate(selected, start=1):
        meta = hit["meta"]
        hit["rank"] = rank
        hit["label"] = f"[{rank}]"
        name = meta.get("title") or meta.get("doc")
        page = meta.get("page")
        if page:
            hit["citation"] = f"{name}, p.{page}"
        else:                                           # articles and web pages have no page number
            ident = f"PMID {meta['pmid']}" if meta.get("pmid") else (f"DOI {meta['doi']}" if meta.get("doi") else "")
            section = f", section '{meta['section']}'" if meta.get("section") else ""
            hit["citation"] = f"{name}{section}" + (f" ({ident})" if ident else "")
        hit["source_file"] = meta.get("doc")
        hit["page"] = page
    return selected


def format_context(hits: list[dict]) -> str:
    """The passages as a numbered block of text for the prompt (used in Step 5)."""
    return "\n\n".join(f"{h['label']} ({h['citation']})\n{h['text']}" for h in hits)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env()
    parser = argparse.ArgumentParser(description="Step 4: retrieve the best passages")
    parser.add_argument("question")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--pool", type=int, default=20)
    parser.add_argument("--max-per-page", type=int, default=2)
    parser.add_argument("--doc")
    parser.add_argument("--org")
    parser.add_argument("--year")
    parser.add_argument("--evidence", help="evidence type(s), e.g. guideline,systematic_review")
    parser.add_argument("--no-boost", action="store_true", help="no priority for guidelines (to compare)")
    parser.add_argument("--show-all", action="store_true",
                        help="also show the candidates that were rejected, with the reason")
    args = parser.parse_args()

    where = make_filter(args.doc, args.org, args.year, args.evidence)
    if args.no_boost:
        os.environ["RAG_BOOST"] = "0"
    hits = retrieve(args.question, args.k, args.min_score, args.pool, args.max_per_page, where)

    print(f"Question: {args.question}")
    print(f"Rules: k={args.k}, min score={args.min_score}, max {args.max_per_page} chunks per page\n")
    if not hits:
        print("NO PASSAGE PASSED THE RULES -> the answer must be: 'not found in the documents'.")
    for h in hits:
        print(f"{h['label']} score {h['score']:.3f} | {h['citation']}")
        print("    " + h["text"][:300].replace("\n", " ") + "...\n")

    if args.show_all:
        kept = {h["id"] for h in hits}
        collection = get_collection(os.environ.get("CHROMA_PATH", "chroma_db"),
                                    os.environ.get("COLLECTION_NAME", "denti_documents"))
        model = os.environ.get("EMBEDDING_MODEL", "bge-m3")
        url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        print("--- candidates (pool) and what happened to them ---")
        for h in search(args.question, collection, model, url, max(args.pool, args.k), where):
            status = "kept" if h["id"] in kept else (
                "rejected: score too low" if h["score"] < args.min_score else "rejected: page limit or k reached")
            print(f"  {h['score']:.3f}  p.{h['meta'].get('page')}  {h['meta'].get('doc')[:40]:<40} {status}")


if __name__ == "__main__":
    main()
