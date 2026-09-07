"""
Fetches all posts from the makerprojectlab.com WordPress REST API and saves
them locally as JSON, so the episode->YouTube-video-ID matching step (a
separate script) can work offline against a stable snapshot instead of
re-hitting the API.
"""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
BASE = "https://makerprojectlab.com/wp-json/wp/v2/posts"
PER_PAGE = 100


def fetch_page(page):
    url = f"{BASE}?per_page={PER_PAGE}&page={page}&_fields=id,date,link,slug,title,content,categories"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0.1", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
        data = json.loads(resp.read())
    return data, total_pages


def main():
    all_posts = []
    page = 1
    total_pages = None
    while total_pages is None or page <= total_pages:
        posts, total_pages = fetch_page(page)
        all_posts.extend(posts)
        print(f"fetched page {page}/{total_pages} ({len(posts)} posts)")
        page += 1
        time.sleep(0.3)

    with open(DATA / "blog_posts_raw.json", "w", encoding="utf-8") as f:
        json.dump(all_posts, f)

    print(f"total posts fetched: {len(all_posts)}")


if __name__ == "__main__":
    main()
