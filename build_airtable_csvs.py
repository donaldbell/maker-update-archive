"""
Splits searchable_dataset.json into per-season CSVs for Airtable import (each
base is capped at 1,000 records on the free tier). Season 2 is split at
episode 108/109 since it alone exceeds 1,000 records.

Column headers match the Airtable field names exactly so the native CSV
import can auto-map every column with no manual work.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = DATA / "airtable_csv"

FIELDNAMES = [
    "Title", "Creator", "Category", "Tags", "Synopsis", "Confidence",
    "Episode Number", "Episode Date", "Edition", "Source URL",
    "Secondary URLs", "Episode Video URL", "Episode Blog URL",
]


def season_of(item):
    source_file = item["id"].split("|")[0]
    m = re.search(r"Season_(\d+)", source_file)
    return int(m.group(1)) if m else None


def to_row(item):
    return {
        "Title": item["title"] or "",
        "Creator": item["creator"] or "",
        "Category": item["category"] or "",
        "Tags": "; ".join(item["tags"]),
        "Synopsis": item["synopsis"] or "",
        "Confidence": item["confidence"] or "",
        "Episode Number": item["episode_number"] if item["episode_number"] is not None else "",
        "Episode Date": item["episode_date"] or "",
        "Edition": item["edition"] or "",
        "Source URL": item["source_url"] or "",
        "Secondary URLs": "; ".join(item["secondary_urls"]),
        "Episode Video URL": item["episode_video_url"] or "",
        "Episode Blog URL": item["episode_blog_url"] or "",
    }


def write_csv(name, items):
    OUT.mkdir(exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(to_row(i) for i in items)
    print(f"{name}.csv: {len(items)} rows")


def main():
    with open(DATA / "searchable_dataset.json", encoding="utf-8") as f:
        items = json.load(f)

    by_season = {}
    for item in items:
        by_season.setdefault(season_of(item), []).append(item)

    for s in sorted(k for k in by_season if k != 2):
        write_csv(f"Season_{s}", by_season[s])

    season2 = by_season.get(2, [])
    season2a = [i for i in season2 if i["episode_number"] is not None and i["episode_number"] <= 108]
    season2b = [i for i in season2 if i["episode_number"] is not None and i["episode_number"] >= 109]
    write_csv("Season_2A", season2a)
    write_csv("Season_2B", season2b)

    print(f"total: {sum(len(v) for v in by_season.values())}")


if __name__ == "__main__":
    main()
