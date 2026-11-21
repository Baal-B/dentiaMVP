"""
COLLECTOR - build a big corpus (thousands of sources) in batches, and never lose the progress.

Why? Reading 7 PDFs by hand does not scale to 2,000+ sources. This tool:
    1. DISCOVER : asks Europe PMC (a free scientific database, official API) for OPEN-ACCESS
                  dental articles, guidelines and reviews. For each one it saves the title,
                  year, DOI, license and ABSTRACT as a small text file. No PDF needed.
    2. FETCH    : (optional, slower) downloads the FULL TEXT of the documents that have it
                  (clean XML, with section titles), instead of the abstract only.
    3. ADD-URLS : downloads web pages / PDFs from a list of URLs that YOU choose
                  (for example a guideline on the site of a dental society).
    4. REGISTRY : data/registry.csv keeps one row per document with a STATUS:
                      abstract_only -> fulltext          (or web)
                  If the PC stops, run the same command again: it continues where it stopped.

Everything lands in data/corpus/ (the folder the ingestion already reads), and the file
data/manifest_collected.csv is written for the ingestion (title, year, license, evidence type).

Commands (run from the rag folder):
    python -m dentia_rag.collect discover --max-per-query 100      # small test first!
    python -m dentia_rag.collect status
    python -m dentia_rag.collect fetch --types guideline,systematic_review --limit 200
    python -m dentia_rag.collect add-urls data/urls.csv

Only the Python standard library is used. Be polite with the server: the tool waits
between requests (--delay). Only OPEN-ACCESS documents are kept, and the license is saved.
"""

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
USER_AGENT = "DentIA-RAG/0.1 (university project; open-access dental guidelines)"

REGISTRY_COLUMNS = ["doc_id", "pmid", "pmcid", "doi", "title", "year", "journal", "evidence_type",
                    "license", "language", "topic", "url", "source", "status", "ft", "reason",
                    "file", "text_chars", "added"]
MANIFEST_COLUMNS = ["file", "title", "organization", "year", "license", "exclude_pages",
                    "evidence_type", "doi", "pmid", "url", "topic"]

# publication types we do not want in a decision-support corpus
EXCLUDED_TYPES = ["editorial", "comment", "letter", "news", "erratum", "retract", "interview",
                  "biography", "personal narrative", "congress"]
# sections of a full text that are noise for question answering
NOISE_SECTIONS = re.compile(r"(reference|acknowledg|conflict|competing|funding|author contribution|"
                            r"supplement|abbreviation|ethics|data availability|disclosure)", re.IGNORECASE)

