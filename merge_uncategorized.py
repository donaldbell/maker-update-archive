"""
Merges the 5 uncategorized-classification chunk outputs (4 from parallel
Haiku 4.5 subagents + 1 covering 7 rows a chunk's CSV-parsing bug silently
dropped, classified by hand) back into the main dataset.

Verified before merging: 275 uncategorized rows total; one row
("Maker Faires") was independently processed by two overlapping chunks with
the same "exclude" decision (deduped, no conflict); 7 rows were silently
skipped by chunk 4 due to a multi-line-cell CSV parsing issue (covered by
chunk_5.csv). Cross-checked: all 275 keys are now accounted for exactly once.

Output:
- data/uncategorized_recovered.csv -- included rows, in the same schema as
  project_tip_scope.csv plus tags/synopsis/confidence, ready to merge into
  the tagging scope.
- data/needs_review.csv -- rows flagged needs_review across all chunks, for
  Donald to make the final call on.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"

with open(DATA / "to_tag.csv", newline="", encoding="utf-8") as f:
    to_tag_rows = list(csv.DictReader(f))
by_key = {f"{r['source_file']}|{r['tab']}|{r['row_index']}": r for r in to_tag_rows}

with open(DATA / "uncategorized_candidates.csv", newline="", encoding="utf-8") as f:
    master_keys = [r["key"] for r in csv.DictReader(f)]

seen = {}
for i in range(1, 6):
    path = DATA / f"uncategorized_tagged_chunk_{i}.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["key"] not in seen:  # first occurrence wins (handles the one dup)
                seen[r["key"]] = r

missing = set(master_keys) - set(seen.keys())
if missing:
    raise SystemExit(f"ERROR: {len(missing)} keys still unaccounted for: {missing}")

included = [r for r in seen.values() if r["decision"] == "include"]
excluded = [r for r in seen.values() if r["decision"] == "exclude"]
needs_review = [r for r in seen.values() if r["decision"] == "needs_review"]

# build recovered rows in the to_tag.csv schema + tags/synopsis/confidence
fieldnames = list(to_tag_rows[0].keys()) + ["tags", "synopsis", "confidence"]
recovered = []
for r in included:
    base = dict(by_key[r["key"]])
    base["category"] = r["category"]
    base["tags"] = r["tags"]
    base["synopsis"] = r["synopsis"]
    base["confidence"] = r["confidence"]
    recovered.append(base)

with open(DATA / "uncategorized_recovered.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(recovered)

review_fieldnames = ["key", "title_guess", "creator_guess", "primary_url", "note"]
with open(DATA / "needs_review.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=review_fieldnames)
    w.writeheader()
    for r in needs_review:
        src = by_key[r["key"]]
        w.writerow({
            "key": r["key"],
            "title_guess": src["title_guess"],
            "creator_guess": src["creator_guess"],
            "primary_url": src["primary_url"],
            "note": r["note"],
        })

proj_count = sum(1 for r in recovered if r["category"] == "project")
tip_count = sum(1 for r in recovered if r["category"] == "tip")

print(f"total uncategorized rows: {len(master_keys)}")
print(f"included: {len(included)} (project={proj_count}, tip={tip_count})")
print(f"excluded: {len(excluded)}")
print(f"needs_review: {len(needs_review)}")
print(f"wrote {len(recovered)} rows to data/uncategorized_recovered.csv")
print(f"wrote {len(needs_review)} rows to data/needs_review.csv")
