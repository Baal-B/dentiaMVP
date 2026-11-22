"""
STEP 7 - EVALUATION: measure the RAG with numbers, on questions with known answers.

You write a list of test questions (eval/questions.jsonl). For each one you say where the
answer is (document + page) and which key words a correct answer must contain.
Then this tool measures:

  RETRIEVAL (fast, no language model)
    hit@1, hit@3, hit@5 : is a correct page among the first 1, 3, 5 results?
    MRR                 : average of 1/rank of the first correct result (1.0 = always first)
    out-of-scope        : for questions that are NOT in the documents, did we return nothing?

  GENERATION (slow, add --generate)
    answered            : the model produced a usable answer (not failed, not "not found")
    citations correct   : every source in the final answer is a page you marked as correct
    raw citations       : the same, but for the numbers the MODEL wrote, BEFORE our correction
                          (this is the real accuracy of the model; the gap shows what Step 6 fixes)
    keywords found      : share of the key words ("immunocompromised", "alveolar osteitis"...)
                          that appear in the answer = a simple measure of completeness
    status counts       : ok / corrected / unverified / failed / not_found
    out-of-scope        : did the system refuse ("not found")?
    average time

Question format (one JSON object per line):
  {"id": "q1", "question": "...", "answerable": true,
   "expected": [{"doc": "file.pdf", "pages": [25]}],
   "must_include": ["cold", "electric"]}
  For a question that is NOT in the documents: {"id": "q9", "question": "...", "answerable": false}

  A passage counts as CORRECT if it is in an "expected" document/page, OR if it contains ALL the
  words of one group of "relevant_terms" (checked in lower case). This is fair to the big corpus:
  an abstract that really answers the question is not a miss.
   "relevant_terms": [["silver diamine fluoride", "caries"], ["sdf", "arrest"]]
  (= correct if the passage has both words of the first group, or both words of the second one)
  An answerable question needs "expected", "relevant_terms", or both.

Run it:
    python -m dentia_rag.evaluate                       # retrieval only, seconds
    python -m dentia_rag.evaluate --generate            # full test, minutes
    python -m dentia_rag.evaluate --generate --limit 3 --lang en
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dentia_rag.cite import CITE
from dentia_rag.embed import load_env
from dentia_rag.retrieve import DEFAULT_MIN_SCORE, retrieve


def load_questions(path: str) -> list[dict]:
    questions = []
    for number, line in enumerate(open(path, encoding="utf-8"), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            q = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"{path} line {number}: not valid JSON ({error})")
        for key in ("id", "question"):
            if key not in q:
                raise SystemExit(f"{path} line {number}: missing '{key}'")
        q.setdefault("answerable", True)
        if q["answerable"] and not (q.get("expected") or q.get("relevant_terms")):
            raise SystemExit(f"{path} line {number}: an answerable question needs 'expected' or 'relevant_terms'")
        questions.append(q)
    return questions


def matches(doc: str, page, expected: list[dict]) -> bool:
    return any(e["doc"] == doc and (not e.get("pages") or page in e["pages"]) for e in expected)


def is_relevant(hit: dict, q: dict) -> bool:
    """A passage is correct if it is in an expected page, or contains all the words of a group."""
    if matches(hit["source_file"], hit["page"], q.get("expected", [])):
        return True
    text = hit.get("text", "").lower()
    return any(all(term.lower() in text for term in group) for group in q.get("relevant_terms", []))


def first_rank(hits: list[dict], q: dict) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if is_relevant(hit, q):
            return rank
    return None


def keyword_share(answer: str, words: list[str]) -> float | None:
    if not words:
        return None
    text = answer.lower()
    return sum(1 for w in words if w.lower() in text) / len(words)


def percent(part: int, total: int) -> str:
    return f"{part}/{total} = {100 * part / total:.0f}%" if total else "n/a"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env()
    parser = argparse.ArgumentParser(description="Step 7: evaluate the RAG")
    parser.add_argument("--questions", default="eval/questions.jsonl")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--generate", action="store_true", help="also test the answers (slow)")
    parser.add_argument("--model", help="language model (default: LLM_MODEL of .env)")
    parser.add_argument("--lang", help="answer language: en, fr, ar")
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--show-answers", action="store_true", help="print each answer")
    parser.add_argument("--out", default="eval/results", help="folder for the JSON report")
    parser.add_argument("--no-boost", action="store_true", help="no priority for guidelines (to compare)")
    args = parser.parse_args()
    if args.no_boost:
        os.environ["RAG_BOOST"] = "0"

    questions = load_questions(args.questions)
    if args.limit:
        questions = questions[:args.limit]
    answerable = [q for q in questions if q["answerable"]]
    out_of_scope = [q for q in questions if not q["answerable"]]
    model = args.model or os.environ.get("LLM_MODEL", "qwen2.5:3b")
    print(f"{len(questions)} questions ({len(answerable)} answerable, {len(out_of_scope)} out of scope)\n")

    rows = []
    for q in questions:
        row = {"id": q["id"], "question": q["question"], "answerable": q["answerable"]}
        # one search without threshold; the threshold is applied here (same result as retrieve())
        all_hits = retrieve(q["question"], k=args.k, min_score=0.0)
        hits = [h for h in all_hits if h["score"] >= args.min_score]
        row["n_hits"] = len(hits)
        row["top"] = [f"{h['source_file']} p.{h['page']} ({h['score']:.3f})" for h in all_hits]
        row["top_score"] = round(all_hits[0]["score"], 3) if all_hits else None
        row["rank"] = first_rank(hits, q) if q["answerable"] else None
        row["correct_score"] = None
        if q["answerable"]:
            for h in all_hits:                       # score of the best correct passage, even below the threshold
                if is_relevant(h, q):
                    row["correct_score"] = round(h["score"], 3)
                    break

        if args.generate:
            from dentia_rag.generate import answer_question
            started = time.time()
            result = answer_question(q["question"], k=args.k, min_score=args.min_score,
                                     model=args.model, language=args.lang)
            row["status"] = result["status"]
            row["answer"] = result["answer"]
            row["seconds"] = round(time.time() - started, 1)
            row["sources"] = [f"{h['source_file']} p.{h['page']}" for h in result["sources"]]
            if q["answerable"]:
                row["citations_correct"] = bool(result["sources"]) and all(
                    is_relevant(h, q) for h in result["sources"])
                row["keywords"] = keyword_share(result["answer"], q.get("must_include", []))
                numbers = [int(n) for n in CITE.findall(result["raw_answer"])]
                row["raw_citations_correct"] = bool(numbers) and all(
                    1 <= n <= len(result["hits"]) and is_relevant(result["hits"][n - 1], q)
                    for n in numbers)
        rows.append(row)

        if q["answerable"]:
            line = f"rank {row['rank'] or '-'}"
        else:
            line = "returned nothing (good)" if row["n_hits"] == 0 else f"returned {row['n_hits']} passages (should be 0)"
        if args.generate:
            line += f" | {row['status']}"
            if q["answerable"]:
                kw = row["keywords"]
                line += f" | citations {'ok' if row['citations_correct'] else 'WRONG/none'}"
                line += f" (model alone: {'ok' if row['raw_citations_correct'] else 'WRONG/none'})"
                line += f" | keywords {'n/a' if kw is None else f'{kw:.0%}'}"
            line += f" | {row['seconds']}s"
        print(f"{q['id']:<6} {line}")
        if args.generate and args.show_answers:
            print("       answer: " + row["answer"].replace("\n", " ")[:600])

    # ------------------------------ summary
    print("\n" + "=" * 60 + "\nRETRIEVAL (k=%d, min score %.2f)" % (args.k, args.min_score))
    ranks = [r["rank"] for r in rows if r["answerable"]]
    for n in (1, 3, 5):
        if n <= args.k:
            print(f"  hit@{n}: {percent(sum(1 for r in ranks if r and r <= n), len(ranks))}")
    if ranks:
        print(f"  MRR  : {sum(1 / r for r in ranks if r) / len(ranks):.2f}")
    print(f"  out-of-scope returned nothing: "
          f"{percent(sum(1 for r in rows if not r['answerable'] and r['n_hits'] == 0), len(out_of_scope))}")

    # ---- help to choose the minimum score, from YOUR data
    correct = [r["correct_score"] for r in rows if r["answerable"] and r["correct_score"] is not None]
    outside = [(r["top_score"], r["id"]) for r in rows if not r["answerable"] and r["top_score"] is not None]
    if correct or outside:
        print("\nMINIMUM SCORE (choose it from the data)")
        if correct:
            print(f"  lowest score of a correct passage      : {min(correct):.3f}")
        if outside:
            worst = max(outside)
            print(f"  highest score of an out-of-scope query : {worst[0]:.3f}  ({worst[1]})")
        if correct and outside:
            low, high = max(o[0] for o in outside), min(correct)
            if high > low:
                print(f"  -> a threshold between {low:.2f} and {high:.2f} separates them on these questions")
            else:
                print("  -> no threshold separates them: a score alone is not enough here "
                      "(the model, the check or a reranker must decide)")
        print("  (with few questions this is only an indication: add more questions)")

    summary = {"questions": len(questions), "k": args.k, "min_score": args.min_score,
               "boost": os.environ.get("RAG_BOOST", "1") != "0"}
    if args.generate:
        done = [r for r in rows if r["answerable"]]
        print("\n" + "=" * 60 + f"\nGENERATION (model {model})")
        usable = [r for r in done if r["status"] in ("ok", "corrected", "unverified")]
        print(f"  answered           : {percent(len(usable), len(done))}")
        print(f"  citations correct  : {percent(sum(1 for r in done if r['citations_correct']), len(done))}  (after our check)")
        print(f"  raw citations      : {percent(sum(1 for r in done if r['raw_citations_correct']), len(done))}  (model alone, before correction)")
        kws = [r["keywords"] for r in done if r["keywords"] is not None]
        if kws:
            print(f"  keywords found     : {100 * sum(kws) / len(kws):.0f}% on average")
        statuses: dict[str, int] = {}
        for r in rows:
            statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        print(f"  status counts      : {statuses}")
        print(f"  out-of-scope refused: "
              f"{percent(sum(1 for r in rows if not r['answerable'] and r['status'] == 'not_found'), len(out_of_scope))}")
        print(f"  average time       : {sum(r['seconds'] for r in rows) / len(rows):.0f} s")
        summary.update(model=model, statuses=statuses)

    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{stamp}_{model.replace(':', '-')}.json" if args.generate else f"{stamp}_retrieval.json"
    (folder / name).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    print(f"\nFull report: {folder / name}")


if __name__ == "__main__":
    main()
