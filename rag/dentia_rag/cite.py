"""
STEP 6 - CITATIONS AND AUTOMATIC CHECK: never trust the model, verify it.

A small model often writes the right fact with the WRONG passage number, or an empty
answer, or a number that is not in the document. This module checks the answer:

    1. EMPTY answer (only "[1]" or a few letters)      -> status "failed" (the caller retries)
    2. "NOT FOUND" answer                              -> status "not_found" (no sources shown)
    3. for every sentence of the answer:
         - the cited passage must exist ([7] when there are 5 passages = invalid),
         - the sentence must be CLOSE IN MEANING to the cited passage (embedding similarity,
           so it also works when the answer is French and the passage is English),
         - if another passage supports it clearly better, the citation is CORRECTED,
         - a sentence with no citation gets the best passage if it is close enough,
         - if no passage supports the sentence, it is marked [?] (unsupported),
         - numbers with 2+ digits, decimals and percentages must appear in the cited passage.
    4. Only the passages really cited are listed as sources.

The thresholds below are STARTING VALUES. We tune them in Step 7 with real questions.

Statuses: ok | corrected | unverified | not_found | failed
"""

import re

from dentia_rag.embed import cosine, embed_texts

SUPPORT_MIN = 0.55      # minimum similarity between a sentence and its passage
MARGIN = 0.05           # another passage must beat the cited one by more than this to replace it
MIN_CLAIM_WORDS = 4     # shorter sentences without citation are not treated as claims

CITE = re.compile(r"\[(\d+)\]")
LEADING_CITES = re.compile(r"^((?:\[\d+\]\s*[.,;]?\s*)+)")
NOT_FOUND = re.compile(
    r"(did not find|do not contain|does not contain|no information|not found in the|"
    r"n'ai pas trouv|ne contiennent pas|ne contient pas|aucune information)", re.IGNORECASE)
NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")


def is_empty(answer: str) -> bool:
    """True if, without the [n] markers, almost nothing is left."""
    return len(re.sub(r"[\s\W\d_]+", "", CITE.sub("", answer))) < 12


def is_not_found(answer: str) -> bool:
    return bool(NOT_FOUND.search(answer)) and len(answer) < 300


def split_sentences(answer: str) -> list[str]:
    """Split an answer into sentences. A marker after the period ("... vitality. [2] Next") joins the sentence before."""
    sentences: list[str] = []
    for piece in re.split(r"(?<=[.!?])\s+|\n+", answer.strip()):
        piece = piece.strip().lstrip("-*\u2022 ").strip()
        if not piece:
            continue
        lead = LEADING_CITES.match(piece)
        # postfix style "... vitality. [2]": the marker belongs to the sentence before.
        # prefix style "[3] Next sentence": the previous sentence already has its own marker.
        if lead and sentences and not CITE.search(sentences[-1]):
            sentences[-1] += " " + lead.group(1).strip()
            piece = piece[lead.end():].strip()
            if not piece:
                continue
        sentences.append(piece)
    return sentences


def checkable_numbers(sentence: str) -> list[str]:
    """Numbers worth checking: 2+ digits, decimals, percentages (not list numbers like 1, 2)."""
    return [n for n in NUMBER.findall(sentence) if len(n.rstrip("%")) >= 2 or "%" in n or "." in n or "," in n]


def number_in_text(number: str, text: str) -> bool:
    plain = number.rstrip("%").replace(",", ".")
    normalized = text.replace(",", ".")
    return re.search(r"(?<![\d.])" + re.escape(plain) + r"(?![\d])", normalized) is not None


