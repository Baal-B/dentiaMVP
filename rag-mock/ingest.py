"""
Fill the Chroma index from PubMed (abstracts).
Usage:  python ingest.py                      (default dental topics, 40 articles each)
        python ingest.py --per-topic 80
        python ingest.py --topics-file my_topics.txt   (one PubMed query per line)
Re-running is safe: articles already indexed are skipped.
Stop the search service first (two processes should not open the Chroma folder at once).
"""
import argparse
import os
import re
import time
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv

load_dotenv()
from store import collection, embed_passages  # noqa: E402

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "dentia-student-project"
EMAIL = os.getenv("NCBI_EMAIL", "")
API_KEY = os.getenv("NCBI_API_KEY", "")
DELAY = 0.12 if API_KEY else 0.4   # NCBI allows ~3 requests/s without a key, ~10/s with one

DEFAULT_TOPICS = [
    "dental caries diagnosis radiographs",
    "deep caries management pulp",
    "periapical lesion radiographic diagnosis",
    "apical periodontitis treatment",
    "periodontitis alveolar bone loss radiographic",
    "impacted third molar management",
    "impacted canine diagnosis",
    "panoramic radiograph interpretation dentistry",
    "artificial intelligence dental radiograph detection",
    "odontogenic infection",
    "dental pain differential diagnosis",
]


def eutils(client: httpx.Client, endpoint: str, **params):
    params["tool"] = TOOL
    if EMAIL:
        params["email"] = EMAIL
    if API_KEY:
        params["api_key"] = API_KEY
    for attempt in range(4):
        time.sleep(DELAY)
        r = client.get(f"{EUTILS}/{endpoint}", params=params)
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("NCBI is rate-limiting this client, try again in a few minutes")


def search_pmids(client, topic: str, n: int) -> list[str]:
    term = f"({topic}) AND hasabstract[text] AND (english[la] OR french[la]) AND 2012:3000[dp]"
    r = eutils(client, "esearch.fcgi", db="pubmed", term=term, retmax=n, retmode="json", sort="relevance")
    return r.json()["esearchresult"]["idlist"]


def text_of(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_year(art) -> int:
    y = text_of(art.find(".//Article/Journal/JournalIssue/PubDate/Year"))
    if not y:
        m = re.search(r"\d{4}", text_of(art.find(".//Article/Journal/JournalIssue/PubDate/MedlineDate")))
        y = m.group(0) if m else ""
    return int(y) if y.isdigit() else 0


def fetch_articles(client, pmids: list[str]) -> list[dict]:
    r = eutils(client, "efetch.fcgi", db="pubmed", id=",".join(pmids), retmode="xml")
    root = ET.fromstring(r.content)
    out = []
    for art in root.findall(".//PubmedArticle"):
        parts = []
        for ab in art.findall(".//Article/Abstract/AbstractText"):
            t, label = text_of(ab), ab.get("Label")
            if t:
                parts.append(f"{label.title()}: {t}" if label else t)
        names = []
        for a in art.findall(".//Article/AuthorList/Author"):
            last, ini = text_of(a.find("LastName")), text_of(a.find("Initials"))
            if last:
                names.append(f"{last} {ini}".strip())
        doi = ""
        for aid in art.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = text_of(aid)
        pmid = text_of(art.find(".//MedlineCitation/PMID"))
        out.append({
            "pmid": pmid,
            "title": text_of(art.find(".//Article/ArticleTitle")),
            "abstract": " ".join(parts),
            "journal": text_of(art.find(".//Article/Journal/Title")),
            "year": parse_year(art),
            "authors": ", ".join(names[:3]) + (" et al." if len(names) > 3 else ""),
            "doi": doi,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return out


def chunk(text: str, max_chars: int = 900) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    chunks, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) + 1 > max_chars:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def add_articles(col, articles: list[dict]) -> int:
    ids, docs, texts, metas = [], [], [], []
    for a in articles:
        if len(a["abstract"]) < 150 or not a["title"]:
            continue
        for i, c in enumerate(chunk(a["abstract"])):
            ids.append(f'{a["pmid"]}:{i}')
            docs.append(c)
            texts.append(f'{a["title"]}. {c}')   # the title gives each chunk its context
            metas.append({
                "pmid": a["pmid"], "chunk": i, "title": a["title"], "authors": a["authors"],
                "journal": a["journal"], "year": a["year"], "doi": a["doi"], "url": a["url"],
            })
    for i in range(0, len(ids), 32):
        sl = slice(i, i + 32)
        col.upsert(ids=ids[sl], documents=docs[sl], embeddings=embed_passages(texts[sl]), metadatas=metas[sl])
    return len(ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-topic", type=int, default=40)
    ap.add_argument("--topics-file")
    args = ap.parse_args()

    if args.topics_file:
        with open(args.topics_file, encoding="utf-8") as f:
            topics = [line.strip() for line in f if line.strip()]
    else:
        topics = DEFAULT_TOPICS

    col = collection()
    with httpx.Client(timeout=60) as client:
        pmids: dict[str, None] = {}
        for t in topics:
            ids = search_pmids(client, t, args.per_topic)
            print(f"{t!r}: {len(ids)} articles")
            pmids.update(dict.fromkeys(ids))

        wanted = list(pmids)
        done = {i.split(":")[0] for i in col.get(ids=[f"{p}:0" for p in wanted])["ids"]}
        new = [p for p in wanted if p not in done]
        print(f"{len(wanted)} unique articles, {len(done)} already indexed, {len(new)} to add")

        total = 0
        for i in range(0, len(new), 50):
            total += add_articles(col, fetch_articles(client, new[i:i + 50]))
            print(f"  {min(i + 50, len(new))}/{len(new)} fetched, {total} chunks added")

    print(f"Done. Index now holds {col.count()} chunks.")


if __name__ == "__main__":
    main()