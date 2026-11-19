"""Compares three notification strategies against the dentists' labels (label = labeller 1, label2 = labeller 2).
Needs Ollama running the first time; agent answers are cached in eval_agent_cache.json (it resets by itself when
the model or the classification prompt changes)."""
import csv
import hashlib
import json
import os

from dotenv import load_dotenv

load_dotenv()
from llm import MODEL, call_json  # noqa: E402
from watch_agent import (ACCEPTED_DESIGNS, DESIGN_FR, RATE_SCHEMA, RATE_SYSTEM, TOPICS,  # noqa: E402
                         _esc, design_override)

YES, NO = {"1", "y", "yes", "o", "oui", "true"}, {"0", "n", "no", "non", "false"}
CACHE = "eval_agent_cache.json"
VERSION = hashlib.md5((MODEL + RATE_SYSTEM + json.dumps(RATE_SCHEMA, sort_keys=True)).encode()).hexdigest()[:10]
cache = {}
if os.path.exists(CACHE):
    cache = json.load(open(CACHE, encoding="utf-8"))
    if cache.get("_version") != VERSION:
        cache = {}
cache["_version"] = VERSION


def parse(v):
    v = str(v or "").strip().lower()
    return 1 if v in YES else 0 if v in NO else None


def agent_says(row):
    if row["url"] in cache:
        design = cache[row["url"]]
    else:
        interests = "\n".join(f"{k}: {v[0]}" for k, v in TOPICS.items())
        payload = (f"<interests>\n{interests}\n</interests>\n<article>\n{_esc(row['title'])}\n"
                   f"{_esc(row['abstract'][:1500])}\n</article>")
        out = call_json(RATE_SYSTEM, payload, RATE_SCHEMA)
        design = out.get("design") if out.get("design") in DESIGN_FR else "other"
        cache[row["url"]] = design
        json.dump(cache, open(CACHE, "w", encoding="utf-8"))
    design = design_override(row["title"], row["abstract"]) or design
    return design in ACCEPTED_DESIGNS, design


def metrics(y, p):
    tp = sum(1 for a, b in zip(y, p) if a and b)
    fp = sum(1 for a, b in zip(y, p) if not a and b)
    fn = sum(1 for a, b in zip(y, p) if a and not b)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return dict(n_notified=tp + fp, tp=tp, fp=fp, fn=fn, precision=prec, recall=rec, f1=f1)


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


rows = [r for r in csv.DictReader(open("eval_pool.csv", encoding="utf-8-sig"))
        if parse(r["label"]) is not None or parse(r["label2"]) is not None]
la = [parse(r["label"]) for r in rows]
lb = [parse(r["label2"]) for r in rows]
lf = [parse(r.get("final")) for r in rows]          # adjudicated labels (disagreements settled against the rule)

preds, designs = [], []
for i, r in enumerate(rows, 1):
    ok, d = agent_says(r)
    preds.append(ok)
    designs.append(d)
    print(f"  agent {i}/{len(rows)}", end="\r")

strategies = {
    "Like scrape.py (notify everything found)": [True] * len(rows),
    "Title/abstract cues only (no model)": [design_override(r["title"], r["abstract"]) is None for r in rows],
    f"Agent (LLM {MODEL} + rule)": preds,
}

both = [i for i in range(len(rows)) if la[i] is not None and lb[i] is not None]
consensus = [i for i in both if la[i] == lb[i]]
if len(both) >= 10:
    a, b = [la[i] for i in both], [lb[i] for i in both]
    print(f"\nAgreement between the two labellers: {len(consensus)}/{len(both)} "
          f"({100 * len(consensus) / len(both):.0f} %), kappa = {kappa(a, b):.2f}")
    print("(kappa: below 0.4 = weak, 0.4-0.6 = moderate, 0.6-0.8 = good, above 0.8 = very good)")
else:
    print("\nNo second labeller yet (fill the label2 column to measure how reliable the labels are).")

sets = {"Labeller 1": ([i for i in range(len(rows)) if la[i] is not None], la),
        "Labeller 2": ([i for i in range(len(rows)) if lb[i] is not None], lb)}
if len(both) >= 10:
    sets["Consensus (both labellers agree)"] = (consensus, la)
final_idx = [i for i in range(len(rows)) if lf[i] is not None]
if len(final_idx) >= 10:
    sets = {"FINAL (adjudicated labels)": (final_idx, lf), **sets}

md = []
for name, (idx, lab) in sets.items():
    if len(idx) < 10:
        continue
    y = [lab[i] for i in idx]
    table = [f"### {name}: {len(idx)} articles, {sum(y)} relevant ({100 * sum(y) / len(y):.0f} %)", "",
             "| Strategy | Notified | Precision | Recall | F1 |", "|---|---|---|---|---|"]
    for sname, p in strategies.items():
        m = metrics(y, [p[i] for i in idx])
        table.append(f"| {sname} | {m['n_notified']} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} |")
    print("\n" + "\n".join(table))
    md += table + [""]

ref_name = next(n for n in ("FINAL (adjudicated labels)", "Consensus (both labellers agree)", "Labeller 1")
                if n in sets)
ref_idx, ref_lab = sets[ref_name]
print(f"\nAgent errors against: {ref_name}")
for i in ref_idx:
    if bool(ref_lab[i]) != preds[i]:
        print(f"  [{'FALSE POSITIVE' if preds[i] else 'MISSED'}] ({rows[i]['topic']}, design={designs[i]}) "
              f"{rows[i]['title'][:110]}")

with open("eval_results.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["topic", "title", "label1", "label2", "agent_notify", "agent_design"])
    for i, r in enumerate(rows):
        w.writerow([r["topic"], r["title"], la[i], lb[i], int(preds[i]), designs[i]])
open("eval_table.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\nSaved: eval_results.csv, eval_table.md")