def verify(answer: str, hits: list[dict], sentence_vectors: list[list[float]] | None,
           chunk_vectors: list[list[float]], sentences: list[str] | None = None) -> dict:
    """Pure logic (no network). sentence_vectors must match split_sentences(answer)."""
    sentences = sentences if sentences is not None else split_sentences(answer)
    checks, rebuilt, used = [], [], set()
    n_claims = n_supported = 0

    for index, sentence in enumerate(sentences):
        cited_all = [int(n) for n in CITE.findall(sentence)]
        cited = [n for n in dict.fromkeys(cited_all) if 1 <= n <= len(hits)]
        invalid = [n for n in dict.fromkeys(cited_all) if not 1 <= n <= len(hits)]
        text = re.sub(r"\s+", " ", CITE.sub("", sentence)).strip()
        text = re.sub(r"\s+([.,;])", r"\1", text)

        if not cited and not invalid and len(text.split()) < MIN_CLAIM_WORDS:
            rebuilt.append(text)                              # "Yes." etc.: not a claim
            continue
        n_claims += 1

        sims = [cosine(sentence_vectors[index], v) for v in chunk_vectors]
        best = max(range(len(sims)), key=lambda i: sims[i]) + 1       # 1-based
        keep = [c for c in cited if sims[c - 1] >= SUPPORT_MIN and sims[best - 1] - sims[c - 1] <= MARGIN]

        if keep:
            final, status = keep, ("ok" if keep == cited and not invalid else "corrected")
        elif sims[best - 1] >= SUPPORT_MIN:
            final, status = [best], ("corrected" if cited or invalid else "added")
        else:
            final, status = [], "unsupported"

        issues = []
        if invalid:
            issues.append(f"invalid citation {invalid}")
        if final:
            for number in checkable_numbers(text):
                if not any(number_in_text(number, hits[c - 1]["text"]) for c in final):
                    issues.append(f"number {number} not found in cited passage")
        if issues and status == "ok":
            status = "corrected" if invalid else "ok"

        if final:
            n_supported += 1 if not any(i.startswith("number") for i in issues) else 0
            used.update(final)
            flag = " [?]" if any(i.startswith("number") for i in issues) else ""
            rebuilt.append(text + " " + "".join(f"[{c}]" for c in final) + flag)
        else:
            rebuilt.append(text + " [?]")
        checks.append({"sentence": text, "cited": cited_all, "final": final, "status": status,
                       "best": best, "best_similarity": round(sims[best - 1], 3), "issues": issues})

    statuses = {c["status"] for c in checks}
    if not checks:
        overall = "unverified"
    elif "unsupported" in statuses or any(c["issues"] and any(i.startswith("number") for i in c["issues"]) for c in checks):
        overall = "unverified"
    elif statuses <= {"ok"}:
        overall = "ok"
    else:
        overall = "corrected"
    return {"status": overall, "answer": " ".join(rebuilt), "checks": checks,
            "sources_used": sorted(used),
            "citation_score": (n_supported / n_claims) if n_claims else 0.0}


def chunk_vectors_for(hits: list[dict], collection) -> list[list[float]]:
    """Read the stored vectors of the retrieved chunks from ChromaDB (no new embedding)."""
    result = collection.get(ids=[h["id"] for h in hits], include=["embeddings"])
    by_id = {i: v for i, v in zip(result["ids"], result["embeddings"])}
    return [list(map(float, by_id[h["id"]])) for h in hits]


def verify_answer(answer: str, hits: list[dict], collection, model: str, url: str) -> dict:
    """Full check: embeds the sentences with Ollama, compares them with the passages."""
    if is_empty(answer):
        return {"status": "failed", "answer": answer, "checks": [], "sources_used": [], "citation_score": 0.0}
    if is_not_found(answer):
        return {"status": "not_found", "answer": answer, "checks": [], "sources_used": [], "citation_score": 1.0}
    sentences = split_sentences(answer)
    cleaned = [re.sub(r"\s+", " ", CITE.sub("", s)).strip() or s for s in sentences]
    sentence_vectors = embed_texts(cleaned, model, url)
    return verify(answer, hits, sentence_vectors, chunk_vectors_for(hits, collection), sentences)
