"""
STEP 1 of the DentIA RAG: from ANY document to clean "chunks".   [version 3: multi-format]

ONE script for all your data. The idea:
    - one small LOADER per file type (PDF, Word, HTML, Markdown, text);
      a loader only has to return "units" = pieces of text with a page or a section title;
    - ONE common pipeline after that: clean -> chunk -> metadata -> save.
    To support a new format later (CSV, JSON...), you only write one new loader.

What it does
    1. Looks in the corpus folder for every file with a supported extension.
    2. Reads the optional manifest.csv (title, organization, year, pages to exclude).
    3. Loads each file with the right loader.
    4. Cuts the text into chunks of at most 1000 characters (small overlap).
    5. Removes exact duplicate chunks, then saves chunks.jsonl (one JSON object per line).

Run it:
    pip install pypdf python-docx beautifulsoup4
    python step1_ingest.py --corpus corpus --out chunks.jsonl

manifest.csv (in the corpus folder, optional) - one line per file:
    file,title,organization,year,license,exclude_pages
    guide.pdf,"My guideline title",ADA,2018,CC-BY?,"1-3,14-18"

Each chunk looks like this:
    {"id": "guide.pdf#p3#c1", "doc": "guide.pdf", "title": "...", "organization": "ADA",
     "year": "2018", "source_type": "pdf", "page": 3, "section": null,
     "chunk_index": 1, "text": "..."}
    (PDF chunks have a page; Word/HTML/Markdown chunks have a section title.)
"""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Cleaning (same for every format)
# ---------------------------------------------------------------------------
def normalize_unicode(text: str) -> str:
    """NFKC turns ligatures into normal letters: the ligature fi becomes the two letters f + i."""
    text = unicodedata.normalize("NFKC", text)
    return text.replace("\u00ad", "")  # remove invisible soft hyphens


