#!/usr/bin/env python3
"""Merge review decisions into quotes.json.

Usage:
    python3 scripts/merge-decisions.py <decisions.json>
    python3 scripts/merge-decisions.py data/review-decisions.json --dry-run

The decisions file is exported from simiono.com/clock/review.html via
the "Export Decisions" button. Each entry has:
  - action: "accept" or "remove"
  - time: corrected HH:MM (only for accept)
  - original_time: time as it was in review-queue
  - quote_start: first 80 chars of the quote
  - author, title
"""

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QUOTES_FILE = DATA_DIR / "quotes.json"
REVIEW_FILE = DATA_DIR / "review-queue.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def match_key(entry):
    """Create a matching key from quote_start + author."""
    start = entry.get("quote_start") or entry.get("quote", "")[:80]
    return (start, entry.get("author", ""))


def main():
    parser = argparse.ArgumentParser(description="Merge review decisions into quotes.json")
    parser.add_argument("decisions", help="Path to exported review-decisions.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    decisions = load_json(args.decisions)
    quotes = load_json(QUOTES_FILE)
    review = load_json(REVIEW_FILE)

    accepted = [d for d in decisions if d["action"] == "accept"]
    removed = [d for d in decisions if d["action"] == "remove"]

    print(f"Decisions: {len(accepted)} accept, {len(removed)} remove")
    print(f"Current quotes.json: {len(quotes)}")
    print(f"Current review-queue: {len(review)}")
    print()

    # Index decisions by key
    decision_map = {}
    for d in decisions:
        key = match_key(d)
        decision_map[key] = d

    # Process review queue
    new_review = []
    added = 0
    removed_count = 0

    for rq in review:
        key = (rq["quote"][:80], rq.get("author", ""))
        d = decision_map.get(key)

        if d is None:
            new_review.append(rq)
        elif d["action"] == "accept":
            rq["time"] = d["time"]
            quotes.append(rq)
            added += 1
            if args.dry_run:
                print(f"  + {d['time']} ({d.get('original_time','?')}) {rq['author']}: {rq['quote'][:60]}...")
        else:
            removed_count += 1
            if args.dry_run:
                print(f"  - REMOVE {rq['author']}: {rq['quote'][:60]}...")

    # Also check for time corrections on existing quotes
    corrected = 0
    existing_keys = {(q["quote"][:80], q.get("author", "")) for q in quotes}
    for d in accepted:
        key = match_key(d)
        if key in existing_keys:
            continue  # already in quotes (possibly just added above)
        # Decision refers to a quote not in review-queue or quotes — skip
        # (would need full quote text to add)

    # Sort by time
    quotes.sort(key=lambda q: q["time"])

    print(f"Added: {added}")
    print(f"Removed: {removed_count}")
    print(f"Remaining in review: {len(new_review)}")
    print(f"New quotes.json total: {len(quotes)}")

    if args.dry_run:
        print("\n--dry-run: no files written.")
    else:
        save_json(QUOTES_FILE, quotes)
        save_json(REVIEW_FILE, new_review)
        print("\n✅ quotes.json and review-queue.json updated.")


if __name__ == "__main__":
    main()
