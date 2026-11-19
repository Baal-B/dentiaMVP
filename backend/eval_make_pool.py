"""Builds a FRESH evaluation pool (eval_pool.csv): articles that are not in eval_pool_dev.csv."""
import csv
import os
import random

import httpx
from dotenv import load_dotenv

load_dotenv()
from watch_agent import TOPICS  # noqa: E402

RAG_URL = os.environ.get("RAG_URL", "http://127.0.0.1:8001")
KEY = os.environ.get("RAG_ADMIN_KEY", "")

dev_urls = {r["url"] for r in csv.DictReader(open("eval_pool_dev.csv", encoding="utf-8-sig"))}
pool, seen = [], set(dev_urls)
for topic, (_label, hint) in TOPICS.items():
    r = httpx.post(f"{RAG_URL}/pubmed", headers={"X-Admin-Key": KEY}, timeout=90,
                   json={"query": hint, "days": 90, "limit": 15})
    r.raise_for_status()
    n = 0
    for a in r.json()["articles"]:
        if a["url"] in seen:
            continue
        seen.add(a["url"])
        pool.append({"topic": topic, "title": a["title"], "journal": a.get("journal") or "",
                     "year": a.get("year") or "", "url": a["url"],
                     "abstract": (a.get("abstract") or "")[:1500], "label": "", "label2": "", "final": ""})
        n += 1
        if n >= 6:
            break

random.Random(2026).shuffle(pool)
pool = pool[:45]
with open("eval_pool.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(pool[0]))
    w.writeheader()
    w.writerows(pool)
print(f"{len(pool)} fresh articles written to eval_pool.csv")