def clean_text(text: str) -> str:
    """Fix the most common problems of extracted text."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # "treat-\nment" -> "treatment"
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)           # single line break -> space
    text = re.sub(r"[ \t]+", " ", text)                    # many spaces -> one
    text = re.sub(r"\n{3,}", "\n\n", text)                 # keep paragraph breaks only
    return text.strip()


# ---------------------------------------------------------------------------
# 2. Chunking (same for every format)
# ---------------------------------------------------------------------------
def split_sentences(text: str) -> list[str]:
    """Cut after . ! ? followed by a space, and at every blank line (paragraph end)."""
    parts = re.split(r"(?<=[.!?])\s+|\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def hard_split(sentence: str, max_chars: int) -> list[str]:
    """Cut a too-long 'sentence' (a list, a table row) at word boundaries."""
    pieces, current = [], ""
    for word in sentence.split(" "):
        if current and len(current) + 1 + len(word) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, max_chars: int = 1000, overlap_chars: int = 200) -> list[str]:
    """
    Pack whole sentences into chunks of at most `max_chars` characters.
    The next chunk starts with the last sentences of the previous one (the "overlap").
    """
    sentences: list[str] = []
    for s in split_sentences(text):
        sentences.extend(hard_split(s, max_chars) if len(s) > max_chars else [s])

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            chunks.append(" ".join(current))
            overlap: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) + 1 > overlap_chars:
                    break
                overlap.insert(0, s)
                overlap_len += len(s) + 1
            if overlap_len + len(sentence) + 1 > max_chars:   # no room: drop the overlap
                overlap, overlap_len = [], 0
            current, current_len = overlap, overlap_len

        current.append(sentence)
        current_len += len(sentence) + 1

    if current:
        chunks.append(" ".join(current))
    return chunks


# ---------------------------------------------------------------------------
# 3. LOADERS: one per file type. Each returns a list of "units":
#       {"page": int or None, "section": str or None, "text": str}
# ---------------------------------------------------------------------------
LOADERS = {}   # extension -> loader function


def loader(*extensions):
    """Decorator: register a function as the loader of these file extensions."""
    def register(fn):
        for ext in extensions:
            LOADERS[ext] = fn
        return fn
    return register


def line_key(line: str) -> str:
    """Digits -> '#', so 'JADA page 840' and 'JADA page 841' look the same."""
    return re.sub(r"\d+", "#", line.strip().lower())


def find_repeated_lines(pages_lines: list[list[str]], edge: int = 6) -> set[str]:
    """Running headers/footers = lines found at the top/bottom of many pages."""
    counter: Counter = Counter()
    for lines in pages_lines:
        edges = lines[:edge] + lines[-edge:]
        for key in {line_key(l) for l in edges if l.strip()}:
            counter[key] += 1
    min_pages = max(3, int(0.10 * len(pages_lines)))
    return {key for key, n in counter.items() if n >= min_pages}


@loader(".pdf")
def load_pdf(path: Path, options: dict) -> list[dict]:
    from pypdf import PdfReader

    if options.get("engine") == "pymupdf":
        import pymupdf                      # pip install pymupdf  (license: AGPL)
        with pymupdf.open(str(path)) as pdf:
            raw_pages = [page.get_text("text") for page in pdf]
    else:
        raw_pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    pages_lines = [normalize_unicode(text).split("\n") for text in raw_pages]
    repeated = find_repeated_lines(pages_lines)
    excluded = options["exclude_pages"]
    units, removed, empty = [], 0, 0

    for page_number, lines in enumerate(pages_lines, start=1):
        if page_number in excluded:
            continue
        kept = [l for l in lines if line_key(l) not in repeated]
        removed += len(lines) - len(kept)
        text = clean_text("\n".join(kept))
        if len(text) < options["min_chars"]:      # almost no text = scanned page -> needs OCR
            empty += 1
            continue
        units.append({"page": page_number, "section": None, "text": text})

    print(f"  pdf ({options.get('engine', 'pypdf')}): {len(raw_pages)} pages | excluded {len(excluded)} | "
          f"header/footer lines removed {removed}")
    if empty:
        print(f"  warning: {empty} page(s) without text (scanned PDF? you may need OCR)")
    return units


def sections_to_units(sections: list[tuple[str | None, list[str]]]) -> list[dict]:
    """[(title, [paragraphs])] -> units, skipping empty sections."""
    units = []
    for title, paragraphs in sections:
        text = clean_text("\n\n".join(p for p in paragraphs if p.strip()))
        if text:
            units.append({"page": None, "section": title, "text": text})
    return units


@loader(".docx")
def load_docx(path: Path, options: dict) -> list[dict]:
    from docx import Document
    from docx.table import Table

    doc = Document(str(path))
    sections: list[tuple[str | None, list[str]]] = []
    title, buf = None, []
    for block in doc.iter_inner_content():          # paragraphs AND tables, in order
        if isinstance(block, Table):
            for row in block.rows:                   # one table row = one paragraph
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    buf.append(" | ".join(cells))
        else:
            text = normalize_unicode(block.text).strip()
            if block.style is not None and block.style.name.lower().startswith("heading"):
                sections.append((title, buf))
                title, buf = text, []
            elif text:
                buf.append(text)
    sections.append((title, buf))
    units = sections_to_units(sections)
    print(f"  docx: {len(units)} section(s)")
    return units


@loader(".html", ".htm")
def load_html(path: Path, options: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()                               # remove menus, scripts, footers
    sections: list[tuple[str | None, list[str]]] = []
    title, buf = None, []
    for el in (soup.body or soup).find_all(["h1", "h2", "h3", "p", "li", "tr"]):
        if el.name != "tr" and el.find_parent("table"):
            continue                                  # table cells are read through their <tr>
        text = normalize_unicode(el.get_text(" | " if el.name == "tr" else " ", strip=True))
        if el.name in ("h1", "h2", "h3"):
            sections.append((title, buf))
            title, buf = text, []
        elif text:
            buf.append(text)
    sections.append((title, buf))
    units = sections_to_units(sections)
    print(f"  html: {len(units)} section(s)")
    return units


@loader(".md", ".markdown")
def load_markdown(path: Path, options: dict) -> list[dict]:
    sections: list[tuple[str | None, list[str]]] = []
    title, buf = None, []
    text = normalize_unicode(path.read_text(encoding="utf-8", errors="replace"))
    for block in re.split(r"\n\s*\n", text):            # paragraph by paragraph
        match = re.match(r"^#{1,3}\s+(.*)", block.strip())
        if match:
            sections.append((title, buf))
            title, buf = match.group(1).strip(), []
        else:
            buf.append(block)
    sections.append((title, buf))
    units = sections_to_units(sections)
    print(f"  markdown: {len(units)} section(s)")
    return units


@loader(".txt")
def load_text(path: Path, options: dict) -> list[dict]:
    text = normalize_unicode(path.read_text(encoding="utf-8", errors="replace"))
    return sections_to_units([(None, [text])])


# ---------------------------------------------------------------------------
# 4. Manifest + common pipeline
# ---------------------------------------------------------------------------
def parse_pages(spec: str) -> set[int]:
    """'1-3,14,27-29' -> {1, 2, 3, 14, 27, 28, 29}"""
    pages: set[int] = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            pages.update(range(int(a), int(b) + 1))
        elif part:
            pages.add(int(part))
    return pages


def read_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row["file"].strip(): row for row in csv.DictReader(f) if row.get("file")}


def ingest_file(path: Path, corpus: Path, meta: dict, args, excluded_cli: set[int]) -> list[dict]:
    ext = path.suffix.lower()
    options = {
        "exclude_pages": parse_pages(meta.get("exclude_pages", "")) | excluded_cli,
        "min_chars": args.min_chars,
        "engine": args.engine,
    }
    units = LOADERS[ext](path, options)

    name = str(path.relative_to(corpus))
    chunks = []
    for unit_index, unit in enumerate(units):
        locator = f"p{unit['page']}" if unit["page"] else f"s{unit_index}"
        for i, text in enumerate(chunk_text(unit["text"], args.max_chars, args.overlap)):
            if len(text) < args.min_chunk_chars:      # a lone title carries no meaning
                continue
            chunks.append({
                "id": f"{name}#{locator}#c{i}",
                "doc": name,
                "title": (meta.get("title") or path.stem).strip(),
                "organization": (meta.get("organization") or "").strip(),
                "year": (meta.get("year") or "").strip(),
                "source_type": ext.lstrip("."),
                "page": unit["page"],
                "section": unit["section"],
                "chunk_index": i,
                "text": text,
            })
    print(f"  -> {len(chunks)} chunks")
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Any documents -> chunks.jsonl")
    parser.add_argument("--corpus", default="corpus", help="folder with your documents")
    parser.add_argument("--out", default="chunks.jsonl", help="output file")
    parser.add_argument("--manifest", default=None,
                        help="CSV file (default: <corpus>/manifest.csv)")
    parser.add_argument("--max-chars", type=int, default=1000)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--min-chars", type=int, default=50,
                        help="PDF pages with less text than this are skipped")
    parser.add_argument("--min-chunk-chars", type=int, default=40,
                        help="chunks shorter than this are skipped")
    parser.add_argument("--engine", choices=["pypdf", "pymupdf"], default="pypdf",
                        help="PDF text extractor (try pymupdf if words are glued together)")
    parser.add_argument("--exclude", action="append", default=[], metavar="FILE.pdf:PAGES",
                        help='extra pages to skip, e.g. "guide.pdf:1-3" (you can also use the manifest)')
    args = parser.parse_args()

    corpus = Path(args.corpus)
    manifest = read_manifest(Path(args.manifest) if args.manifest else corpus / "manifest.csv")
    excluded_cli: dict[str, set[int]] = {}
    for item in args.exclude:
        name, _, spec = item.partition(":")
        excluded_cli.setdefault(name, set()).update(parse_pages(spec))

    files = sorted(p for p in corpus.rglob("*") if p.is_file())
    supported = [p for p in files if p.suffix.lower() in LOADERS]
    unsupported = Counter(p.suffix.lower() for p in files
                          if p.suffix.lower() not in LOADERS and p.name != "manifest.csv"
                          and not p.name.startswith("."))
    if not supported:
        raise SystemExit(f"No supported file in '{corpus}'. Supported: {sorted(LOADERS)}")

    for p in supported:                               # help the user keep the manifest complete
        if manifest and str(p.relative_to(corpus)) not in manifest:
            print(f"note: {p.name} is not in the manifest (title/organization will be empty)")
    for name in manifest:
        if not (corpus / name).exists():
            print(f"note: manifest lists '{name}' but the file does not exist")

    all_chunks: list[dict] = []
    for path in supported:
        key = str(path.relative_to(corpus))
        print(f"Reading {key} ...")
        all_chunks.extend(ingest_file(path, corpus, manifest.get(key, {}), args,
                                      excluded_cli.get(path.name, set())))

    # Exact duplicates (the same paragraph in two documents) would waste search results.
    seen, unique, duplicates = set(), [], 0
    for c in all_chunks:
        digest = hashlib.md5(re.sub(r"\W+", "", c["text"].lower()).encode()).hexdigest()
        if digest in seen:
            duplicates += 1
            continue
        seen.add(digest)
        unique.append(c)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)   # create data/processed/ if needed
    with open(args.out, "w", encoding="utf-8") as f:
        for c in unique:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    lengths = [len(c["text"]) for c in unique]
    print("\n--- Summary ---")
    print(f"Files read     : {len(supported)}  " + str(dict(Counter(p.suffix.lower() for p in supported))))
    if unsupported:
        print(f"Files ignored  : {dict(unsupported)}  (no loader for these types yet)")
    print(f"Chunks         : {len(unique)}  (exact duplicates removed: {duplicates})")
    if lengths:
        print(f"Chunk length   : min {min(lengths)} / average {sum(lengths)//len(lengths)} "
              f"/ max {max(lengths)} characters")
        print(f"Chunks > {args.max_chars}  : {sum(l > args.max_chars for l in lengths)}  (must be 0)")
    print(f"Saved to       : {args.out}")


if __name__ == "__main__":
    main()