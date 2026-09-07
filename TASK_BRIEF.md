# Maker Update Archive — Tagging & Enrichment Handoff

## Context
9 years of a weekly maker/DIY show ("Maker Update," episodes 1–500, plus an
Adafruit-branded edition for some early episodes) have been consolidated from
messy per-season spreadsheets into `to_tag.csv` — 7,376 items, one row per
project/tip/news mention/spotlight segment. Goal: tag every item so people can
search by theme ("laser cut," "3d printing," "woodworking") and get a list of
matching *items* across all 9 years, not a list of episodes.

The consolidation, category classification, and data-quality cleanup are
already done. What's left is the AI enrichment: tags, synopses, and a
related-terms structure for the search UI.

## Files in this handoff
- `to_tag.csv` — the corpus to enrich. Key columns: `title_guess`,
  `creator_guess`, `category` (already classified — see below),
  `section`, `episode_number`, `episode_date`, `edition` (main/adafruit/
  digikey_only), `primary_url`, `secondary_urls`, `timestamp_seconds`
  (seconds into the YouTube episode where this item appears), `no_url_flag`,
  `confidence` fields from any earlier pass.
- `categorized_all9.csv` — full dataset including the 104 `plug` (outro/
  credits) items that were deliberately excluded from `to_tag.csv` — not
  real content, don't tag these.
- `tag_pass1_batch.py` — reference implementation for the first tagging
  pass using the Message Batches API (title/creator/section only, no
  source-fetching). Verify the `client.messages.batches.*` calls against
  current docs before running — the API moves fast and this was written
  from documentation, not tested against a live key.

## What's already decided (don't redo this)
- **Category mapping** (section → category) is deterministic and already
  applied: `project`, `tip`, `sponsor_spotlight`, `creator_spotlight`,
  `news`, `plug`, `uncategorized`. The 275 `uncategorized` rows have no
  section header captured — worth a quick look to see if they're real
  content that needs a category guess, or noise.
- **Host** field is intentionally blank for most of the archive — this was
  a deliberate decision with Donald, not a gap to fill in.
- **1,250 items are flagged `no_url_flag`** — many are one-off text (event
  mentions, social plugs) with no real link. Use judgment: some may still
  be worth a synopsis/tags, others should probably be excluded from the
  final searchable set entirely.

## What's left to build

### 1. Tagging (pass 1 — batch, cheap)
Run `tag_pass1_batch.py` or your own version of it. Output: every item
gets `tags` (a handful of short lowercase hyphenated keywords spanning
material/technique/tool/domain — see the prompt in the script for the
full taxonomy guidance), a one-sentence `synopsis`, and a `confidence`
flag.

### 2. Tagging (pass 2 — source-fetch for low-confidence items)
Titles alone aren't always enough (e.g. "Heat Set Insert Rig" needs
domain knowledge to know it's 3D-printing-adjacent; "Polygonia Design"
needs the actual link). For rows where pass 1 returns `confidence: low`,
fetch `primary_url` and re-tag with the page content as extra context.
This should be a much smaller subset than the full corpus.

### 3. Related-terms graph
Once tags exist, compute tag co-occurrence across items (pure Python, no
AI needed): for each tag, which other tags most frequently appear
alongside it. This powers the "searched 'cardboard,' here are related
terms to try" feature. Store as a simple `tag -> [related tags]` lookup.

### 4. Final searchable dataset
Merge everything into one clean file (JSON or a proper DB) with per-item:
title, creator, category, tags, synopsis, episode number/date, edition,
link to the item's source, and a deep link to the moment in the YouTube
episode (`https://youtube.com/watch?v=VIDEO_ID&t=<timestamp_seconds>s` —
note: `to_tag.csv` doesn't yet have YouTube video IDs per episode, only
timestamps; matching episode_number/date to the actual video ID from the
playlist is a separate step).

## Not in scope for this pass
Building the actual search UI/site — that's a follow-on step once the
enriched dataset exists. Donald's plan (from earlier planning) leans
toward reusing his existing Airtable + static-site-generator + GitHub
Pages pattern from a previous project (Augmented Artifacts), but that
decision can be revisited once the enrichment shape is known.
