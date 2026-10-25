# DentIA - RAG module

Finds the right passages in dental guidelines and helps the LLM answer with citations.

## Setup (done by setup_rag_v2.ps1)
```bash
cd rag
python -m venv .venv
.venv\Scripts\activate           # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Step 1 - documents -> chunks
1. Put your documents in `data/corpus/` (NOT committed: licenses + size).
2. List them in `data/manifest.csv` (title, organization, year, license, pages to exclude).
3. Look at the structure of each PDF:
   `python -m dentia_rag.find_sections --corpus data/corpus > sections.txt 2>$null`
4. Build the chunks:
   `python -m dentia_rag.ingest --corpus data/corpus --manifest data/manifest.csv --out data/processed/chunks.jsonl`
5. Check the quality:
   `python -m dentia_rag.inspect_chunks --chunks data/processed/chunks.jsonl`
6. Glued words ("ofthe")? Compare extractors on one page, then add `--engine pymupdf` to step 4:
   `python -m dentia_rag.compare_extractors --pdf data/corpus/FILE.pdf --page 25 --skip-pdfminer`

## Modules
| File | Role |
|---|---|
| `dentia_rag/ingest.py` | documents -> chunks (done) |
| `dentia_rag/find_sections.py` | bookmarks and headings of each PDF (done) |
| `dentia_rag/inspect_chunks.py` | quality check of the chunks (done) |
| `dentia_rag/compare_extractors.py` | compare PDF text extractors (done) |
| `dentia_rag/embed.py` | chunks -> vectors (bge-m3) |
| `dentia_rag/store.py` | save and search vectors (ChromaDB) |
| `dentia_rag/retrieve.py` | question -> best passages |
| `dentia_rag/generate.py` | passages -> answer (Ollama) |
| `dentia_rag/cite.py` | citations + automatic check |
| `dentia_rag/pipeline.py` | `ask()`: the one function the backend will call |
| `eval/` | test questions and metrics |