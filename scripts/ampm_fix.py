#!/usr/bin/env python3
"""
AM/PM Fix — Korrigiert falsch zugeordnete Zeiten und entfernt Müll-Zitate.

1. Findet Zitate wo die zugewiesene Zeit nicht zum AM/PM-Kontext im Text passt
2. Fixe eindeutige Fälle automatisch
3. Entfernt Zitate aus Nicht-Literatur-Quellen (Lehrbücher mit Uhrzeitbeispielen)
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

QUOTES_FILE = Path(__file__).parent.parent / "data" / "quotes.json"

# Books that are not literature — time references are teaching examples
TRASH_BOOKS = {
    "German For Dummies",
    "Excel 2013 fur Dummies (Für Dummies) (German Edition)",
    "Microsoft Dynamics® CRM 2011 Step by Step",
}


def find_ampm_conflicts(quotes):
    """Find quotes where assigned time conflicts with AM/PM in text."""
    fixes = []
    
    for i, quote in enumerate(quotes):
        t = quote.get('time', '')
        text = quote.get('quote', '')
        if ':' not in t or len(t) != 5:
            continue
        try:
            h = int(t.split(':')[0])
            m = int(t.split(':')[1])
        except (ValueError, IndexError):
            continue

        # Find explicit time+AM/PM patterns in text
        matches = re.findall(
            r'(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?|AM|PM)',
            text, re.IGNORECASE
        )
        
        for mh, mm, meridiem in matches:
            mh_i, mm_i = int(mh), int(mm)
            is_pm = meridiem.lower().startswith('p')

            expected_h = mh_i
            if is_pm and mh_i != 12:
                expected_h = mh_i + 12
            elif not is_pm and mh_i == 12:
                expected_h = 0

            if expected_h != h and mm_i == m and 0 <= expected_h < 24:
                fixes.append({
                    "idx": i,
                    "current": t,
                    "correct": f"{expected_h:02d}:{mm_i:02d}",
                    "match": f"{mh}:{mm} {meridiem}",
                    "title": quote.get("title", ""),
                })
                break

    return fixes


def find_trash_quotes(quotes):
    """Find quotes from non-literature sources."""
    trash = []
    for i, quote in enumerate(quotes):
        title = quote.get('title', '')
        if title in TRASH_BOOKS:
            trash.append(i)
    return trash


def main():
    dry_run = "--dry-run" in sys.argv
    
    with open(QUOTES_FILE) as f:
        quotes = json.load(f)

    print(f"Gesamte Zitate: {len(quotes)}\n")

    # Step 1: Find and remove trash
    trash_indices = set(find_trash_quotes(quotes))
    print(f"🗑️  Müll-Zitate (Lehrbücher): {len(trash_indices)}")
    for i in sorted(trash_indices)[:5]:
        print(f"   [{i}] {quotes[i].get('time','')} | {quotes[i].get('title','')}")
    if len(trash_indices) > 5:
        print(f"   ... und {len(trash_indices)-5} weitere")

    # Step 2: Find AM/PM conflicts (excluding trash)
    fixes = [f for f in find_ampm_conflicts(quotes) if f["idx"] not in trash_indices]
    print(f"\n🔧 AM/PM-Korrekturen: {len(fixes)}")
    for f in fixes[:5]:
        print(f"   {f['current']} → {f['correct']} | {f['match']} | {f['title']}")
    if len(fixes) > 5:
        print(f"   ... und {len(fixes)-5} weitere")

    if dry_run:
        print(f"\n⚠️  Dry Run — keine Änderungen geschrieben.")
        return

    # Apply fixes
    fixed_count = 0
    for f in fixes:
        quotes[f["idx"]]["time"] = f["correct"]
        fixed_count += 1

    # Remove trash (reverse order to preserve indices)
    removed_count = 0
    for i in sorted(trash_indices, reverse=True):
        quotes.pop(i)
        removed_count += 1

    # Save
    backup = QUOTES_FILE.with_suffix('.json.bak')
    with open(backup, 'w') as f:
        json.dump(json.load(open(QUOTES_FILE)), f)
    
    with open(QUOTES_FILE, 'w') as f:
        json.dump(quotes, f, indent=2, ensure_ascii=False)

    # Stats
    times = set(
        q['time'] for q in quotes
        if len(q.get('time', '')) == 5 and ':' in q['time']
        and int(q['time'].split(':')[0]) < 24
    )

    print(f"\n✅ Ergebnis:")
    print(f"   Zitate entfernt: {removed_count}")
    print(f"   Zeiten korrigiert: {fixed_count}")
    print(f"   Zitate gesamt: {len(quotes)}")
    print(f"   Unique Zeiten: {len(times)}/1440 ({len(times)/1440*100:.1f}%)")


if __name__ == "__main__":
    main()
