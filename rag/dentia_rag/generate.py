"""
STEP 5 - GENERATION: the language model writes the answer from the retrieved passages.

The model (for example qwen2.5:3b, run by Ollama) does NOT answer from its own memory.
We give it the numbered passages and strict rules:
    - use ONLY the passages,
    - put the passage number [1], [2]... after each statement,
    - if the passages do not contain the answer, say so (never invent),
    - answer in the language of the question.
Temperature 0 = the most stable answer (important for a medical tool).

STEP 6 is connected here: the answer is checked by dentia_rag.cite (empty answer ->
one retry, wrong passage number -> corrected, unsupported sentence -> marked [?],
"not found" -> no sources shown). Use --no-check to see the raw answer only.

Test it (retrieval + generation, one question):
    python -m dentia_rag.generate "How do I test if the pulp of a tooth is vital?"
    python -m dentia_rag.generate "Faut-il donner des antibiotiques avant l'extraction d'une dent de sagesse ?"
    python -m dentia_rag.generate "recette de gateau au chocolat"        # no passage -> no model call
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from dentia_rag.cite import is_empty, verify_answer
from dentia_rag.embed import load_env
from dentia_rag.retrieve import DEFAULT_MIN_SCORE, format_context, retrieve
from dentia_rag.store import get_collection, make_filter

NOT_FOUND = ("I did not find the answer in the available documents. / "
             "Je n'ai pas trouve la reponse dans les documents disponibles.")

SYSTEM_PROMPT = """You are a decision-support assistant for dentists.
You answer ONLY with the information contained in the numbered passages given by the user.

Rules:
1. After every statement, write the number of the passage that supports it, like [1] or [2][3].
   Put the number at the END of the sentence, never at the start. Example: "Cold testing is suggested [1]. Electric testing may be added [2]."
