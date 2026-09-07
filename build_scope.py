"""
Clean-up pass before tagging: narrows to_tag.csv down to the actual
"projects and tips" inspiration database Donald wants, per his scoping
decisions (see project memory / conversation for the full investigation):

1. Companion-link merge (runs first, on the full row set): rows whose
   title_guess is just a link-type label ("GitHub", "Code:", "Thingiverse",
   "News") are NOT standalone items -- verified by hand that each one's
   primary_url is a second/alternate link for the project in the
   immediately preceding row of the same spreadsheet tab (e.g. a project's
   own page/video plus a separate row for its GitHub code). These are
   merged into the parent row's `secondary_urls` (using the "; " delimiter
   already used elsewhere in that column) and then dropped as their own
   row, so a search result surfaces both links under the one project.

2. Base scope: category in {project, tip} -- this maps 1:1 and deterministically
   from `section` (verified: no section maps to more than one category), so it
   cleanly captures "Project of the Week" / "More Projects" / "Tips & Tools"
   and excludes News / DigiKey & Product Spotlight / Maker Channel Spotlight.

3. Exclude rows verified (by hand, not by blind keyword match) to be generic
   bumpers, data-quality artifacts, or non-content announcements.

4. Exclude all Maker Faire / event-mention titles (385 rows, 93% concentrated
   in episodes 0-99 -- a standing early-show segment, not individual
   projects) and Maker-Update-produced "bonus projects" roundup segments that
   bundle several different items into one row -- both per Donald's explicit
   decision.

5. Exclude Gareth Branwyn's "Tips of the Week" / "Tips, Tools, and Shop
   Tales" newsletter mentions -- per Donald: these link out to a roundup
   page covering several different tips, not to one tip itself, so they
   don't fit a single-item search result. A few titles that name one
   specific real thing (not a newsletter issue) are kept as exceptions.

Output: data/project_tip_scope.csv -- the candidate set for tagging.
Does NOT yet include any rows recovered from the 275 "uncategorized" bucket;
that needs its own classification pass (separate step) -- which will also
need to watch for "episode title" leaks (an episode's own punny theme name
ending up as a row's title_guess), confirmed present in that bucket.
"""
import csv
import re
from pathlib import Path
from collections import Counter
from typing import Optional

ROOT = Path(__file__).parent
INPUT_CSV = ROOT / "data" / "to_tag.csv"
OUTPUT_CSV = ROOT / "data" / "project_tip_scope.csv"

# Verified by hand: each of these titles is just a link-type label, and its
# primary_url is a genuine second link for the project in the preceding row
# of the same tab (not independent content). NOTE: "News" was tested and
# rejected -- one instance's url (an unrelated Arduino Nano announcement)
# had nothing to do with its preceding row ("Hackaday take", a DSKY replica),
# so "News" rows are left as their own entries rather than merged.
COMPANION_LABELS = {"github", "code", "thingiverse"}

# Verified by hand: generic bumpers, contest/ad announcements, and parsing
# artifacts with no real per-row content (confirmed via primary_url/creator_guess
# inspection -- these all share one non-specific URL or are entirely blank).
EXCLUDE_EXACT_TITLES = {
    "Maker Faires",              # 90x, always links to the generic faire map page
    "Cool Tools Minute",         # 42x, always links to cool-tools.org homepage, not the specific tool
    "Contests Ending Soon",      # 10x, generic Instructables contest page
    "Hackspace U.S. Subscription half-off",  # magazine subscription ad
    "Wood",                      # 2x, both the generic Instructables Wood Contest 2016 page
    "1st", "2nd", "3rd", "4th", "5th",  # ordinal fragments, blank url/creator
    "Tips",                      # bare word, blank url/creator (distinct from "Tips of the Week")
    "Rome", "Berlin",            # likely truncated Maker Faire city mentions (early eps, tools tips, no url/creator)
    # Maker-Update-produced "bonus projects" roundup shorts -- bundle several
    # separate items into one row, per Donald's decision to exclude roundups:
    "5 Bonus Projects - Maker Update #Shorts",
    "5 Cool Projects This Week",
    "5 Bonus #Maker Projects - #MakerUpdate #Electronics #DIY",
    "5 Maker Update Bonus Projects",
    "5 Bonus Projects",
    # Announcements/asks, not content:
    "Winner picked next week 12/15/2016. To enter, pitch donald@makerprojectlab.com with Pi Project your ideas.",
    "If you have a favorite project of the year we didn't cover, let us know down in the comments.",
    "Spring 2025 Electronics Project Contests on Instructables",
    "Thanks Gareth and Boing Boing",  # links to a Boing Boing roundup page, not a specific tip
}

