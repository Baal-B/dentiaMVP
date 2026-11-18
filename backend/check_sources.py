"""Can a plain HTTP fetch see event dates on these pages? Run: python check_sources.py"""
import re
import sys

import httpx

URLS = [
    "https://fdiworlddental.org/all-events",
    "https://efficience-dentaire.fr/summit",
    "https://dentex.dz/",
    "https://mdentalexpo.ma/",
    "https://ids-cologne.de/",
    "https://infodentinternational.com/calendars",
]
DATE = re.compile(r"\b(202[6-8]|janv|févr|mars|avr|mai|juin|juil|août|sept|oct|nov|déc|jan|feb|mar|apr|may|jun|jul|aug|sep|dec)",
                  re.I)


def to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", "\n", html)
    lines = (" ".join(l.split()) for l in html.splitlines())
    return [l for l in lines if l]


for url in (sys.argv[1:] or URLS):
    print("=" * 80, "\n" + url)
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (DentIA research)"})
    except Exception as e:
        print("  ERROR:", type(e).__name__, str(e)[:100])
        continue
    lines = to_text(r.text)
    dated = [l for l in lines if DATE.search(l) and 8 < len(l) < 200]
    print(f"  status {r.status_code}, {len(lines)} text lines, {len(dated)} lines with a date")
    for l in dated[:12]:
        print("   -", l)