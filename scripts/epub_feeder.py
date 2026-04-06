#!/usr/bin/env python3
"""
ePub Feeder — Sequential batch processing from Bob's Calibre DB.

Reads N books starting from last processed Calibre ID, fetches ePubs,
runs them through the pipeline. Remembers position.

Usage:
    python3 epub_feeder.py                # Process next 20 (default)
    python3 epub_feeder.py --batch 10     # Process next 10
    python3 epub_feeder.py --fiction      # Fiction only (tagged)
    python3 epub_feeder.py --english      # English only
    python3 epub_feeder.py --status       # Show progress
    python3 epub_feeder.py --reset        # Reset position to 0
"""

import subprocess
import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
LITCLOCK_DIR = SCRIPT_DIR.parent
STATE_FILE = LITCLOCK_DIR / "data" / "feeder-state.json"
BOB_HOST = "wintermute@bob"
CALIBRE_DB = "/media/uwe/eBooks/eBooks_calibre/metadata.db"
CALIBRE_BASE = "/media/uwe/eBooks/eBooks_calibre"
BATCH_DIR = Path("/tmp/litclock-batch")

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_id": 0, "total_processed": 0, "total_quotes": 0,
            "last_run": None, "runs": 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def ssh_query(sql):
    """Run SQLite query on Bob via SSH."""
    cmd = f'ssh {BOB_HOST} "sqlite3 \'{CALIBRE_DB}\' \\"{sql}\\""'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"❌ SSH/SQL Fehler: {result.stderr[:100]}")
        return []
    return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]

def get_next_batch(last_id, batch_size, fiction_only=False, english_only=False):
    """Get next N ePub Calibre IDs + paths from Bob."""
    where = [f"b.id > {last_id}", "d.format = 'EPUB'"]
    joins = ["JOIN data d ON b.id = d.book AND d.format = 'EPUB'"]
    
    if fiction_only:
        joins.append("JOIN books_tags_link btl ON b.id = btl.book")
        joins.append("JOIN tags t ON btl.tag = t.id")
        where.append("t.name IN ('Fiction','Novel','Roman','Literature & Fiction','Novels','Literary Fiction')")
    
    if english_only:
        joins.append("JOIN books_languages_link bll ON b.id = bll.book")
        joins.append("JOIN languages l ON bll.lang_code = l.id")
        where.append("l.lang_code IN ('eng','en')")
    
    join_str = ' '.join(joins)
    where_str = ' AND '.join(where)
    
    sql = f"""SELECT DISTINCT b.id, b.title, b.path, d.name 
              FROM books b {join_str}
              WHERE {where_str}
              ORDER BY b.id LIMIT {batch_size}"""
    
    rows = ssh_query(sql)
    books = []
    for row in rows:
        parts = row.split('|')
        if len(parts) >= 4:
            books.append({
                'id': int(parts[0]),
                'title': parts[1],
                'path': f"{CALIBRE_BASE}/{parts[2]}/{parts[3]}.epub"
            })
    return books

def process_batch(books, state):
    """Fetch and process a batch of ePubs."""
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    
    processed = 0
    total_quotes = 0
    
    for book in books:
        bid = book['id']
        title = book['title'][:50]
        remote_path = book['path']
        local_path = BATCH_DIR / f"{bid}.epub"
        
        print(f"  [{bid}] {title}")
        
        # Fetch
        scp_result = subprocess.run(
            f"scp '{BOB_HOST}:{remote_path}' '{local_path}'",
            shell=True, capture_output=True, timeout=60
        )
        if scp_result.returncode != 0:
            print(f"    ⚠️ SCP fehlgeschlagen, überspringe")
            continue
        
        # Process
        try:
            result = subprocess.run(
                f"bash {SCRIPT_DIR}/ingest-epub.sh '{local_path}'",
                shell=True, capture_output=True, text=True, timeout=120
            )
            output = result.stdout + result.stderr
            # Count quotes from output
            import re
            match = re.search(r'(\d+)\s+quotes?\s', output)
            quotes = int(match.group(1)) if match else 0
            total_quotes += quotes
            print(f"    ✅ {quotes} Zitate")
        except subprocess.TimeoutExpired:
            print(f"    ⚠️ Timeout (120s)")
        except Exception as e:
            print(f"    ❌ {e}")
        
        # Cleanup
        local_path.unlink(missing_ok=True)
        
        processed += 1
        state['last_id'] = bid
    
    state['total_processed'] += processed
    state['total_quotes'] += total_quotes
    state['last_run'] = datetime.now().isoformat()
    state['runs'] += 1
    save_state(state)
    
    return processed, total_quotes

def show_status(state):
    max_id_rows = ssh_query("SELECT MAX(id) FROM books")
    max_id = int(max_id_rows[0]) if max_id_rows else 0
    
    print(f"📊 ePub Feeder Status")
    print(f"   Position:    ID {state['last_id']} / {max_id}")
    print(f"   Fortschritt: {state['last_id']/max_id*100:.1f}%" if max_id else "   ?")
    print(f"   Verarbeitet: {state['total_processed']}")
    print(f"   Zitate:      {state['total_quotes']}")
    print(f"   Runs:        {state['runs']}")
    print(f"   Letzter Run: {state['last_run'] or 'nie'}")

def main():
    parser = argparse.ArgumentParser(description='ePub Feeder for LiteratureClock')
    parser.add_argument('--batch', type=int, default=20, help='Batch size (default: 20)')
    parser.add_argument('--fiction', action='store_true', help='Fiction only')
    parser.add_argument('--english', action='store_true', help='English only')
    parser.add_argument('--status', action='store_true', help='Show status')
    parser.add_argument('--reset', action='store_true', help='Reset position')
    args = parser.parse_args()
    
    state = load_state()
    
    if args.reset:
        state['last_id'] = 0
        save_state(state)
        print("✅ Position zurückgesetzt auf 0")
        return
    
    if args.status:
        show_status(state)
        return
    
    print(f"📚 ePub Feeder — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Ab ID: {state['last_id']}, Batch: {args.batch}")
    if args.fiction: print("   Filter: Fiction")
    if args.english: print("   Filter: English")
    print()
    
    books = get_next_batch(state['last_id'], args.batch, args.fiction, args.english)
    
    if not books:
        print("✅ Keine weiteren ePubs (Ende erreicht oder Filter zu eng)")
        return
    
    print(f"📋 {len(books)} ePubs gefunden (ID {books[0]['id']}–{books[-1]['id']})")
    processed, quotes = process_batch(books, state)
    
    print(f"\n📊 Ergebnis: {processed} verarbeitet, {quotes} Zitate")
    print(f"   Nächster Start ab ID: {state['last_id']}")

if __name__ == '__main__':
    main()
