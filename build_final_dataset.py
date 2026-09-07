"""
Phase 4 (final): merges tagged_final.csv + episode_video_map.json into one
clean searchable dataset, per item: title, creator, category, tags, synopsis,
episode number/date, edition, the item's own source link, and a deep link to
the moment in the YouTube episode (or the blog post as a fallback, per
Donald's note that a blog-post link is an acceptable fallback when a clean
timestamped video link isn't available).

Deep link priority per item:
1. episode's video_id + timestamp_seconds (if the item has one) ->
   https://youtube.com/watch?v=<id>&t=<seconds>s
2. episode's video_id alone (no timestamp for this specific item) ->
   https://youtube.com/watch?v=<id>
3. episode's blog post URL (only set for entries sourced from the blog, not
   the 5 episodes Donald supplied a bare video link for)
4. null -- should not occur given 499/499 episode coverage, but handled
   rather than assumed away

Also carries related_tags.json forward unchanged as a companion file for the
eventual site's "related terms" feature.

Output: data/searchable_dataset.json -- a JSON array, one object per item.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"


def resolve_source_url(row):
    primary = row["primary_url"].strip()
    if primary:
        return primary
    title = row["title_guess"].strip()
    if title.lower().startswith(("http://", "https://")):
        return title
    return None


def resolve_deep_link(video_map_entry, timestamp_seconds):
    if not video_map_entry:
        return None
    video_id = video_map_entry.get("video_id")
    if video_id:
        if timestamp_seconds:
            return f"https://youtube.com/watch?v={video_id}&t={timestamp_seconds}s"
        return f"https://youtube.com/watch?v={video_id}"
    if video_map_entry.get("blog_url"):
        return video_map_entry["blog_url"]
    return None


def main():
    with open(DATA / "tagged_final.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with open(DATA / "episode_video_map.json", encoding="utf-8") as f:
        video_map = json.load(f)

    items = []
    no_deep_link = 0
    for r in rows:
        ep_entry = video_map.get(r["episode_number"]) if r["episode_number"] else None
        timestamp = r["timestamp_seconds"].strip() or None
        deep_link = resolve_deep_link(ep_entry, timestamp)
        if deep_link is None:
            no_deep_link += 1

        secondary = [u.strip() for u in r["secondary_urls"].split(";") if u.strip()]
        tags = [t.strip() for t in r["tags"].split(";") if t.strip()]

        items.append({
            "id": f"{r['source_file']}|{r['tab']}|{r['row_index']}",
            "title": r["title_guess"].strip(),
            "creator": r["creator_guess"].strip() or None,
            "category": r["category"],
            "tags": tags,
            "synopsis": r["synopsis"].strip() or None,
            "confidence": r["confidence"],
            "episode_number": int(r["episode_number"]) if r["episode_number"] else None,
            "episode_date": r["episode_date"] or None,
            "edition": r["edition"] or None,
            "source_url": resolve_source_url(r),
            "secondary_urls": secondary,
            "episode_video_url": deep_link,
            "episode_blog_url": (ep_entry or {}).get("blog_url"),
        })

    with open(DATA / "searchable_dataset.json", "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

    print(f"total items: {len(items)}")
    print(f"items with no deep link at all: {no_deep_link}")
    print(f"items with a source_url: {sum(1 for i in items if i['source_url'])}")
    print(f"items with a timestamped deep link: {sum(1 for i in items if i['episode_video_url'] and '&t=' in i['episode_video_url'])}")
    print(f"items with a non-timestamped video deep link: {sum(1 for i in items if i['episode_video_url'] and '&t=' not in i['episode_video_url'] and 'youtube.com/watch' in i['episode_video_url'])}")
    print(f"items falling back to blog_url as deep link: {sum(1 for i in items if i['episode_video_url'] and 'makerprojectlab.com' in (i['episode_video_url'] or ''))}")
    print("wrote data/searchable_dataset.json")


if __name__ == "__main__":
    main()
