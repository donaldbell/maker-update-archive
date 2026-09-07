"""
Phase 3 of the enrichment pipeline: tag co-occurrence / related-terms graph.
Pure Python, no AI -- for each tag, which other tags most frequently appear
alongside it across all items. Powers a "searched 'cardboard', here are
related terms to try" feature.

Method: for every item, every unordered pair of its tags counts as one
co-occurrence for both tags in the pair. For each tag, rank its partners by
raw co-occurrence count (ties broken by the partner's overall frequency, so
a common/recognizable tag is preferred over an equally-rare one) and keep the
top N. Items with 0 or 1 tags contribute no pairs -- expected, not a bug.

Output:
- data/related_tags.json -- the simple lookup: {tag: [related_tag, ...]}
- data/related_tags_detailed.json -- same, but with co-occurrence counts,
  for inspection/verification.
"""
import csv
import json
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations

ROOT = Path(__file__).parent
DATA = ROOT / "data"
TOP_N = 8


def main():
    with open(DATA / "tagged_final.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    tag_counts = Counter()
    cooccurrence = defaultdict(Counter)

    for r in rows:
        tags = sorted(set(t.strip().lower() for t in r["tags"].split(";") if t.strip()))
        tag_counts.update(tags)
        for a, b in combinations(tags, 2):
            cooccurrence[a][b] += 1
            cooccurrence[b][a] += 1

    related_detailed = {}
    related_simple = {}
    for tag in tag_counts:
        partners = cooccurrence.get(tag, Counter())
        ranked = sorted(partners.items(), key=lambda kv: (-kv[1], -tag_counts[kv[0]], kv[0]))
        top = ranked[:TOP_N]
        related_detailed[tag] = [{"tag": t, "count": c} for t, c in top]
        related_simple[tag] = [t for t, c in top]

    with open(DATA / "related_tags.json", "w", encoding="utf-8") as f:
        json.dump(related_simple, f, indent=2, sort_keys=True)
    with open(DATA / "related_tags_detailed.json", "w", encoding="utf-8") as f:
        json.dump(related_detailed, f, indent=2, sort_keys=True)

    n_tags = len(tag_counts)
    n_with_related = sum(1 for v in related_simple.values() if v)
    n_isolated = n_tags - n_with_related
    print(f"total unique tags: {n_tags}")
    print(f"tags with at least one related tag: {n_with_related}")
    print(f"isolated tags (no co-occurrence data, e.g. only in single-tag items): {n_isolated}")
    print()
    print("sample: related tags for a few common tags")
    for sample_tag in ["3d-printing", "cardboard", "robotics", "cosplay", "raspberry-pi"]:
        if sample_tag in related_simple:
            print(f"  {sample_tag}: {related_simple[sample_tag]}")


if __name__ == "__main__":
    main()