# Gareth mentions that name one specific real thing, not a newsletter/roundup issue:
GARETH_KEEP_EXCEPTIONS = {
    "Body Ruler (via Gareth)",
    "Exploring gradient infills for 3D prints via Gareth Branwyn",
    "Gareths New Book: Tips and Tales from the Workshop: A Handy Reference for Makers",
}

DATE_ARTIFACT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(\s\d{2}:\d{2}:\d{2})?$")


def exclusion_reason(title: str) -> Optional[str]:
    t = title.strip()
    if not t:
        return None
    if t in EXCLUDE_EXACT_TITLES:
        return "generic_bumper_or_ad_or_artifact"
    if DATE_ARTIFACT_RE.match(t):
        return "date_artifact"
    if "faire" in t.lower():
        return "maker_faire_event_mention"
    if t not in GARETH_KEEP_EXCEPTIONS:
        tl = t.lower()
        if "gareth" in tl or "tips of the week" in tl:
            return "gareth_tips_roundup"
    return None


def merge_companion_links(rows):
    """Fold GitHub/Code/Thingiverse/News companion rows into the preceding
    row of the same tab, appending to secondary_urls. Returns (remaining_rows, merge_count)."""
    by_tab = {}
    for r in rows:
        by_tab.setdefault((r["source_file"], r["tab"]), []).append(r)
    for tab_rows in by_tab.values():
        tab_rows.sort(key=lambda r: int(r["row_index"]))

    dropped_ids = set()
    merge_count = 0
    for r in rows:
        norm = r["title_guess"].strip().lower().rstrip(":")
        if norm not in COMPANION_LABELS:
            continue
        tab_rows = by_tab[(r["source_file"], r["tab"])]
        idx = int(r["row_index"])
        preceding = [x for x in tab_rows if int(x["row_index"]) < idx and id(x) not in dropped_ids]
        if not preceding:
            continue  # no parent found -- leave as its own row rather than silently drop
        parent = preceding[-1]
        extra_url = r["primary_url"].strip()
        if extra_url:
            existing = parent["secondary_urls"].strip()
            parent["secondary_urls"] = f"{existing}; {extra_url}" if existing else extra_url
        dropped_ids.add(id(r))
        merge_count += 1

    remaining = [r for r in rows if id(r) not in dropped_ids]
    return remaining, merge_count


def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows, merge_count = merge_companion_links(rows)

    base_scope = [r for r in rows if r["category"] in ("project", "tip")]

    kept = []
    excluded_by_reason = Counter()
    for r in base_scope:
        reason = exclusion_reason(r["title_guess"])
        if reason:
            excluded_by_reason[reason] += 1
        else:
            kept.append(r)

    fieldnames = list(rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(kept)

    print(f"companion links merged into parent rows: {merge_count}")
    print(f"to_tag.csv total rows (post-merge):       {len(rows)}")
    print(f"category in (project, tip):               {len(base_scope)}")
    print(f"excluded by reason:")
    for reason, count in excluded_by_reason.most_common():
        print(f"    {reason:30s} {count}")
    print(f"total excluded:                            {sum(excluded_by_reason.values())}")
    print(f"final project_tip_scope.csv rows:         {len(kept)}")


if __name__ == "__main__":
    main()
