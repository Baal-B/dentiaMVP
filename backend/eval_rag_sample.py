"""Lists ~25 articles that are really in the RAG index, to write test questions about."""
import os
import random

import httpx
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
RAG_URL = os.environ.get("RAG_URL", "http://127.0.0.1:8001")

rows = sb.table("articles").select("title, journal, published_at").execute().data
random.Random(7).shuffle(rows)
shown = 0
for r in rows:
    res = httpx.post(f"{RAG_URL}/search", json={"query": r["title"], "top_k": 1}, timeout=30).json()["results"]
    if res and res[0]["title"].strip().lower() == r["title"].strip().lower():      # really indexed
        shown += 1
        print(f'{shown:>2}. {r["title"]}\n    {r["journal"]} · {(r["published_at"] or "")[:4]}')
    if shown >= 25:
        break
