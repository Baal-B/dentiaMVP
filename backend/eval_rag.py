"""hit@1, hit@3 and MRR on in-scope questions; refusal rate on off-topic ones. Needs the RAG service up."""
import csv
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
RAG_URL = os.environ.get("RAG_URL", "http://127.0.0.1:8001")

rows = list(csv.DictReader(open("rag_questions.csv", encoding="utf-8-sig")))
hit1 = hit3 = n_in = refused = n_out = 0
mrr = 0.0
for r in rows:
    d = httpx.post(f"{RAG_URL}/search", json={"query": r["question"], "top_k": 3}, timeout=60).json()
    titles = [x["title"].lower() for x in d["results"]]
    exp = r["expected_title"].strip().lower()
    if exp == "none":
        n_out += 1
        ok = d.get("insufficient_evidence") or not titles
        refused += bool(ok)
        print(f'  [{"OK  " if ok else "FAIL"}] off-topic: {r["question"][:70]}')
        continue
    n_in += 1
    rank = next((i for i, t in enumerate(titles, 1) if exp in t), None)
    hit1 += rank == 1
    hit3 += rank is not None
    mrr += 1 / rank if rank else 0
    print(f'  [{"rank " + str(rank) if rank else "MISS"}] {r["question"][:70]}')

print(f"\nIn-scope questions: {n_in}  hit@1 = {hit1 / n_in:.2f}  hit@3 = {hit3 / n_in:.2f}  MRR@3 = {mrr / n_in:.2f}")
if n_out:
    print(f"Off-topic questions correctly refused: {refused}/{n_out}")
