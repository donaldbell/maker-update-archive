"""
Tag normalization pass: consolidates near-duplicate tag variants that
fragment the browse/search and co-occurrence signal, found by surveying the
full tag vocabulary (3,546 unique tags) after tagging + pass-2.

Three mechanical (safe, rule-based) passes, applied in order:
1. Singular/plural: if tag+"s" (or "y"->"ies") both exist, merge to whichever
   has the higher item count.
2. Hyphen/space-insensitive duplicates: tags that are identical once hyphens/
   spaces/underscores are stripped (e.g. "3dprinting" vs "3d-printing") merge
   to the highest-count variant.
3. A curated list of suffix-variant synonyms found by manually reviewing the
   top 150 tags (e.g. "prop-making"/"prop-hacking" -> "props", "clock-making"
   -> "clock") -- NOT applied to pairs with substantial independent usage on
   both sides (kept "game" separate from "game-design", "mechanical" separate
   from "mechanical-design"), since those likely represent a real facet split
   rather than a spelling variant.

Also strips a handful of tags that are generic filler in plural/variant form
and slipped past the original GENERIC_STRIP_TAGS list (e.g. "techniques",
"tips", "reference", "review", "materials", "components", "modification").

Rewrites data/tagged_final.csv in place (tags column only) and rebuilds
data/related_tags.json / data/related_tags_detailed.json from the normalized
tags via build_related_tags.py's logic.
"""
import csv
import json
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations

ROOT = Path(__file__).parent
DATA = ROOT / "data"
TOP_N = 8

# Additional generic filler that slipped past the original strip list in
# plural/variant form -- carries no faceted-search value.
EXTRA_STRIP = {"techniques", "tips", "reference", "review", "materials", "components", "modification"}

# Curated suffix-variant synonyms (canonical -> variants to fold in).
# Only pairs where the variant's count is small relative to a clear base
# concept; deliberately excludes cases with substantial independent usage
# on both sides (e.g. game vs game-design, mechanical vs mechanical-design).
CURATED_MERGES = {
    "props": ["prop", "prop-making", "prop-hacking"],
    "clock": ["clock-making", "clock-design"],
    "costume": ["costume-design"],
    "jewelry": ["jewelry-making"],
    "toy": ["toy-making", "toy-design", "toy-hacking", "toys"],
    "camera": ["camera-hack"],
    "metalworking": ["metal-work", "metalwork"],
    "pcb": ["pcb-work", "pcb-design"],
    "mechanism": ["mechanism-design"],
    "vintage-tech": ["vintage-tech-hack"],
    "precision": ["precision-work"],
    "hardware": ["hardware-hacking"],
    "led": ["led-design"],
    "lighting": ["lighting-design"],
    "cad": ["cad-design"],
    "design": ["design-tips"],
    "programming": ["programming-tips"],
    "audio": ["audio-hack"],
    "fashion": ["fashion-diy"],
    "software": ["software-tips", "software-review"],
    "electronics": ["electronics-design", "electronics-hack", "electronics-hacking"],
    "diy": ["diy-project"],
}


def build_canonical_map(tag_counts):
    canon = {}  # variant -> canonical

    def union(a, b):
        # merge b into whichever of (a, canon.get(a,a)) has the higher count
        ra, rb = canon.get(a, a), canon.get(b, b)
        if ra == rb:
            return
        if tag_counts.get(ra, 0) >= tag_counts.get(rb, 0):
            canon[rb] = ra
            for k, v in list(canon.items()):
                if v == rb:
                    canon[k] = ra
        else:
            canon[ra] = rb
            for k, v in list(canon.items()):
                if v == ra:
                    canon[k] = rb

    all_tags = set(tag_counts)

    # 1. singular/plural
    for t in all_tags:
        if t.endswith("s") and t[:-1] in all_tags:
            union(t, t[:-1])
        if t.endswith("ies") and (t[:-3] + "y") in all_tags:
            union(t, t[:-3] + "y")

    # 2. hyphen/space-insensitive
    def norm(t):
        return t.replace("-", "").replace(" ", "").replace("_", "")
    groups = defaultdict(list)
    for t in all_tags:
        groups[norm(t)].append(t)
    for variants in groups.values():
        if len(variants) > 1:
            base = variants[0]
            for v in variants[1:]:
                union(base, v)

    # 3. curated suffix-variant synonyms
    for canonical, variants in CURATED_MERGES.items():
        for v in variants:
            if v in all_tags:
                union(canonical, v)

    # resolve chains (canon[x] should point straight to a final root)
    def resolve(t):
        seen = set()
        while t in canon and t not in seen:
            seen.add(t)
            t = canon[t]
        return t

    return {t: resolve(t) for t in all_tags}


def main():
    with open(DATA / "tagged_final.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    tag_counts = Counter()
    for r in rows:
        tags = set(t.strip().lower() for t in r["tags"].split(";") if t.strip())
        tag_counts.update(tags)

    canonical_map = build_canonical_map(tag_counts)

    merges_applied = Counter()
    for r in rows:
        tags = [t.strip().lower() for t in r["tags"].split(";") if t.strip()]
        new_tags = []
        seen = set()
        for t in tags:
            c = canonical_map.get(t, t)
            if t in EXTRA_STRIP or c in EXTRA_STRIP:
                continue
            if c != t:
                merges_applied[f"{t} -> {c}"] += 1
            if c not in seen:
                seen.add(c)
                new_tags.append(c)
        r["tags"] = "; ".join(new_tags)

    with open(DATA / "tagged_final.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    new_tag_counts = Counter()
    for r in rows:
        new_tag_counts.update(set(t.strip().lower() for t in r["tags"].split(";") if t.strip()))

    print(f"tags before normalization: {len(tag_counts)}")
    print(f"tags after normalization:  {len(new_tag_counts)}")
    print(f"distinct merge rules applied: {len(merges_applied)}")
    print(f"total tag-instances remapped: {sum(merges_applied.values())}")
    print()
    print("top 20 merges by frequency:")
    for merge, count in merges_applied.most_common(20):
        print(f"  {count:4d}x  {merge}")

    # rebuild co-occurrence graph on the normalized tags
    cooccurrence = defaultdict(Counter)
    for r in rows:
        tags = sorted(set(t.strip().lower() for t in r["tags"].split(";") if t.strip()))
        for a, b in combinations(tags, 2):
            cooccurrence[a][b] += 1
            cooccurrence[b][a] += 1

    related_detailed = {}
    related_simple = {}
    for tag in new_tag_counts:
        partners = cooccurrence.get(tag, Counter())
        ranked = sorted(partners.items(), key=lambda kv: (-kv[1], -new_tag_counts[kv[0]], kv[0]))
        top = ranked[:TOP_N]
        related_detailed[tag] = [{"tag": t, "count": c} for t, c in top]
        related_simple[tag] = [t for t, c in top]

    with open(DATA / "related_tags.json", "w", encoding="utf-8") as f:
        json.dump(related_simple, f, indent=2, sort_keys=True)
    with open(DATA / "related_tags_detailed.json", "w", encoding="utf-8") as f:
        json.dump(related_detailed, f, indent=2, sort_keys=True)

    print()
    print("rebuilt related_tags.json with normalized tags")
    for sample_tag in ["cosplay", "props", "3d-printing", "woodworking", "toy"]:
        if sample_tag in related_simple:
            print(f"  {sample_tag}: {related_simple[sample_tag]}")


if __name__ == "__main__":
    main()
