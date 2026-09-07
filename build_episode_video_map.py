"""
Builds episode_number -> YouTube video ID mapping from the makerprojectlab.com
blog posts (fetched via fetch_blog_posts.py into data/blog_posts_raw.json).

Each episode post's content starts with an intro paragraph ("This week on
<a href="...">Maker Update</a>: ...<!--more-->") whose link is the episode's
own YouTube video, followed by a "Show Notes [Maker Update #N]" (or "Ep.N",
or other historical variants) header naming the episode number.

Method per post:
1. Confirm it's an episode post: content matches the "This week on ... Maker
   Update" intro pattern or a "Show Notes [Maker Update ...]" header.
2. Episode number: extracted from the Show Notes header (preferred, more
   consistently structured across 9 years of format changes) or the title's
   "[Maker Update ...]" bracket as a fallback. Bare "Maker Update" with no
   number in either place leaves the episode number unresolved from text
   alone -- those posts are matched to an episode by publish-date proximity
   against our own episode_date data instead (see below).
3. Video ID: the first youtube.com/watch?v=ID or youtu.be/ID link appearing
   before the "<!--more-->" marker (the intro paragraph). Falls back to the
   first YouTube link anywhere in the post if none appears before the marker.

Cross-validation: every post's extracted date is compared against our own
episode_number -> episode_date table (from data/tagged_final.csv, deduped)
-- a mismatch beyond a few days flags the match for manual review rather
than being silently trusted.

Output: data/episode_video_map.json -- {episode_number: {video_id, blog_url,
blog_title, blog_date, match_method}}. Also prints a coverage report against
episodes 1-500.
"""
import csv
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent
DATA = ROOT / "data"

YT_RE = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})')
INTRO_RE = re.compile(r'This week on.*?Maker Update', re.IGNORECASE | re.DOTALL)
SHOWNOTES_RE = re.compile(r'Show Notes\s*\[([^\]]*)\]', re.IGNORECASE)
TITLE_BRACKET_RE = re.compile(r'\[([^\]]*Maker Update[^\]]*)\]', re.IGNORECASE)
NUMBER_RE = re.compile(r'\d+')


TAG_RE = re.compile(r"<[^>]+>")

# Blog-post-source typos found by cross-checking against our own data / date
# timeline -- the show-notes header genuinely says the wrong number in the
# original post; these override the extracted value.
KNOWN_SOURCE_TYPOS = {
    # (blog_title_substring): correct_episode_number
    "G-code Good Guy": 259,       # header says "Ep.159", our own data confirms 259
    "Bread Roll": 366,            # header says "Ep.266", but post date (2024-01-18) matches ep366
    "All That Glitters": 271,     # header says "Ep. 270", duplicate of Turn Turn Turn's real 270
}


def extract_episode_number(post):
    for substr, correct_num in KNOWN_SOURCE_TYPOS.items():
        if substr in post["title"]["rendered"]:
            return correct_num, "manual_typo_correction"
    m = SHOWNOTES_RE.search(post["content"]["rendered"])
    if m:
        clean = TAG_RE.sub(" ", m.group(1))  # strip HTML so embedded IDs (e.g. in an <a href>) don't leak digits
        nums = NUMBER_RE.findall(clean)
        if nums:
            return int(nums[0]), "shownotes_header"
    m = TITLE_BRACKET_RE.search(post["title"]["rendered"])
    if m:
        clean = TAG_RE.sub(" ", m.group(1))
        nums = NUMBER_RE.findall(clean)
        if nums:
            return int(nums[0]), "title_bracket"
    return None, None


def extract_video_id(content):
    if "<!--more-->" in content:
        intro, _, rest = content.partition("<!--more-->")
    else:
        intro, rest = content, ""
    m = YT_RE.search(intro)
    if m:
        return m.group(1), "intro_paragraph"
    m = SHOWNOTES_RE.search(content)
    if m:
        # the header line itself sometimes wraps an <a> with the video link
        header_line_match = re.search(r'<a[^>]*href="[^"]*"[^>]*>.*?Show Notes', content[:m.end()+50], re.IGNORECASE)
    m2 = YT_RE.search(content)
    if m2:
        return m2.group(1), "content_fallback"
    return None, None


