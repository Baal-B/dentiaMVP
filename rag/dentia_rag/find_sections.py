"""
FIND THE SECTIONS of each PDF, to decide which pages to exclude.

The most reliable way to know where "References" or "Appendix" starts is to read the
document's own structure. This tool shows, for every PDF in your corpus:
    1. the bookmarks (table of contents) if the PDF has them,
    2. the heading lines like "References", "Appendix", "Conflicts of interest",
       with their page numbers,
    3. a HINT for exclude_pages (from the first noisy heading to the last page).

It only reads the PDFs. It changes nothing. YOU decide what to exclude: open the PDF
at those pages and check.

Run it:
    python -m dentia_rag.find_sections --corpus data/corpus
"""

import argparse
import re
import sys
from pathlib import Path

from pypdf import PdfReader

# Headings of sections that are usually noise for a question-answering RAG.
# (The singular "Reference" is NOT included: it is a common table column title.)
NOISE_HEADING = re.compile(
    r"^\s*(references|reference list|bibliography|appendix(es)?(\s+[A-Z0-9].{0,40})?|"
    r"conflicts?\s+of\s+interests?.{0,40}|declarations?\s+of\s+interests?.{0,40}|"
    r"disclosures?|acknowledg(e)?ments?|supplementary\s+(material|data|information).{0,30}|"
    r"author\s+contributions?|funding)\s*$",
    re.IGNORECASE,
)


def read_bookmarks(reader: PdfReader) -> list[tuple[int, int, str]]:
    """Return [(depth, page_number, title)] from the PDF outline (empty if none)."""
    result: list[tuple[int, int, str]] = []

    def walk(items, depth=0):
        for item in items:
            if isinstance(item, list):
                walk(item, depth + 1)
            else:
                try:
                    result.append((depth, reader.get_destination_page_number(item) + 1,
                                   str(item.title)))
                except Exception:
                    pass

    try:
        walk(reader.outline)
    except Exception:
        pass
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):                 # avoid Windows console errors
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Show sections of each PDF")
    parser.add_argument("--corpus", default="data/corpus")
    parser.add_argument("--max-bookmarks", type=int, default=40)
    args = parser.parse_args()

    pdfs = sorted(Path(args.corpus).rglob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF found in {args.corpus}")

    for pdf in pdfs:
        reader = PdfReader(str(pdf))
        n_pages = len(reader.pages)
        print("=" * 70)
        print(f"{pdf.name}   ({n_pages} pages)")
        print("=" * 70)

        bookmarks = read_bookmarks(reader)
        if bookmarks:
            print(f"Bookmarks (table of contents), {len(bookmarks)} entries:")
            for depth, page, title in bookmarks[: args.max_bookmarks]:
                if depth <= 1:
                    print(f"   p{page:>3}  {'   ' * depth}{title[:70]}")
            if len(bookmarks) > args.max_bookmarks:
                print("   ...")
        else:
            print("No bookmarks in this PDF.")

        found: list[tuple[int, str]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            for line in (page.extract_text() or "").split("\n"):
                if NOISE_HEADING.match(line):
                    found.append((page_number, line.strip()))
        print("\nHeadings that often start pages you may want to exclude:")
        if found:
            for page_number, heading in found:
                print(f"   p{page_number:>3}  {heading}")
            # End matter = headings in the last 60% of the document (a "Disclosure" on
            # page 1 is front matter, not end matter). "References" is the best marker.
            end_matter = [(p, h) for p, h in found if p >= 0.4 * n_pages]
            refs = [p for p, h in end_matter if re.match(r"(references|reference list|bibliography)",
                                                          h, re.IGNORECASE)]
            start = min(refs) if refs else (min(p for p, _ in end_matter) if end_matter else None)
            if start:
                print(f"\n   HINT: from page {start} to the end of the document: "
                      f"\"{start}-{n_pages}\"")
                print("   Check before you use it: some PDFs put useful pages AFTER the references")
                print("   (recommendation boxes, method appendix). Look at the bookmarks above.")
        else:
            print("   none found (the PDF may use other titles: open it and look).")
        print()


if __name__ == "__main__":
    main()