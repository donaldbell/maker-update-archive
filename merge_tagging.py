"""
Final merge of the 18 pass-1 tagging chunks into one tagged dataset, plus
the already-tagged uncategorized_recovered.csv rows.

Fixes applied here rather than by re-running (more subagent calls) or
patching the 18 intermediate files:

1. Confidence normalization: chunks 4/5/6/7 (run before the "high"/"low"-only
   instruction was tightened) used a "medium" value in some rows -- folded
   into "low" (same meaning: needs a source check).

2. Known duplicate/gap from wave 1's off-by-one (chunks 4 and 5 each shifted
   their whole assigned range by one row): row 855 ("Hackaday Supercon...")
   was tagged by both chunk 3 and chunk 4 -- first occurrence (chunk 3) kept.
   Row 1425 ("Designing And Building An 8 Foot Long River of Light" by Caleb
   Kraft) was never tagged by anyone -- added by hand below.

3. Tag vocabulary cleanup: several chunks (despite instructions) fell back to
   generic filler tags that carry no real search value -- "other",
   "maker-project", "maker-resource", "resource", "technique", "project",
   "tools", "publication", "making", "build", "guide", "workshop",
   "community". These describe "we don't know what this is," not the item's
   actual subject, so they're stripped from every row's tag list rather than
   re-running the tagging (cheaper and just as effective for this specific
   problem). Rows that end up with zero tags after stripping keep their
   synopsis/category but are flagged in the report.

Output: data/tagged_final.csv -- all in-scope rows (project_tip_scope.csv +
uncategorized_recovered.csv) with tags/synopsis/confidence, deduped and
cleaned. Also data/low_confidence_for_pass2.csv -- the subset needing
source-fetch enrichment.
"""
import csv
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent
DATA = ROOT / "data"

GENERIC_STRIP_TAGS = {
    "other", "maker-project", "maker-resource", "resource", "technique",
    "project", "tools", "publication", "making", "build", "guide",
    "workshop", "community",
}

MANUAL_GAP_FIX = {
    "key": "Maker_Update_Season_2.xlsx|104 121218|12",
    "tags": "led;lighting;kinetic-art;installation",
    "synopsis": "An 8-foot LED 'river of light' installation designed and built by Caleb Kraft.",
    "confidence": "high",
}


def clean_tags(raw):
    tags = [t.strip().lower() for t in raw.split(";") if t.strip()]
    return [t for t in tags if t not in GENERIC_STRIP_TAGS]


def main():
    with open(DATA / "project_tip_scope.csv", newline="", encoding="utf-8") as f:
        scope_rows = list(csv.DictReader(f))
    by_key = {f"{r['source_file']}|{r['tab']}|{r['row_index']}": r for r in scope_rows}

    tagged = {}
    for i in range(1, 19):
        with open(DATA / f"tagged_chunk_{i:02d}.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["key"] not in tagged:  # first occurrence wins (handles the one dup)
                    tagged[r["key"]] = r

    tagged[MANUAL_GAP_FIX["key"]] = MANUAL_GAP_FIX

    missing = set(by_key.keys()) - set(tagged.keys())
    if missing:
        raise SystemExit(f"ERROR: {len(missing)} project_tip_scope keys still untagged: {missing}")

    fieldnames = list(scope_rows[0].keys()) + ["tags", "synopsis", "confidence"]
    final_rows = []
    zero_tag_count = 0
    conf_counts = Counter()
    for key, base in by_key.items():
        t = tagged[key]
        row = dict(base)
        tags = clean_tags(t["tags"])
        if not tags:
            zero_tag_count += 1
        row["tags"] = "; ".join(tags)
        row["synopsis"] = t["synopsis"]
        conf = t["confidence"].strip().lower()
        conf = "low" if conf not in ("high", "low") else conf
        row["confidence"] = conf
        conf_counts[conf] += 1
        final_rows.append(row)

    # fold in the already-tagged uncategorized_recovered rows (same cleanup applied)
    with open(DATA / "uncategorized_recovered.csv", newline="", encoding="utf-8") as f:
        recovered_rows = list(csv.DictReader(f))
    for r in recovered_rows:
        row = dict(r)
        tags = clean_tags(r["tags"])
        if not tags:
            zero_tag_count += 1
        row["tags"] = "; ".join(tags)
        conf = r["confidence"].strip().lower()
        conf = "low" if conf not in ("high", "low") else conf
        row["confidence"] = conf
        conf_counts[conf] += 1
        final_rows.append(row)

    with open(DATA / "tagged_final.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(final_rows)

    low_conf = [r for r in final_rows if r["confidence"] == "low"]
    with open(DATA / "low_confidence_for_pass2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(low_conf)

    print(f"total final tagged rows: {len(final_rows)}")
    print(f"confidence breakdown: {dict(conf_counts)}")
    print(f"rows with zero tags after generic-tag cleanup: {zero_tag_count}")
    print(f"wrote data/tagged_final.csv")
    print(f"wrote data/low_confidence_for_pass2.csv ({len(low_conf)} rows)")


if __name__ == "__main__":
    main()
