"""
Import the French public medicines database (BDPM) into the `medications` table.
Usage (from backend/, venv active):  python import_bdpm.py "C:\\path\\to\\folder" [--drop-seed]
The folder must contain CIS_bdpm.txt and CIS_COMPO_bdpm.txt. Not tested: check the printed counts.
"""
import argparse
import os
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def read_rows(path: Path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")   # older BDPM files are not UTF-8
    for line in text.splitlines():
        if line.strip():
            yield line.split("\t")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--drop-seed", action="store_true", help="delete the 14 starter rows afterwards")
    args = ap.parse_args()
    folder = Path(args.folder)

    ingredients = defaultdict(list)
    for r in read_rows(folder / "CIS_COMPO_bdpm.txt"):
        if len(r) >= 7 and r[6].strip() == "SA":          # active substances only
            name = r[3].strip().lower()
            if name and name not in ingredients[r[0]]:
                ingredients[r[0]].append(name)

    rows, status_seen = [], Counter()
    for r in read_rows(folder / "CIS_bdpm.txt"):
        if len(r) < 7:
            continue
        cis, name, form, routes, amm, _proc, market = (c.strip() for c in r[:7])
        status_seen[(amm, market)] += 1
        if "non commercialis" in market.lower() or "commercialis" not in market.lower():
            continue
        if any(w in amm.lower() for w in ("abrog", "archiv", "retir", "suspend")):
            continue
        rows.append({
            "doctor_id": None, "cis": cis, "name": name, "form": form,
            "routes": routes, "ingredients": " + ".join(ingredients.get(cis, [])), "source": "bdpm",
        })

    print("Status combinations in the file (administrative status, marketing status):")
    for (amm, market), n in status_seen.most_common(8):
        print(f"  {n:6d}  {amm!r} / {market!r}")
    print(f"{len(rows)} medicines kept")
    if not rows:
        raise SystemExit("Nothing kept: check the filters above against the values printed.")

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    for i in range(0, len(rows), 500):
        sb.table("medications").upsert(rows[i:i + 500], on_conflict="cis").execute()
        print(f"  {min(i + 500, len(rows))}/{len(rows)}")
    if args.drop_seed:
        sb.table("medications").delete().eq("source", "seed").execute()
        print("Starter rows removed.")


if __name__ == "__main__":
    main()