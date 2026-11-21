# DentIA - RAG module

Answers dental questions **with citations**, using only the documents in the corpus
(clinical guidelines, systematic reviews, trials, open-access articles).

```
OFFLINE (once, or when the corpus changes)
  documents --ingest--> chunks --embed (bge-m3)--> ChromaDB

ONLINE (for each question)
  question --embed--> retrieve (top-k + minimum score) --> LLM (Ollama) --> citation check --> answer
```

If nothing in the corpus is close enough to the question, the module says so
(`not_found`) instead of inventing an answer.

## 1. Setup (Windows PowerShell)

Requirements: Python 3.11+, [Ollama](https://ollama.com), Git.

```powershell
cd rag
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env          # then adapt the values if needed
ollama pull bge-m3                   # embedding model (1024 dimensions, multilingual)
ollama pull qwen2.5:3b               # answer model (LLM_MODEL in .env)
```

On Linux / macOS use `.venv/bin/python` and `cp`.
Use the **same `chromadb` version** on every machine (a database made by one version
may not open in another): `pip install chromadb==1.5.9`.

## 2. Run it from zero

Every command is run from the `rag/` folder. Documents are **not** in Git
(licences and size): they are rebuilt with the steps below.

### 2.1 Get the documents

**a) PDFs added by hand**: copy them into `data/corpus/` (or `data/corpus/manual/`) and describe them
in a manifest (`data/manifest.csv`, `data/manifest_manual.csv`):

