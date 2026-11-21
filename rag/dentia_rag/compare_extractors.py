"""
COMPARE PDF TEXT EXTRACTORS on ONE page, to fix glued words ("ofthe", "twohad", "acase").

Some PDFs (special fonts, tight justified text) make an extractor lose the spaces
between words. A different extractor can read the same page correctly.
This tool prints the beginning of the same page with each extractor, and counts the
very long "words" (16+ letters) in the whole PDF: more long words = more glued words
(a rough signal: real long words like "temporomandibular" also count, so compare
the engines with each other, not with zero).

Run it:
    python -m dentia_rag.compare_extractors --pdf data/corpus/my_file.pdf --page 25

Extractors tested: pypdf (the default), pymupdf (pip install pymupdf),
pdfminer (pip install pdfminer.six).
"""

import argparse
import re
import sys
import unicodedata


def long_words(text: str, n: int = 16) -> int:
    text = unicodedata.normalize("NFKC", text)
    return sum(1 for w in re.findall(r"[A-Za-z]{2,}", text) if len(w) >= n)


def extract_pypdf(path: str, page: int | None):
    from pypdf import PdfReader
    pages = PdfReader(path).pages
    texts = [p.extract_text() or "" for p in pages]
    return texts


def extract_pymupdf(path: str, page: int | None):
    import pymupdf
    with pymupdf.open(path) as doc:
        return [p.get_text("text") for p in doc]


def extract_pdfminer(path: str, page: int | None):
    from pdfminer.high_level import extract_text
    from pdfminer.pdfpage import PDFPage
    with open(path, "rb") as f:
        n = len(list(PDFPage.get_pages(f)))
    return [extract_text(path, page_numbers=[i]) for i in range(n)]


ENGINES = {"pypdf": extract_pypdf, "pymupdf": extract_pymupdf, "pdfminer": extract_pdfminer}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Compare PDF extractors")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--page", type=int, required=True, help="page number (1 = first page)")
    parser.add_argument("--chars", type=int, default=500, help="characters to print per engine")
    parser.add_argument("--skip-pdfminer", action="store_true",
                        help="pdfminer is slow on long PDFs")
    args = parser.parse_args()

    for name, fn in ENGINES.items():
        if name == "pdfminer" and args.skip_pdfminer:
            continue
        print("=" * 70)
        try:
            texts = fn(args.pdf, args.page)
        except ImportError:
            print(f"{name}: not installed (pip install {'pymupdf' if name == 'pymupdf' else 'pdfminer.six'})")
            continue
        except Exception as error:                      # a broken PDF for one engine
            print(f"{name}: failed ({error})")
            continue
        page_text = re.sub(r"\s+", " ", texts[args.page - 1]).strip()
        total = sum(long_words(t) for t in texts)
        print(f"{name}: page {args.page}, words of 16+ letters in the WHOLE pdf = {total}")
        print("-" * 70)
        print(page_text[: args.chars])
    print("=" * 70)
    print("Read the texts. The best engine is the one with the fewest glued words.")
    print("If it is not pypdf, run the ingestion with:  --engine pymupdf")


if __name__ == "__main__":
    main()