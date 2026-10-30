"""
Fetch recent PubMed articles per topic, store their metadata in Supabase,
index them in Chroma (via the running RAG service), and notify matching doctors.

Usage:  python scrape.py                      (last 7 days, 20 articles per topic)
        python scrape.py --days 30 --dry-run  (show what would happen, write nothing)
The RAG service (port 8001) should be running so the new articles are searchable.
"""
import argparse
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client  # noqa: E402
from ingest import eutils, fetch_articles  # noqa: E402
from topics import TOPICS  # noqa: E402

RAG_URL = os.getenv("RAG_URL", "http://127.0.0.1:8001")
ADMIN_KEY = os.getenv("RAG_ADMIN_KEY", "")


def recent_pmids(client, query: str, days: int, n: int) -> list[str]:
    term = f"({query}) AND hasabstract[text] AND (english[la] OR french[la])"
    r = eutils(client, "esearch.fcgi", db="pubmed", term=term, retmax=n, retmode="json",
               sort="date", reldate=days, datetype="edat")
    return r.json()["esearchresult"]["idlist"]


def batches(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--per-topic", type=int, default=20)
    ap.add_argument("--max-notify", type=int, default=8, help="max notifications per doctor per run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    topics_of: dict[str, list[str]] = {}   # pmid -> topic keys
    with httpx.Client(timeout=60) as client:
        for key, (label, query) in TOPICS.items():
            ids = recent_pmids(client, query, args.days, args.per_topic)
            print(f"{label}: {len(ids)} recent articles")
            for p in ids:
                topics_of.setdefault(p, []).append(key)

        url_of = {p: f"https://pubmed.ncbi.nlm.nih.gov/{p}/" for p in topics_of}
        known: set[str] = set()
        for chunk in batches(list(url_of.values()), 100):
            known |= {r["url"] for r in sb.table("articles").select("url").in_("url", chunk).execute().data}
        new_pmids = [p for p, u in url_of.items() if u not in known]
        print(f"{len(topics_of)} articles found, {len(new_pmids)} new")

        articles = []
        for chunk in batches(new_pmids, 50):
            articles += [a for a in fetch_articles(client, chunk) if a["title"]]

    if not articles:
        print("Nothing new.")
        return
    if args.dry_run:
        for a in articles[:10]:
            print(" -", a["title"][:100], topics_of[a["pmid"]])
        print("Dry run: nothing written.")
        return

    # 1. article metadata (the year is stored as Jan 1st: show only the year in the UI)
    rows = [{
        "title": a["title"], "authors": a["authors"], "journal": a["journal"] or None,
        "published_at": f'{a["year"]}-01-01' if a["year"] else None,
        "doi": a["doi"] or None, "url": a["url"], "source": "pubmed",
        "topics": topics_of[a["pmid"]],
    } for a in articles]
    for chunk in batches(rows, 100):
        sb.table("articles").upsert(chunk, on_conflict="url", ignore_duplicates=True).execute()
    id_of = {}
    for chunk in batches([a["url"] for a in articles], 100):
        for r in sb.table("articles").select("id, url").in_("url", chunk).execute().data:
            id_of[r["url"]] = r["id"]

    # 2. search index
    if ADMIN_KEY:
        try:
            for chunk in batches(articles, 25):
                r = httpx.post(f"{RAG_URL}/ingest", headers={"X-Admin-Key": ADMIN_KEY},
                               json={"articles": chunk}, timeout=300)
                r.raise_for_status()
            print("Indexed in Chroma.")
        except httpx.HTTPError as e:
            print(f"WARNING: indexing failed ({e}). Articles saved, but not searchable yet.")
    else:
        print("WARNING: RAG_ADMIN_KEY not set, skipping indexing.")

    # 3. notifications
    doctors = [p for p in sb.table("profiles").select("id, interests").execute().data if p["interests"]]
    notifs = []
    for d in doctors:
        mine = set(d["interests"])
        matches = []
        for a in articles:
            hit = mine & set(topics_of[a["pmid"]])
            if hit and a["url"] in id_of:
                matches.append((len(hit), a, hit))
        matches.sort(key=lambda m: -m[0])
        for _, a, hit in matches[:args.max_notify]:
            notifs.append({
                "user_id": d["id"],
                "kind": "new_article",
                "title": f'Nouvel article : {a["title"][:140]}',
                "body": f'{a["journal"] or "Journal inconnu"}, {a["year"] or "s.d."} · '
                        + ", ".join(TOPICS[k][0] for k in sorted(hit)),
                "article_id": id_of[a["url"]],
                "link": a["url"],
            })
    for chunk in batches(notifs, 100):
        sb.table("notifications").upsert(chunk, on_conflict="user_id,article_id", ignore_duplicates=True).execute()
    print(f"Done: {len(articles)} new articles, {len(notifs)} notifications for {len(doctors)} doctor(s).")


if __name__ == "__main__":
    main()