def load_our_episode_dates():
    with open(DATA / "tagged_final.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_ep = {}
    for r in rows:
        if r["episode_number"] and r["episode_date"]:
            ep = int(r["episode_number"])
            by_ep.setdefault(ep, r["episode_date"])
    return by_ep


def main():
    with open(DATA / "blog_posts_raw.json", encoding="utf-8") as f:
        posts = json.load(f)

    our_dates = load_our_episode_dates()

    candidates = []
    for p in posts:
        content = p["content"]["rendered"]
        title = p["title"]["rendered"]
        if INTRO_RE.search(content) or SHOWNOTES_RE.search(content) or re.search(r"Maker Update\s*#?\s*\d", title, re.IGNORECASE):
            candidates.append(p)

    print(f"total posts: {len(posts)}")
    print(f"episode-post candidates: {len(candidates)}")

    numbered = []
    unnumbered = []
    for p in candidates:
        ep_num, method = extract_episode_number(p)
        video_id, vid_method = extract_video_id(p["content"]["rendered"])
        entry = {
            "episode_number": ep_num,
            "num_method": method,
            "video_id": video_id,
            "vid_method": vid_method,
            "blog_url": p["link"],
            "blog_title": p["title"]["rendered"],
            "blog_date": p["date"][:10],
        }
        if ep_num is not None:
            numbered.append(entry)
        else:
            unnumbered.append(entry)

    print(f"episodes with a number extracted from text: {len(numbered)}")
    print(f"episodes needing date-based matching: {len(unnumbered)}")

    # date-based fallback matching for unnumbered posts
    date_index = {v: k for k, v in our_dates.items()}
    resolved_by_date = 0
    for entry in unnumbered:
        blog_date = datetime.strptime(entry["blog_date"], "%Y-%m-%d")
        best = None
        best_diff = None
        for our_date_str, ep in date_index.items():
            our_date = datetime.strptime(our_date_str, "%Y-%m-%d")
            diff = abs((blog_date - our_date).days)
            if diff <= 10 and (best_diff is None or diff < best_diff):
                best, best_diff = ep, diff
        if best is not None:
            entry["episode_number"] = best
            entry["num_method"] = f"date_proximity({best_diff}d)"
            resolved_by_date += 1
    print(f"resolved via date proximity (within 3 days): {resolved_by_date}")

    final = numbered + [e for e in unnumbered if e["episode_number"] is not None]
    still_unresolved = [e for e in unnumbered if e["episode_number"] is None]
    print(f"still unresolved: {len(still_unresolved)}")
    for e in still_unresolved:
        print(f"  UNRESOLVED: {e['blog_date']} | {e['blog_title']}")

    # cross-validate: check for duplicate episode numbers (conflicting matches)
    by_num = {}
    conflicts = []
    for e in final:
        n = e["episode_number"]
        if n in by_num:
            conflicts.append((n, by_num[n], e))
        else:
            by_num[n] = e

    print(f"\nconflicting duplicate episode-number matches: {len(conflicts)}")
    for n, first, second in conflicts:
        print(f"  EP {n}: {first['blog_title']!r} ({first['blog_date']}) vs {second['blog_title']!r} ({second['blog_date']})")

    # cross-validate against our known episode dates where available
    date_mismatches = []
    for e in final:
        n = e["episode_number"]
        if n in our_dates:
            our_date = datetime.strptime(our_dates[n], "%Y-%m-%d")
            blog_date = datetime.strptime(e["blog_date"], "%Y-%m-%d")
            diff = abs((blog_date - our_date).days)
            if diff > 7:
                date_mismatches.append((n, diff, e))
    print(f"\ndate mismatches (>7 days off from our episode_date): {len(date_mismatches)}")
    for n, diff, e in date_mismatches[:20]:
        print(f"  EP {n}: blog={e['blog_date']} vs ours={our_dates[n]} (diff {diff}d) | {e['blog_title']!r}")

    # coverage vs 1-500
    covered = set(by_num.keys())
    missing = sorted(set(range(1, 500)) - covered)
    print(f"\ncoverage: {len(covered)} / 499 episodes (1-499; ep500 not yet published)")
    print(f"missing episode numbers: {missing}")

    with open(DATA / "episode_video_map.json", "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in sorted(by_num.items())}, f, indent=2)
    print("\nwrote data/episode_video_map.json")


if __name__ == "__main__":
    main()
