"""
Rebuilds docs/data.json from Donald's current, actively-edited Airtable
data (data/airtable_live_snapshot.json), instead of the older locally-
generated data/searchable_dataset.json.

Applies the same hygiene rules as final_cleanup.py's Airtable-import pass
(bare-URL-title companion-link merge, commentary/event junk exclusion,
zero-tag drop), adapted to the Airtable pull: within-season record order
is used as the "preceding row" adjacency proxy (Airtable's list order for
CSV-imported data tracks the original spreadsheet row order), since the
Airtable schema doesn't carry the original tab/row_index columns.

Shorts exclusion is NOT reapplied here -- the Airtable schema has no
`section` field, so Shorts can't be distinguished from this data. (They
were not observed as bare url titles, ~and no `edition`/`category` value
in the pull corresponds to them -- they're either already absent from
Donald's Airtable bases or unidentifiable here; flagged, not silently
assumed-handled.)
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
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


def main():
    with open(DATA / "airtable_live_snapshot.json", encoding="utf-8") as f:
        records = json.load(f)

    by_season = defaultdict(list)
    for r in records:
        by_season[r["season"]].append(r)

    drop_reasons = Counter()
    pre_drop = set()
    for r in records:
        title = (r["title"] or "").strip()
        if title in EXCLUDE_TITLES:
            pre_drop.add(r["airtable_record_id"])
            drop_reasons["commentary_or_event"] += 1

    consumed = set()
    merged_count = 0
    orphaned_count = 0
    by_id = {r["airtable_record_id"]: r for r in records}

    for season, season_rows in by_season.items():
        for idx, r in enumerate(season_rows):
            rid = r["airtable_record_id"]
            title = (r["title"] or "").strip()
            if rid in pre_drop or not URL_RE.match(title):
                continue
            parent = None
            for cand in reversed(season_rows[:idx]):
                cand_title = (cand["title"] or "").strip()
                if not cand_title or URL_RE.match(cand_title):
                    continue
                cid = cand["airtable_record_id"]
                if cid in pre_drop or cid in consumed:
                    continue
                parent = cand
                break
            if parent is None:
                consumed.add(rid)
                drop_reasons["orphaned_url_row"] += 1
                orphaned_count += 1
                continue
            extra_url = (r["source_url"] or title).strip()
            if extra_url and extra_url not in parent["secondary_urls"]:
                parent["secondary_urls"].append(extra_url)
            consumed.add(rid)
            merged_count += 1

    zero_tag_drop = set()
    for r in records:
        rid = r["airtable_record_id"]
        if rid in pre_drop or rid in consumed:
            continue
        if not r["tags"]:
            zero_tag_drop.add(rid)
            drop_reasons["zero_tag"] += 1

    drop_set = pre_drop | consumed | zero_tag_drop
    kept = [r for r in records if r["airtable_record_id"] not in drop_set]

    items = []
    for r in kept:
        items.append({
            "id": r["airtable_record_id"],
            "title": r["title"],
            "creator": r["creator"],
            "category": r["category"],
            "tags": r["tags"],
            "synopsis": r["synopsis"],
            "confidence": r["confidence"],
            "episode_number": r["episode_number"],
            "episode_date": r["episode_date"],
            "edition": r["edition"],
            "source_url": r["source_url"],
            "secondary_urls": r["secondary_urls"],
            "episode_video_url": r["episode_video_url"],
            "episode_blog_url": r["episode_blog_url"],
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }

    out_path = DOCS / "data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"starting records: {len(records)}")
    print(f"URL-companion rows merged into parent: {merged_count}")
    print(f"URL-companion rows orphaned (dropped): {orphaned_count}")
    print(f"drop reasons: {dict(drop_reasons)}")
    print(f"total dropped: {len(drop_set)}")
    print(f"wrote {out_path}: {len(items)} items, {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
