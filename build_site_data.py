"""
Wraps the cleaned local dataset (data/searchable_dataset.json -- the
authoritative, cleaned 4,194-row dataset) into docs/data.json, the file the
static site's client-side search actually loads.

NOTE: deliberately NOT sourced from data/airtable_live_snapshot.json. That
snapshot reflects Airtable's current (broken) state -- a stale pre-cleanup
re-import sitting in the wrong table -- not the cleaned dataset. Once
Airtable is fixed and becomes the live-edited source of truth, this script
should be pointed at a fresh Airtable pull instead.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"


def main():
    with open(DATA / "searchable_dataset.json", encoding="utf-8") as f:
        items = json.load(f)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }

    out_path = DOCS / "data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"wrote {out_path}: {len(items)} items, {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
