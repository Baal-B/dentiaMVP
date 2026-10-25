"""
QUALITY CHECK of chunks.jsonl (run it after ingest, before Step 2).

Why? Garbage chunks make a bad RAG. A guideline PDF contains pages that are useful
(recommendations, evidence) and pages that are noise for search (author lists,
references, big tables). This tool:
    1. shows the numbers per document,
    2. suggests pages to exclude (reference pages, author pages, table pages),
    3. warns about broken text (encoding problems),
    4. prints a few random chunks so YOU can read them.

Run it (best on a first ingest done WITHOUT exclusions, so every page is visible):
    python -m dentia_rag.inspect_chunks --chunks data/processed/chunks.jsonl
"""

import argparse
import json
import random
import re
from collections import defaultdict

YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
REF_ITEM = re.compile(r"\b\d{1,3}\.\s+[A-Z][A-Za-z'-]+ [A-Z]{1,3}[,.]")
AFFILIATION = re.compile(
    r"\b(Department|University|School of|College of|Institute|Hospital|Faculty|"
    r"DDS|DMD|PhD|MSc|MPH|BDS|DrPH|MSD|Professor|Dr|Mr|Ms|Director|Consultant|"
    r"Lecturer|Practitioner|Chair|Chairman)\b")

# Pages of "conflict of interest" declarations
DISCLOSURE = re.compile(
    r"(Grants or contracts|honoraria|conflicts? of interest|Data Safety Monitoring|"
    r"fiduciary|Patents, copyrights|declarations? of interests?|royalt)", re.IGNORECASE)

# Thresholds (scores per 1000 characters). They were calibrated on 3 real guidelines,
# so they are a starting point: look at the pages yourself and adjust if needed.
REFS_MIN = 10        # years + "doi" + "et al" + numbered references
AUTHORS_MIN = 6      # departments, universities, degrees, "Professor", "Dr"
DIGITS_MIN = 0.06    # share of digits in the page (big tables)


def to_ranges(pages: list[int]) -> str:
    """[1, 2, 3, 7, 9, 10] -> '1-3,7,9-10'"""
    pages = sorted(pages)
    out, start, prev = [], None, None
    for p in pages:
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = p
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(out)


def split_runs(pages: list[int]) -> list[tuple[int, int]]:
    """[1, 2, 3, 7, 9, 10] -> [(1, 3), (7, 7), (9, 10)]"""
    runs, start, prev = [], None, None
    for p in sorted(pages):
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            runs.append((start, prev))
            start = prev = p
    if start is not None:
        runs.append((start, prev))
    return runs


def page_scores(text: str) -> dict:
    """Three simple 'noise' scores for one page (per 1000 characters)."""
    k = max(len(text), 1) / 1000
    refs = (len(YEAR.findall(text)) + 3 * text.lower().count("doi")
            + 3 * text.count("et al") + 3 * len(REF_ITEM.findall(text))) / k
    authors = (len(AFFILIATION.findall(text)) + 3 * len(DISCLOSURE.findall(text))) / k
    digits = sum(c.isdigit() for c in text) / max(len(text), 1)
    return {"refs": refs, "authors": authors, "digits": digits}


def main() -> None:
    parser = argparse.ArgumentParser(description="Quality check of chunks.jsonl")
    parser.add_argument("--chunks", default="data/processed/chunks.jsonl")
    parser.add_argument("--samples", type=int, default=5, help="random chunks to print")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    rows = [json.loads(line) for line in open(args.chunks, encoding="utf-8")]
    print(f"{len(rows)} chunks in {args.chunks}\n")

    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc"]].append(r)

    # ---------------- 1 + 2: numbers and suspect pages, document by document
    print("=" * 70)
    print("1. DOCUMENTS AND SUSPECT PAGES")
    print("=" * 70)
    for doc, chunks in sorted(by_doc.items()):
        avg = sum(len(c["text"]) for c in chunks) // len(chunks)
        print(f"\n{doc}\n   {len(chunks)} chunks, average {avg} characters")

        pages = defaultdict(str)
        for c in chunks:
            if c["page"] is not None:                 # only PDFs have pages
                pages[c["page"]] += " " + c["text"]
        if not pages:
            print("   (no page numbers: Word/HTML/Markdown/text file, nothing to exclude by page)")
            continue

        suspects = {"references": [], "authors": [], "tables": []}
        for page, text in pages.items():
            s = page_scores(text)
            if s["refs"] >= REFS_MIN:
                suspects["references"].append(page)
            elif s["authors"] >= AUTHORS_MIN:
                suspects["authors"].append(page)
            elif s["digits"] >= DIGITS_MIN:
                suspects["tables"].append(page)

        # A real references list or a table section covers SEVERAL pages in a row.
        # A single suspect page in the middle of the document is often real content
        # (a recommendation page full of study citations), so we do not suggest it.
        kind_of = {p: kind for kind, plist in suspects.items() for p in plist}
        last_page = max(pages)
        keep_runs, check_pages = [], []
        for a, b in split_runs(list(kind_of)):               # runs of ANY suspect kind
            length = b - a + 1
            kinds = sorted({kind_of[p] for p in range(a, b + 1)})
            # author lists / declarations sit at the very start or end of a document;
            # a reference list may be short but starts in the second half of the text
            edge_authors = "authors" in kinds and (a <= 3 or b >= last_page - 1)
            late_refs = "references" in kinds and length >= 2 and a >= 0.25 * last_page
            if length >= 3 or edge_authors or late_refs:
                keep_runs.append((a, b))
                where = f"page {a}" if a == b else f"pages {a}-{b}"
                print(f"   likely noise ({'+'.join(kinds)}): {where}")
            else:
                check_pages.extend(range(a, b + 1))
        if keep_runs:
            pages_list = [p for a, b in keep_runs for p in range(a, b + 1)]
            print(f"   --> suggestion for manifest.csv, column exclude_pages:  \"{to_ranges(pages_list)}\"")
        else:
            print("   no long series of suspect pages found")
        if check_pages:
            print(f"   CHECK BY HAND (isolated pages, may be real content): {to_ranges(check_pages)}")
        print("   (only a SUGGESTION: open the PDF and look at these pages before you exclude them)")

    # ---------------- 3: broken text
    print("\n" + "=" * 70)
    print("2. BROKEN TEXT (encoding problems)")
    print("=" * 70)
    broken = [r for r in rows
              if "\ufffd" in r["text"] or "(cid:" in r["text"]
              or sum(not (c.isalnum() or c.isspace() or c in ".,;:()-%/'\"") for c in r["text"])
              > 0.15 * len(r["text"])]
    if broken:
        print(f"{len(broken)} chunk(s) look broken. First ones:")
        for r in broken[:3]:
            print(f"   {r['id']}: {r['text'][:100]!r}")
        print("   -> try: pip install fonttools, run ingest again; if it stays, the PDF may need OCR.")
    else:
        print("No broken chunk found.")

    # ---------------- 4: samples to read
    print("\n" + "=" * 70)
    print(f"3. {args.samples} RANDOM CHUNKS: read them! Does each one make sense alone?")
    print("=" * 70)
    random.seed(args.seed)
    for r in random.sample(rows, min(args.samples, len(rows))):
        where = f"page {r['page']}" if r["page"] else f"section {r['section']!r}"
        print(f"\n[{r['doc']} | {where} | {len(r['text'])} characters]")
        print(r["text"][:600] + ("..." if len(r["text"]) > 600 else ""))


if __name__ == "__main__":
    main()