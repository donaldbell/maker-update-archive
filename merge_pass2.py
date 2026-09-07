"""
Merges pass-2 source-fetch enrichment results back into tagged_final.csv.

Handles:
1. Confidence normalization: several chunks used "medium"/"failed" as a
   confidence value despite the "high"/"low"-only instruction -- folded to "low".
2. Known duplicate: pass2_chunk_09 includes one row (last row of pass2_chunk_08's
   range) that overlaps -- pass2_chunk_08's version is kept, the duplicate dropped.
3. Expanded generic-tag stripping: beyond the original list, several pass-2
   chunks fell back to honest-but-uninformative placeholder tags for rows
   where the fetch genuinely failed ("item", "unknown", "unclear", "video"
   used as bare tags) -- these are stripped the same way, leaving those rows
   with fewer/no tags rather than pretending to have real content.
4. One chunk (the original pass2_chunk_14, and one early tagged_chunk_04_pass2
   attempt) was outright fabricated (same tag set applied to unrelated rows,
   or titles copied as synopses) -- both were fully redone before this merge
   runs; this script only reads the final, verified files.

For the 1,495 rows that went through pass-2, their tags/synopsis/confidence
REPLACE the pass-1 values. For the 244 rows that had no fetchable URL, pass-1
values are kept as-is (pass-2 had nothing to add).

Output: data/tagged_final_v2.csv -- the complete, pass-2-enriched dataset.
"""
import csv
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent
DATA = ROOT / "data"

GENERIC_STRIP_TAGS = {
    "other", "maker-project", "maker-resource", "resource", "technique",
    "project", "tools", "publication", "making", "build", "guide",
    "workshop", "community", "item", "unknown", "unclear", "video",
}

PASS2_CHUNK_FILES = [f"pass2_chunk_{i:02d}.csv" for i in [1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13, 15]]
PASS2_CHUNK_FILES.append("tagged_chunk_04_pass2.csv")
PASS2_CHUNK_FILES.append("pass2_chunk_14.csv")
PASS2_CHUNK_FILES.append("pass2_chunk_10a.csv")
PASS2_CHUNK_FILES.append("pass2_chunk_10b.csv")


def clean_tags(raw):
    tags = [t.strip().lower() for t in raw.split(";") if t.strip()]
    return [t for t in tags if t not in GENERIC_STRIP_TAGS]


def main():
    with open(DATA / "tagged_final.csv", newline="", encoding="utf-8") as f:
        base_rows = list(csv.DictReader(f))
        fieldnames = list(base_rows[0].keys())
    by_key = {f"{r['source_file']}|{r['tab']}|{r['row_index']}": r for r in base_rows}

    pass2_results = {}
    for fname in PASS2_CHUNK_FILES:
        with open(DATA / fname, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["key"] not in pass2_results:  # first occurrence wins (handles the chunk 9/8 overlap)
                    pass2_results[r["key"]] = r

    updated = 0
    conf_counts = Counter()
    zero_tag_after_pass2 = 0
    for key, r in pass2_results.items():
        if key not in by_key:
            continue  # shouldn't happen, but don't crash on an unexpected key
        row = by_key[key]
        tags = clean_tags(r["tags"])
        row["tags"] = "; ".join(tags)
        row["synopsis"] = r["synopsis"] or row["synopsis"]
        conf = r["confidence"].strip().lower()
        conf = "low" if conf not in ("high", "low") else conf
        row["confidence"] = conf
        if not tags:
            zero_tag_after_pass2 += 1
        updated += 1

    final_rows = list(by_key.values())
    for r in final_rows:
        conf_counts[r["confidence"]] += 1

    with open(DATA / "tagged_final_v2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(final_rows)

    print(f"total rows: {len(final_rows)}")
    print(f"rows updated by pass-2: {updated} (expected 1495)")
    print(f"final confidence breakdown: {dict(conf_counts)}")
    print(f"rows with zero tags after pass-2 cleanup: {zero_tag_after_pass2}")
    print("wrote data/tagged_final_v2.csv")


if __name__ == "__main__":
    main()
