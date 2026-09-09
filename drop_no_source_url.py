"""
Applies Donald's rule: an entry with no source URL isn't useful for a
project/tip resource and should be dropped. Applied here (rather than only
enforced manually in Airtable) since building the site's dataset is a
natural point to fold it in without requiring another Airtable round-trip.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"


def main():
    with open(DATA / "tagged_final.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    kept = [r for r in rows if r["primary_url"].strip()]
    dropped = len(rows) - len(kept)

    with open(DATA / "tagged_final.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(kept)

    print(f"dropped (no source_url): {dropped}")
    print(f"final row count: {len(kept)}")


if __name__ == "__main__":
    main()