2. Use only facts, numbers and recommendations that are written in the passages. Do not add knowledge from elsewhere.
3. If the passages do not contain the answer, reply with one sentence saying that you did not find the answer in the documents. Do not guess.
4. If a passage says the evidence is weak or uncertain, or the recommendation is conditional, say it.
5. Answer in the same language as the question. Be short and clear: 3 to 6 sentences."""


RETRY_HINT = ("\n\nYour previous answer was empty. Write 3 to 6 complete sentences that answer the "
              "question using the passages, with the passage number after each sentence.")


FRENCH_WORDS = {"le", "la", "les", "un", "une", "des", "de", "du", "et", "est", "faut", "il", "comment",
                "quel", "quelle", "quels", "quelles", "pour", "dans", "avant", "apres", "que", "qui", "sur",
                "avec", "peut", "dois", "doit", "puis", "je", "vous", "quand", "pourquoi", "dent", "dents",
                "ou", "en", "au", "aux", "ce", "cette", "sont", "ai", "faire", "donner"}


def detect_language(question: str) -> str:
    """A small, fast guess: Arabic, French or English. Used to tell the model which language to write."""
    if re.search(r"[\u0600-\u06FF]", question):
        return "Arabic"
    lower = question.lower()
    if re.search(r"[\u00e0\u00e2\u00e7\u00e8\u00e9\u00ea\u00eb\u00ee\u00ef\u00f4\u00f9\u00fb]", lower):
        return "French"
    if len(set(re.findall(r"[a-z]+", lower)) & FRENCH_WORDS) >= 2:
        return "French"
    return "English"


def build_messages(question: str, hits: list[dict], retry: bool = False) -> list[dict]:
    user = f"Passages:\n\n{format_context(hits)}\n\nQuestion: {question}"
    user += f"\n\nAnswer in {detect_language(question)}."
    if retry:
        user += RETRY_HINT
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def generate_answer(question: str, hits: list[dict], model: str, url: str,
                    num_ctx: int = 4096, max_tokens: int = 400, on_token=None,
                    retry: bool = False) -> str:
    """Call Ollama (/api/chat, streaming). on_token(text) is called for each piece."""
    payload = json.dumps({
        "model": model,
        "messages": build_messages(question, hits, retry),
        "stream": True,
        "keep_alive": "10m",                       # keep the model in memory between questions
        "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": max_tokens},
    }).encode("utf-8")
    request = urllib.request.Request(url.rstrip("/") + "/api/chat", data=payload,
                                     headers={"Content-Type": "application/json"})
    parts: list[str] = []
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            for line in response:
                if not line.strip():
                    continue
                data = json.loads(line.decode("utf-8"))
                if "error" in data:
                    raise SystemExit(f"Ollama error: {data['error']}")
                piece = data.get("message", {}).get("content", "")
                if piece:
                    parts.append(piece)
                    if on_token:
                        on_token(piece)
                if data.get("done"):
                    break
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise SystemExit(f"The model '{model}' is not installed. Run: ollama pull {model}")
        raise SystemExit(f"Ollama returned HTTP {error.code}.")
    except (urllib.error.URLError, TimeoutError) as error:
        raise SystemExit(f"Cannot reach Ollama at {url} ({error}). Is Ollama running?")
    return "".join(parts).strip()


def answer_question(question: str, k: int = 5, min_score: float = DEFAULT_MIN_SCORE,
                    where=None, model: str | None = None, on_token=None, check: bool = True) -> dict:
    """Retrieval + generation + check.

    Returns {"status", "answer", "raw_answer", "sources", "hits", "checks",
             "citation_score", "model", "seconds"}.
    status: ok | corrected | unverified | not_found | failed
    """
    load_env()
    model = model or os.environ.get("LLM_MODEL", "qwen2.5:3b")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    embedding_model = os.environ.get("EMBEDDING_MODEL", "bge-m3")
    started = time.time()
    result = {"status": "not_found", "answer": NOT_FOUND, "raw_answer": NOT_FOUND, "sources": [],
              "hits": [], "checks": [], "citation_score": 1.0, "model": model, "seconds": 0.0}

    hits = retrieve(question, k=k, min_score=min_score, where=where)
    if not hits:                                   # nothing relevant: do not call the model
        if on_token:
            on_token(NOT_FOUND)
        result["seconds"] = time.time() - started
        return result
    result["hits"] = hits

    raw = generate_answer(question, hits, model, url, on_token=on_token)
    if is_empty(raw):                              # small models sometimes return only "[1]"
        if on_token:
            on_token("\n(empty answer, trying again...)\n")
        raw = generate_answer(question, hits, model, url, on_token=on_token, retry=True)
    result["raw_answer"] = raw
    result["answer"] = raw

    if check:
        collection = get_collection(os.environ.get("CHROMA_PATH", "chroma_db"),
                                    os.environ.get("COLLECTION_NAME", "denti_documents"))
        verdict = verify_answer(raw, hits, collection, embedding_model, url)
        result.update(status=verdict["status"], answer=verdict["answer"], checks=verdict["checks"],
                      citation_score=verdict["citation_score"])
        result["sources"] = [hits[n - 1] for n in verdict["sources_used"]]
        if verdict["status"] == "failed":
            result["answer"] = "The model did not produce a usable answer. Please try again."
    result["seconds"] = time.time() - started
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env()
    parser = argparse.ArgumentParser(description="Step 5: retrieval + generation")
    parser.add_argument("question")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--model", help="override LLM_MODEL of .env")
    parser.add_argument("--doc")
    parser.add_argument("--org")
    parser.add_argument("--year")
    parser.add_argument("--show-prompt", action="store_true", help="print the exact prompt sent")
    parser.add_argument("--no-check", action="store_true", help="skip the citation check (Step 6)")
    args = parser.parse_args()

    where = make_filter(args.doc, args.org, args.year)
    if args.show_prompt:
        hits = retrieve(args.question, k=args.k, min_score=args.min_score, where=where)
        for message in build_messages(args.question, hits):
            print(f"--- {message['role'].upper()} ---\n{message['content']}\n")
        return

    print(f"Question: {args.question}\n\nModel answer (raw):")
    result = answer_question(args.question, args.k, args.min_score, where, args.model,
                             on_token=lambda piece: print(piece, end="", flush=True),
                             check=not args.no_check)
    print(f"\n\n(model {result['model']}, {result['seconds']:.0f} seconds)")
    if args.no_check:
        return

    labels = {"ok": "OK - every sentence is supported by its passage",
              "corrected": "CORRECTED - some passage numbers were wrong and were fixed",
              "unverified": "UNVERIFIED - at least one sentence is marked [?]: check it yourself",
              "not_found": "NOT FOUND in the documents",
              "failed": "FAILED - the model gave no usable answer"}
    print(f"\nCHECK: {labels[result['status']]}")
    if result["checks"]:
        print(f"Supported sentences: {result['citation_score']:.0%}")
        for check in result["checks"]:
            mark = {"ok": "ok", "corrected": "fixed", "added": "added", "unsupported": "[?]"}.get(check["status"], check["status"])
            cites = "".join(f"[{c}]" for c in check["cited"]) or "none"
            final = "".join(f"[{c}]" for c in check["final"]) or "none"
            print(f"  - {mark:<6} cited {cites} -> final {final}   {check['sentence'][:70]}")
            for issue in check["issues"]:
                print(f"           ! {issue}")
    print(f"\nFinal answer:\n{result['answer']}")
    if result["sources"]:
        print("\nSources cited:")
        for h in result["sources"]:
            print(f"  {h['label']} {h['citation']}   (score {h['score']:.3f})")


if __name__ == "__main__":
    main()
