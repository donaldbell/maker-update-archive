"""
Final cleanup pass, per Donald's review of the imported Airtable data:

1. Merge bare-URL-as-title rows (278 of them) into their real parent project's
   Secondary URLs -- same companion-link pattern as the earlier GitHub/Code/
   Thingiverse merge, generalized to catch ANY bare URL title, and walking
   back past chains of multiple consecutive URL-titled rows to find the
   real parent (verified: all 278 resolve cleanly this way).
2. Drop host/production commentary rows that aren't project/tip content
   (sign-offs, shoutout segments, a sponsor discount code, a scheduling note).
3. Drop event/festival/meetup promo rows (expands the original Maker-Faire-only
   exclusion to other event types found on manual review) -- keeping real
   projects that just happen to mention a festival by name (e.g. "LED Festival
   Coat", "Playa Festival Bike" -- these are creator projects, not event promos).
4. Drop all `section == 'short'` rows entirely -- Donald's "Shorts" are a
   separate short-form content bit alongside the main show (editorial asides
   or recaps of earlier episodes), explicitly out of scope for this database.
5. Drop all rows with zero tags -- pass-2 source-fetching couldn't resolve
   real content for these even after a fetch attempt; too sparse to be useful
   in a browse/search database.

Rebuilds tagged_final.csv, related_tags.json/_detailed.json,
searchable_dataset.json, and the per-season Airtable CSVs from scratch so
everything stays consistent.
"""
import csv
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations

ROOT = Path(__file__).parent
DATA = ROOT / "data"
TOP_N = 8
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

COMMENTARY_EXCLUDE_TITLES = {
    "Shoutout",
    "Shout Out",
    "Thanks to everyone who liked or commented or shared a Maker Update this year. Big thanks to DigiKey.",
    "Happy new year! We'll see you soon.",
    "Maybe a teaser for the full year in review show?",
    "Use code: MAKER30 for 30% off entire purchase of any items (excluding subscriptions).",
    "Move to Fridays, every other week. Work at ADSK.",
}

EVENT_EXCLUDE_TITLES = {
    "2018 Midwest RepRap Festival 3/23-25",
    "Market St. Prototyping Festival",
    "Eyeo Festival June 3-6",
    "Plotter People Meetup #2",
    "Maker Music Festival",
    "Chimera Arts launches First Annual “Maker Music Festival” Saturday, October 13th, 2018",
    "2023 Open Hardware Summit",
    "LLUM BCN Light Festival",
    "Donald talks at EBMF",
    "Moat Boat Paddle Battle",
}

EXCLUDE_TITLES = COMMENTARY_EXCLUDE_TITLES | EVENT_EXCLUDE_TITLES


def key_of(r):
    return f"{r['source_file']}|{r['tab']}|{r['row_index']}"


def main():
    with open(DATA / "tagged_final.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())
    by_key = {key_of(r): r for r in rows}

    # full original sequence (pre-scope-filtering) for walk-back adjacency
    with open(DATA / "to_tag.csv", newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    by_tab = defaultdict(list)
    for r in all_rows:
        by_tab[(r["source_file"], r["tab"])].append(r)
    for k in by_tab:
        by_tab[k].sort(key=lambda r: int(r["row_index"]))

    drop_reasons = Counter()

    # Step 1: "hard" drops that apply regardless of a row's own tag content --
    # commentary/event junk and Shorts segments. Computed BEFORE the zero-tag
    # check so a companion URL row that happens to have empty tags (very
    # common -- pass-2 often can't tag a bare URL) still gets a chance to be
    # merged into its parent rather than silently discarded.
    pre_drop = set()
    for k, r in by_key.items():
        if r["section"] == "short":
            pre_drop.add(k)
            drop_reasons["shorts_segment"] += 1
        elif r["title_guess"].strip() in EXCLUDE_TITLES:
            pre_drop.add(k)
            drop_reasons["commentary_or_event"] += 1

    # Step 2: URL-as-title companion merge, over rows not already hard-dropped.
    url_rows = [r for r in by_key.values() if URL_RE.match(r["title_guess"].strip()) and key_of(r) not in pre_drop]
    consumed = set()
    merged_count = 0
    orphaned_count = 0
    for r in url_rows:
        k = key_of(r)
        tab_rows = by_tab.get((r["source_file"], r["tab"]), [])
        idx = int(r["row_index"])
        preceding = [x for x in tab_rows if int(x["row_index"]) < idx]
        parent = None
        for cand in reversed(preceding):
            t = cand["title_guess"].strip()
            if not t or URL_RE.match(t):
                continue
            cand_key = key_of(cand)
            if cand_key in pre_drop or cand_key in consumed or cand_key not in by_key:
                continue  # this candidate parent is itself being dropped or out of scope -- keep walking back
            parent = by_key[cand_key]
            break
        if parent is None:
            consumed.add(k)
            drop_reasons["orphaned_url_row"] += 1
            orphaned_count += 1
            continue
        extra_url = r["primary_url"].strip() or r["title_guess"].strip()
        existing = parent["secondary_urls"].strip()
        parent["secondary_urls"] = f"{existing}; {extra_url}" if existing else extra_url
        consumed.add(k)  # consumed into parent, not kept as its own row
        merged_count += 1

    # Step 3: NOW evaluate zero-tag on whatever's left standing -- real
    # candidate rows only, never a companion URL row (already merged/dropped
    # above) or an already-hard-dropped row.
    zero_tag_drop = set()
    for k, r in by_key.items():
        if k in pre_drop or k in consumed:
            continue
        if not r["tags"].strip():
            zero_tag_drop.add(k)
            drop_reasons["zero_tag"] += 1

    drop_set = pre_drop | consumed | zero_tag_drop
    kept_rows = [r for k, r in by_key.items() if k not in drop_set]

    with open(DATA / "tagged_final.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(kept_rows)

    print(f"starting rows: {len(rows)}")
    print(f"URL-companion rows merged into parent: {merged_count}")
    print(f"URL-companion rows orphaned (no valid surviving parent, dropped): {orphaned_count}")
    print(f"drop reasons: {dict(drop_reasons)}")
    print(f"total dropped: {len(drop_set)}")
    print(f"final row count: {len(kept_rows)}")
    print("wrote data/tagged_final.csv")


if __name__ == "__main__":
    main()