DEFAULT_QUERIES = """\
# label | Europe PMC query.   (Only open-access documents are kept: the tool adds OPEN_ACCESS:y itself.)
# One query per line. Lines that start with # are ignored. Edit this file to change the topics.
guidelines  | (dental OR dentistry OR "oral health" OR endodontic OR periodontal) AND ("practice guideline" OR "clinical practice guideline" OR guideline OR "consensus statement")
caries      | ("dental caries" OR "tooth decay" OR "carious lesion") AND ("systematic review" OR "meta-analysis" OR guideline OR "randomized controlled trial")
endodontics | (endodontic OR "root canal" OR pulpitis OR "apical periodontitis" OR "pulp therapy") AND ("systematic review" OR guideline OR "randomized controlled trial")
periodontal | (periodontitis OR gingivitis OR "periodontal disease") AND ("systematic review" OR guideline OR "randomized controlled trial")
third_molar | ("third molar" OR "wisdom tooth" OR "wisdom teeth") AND ("systematic review" OR guideline OR "randomized controlled trial")
implants    | ("dental implant" OR "dental implants" OR peri-implantitis) AND ("systematic review" OR guideline OR "randomized controlled trial")
surgery     | ("oral surgery" OR "tooth extraction" OR "dental extraction") AND ("systematic review" OR guideline OR "randomized controlled trial")
antibiotics | (dental OR odontogenic OR "oral surgery") AND (antibiotic OR "antibiotic prophylaxis" OR analgesic OR "local anesthesia") AND ("systematic review" OR guideline)
radiology   | ("dental radiography" OR "panoramic radiograph" OR CBCT OR "cone beam") AND ("systematic review" OR guideline OR "diagnostic accuracy")
orthodontics| (orthodontic OR malocclusion) AND ("systematic review" OR guideline OR "randomized controlled trial")
restorative | ("dental restoration" OR "composite resin" OR "glass ionomer" OR "dental amalgam") AND ("systematic review" OR guideline OR "randomized controlled trial")
pediatric   | ("pediatric dentistry" OR "primary teeth" OR "children dental") AND ("systematic review" OR guideline)
ai_dental   | (dental OR tooth OR teeth) AND ("deep learning" OR "artificial intelligence" OR "machine learning") AND (radiograph OR panoramic OR diagnosis)
"""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def http_get(url: str, params: dict | None = None, retries: int = 4, delay: float = 0.0,
             accept: str = "*/*") -> tuple[int, bytes, str]:
    """GET with retries. Returns (status, body, content_type). 404 is returned, not raised."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last_error = None
    for attempt in range(1, retries + 1):
        if delay:
            time.sleep(delay)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            if error.code in (404, 410):
                return error.code, b"", ""
            last_error = f"HTTP {error.code}"
            if error.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = str(error)
        time.sleep(2 * attempt)                       # wait more and more before the next try
    raise RuntimeError(f"cannot get {url[:90]} ({last_error})")


def clean_abstract(raw: str) -> str:
    """Abstracts from the API can contain HTML (<h4>Background</h4>, <i>...). Make plain text."""
    text = re.sub(r"<h\d[^>]*>(.*?)</h\d>", r" \1: ", raw or "", flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")[:80]


def pub_types(record: dict) -> list[str]:
    types = []
    listed = (record.get("pubTypeList") or {}).get("pubType") or []
    types.extend(listed if isinstance(listed, list) else [listed])
    types.extend(str(record.get("pubType") or "").split(";"))
    return [t.strip().lower() for t in types if t and t.strip()]


def classify(record: dict) -> str:
    """guideline / systematic_review / rct / review / case_report / article (from type and title)."""
    types = " | ".join(pub_types(record))
    title = (record.get("title") or "").lower()
    if "guideline" in types or "guideline" in title or "consensus statement" in title:
        return "guideline"
    if "systematic review" in types or "meta-analysis" in types or "systematic review" in title \
            or "meta-analysis" in title:
        return "systematic_review"
    if "randomized controlled trial" in types or "randomised controlled trial" in title \
            or "randomized controlled trial" in title:
        return "rct"
    if "case report" in types:
        return "case_report"
    if "review" in types:
        return "review"
    return "article"


def eligible(record: dict, options) -> tuple[bool, str]:
    if str(record.get("isOpenAccess", "")).upper() != "Y":
        return False, "not open access"
    if len(clean_abstract(record.get("abstractText", ""))) < options.min_abstract:
        return False, "no usable abstract"
    year = int(record.get("pubYear") or 0)
    if year and year < options.from_year:
        return False, "too old"
    if year > date.today().year:
        return False, "year in the future (ahead of print)"
    language = (record.get("language") or "").lower()
    if language and language not in options.languages:
        return False, "language"
    types = " | ".join(pub_types(record))
    for word in EXCLUDED_TYPES:
        if word in types:
            return False, f"type: {word}"
    return True, ""


# ---------------------------------------------------------------------------
# Registry: one row per document, saved to disk often (so we can resume)
# ---------------------------------------------------------------------------
class Registry:
    def __init__(self, path: Path):
        self.path = path
        self.rows: dict[str, dict] = {}
        self.index: dict[str, str] = {}                  # pmid / pmcid / doi / url -> doc_id
        if path.exists():
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    self.rows[row["doc_id"]] = {c: row.get(c, "") for c in REGISTRY_COLUMNS}
        for row in self.rows.values():
            self._index(row)

    def _index(self, row: dict) -> None:
        for key in ("pmid", "pmcid", "doi", "url"):
            if row.get(key):
                self.index[f"{key}:{row[key].lower()}"] = row["doc_id"]

    def find(self, record: dict) -> str | None:
        for key in ("pmid", "pmcid", "doi", "url"):
            value = (record.get(key) or "").lower()
            if value and f"{key}:{value}" in self.index:
                return self.index[f"{key}:{value}"]
        return None

    def add(self, row: dict) -> None:
        row.setdefault("added", date.today().isoformat())
        self.rows[row["doc_id"]] = {c: row.get(c, "") for c in REGISTRY_COLUMNS}
        self._index(self.rows[row["doc_id"]])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=REGISTRY_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows.values())
        temp.replace(self.path)                           # replace the file in one step

    def export_manifest(self, path: Path) -> int:
        """The file the ingestion reads (title, year, license, evidence type, DOI...)."""
        rows = [r for r in self.rows.values() if r["status"] in ("abstract_only", "fulltext", "web") and r["file"]]
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()
            for r in rows:
                writer.writerow({"file": r["file"], "title": r["title"], "organization": r["journal"],
                                 "year": r["year"], "license": r["license"], "exclude_pages": "",
                                 "evidence_type": r["evidence_type"], "doi": r["doi"], "pmid": r["pmid"],
                                 "url": r["url"], "topic": r["topic"]})
        return len(rows)


# ---------------------------------------------------------------------------
# 1. DISCOVER (abstracts)
# ---------------------------------------------------------------------------
def abstract_markdown(record: dict, abstract: str) -> str:
    title = (record.get("title") or "").strip().rstrip(".")
    return f"# {title}\n\n## Abstract\n\nTitle: {title}. {abstract}\n"


def read_queries(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_QUERIES, encoding="utf-8")
        print(f"Created the default query file: {path}  (edit it to change the topics)")
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "|" in line:
            label, query = line.split("|", 1)
            queries.append((label.strip(), query.strip()))
    return queries


def cmd_discover(args) -> None:
    registry = Registry(Path(args.registry))
    out_dir = Path(args.corpus) / "europepmc"
    out_dir.mkdir(parents=True, exist_ok=True)
    queries = read_queries(Path(args.queries))
    if args.only:
        queries = [q for q in queries if q[0] in args.only.split(",")]
    totals = Counter()

    try:
        sort_clause = {"cited": " sort_cited:y", "date": " sort_date:y"}.get(args.sort, "")
        years = list(range(args.from_year, date.today().year + 1)) if args.spread_years else [None]
        limit = -(-args.max_per_query // len(years))            # quota per year (rounded up)
        jobs = [(label, query, year) for label, query in queries for year in years]
        for label, query, year in jobs:
            year_clause = f" AND (PUB_YEAR:{year})" if year else ""
            full_query = f"({query}) AND OPEN_ACCESS:y AND (SRC:MED OR SRC:PMC){year_clause}{sort_clause}"
            tag = f"{label} {year}" if year else label
            cursor, kept, scanned = "*", 0, 0
            if not year:
                print(f"\n[{label}] looking for up to {limit} new documents ...")
            while kept < limit and scanned < 20 * limit:
                code, body, _ = http_get(args.api + "/search", {
                    "query": full_query, "format": "json", "resultType": "core",
                    "pageSize": 100, "cursorMark": cursor}, delay=args.delay, accept="application/json")
                data = json.loads(body)
                results = (data.get("resultList") or {}).get("result") or []
                if not results:
                    break
                for record in results:
                    scanned += 1
                    ok, reason = eligible(record, args)
                    if not ok:
                        totals["skipped: " + reason] += 1
                        continue
                    ids = {"pmid": record.get("pmid") or "", "pmcid": record.get("pmcid") or "",
                           "doi": record.get("doi") or ""}
                    if registry.find(ids):
                        totals["already known"] += 1
                        continue
                    doc_id = ids["pmcid"] or (f"MED{ids['pmid']}" if ids["pmid"] else
                                              "DOI_" + safe_name(ids["doi"]))
                    if not doc_id or doc_id == "DOI_":
                        continue
                    abstract = clean_abstract(record.get("abstractText", ""))
                    journal = record.get("journalTitle") or (
                        ((record.get("journalInfo") or {}).get("journal") or {}).get("title")) or ""
                    url = (f"https://doi.org/{ids['doi']}" if ids["doi"] else
                           f"https://europepmc.org/article/{record.get('source', 'MED')}/{record.get('id', '')}")
                    path = out_dir / f"{safe_name(doc_id)}.md"
                    path.write_text(abstract_markdown(record, abstract), encoding="utf-8")
                    registry.add({
                        "doc_id": doc_id, **ids, "title": (record.get("title") or "").strip(),
                        "year": str(record.get("pubYear") or ""), "journal": journal,
                        "evidence_type": classify(record),
                        "license": record.get("license") or "open access (license not given)",
                        "language": record.get("language") or "", "topic": label, "url": url,
                        "source": "europepmc", "status": "abstract_only", "ft": "" if ids["pmcid"] else "no",
                        "file": f"europepmc/{path.name}", "text_chars": str(len(abstract))})
                    kept += 1
                    totals["new documents"] += 1
                    if kept >= limit:
                        break
                registry.save()
                next_cursor = data.get("nextCursorMark")
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                if not year:
                    print(f"   ... {kept} new so far ({scanned} records looked at)")
            print(f"   [{tag}] done: {kept} new documents" if not year else f"   [{tag}] +{kept}")
    finally:
        registry.save()                                   # even after Ctrl+C or an error
        n = registry.export_manifest(Path(args.manifest_out))
        print(f"\nRegistry saved: {len(registry.rows)} documents. Manifest for the ingestion: {n} rows.")
        for key, value in sorted(totals.items()):
            print(f"   {value:>6}  {key}")


# ---------------------------------------------------------------------------
# 2. FETCH (full text, JATS XML)
# ---------------------------------------------------------------------------
def local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def inline_text(element) -> str:
    """Text of an element without citation numbers, tables and figures."""
    parts = [element.text or ""]
    for child in element:
        name = local(child.tag)
        if name == "xref" or name in ("table-wrap", "fig", "disp-formula", "supplementary-material"):
            pass                                          # drop "[12]" markers, tables, figures
        elif name:
            parts.append(inline_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def section_blocks(section, trail: list[str], out: list[tuple[str, list[str]]]) -> None:
    title = re.sub(r"\s+", " ", inline_text(section.find("title")) if section.find("title") is not None else "").strip()
    if title and NOISE_SECTIONS.search(title):
        return
    path = trail + ([title] if title else [])
    paragraphs = []
    for child in section:
        name = local(child.tag)
        if name == "p":
            text = re.sub(r"\s+", " ", inline_text(child)).strip()
            if text:
                paragraphs.append(text)
        elif name == "sec":
            if paragraphs:
                out.append((" - ".join(path), paragraphs))
                paragraphs = []
            section_blocks(child, path, out)
    if paragraphs:
        out.append((" - ".join(path), paragraphs))


def jats_to_markdown(xml_bytes: bytes, title: str, fallback_abstract: str) -> tuple[str, int]:
    """JATS full-text XML -> (markdown text, number of characters in the body)."""
    root = ET.fromstring(xml_bytes)
    abstract = ""
    for element in root.iter():
        if local(element.tag) == "abstract" and not element.get("abstract-type"):
            abstract = re.sub(r"\s+", " ", inline_text(element)).strip()
            break
    body = next((e for e in root.iter() if local(e.tag) == "body"), None)
    blocks: list[tuple[str, list[str]]] = []
    if body is not None:
        section_blocks(body, [], blocks)
    chars = sum(len(p) for _, paragraphs in blocks for p in paragraphs)
    lines = [f"# {title}", "", "## Abstract", "", f"Title: {title}. {abstract or fallback_abstract}", ""]
    for heading, paragraphs in blocks:
        lines += [f"## {heading or 'Text'}", ""]
        for paragraph in paragraphs:
            lines += [paragraph.lstrip("#").strip(), ""]
    return "\n".join(lines), chars


def cmd_fetch(args) -> None:
    registry = Registry(Path(args.registry))
    corpus = Path(args.corpus)
    wanted_types = set(args.types.split(",")) if args.types else None
    todo = [r for r in registry.rows.values()
            if r["status"] == "abstract_only" and r["pmcid"] and r["ft"] == ""
            and (wanted_types is None or r["evidence_type"] in wanted_types)]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} documents to download in full text"
          f"{' (types: ' + args.types + ')' if args.types else ''}.")
    counts = Counter()
    try:
        for number, row in enumerate(todo, start=1):
            try:
                code, body, _ = http_get(f"{args.api}/{row['pmcid']}/fullTextXML", delay=args.delay)
            except RuntimeError as error:
                row["reason"] = str(error)[:120]
                counts["network error (will retry later)"] += 1
                continue
            if code != 200 or not body:
                row["ft"], row["reason"] = "no", "no full text available"
                counts["no full text"] += 1
                continue
            path = corpus / row["file"]
            try:
                old_abstract = path.read_text(encoding="utf-8").split("Title:", 1)[-1].split(". ", 1)[-1].strip()
                text, chars = jats_to_markdown(body, row["title"], old_abstract)
            except ET.ParseError:
                row["ft"], row["reason"] = "no", "full text could not be read"
                counts["unreadable"] += 1
                continue
            if chars < args.min_body:
                row["ft"], row["reason"] = "no", "full text too short"
                counts["too short"] += 1
                continue
            path.write_text(text, encoding="utf-8")
            row.update(status="fulltext", ft="yes", reason="", text_chars=str(chars))
            counts["full text saved"] += 1
            if number % 25 == 0:
                registry.save()
                print(f"   {number}/{len(todo)} ...")
    finally:
        registry.save()
        n = registry.export_manifest(Path(args.manifest_out))
        print(f"\nRegistry saved. Manifest: {n} rows.")
        for key, value in sorted(counts.items()):
            print(f"   {value:>6}  {key}")


# ---------------------------------------------------------------------------
# 3. ADD-URLS (web pages and PDFs chosen by you)
# ---------------------------------------------------------------------------
def cmd_add_urls(args) -> None:
    registry = Registry(Path(args.registry))
    path = Path(args.file)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("url,title,organization,year,evidence_type,license\n", encoding="utf-8")
        raise SystemExit(f"Created {path}. Add one line per page: url,title,organization,year,evidence_type,license")
    out_dir = Path(args.corpus) / "web"
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                url = (row.get("url") or "").strip()
                if not url:
                    continue
                if registry.find({"url": url}):
                    counts["already known"] += 1
                    continue
                try:
                    code, body, ctype = http_get(url, delay=args.delay)
                except RuntimeError as error:
                    counts["failed"] += 1
                    print(f"   failed: {error}")
                    continue
                if code != 200 or not body:
                    counts["failed"] += 1
                    print(f"   failed (HTTP {code}): {url[:80]}")
                    continue
                extension = ".pdf" if ("pdf" in ctype.lower() or url.lower().split("?")[0].endswith(".pdf")) else ".html"
                doc_id = "WEB_" + hashlib.sha1(url.encode()).hexdigest()[:10]
                (out_dir / f"{doc_id}{extension}").write_bytes(body)
                registry.add({
                    "doc_id": doc_id, "url": url, "title": (row.get("title") or url).strip(),
                    "year": (row.get("year") or "").strip(), "journal": (row.get("organization") or "").strip(),
                    "evidence_type": (row.get("evidence_type") or "web_page").strip(),
                    "license": (row.get("license") or "to check").strip(), "topic": "web", "source": "web",
                    "status": "web", "ft": "no", "file": f"web/{doc_id}{extension}", "text_chars": str(len(body))})
                counts["downloaded"] += 1
                registry.save()
    finally:
        registry.save()
        n = registry.export_manifest(Path(args.manifest_out))
        print(f"Registry saved. Manifest: {n} rows. {dict(counts)}")


# ---------------------------------------------------------------------------
# STATUS
# ---------------------------------------------------------------------------
def cmd_status(args) -> None:
    registry = Registry(Path(args.registry))
    rows = list(registry.rows.values())
    if not rows:
        raise SystemExit("The registry is empty. Run: python -m dentia_rag.collect discover --max-per-query 100")
    print(f"{len(rows)} documents in {args.registry}\n")
    for column, title in (("status", "STATUS"), ("evidence_type", "EVIDENCE TYPE"), ("topic", "TOPIC")):
        print(title)
        for key, value in Counter(r[column] or "-" for r in rows).most_common():
            print(f"   {value:>6}  {key}")
        print()
    years = Counter(r["year"] for r in rows if r["year"])
    if years:
        print(f"YEARS: {min(years)} to {max(years)}\n")
    pending = sum(1 for r in rows if r["status"] == "abstract_only" and r["pmcid"] and r["ft"] == "")
    print(f"{pending} documents could still be upgraded to full text (command: fetch).")
    chars = sum(int(r["text_chars"] or 0) for r in rows)
    chunks = chars // 700 + len(rows)
    print(f"\nEstimated chunks: about {chunks:,}. Embedding time: about {chunks / 3600:.1f} hours on a CPU "
          f"(1 chunk/second, as measured on your PC), much less on a GPU.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Collect a big corpus (Europe PMC, web pages)")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--registry", default="data/registry.csv")
        p.add_argument("--corpus", default="data/corpus")
        p.add_argument("--manifest-out", default="data/manifest_collected.csv")
        p.add_argument("--api", default=os.environ.get("EUROPEPMC_API", API))
        p.add_argument("--delay", type=float, default=0.25, help="seconds to wait before each request")

    d = sub.add_parser("discover", help="find open-access documents and save their abstracts")
    common(d)
    d.add_argument("--queries", default="data/queries.txt")
    d.add_argument("--only", help="only these query labels, comma separated")
    d.add_argument("--max-per-query", type=int, default=100)
    d.add_argument("--from-year", type=int, default=2010)
    d.add_argument("--sort", choices=["relevance", "cited", "date"], default="relevance",
                   help="cited = most cited first (a good quality signal); date = newest first")
    d.add_argument("--spread-years", action="store_true",
                   help="share --max-per-query between the years (from --from-year to today), "
                        "so the corpus is not only the newest papers")
    d.add_argument("--languages", default="eng", type=lambda s: [x.strip().lower() for x in s.split(",")])
    d.add_argument("--min-abstract", type=int, default=400, help="minimum abstract length (characters)")
    d.set_defaults(run=cmd_discover)

    f = sub.add_parser("fetch", help="download the full text of documents that have it")
    common(f)
    f.add_argument("--types", help="only these evidence types, e.g. guideline,systematic_review")
    f.add_argument("--limit", type=int, help="at most N documents in this run")
    f.add_argument("--min-body", type=int, default=2000, help="minimum body length (characters)")
    f.set_defaults(run=cmd_fetch)

    u = sub.add_parser("add-urls", help="download web pages / PDFs listed in a CSV file")
    common(u)
    u.add_argument("file", nargs="?", default="data/urls.csv")
    u.set_defaults(run=cmd_add_urls)

    s = sub.add_parser("status", help="counts per status, type, topic and an estimate of the size")
    common(s)
    s.set_defaults(run=cmd_status)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