| Column | Meaning |
|---|---|
| `file` | path inside `data/corpus` (`/` or `\` both work) |
| `title`, `organization`, `year`, `license` | shown in the citation and in `data/sources.md` |
| `exclude_pages` | pages to skip, e.g. `"2,54-63,69"` (references, tables of contents, appendices) |
| `evidence_type` | `guideline`, `systematic_review`, `rct`, `review`, `case_report`, `article` |

To choose `exclude_pages`, look at the structure of each PDF first:
```powershell
.\.venv\Scripts\python.exe -m dentia_rag.find_sections --corpus data\corpus\manual
```
It only gives hints: open the PDF and check. (Example: a page that starts the references can also contain the end of the conclusions.)

**b) Open-access articles from Europe PMC** (the big corpus):
```powershell
.\.venv\Scripts\python.exe -m dentia_rag.collect discover --max-per-query 300 --from-year 2005 --sort cited --spread-years
.\.venv\Scripts\python.exe -m dentia_rag.collect status
.\.venv\Scripts\python.exe -m dentia_rag.collect fetch --types guideline     # optional: full text
```
The search topics are in `data/queries.txt` (one per line: `label | Europe PMC query`).
The collector writes `data/registry.csv` (one row per document, with its licence) and
`data/manifest_collected.csv`. It is polite to the API (0.25 s between requests) and resumable.

**c) Web pages** (optional): list them in `data/urls.csv`
(`url,title,organization,year,evidence_type,license`), then
`.\.venv\Scripts\python.exe -m dentia_rag.collect add-urls data\urls.csv`.

### 2.2 Documents -> chunks
```powershell
.\.venv\Scripts\python.exe -m dentia_rag.ingest --corpus data\corpus `
   --manifest data\manifest.csv --manifest data\manifest_manual.csv --manifest data\manifest_collected.csv `
   --out data\processed\chunks.jsonl --engine pymupdf
.\.venv\Scripts\python.exe -m dentia_rag.inspect_chunks --chunks data\processed\chunks.jsonl
```
Chunks have at most 1000 characters, with 200 overlap, never cross a page, and carry their metadata.
The summary must say `Chunks > 1000 : 0`. Later manifests win over earlier ones.
`--engine pymupdf` fixes words glued together in some PDFs.

### 2.3 Chunks -> vector database
```powershell
.\.venv\Scripts\python.exe -m dentia_rag.store index --batch-size 64
.\.venv\Scripts\python.exe -m dentia_rag.store stats
```
`index` is **resumable and incremental**: it embeds only new or changed chunks and deletes the old ones.
Embedding about 14,000 chunks takes minutes on a GPU and hours on a CPU (about 1 chunk/s).
So the heavy step can be done on a strong PC: copy `data/processed/chunks.jsonl` there, run `index`,
then copy the folder `chroma_db/` back (same `chromadb` version).

### 2.4 Ask a question
```powershell
# only the search (no LLM):
.\.venv\Scripts\python.exe -m dentia_rag.retrieve "How do I test if the pulp of a tooth is vital?"
# full answer with citations and automatic check:
.\.venv\Scripts\python.exe -m dentia_rag.generate "Should I give antibiotics before wisdom tooth surgery?" --lang en
# only some evidence types:
.\.venv\Scripts\python.exe -m dentia_rag.generate "..." --evidence guideline,systematic_review
```
Useful options: `--k` (passages), `--min-score` (default 0.50), `--doc`, `--org`, `--year`,
`--evidence`, `--lang en|fr|ar`, `--model`, `--show-prompt`, `--no-check`.

### 2.5 Evaluate
```powershell
.\.venv\Scripts\python.exe -m dentia_rag.evaluate                                  # retrieval only
.\.venv\Scripts\python.exe -m dentia_rag.evaluate --generate --lang en --show-answers   # with answers (slow)
```
Questions are in `eval/questions.jsonl`
(`{"id","question","answerable","expected":[{"doc","pages"}],"must_include":[...]}`).
Reports are saved in `eval/results/` (not in Git).
Metrics: hit@k, MRR, refusal of out-of-scope questions, citations correct, keywords found, status counts, time.

### 2.6 List the sources
```powershell
.\.venv\Scripts\python.exe -m dentia_rag.make_sources     # writes data/sources.md
```

## 3. How the answer is checked

1. **Retrieval**: top-k chunks by cosine similarity, minimum score 0.50, at most 2 chunks per page
   (per document for articles), optional filters (`doc`, `org`, `year`, `evidence_type`).
2. **Generation**: a strict prompt (only the passages, number at the end of each sentence, keep conditions
   and medical terms, say "not found" if the passages do not answer).
3. **Citation check** (`cite.py`): each sentence is compared with the passage it cites. A wrong number is corrected,
   an unsupported sentence is marked `[?]`, numbers and unseen terms are checked, empty or looping answers are rejected
   (one retry). Status: `ok`, `corrected`, `unverified`, `not_found`, `failed`.

**Known limits**: the check cannot detect an omitted condition, or a distortion that stays on the same topic.
A small model on CPU (qwen2.5:3b) sometimes answers "yes" without the conditions, and its French is weak:
use `--lang en`. The corpus is mostly **abstracts**, not full text. A clinician must validate any use in a real setting.

## 4. Modules

| File | Role |
|---|---|
| `dentia_rag/ingest.py` | documents -> chunks |
| `dentia_rag/find_sections.py` | bookmarks and headings of each PDF (to choose `exclude_pages`) |
| `dentia_rag/inspect_chunks.py` | quality check of the chunks |
| `dentia_rag/compare_extractors.py` | compare PDF text extractors on one page |
| `dentia_rag/collect.py` | collect open-access documents (Europe PMC) and web pages |
| `dentia_rag/embed.py` | text -> vectors (bge-m3, through Ollama) |
| `dentia_rag/store.py` | build, index, search and inspect the ChromaDB database |
| `dentia_rag/retrieve.py` | question -> best passages |
| `dentia_rag/generate.py` | passages -> answer (Ollama) + citation check |
| `dentia_rag/cite.py` | citation verification |
| `dentia_rag/evaluate.py` | test questions and metrics |
| `dentia_rag/make_sources.py` | writes `data/sources.md` |
| `dentia_rag/pipeline.py` | `ask()`: the one function the backend will call (to do) |

## 5. Files that are not in Git
`data/corpus/*` (licences, size), `data/processed/`, `chroma_db/`, `.env`, `data/registry.csv`,
`data/manifest_collected.csv`, `eval/results/`. All of them can be rebuilt with section 2.

## 6. Licences of the tools
PyMuPDF (`--engine pymupdf`) is AGPL: keep it in the list of licences of the project.
Each collected article keeps its own open-access licence (see `data/sources.md`).
