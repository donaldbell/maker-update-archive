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

Shorts exclusion: the Airtable schema has no `section` field, so Shorts
rows can't be identified the way final_cleanup.py did it (section=="short").
As a proxy, titles are cross-checked against the known Shorts-title set
recovered from data/to_tag.csv's `section` column (still available locally,
independent of Airtable). This is title-based, not row-identity-based, so
it's an approximation: a handful of titles do legitimately recur across
different episodes for non-Shorts content, and any of those would be
excluded too if they happen to collide with a Shorts title. Traded off
deliberately in favor of catching the ~171 Shorts rows confirmed present
in Donald's current Airtable data (spot-checked against the original
343-row Shorts exclusion) over leaving them all in.

No-source-URL exclusion: reapplies the "no source URL = not useful, drop
it" rule from the 2026-09-09 pass (drop_no_source_url.py) -- this rebuild
had dropped it, letting 82 no-source-URL rows back into the live dataset.

Year-end/best-of recap duplicate exclusion (2026-09-16): year-end and
"favorite projects of <year>" episodes re-mention projects already
featured earlier that same year, creating duplicate entries pointing at
the same source. Donald wants those duplicates gone from the site while
the original debut-episode entry stays put. The Airtable schema carries
no episode title or "is this a recap episode" flag, so recap episodes are
identified via data/to_tag.csv's `special_type` column (best_of /
year_end / favorites_roundup), cross-referenced by episode_number.

This is a DUPLICATE exclusion, not a blanket episode exclusion: a recap
row is only dropped if a matching source_url or exact title is also found
on a non-recap row elsewhere in the CURRENT Airtable data. An earlier
version of this rule dropped every row from a recap episode outright, on
the assumption (verified against data/to_tag.csv, the older pre-Airtable
source) that recap rows always duplicate an earlier row. But to_tag.csv
predates a lot of Donald's manual Airtable cleanup, and 8 of the 57 recap
rows in the live Airtable snapshot turned out to have no surviving
duplicate anywhere else in the current data -- their original debut-
episode row is already gone (dropped in some earlier cleanup pass before
this snapshot), so the recap mention is now the ONLY surviving record of
that project (e.g. "Introducing the Raspberry Pi Pico", ep263). Blanket-
excluding those would delete real content, not dedupe it, so they're kept.
"""
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def load_shorts_titles():
    with open(DATA / "to_tag.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {r["title_guess"].strip() for r in rows if r["section"] == "short" and r["title_guess"].strip()}


RECAP_SPECIAL_TYPES = {"best_of", "year_end", "favorites_roundup"}

# Episodes 65 and 213 are also year-end recap shows but predate/missed the
# to_tag.csv special_type tagging pass. Found by scanning every Dec/Jan
# episode for what fraction of its rows duplicate a source_url or title
# found elsewhere: 65 (89%) and 213 (83%, one row literally titled "Best
# of 2020 - Adafruit Edition") sit with the confirmed recap episodes
# (79-100%), while every other Dec/Jan episode tops out at 33% -- a clean
# cliff, not a judgment call.
MANUAL_RECAP_EPISODE_NUMBERS = {65, 213}


def load_recap_episode_numbers():
    with open(DATA / "to_tag.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    nums = set(MANUAL_RECAP_EPISODE_NUMBERS)
    for r in rows:
        if r["special_type"] in RECAP_SPECIAL_TYPES and r["episode_number"].strip():
            try:
                nums.add(int(r["episode_number"]))
            except ValueError:
                pass
    return nums

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

    shorts_titles = load_shorts_titles()
    recap_episode_numbers = load_recap_episode_numbers()

    # A recap row is only a duplicate-drop candidate if the same source_url
    # or exact title also appears on a non-recap row -- see docstring above
    # for why this can't be a blanket per-episode exclusion.
    nonrecap_urls = {
        (r["source_url"] or "").strip()
        for r in records
        if r["episode_number"] not in recap_episode_numbers and (r["source_url"] or "").strip()
    }
    nonrecap_titles = {
        (r["title"] or "").strip().lower()
        for r in records
        if r["episode_number"] not in recap_episode_numbers and (r["title"] or "").strip()
    }

    by_season = defaultdict(list)
    for r in records:
        by_season[r["season"]].append(r)

    drop_reasons = Counter()
    pre_drop = set()
    for r in records:
        title = (r["title"] or "").strip()
        url = (r["source_url"] or "").strip()
        if title in EXCLUDE_TITLES:
            pre_drop.add(r["airtable_record_id"])
            drop_reasons["commentary_or_event"] += 1
        elif title in shorts_titles:
            pre_drop.add(r["airtable_record_id"])
            drop_reasons["shorts_segment"] += 1
        elif r["episode_number"] in recap_episode_numbers and (
            (url and url in nonrecap_urls) or (title and title.lower() in nonrecap_titles)
        ):
            pre_drop.add(r["airtable_record_id"])
            drop_reasons["year_review_recap_duplicate"] += 1

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

    # Both checked post-merge (not pre_drop) so a companion row whose own
    # source_url/tags happen to be blank still gets a chance to be merged
    # into its parent first -- checking these too early was the bug that
    # silently dropped ~120 companion links in an earlier version of this
    # pipeline (final_cleanup.py, 2026-09-07).
    zero_tag_drop = set()
    no_source_drop = set()
    for r in records:
        rid = r["airtable_record_id"]
        if rid in pre_drop or rid in consumed:
            continue
        if not r["tags"]:
            zero_tag_drop.add(rid)
            drop_reasons["zero_tag"] += 1
        elif not (r["source_url"] or "").strip():
            no_source_drop.add(rid)
            drop_reasons["no_source_url"] += 1

    drop_set = pre_drop | consumed | zero_tag_drop | no_source_drop
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
