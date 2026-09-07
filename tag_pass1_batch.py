"""
Maker Update tagging pass -- Pass 1 (cheap, title-only, batched).

Reads data/to_tag.csv and submits one Message Batches API request per item,
asking for search tags, a one-line synopsis, and a confidence flag. Designed
to run unattended.

Before running: `pip install anthropic`, set ANTHROPIC_API_KEY.

Verified against current Anthropic docs (2026-09-05):
- client.messages.batches.create/retrieve/results is the correct current
  shape (no beta header needed).
- custom_id must match ^[a-zA-Z0-9_-]{1,64}$ -- the original design
  (f"{source_file}::{tab}::{row_index}") contains "::", ".", and spaces and
  would have been rejected. Fixed by using a plain row index and keeping the
  source_file/tab/row_index identity in row_by_id instead.
- Swapped the model to claude-haiku-4-5 (current cheapest batch-eligible
  model) -- claude-sonnet-4-5 is a retired model ID. This is a simple
  classification-style task (title/creator/section only, no source
  fetching), which is exactly what Haiku 4.5 is for; pass 2 (source-fetch
  for low-confidence items) can use a stronger model if needed.
"""
import csv
import json
import time
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

MODEL = "claude-haiku-4-5"
ROOT = Path(__file__).parent
INPUT_CSV = ROOT / "data" / "to_tag.csv"
OUTPUT_CSV = ROOT / "data" / "tagged_pass1.csv"

TAXONOMY_GUIDANCE = """
You are tagging items from a 9-year-old maker/DIY show's archive for a
searchable database. Given a title, creator, category, and section, produce:

1. tags: 3-8 short lowercase hyphenated tags drawn from these facets as
   relevant (skip facets that don't apply):
   - material: e.g. wood, cardboard, acrylic, metal, fabric, pla
   - technique: e.g. 3d-printing, laser-cutting, cnc, woodworking, sewing,
     soldering, papercraft, electroplating
   - tool/platform: e.g. arduino, raspberry-pi, esp32, cricut
   - domain: e.g. robotics, cosplay, home-automation, retro-tech, wearables,
     music, ai, space, woodworking, kinetic-art
   Prefer tags likely to recur across many items (for a "browse by tag"
   feature) over hyper-specific one-off descriptors.
2. synopsis: one plain sentence (<20 words) on what the item is and why
   it's notable -- written for a search-result list, not a summary of the
   show segment.
3. confidence: "high" if the title/creator gave enough to tag confidently,
   "low" if you're guessing and the linked source page should be checked.

Respond with ONLY a JSON object: {"tags": [...], "synopsis": "...", "confidence": "high"|"low"}
No markdown fences, no other text.
"""


def build_batch_requests(rows):
    requests = []
    for i, r in enumerate(rows):
        user_content = (
            f"Title: {r['title_guess']}\n"
            f"Creator: {r['creator_guess'] or '(not given)'}\n"
            f"Category: {r['category']}\n"
            f"Section: {r['section']}\n"
            f"Show: {'Adafruit Edition' if r['edition']=='adafruit' else 'Maker Update'}"
        )
        requests.append(
            Request(
                custom_id=f"row-{i}",
                params=MessageCreateParamsNonStreaming(
                    model=MODEL,
                    max_tokens=300,
                    system=TAXONOMY_GUIDANCE,
                    messages=[{"role": "user", "content": user_content}],
                ),
            )
        )
    return requests


def main():
    client = anthropic.Anthropic()

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # custom_id ("row-{i}") -> row, for merging results back afterward
    row_by_id = {f"row-{i}": r for i, r in enumerate(rows)}

    all_requests = build_batch_requests(rows)

    # Batches cap at 100k requests / 256MB; ~7,400 items fits in one batch,
    # but chunk defensively in case the corpus grows (e.g. next season).
    CHUNK = 20000
    batch_ids = []
    for i in range(0, len(all_requests), CHUNK):
        chunk = all_requests[i:i + CHUNK]
        batch = client.messages.batches.create(requests=chunk)
        batch_ids.append(batch.id)
        print(f"Submitted batch {batch.id} with {len(chunk)} requests")

    # poll until all batches finish (can take up to 24h per Anthropic's docs;
    # in practice usually much faster for a job this size)
    results_by_id = {}
    for batch_id in batch_ids:
        while True:
            batch = client.messages.batches.retrieve(batch_id)
            print(f"{batch_id}: {batch.processing_status}")
            if batch.processing_status == "ended":
                break
            time.sleep(60)

        for result in client.messages.batches.results(batch_id):
            if result.result.type == "succeeded":
                text = next(
                    (b.text for b in result.result.message.content if b.type == "text"),
                    "",
                )
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = {"tags": [], "synopsis": "", "confidence": "low", "parse_error": text[:200]}
                results_by_id[result.custom_id] = parsed
            else:
                results_by_id[result.custom_id] = {"tags": [], "synopsis": "", "confidence": "low", "error": str(result.result)}

    # merge back into the original rows
    for cid, row in row_by_id.items():
        r = results_by_id.get(cid, {})
        row["tags"] = "; ".join(r.get("tags", []))
        row["synopsis"] = r.get("synopsis", "")
        row["confidence"] = r.get("confidence", "low")

    fieldnames = list(rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    low_conf = sum(1 for r in rows if r.get("confidence") == "low")
    print(f"Done. {len(rows)} items tagged, {low_conf} flagged low-confidence for pass 2.")


if __name__ == "__main__":
    main()
