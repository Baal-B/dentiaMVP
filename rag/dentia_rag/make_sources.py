"""
MAKE data/sources.md - the list of every source in the corpus, for the report and for the
copyright question ("where does each document come from, and under which licence?").

It reads:
  - the manifests of the PDFs you added by hand (data/manifest.csv, data/manifest_manual.csv)
  - the registry of the collector (data/registry.csv), only for counts

Run it (after every change of the corpus):
    python -m dentia_rag.make_sources
"""

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cell(text: str) -> str:
    """Make a text safe for a Markdown table."""
    return (text or "").replace("|", "/").replace("\n", " ").strip() or "-"


def table(counter: Counter) -> list[str]:
    lines = ["| Value | Documents |", "|---|---|"]
    for key, count in counter.most_common():
        lines.append(f"| {cell(key)} | {count} |")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Write data/sources.md")
    parser.add_argument("--manifest", action="append", default=None,
                        help="manifests of the PDFs added by hand (repeatable)")
    parser.add_argument("--registry", default="data/registry.csv")
    parser.add_argument("--out", default="data/sources.md")
    args = parser.parse_args()

    manual: list[dict] = []
    for path in args.manifest or ["data/manifest.csv", "data/manifest_manual.csv"]:
        manual.extend(read_csv(Path(path)))
    registry = [r for r in read_csv(Path(args.registry))
                if r.get("status") in ("abstract_only", "fulltext", "web")]

    out = [
        "# Sources of the DentIA RAG corpus", "",
        f"Generated on {date.today().isoformat()} by `python -m dentia_rag.make_sources`. "
        "Do not edit by hand: change the manifests, then run the command again.", "",
        "## 1. Documents added by hand (PDF)", "",
        f"{len(manual)} documents. A licence marked `TO CHECK` must be verified before the corpus "
        "is shared outside the team: the PDFs themselves are **not** stored in Git.", "",
        "| File | Title | Organization | Year | Type | Licence | Pages excluded |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(manual, key=lambda r: r.get("file", "")):
        out.append("| " + " | ".join(cell(r.get(k, "")) for k in (
            "file", "title", "organization", "year", "evidence_type", "license", "exclude_pages")) + " |")

    out += ["", "## 2. Documents collected from Europe PMC (open access)", ""]
    if not registry:
        out.append("No registry found (`data/registry.csv`). Run `python -m dentia_rag.collect discover` first.")
    else:
        full = sum(1 for r in registry if r.get("status") == "fulltext")
        out += [
            f"{len(registry)} documents: {full} with full text, "
            f"{len(registry) - full} abstract only. Each one is open access; its own licence "
            "is kept in `data/registry.csv` (column `license`) and in the chunk metadata (`url`, `doi`, `pmid`).", "",
            "Source: Europe PMC REST API (https://europepmc.org/RestfulWebService).", "",
            "### By evidence type", "", *table(Counter(r.get("evidence_type") or "unknown" for r in registry)), "",
            "### By licence", "", *table(Counter(r.get("license") or "unknown" for r in registry)), "",
            "### By topic", "", *table(Counter(r.get("topic") or "unknown" for r in registry)), "",
            "### By publication year", "",
            *table(Counter(r.get("year") or "unknown" for r in sorted(registry, key=lambda r: r.get("year", "")))), "",
        ]

    web = [r for r in registry if r.get("status") == "web"]
    out += ["## 3. Web pages", ""]
    if not web:
        out.append("None yet. Add them with `python -m dentia_rag.collect add-urls data/urls.csv`.")
    else:
        out += ["| Title | Organization | Year | Licence | URL |", "|---|---|---|---|---|"]
        for r in web:
            out.append("| " + " | ".join(cell(r.get(k, "")) for k in (
                "title", "journal", "year", "license", "url")) + " |")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Written: {args.out}  ({len(manual)} manual documents, {len(registry)} collected)")


if __name__ == "__main__":
    main()
