#!/usr/bin/env python3
"""
LiteratureClock ePub Tracking DB — tracks which ePubs have been processed.

Commands:
    init          Create/migrate database
    add PATH      Register an ePub (hash + metadata)
    status PATH   Check if already processed
    stats         Show processing statistics
    pending N     List N unprocessed ePubs from Bob catalog
    list          List all processed ePubs
"""

import sqlite3
import hashlib
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "tracking.db"
BOB_EPUB_BASE = "/media/uwe/eBooks/eBooks_calibre"
BOB_HOST = "wintermute@bob"

def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS epubs (
            id INTEGER PRIMARY KEY,
            file_hash TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT,
            author TEXT,
            title TEXT,
            language TEXT,
            file_size INTEGER,
            scanned_at TEXT,
            quotes_found INTEGER DEFAULT 0,
            quotes_high INTEGER DEFAULT 0,
            quotes_medium INTEGER DEFAULT 0,
            quotes_low INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',  -- pending, processing, done, error, skipped
            error_msg TEXT,
            source TEXT DEFAULT 'bob'
        );
        CREATE INDEX IF NOT EXISTS idx_status ON epubs(status);
        CREATE INDEX IF NOT EXISTS idx_hash ON epubs(file_hash);
        CREATE INDEX IF NOT EXISTS idx_author ON epubs(author);

        CREATE TABLE IF NOT EXISTS scan_runs (
            id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            epubs_processed INTEGER DEFAULT 0,
            quotes_found INTEGER DEFAULT 0,
            quotes_high INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'  -- running, done, error
        );
    """)
    db.commit()
    print(f"✅ DB initialisiert: {DB_PATH}")
    return db

def file_hash(filepath):
    """SHA256 of first 64KB + file size (fast, collision-safe enough)."""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            h.update(f.read(65536))
        size = os.path.getsize(filepath)
        h.update(str(size).encode())
        return h.hexdigest()[:16]
    except Exception:
        return None

def extract_metadata_from_path(filepath):
    """Extract author/title from Calibre path structure: Author/Title (ID)/file.epub"""
    parts = Path(filepath).parts
    author, title = None, None
    # Calibre: .../Author Name/Book Title (123)/book.epub
    if len(parts) >= 3:
        author = parts[-3] if parts[-3] != "eBooks_calibre" else None
        title_part = parts[-2]
        # Remove Calibre ID suffix like " (1234)"
        import re
        title = re.sub(r'\s*\(\d+\)$', '', title_part)
    return author, title

def add_epub(filepath, status='done', quotes=0, high=0, medium=0, low=0):
    db = get_db()
    fhash = file_hash(filepath)
    if not fhash:
        print(f"⚠️ Kann {filepath} nicht hashen")
        return
    author, title = extract_metadata_from_path(filepath)
    try:
        db.execute("""
            INSERT OR REPLACE INTO epubs 
            (file_hash, filename, filepath, author, title, scanned_at, 
             quotes_found, quotes_high, quotes_medium, quotes_low, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fhash, Path(filepath).name, str(filepath), author, title,
              datetime.now().isoformat(), quotes, high, medium, low, status))
        db.commit()
        print(f"✅ {Path(filepath).name} → {status} ({quotes} Zitate)")
    except Exception as e:
        print(f"❌ {e}")

def check_status(filepath):
    db = get_db()
    fhash = file_hash(filepath)
    if not fhash:
        print("unknown")
        return
    row = db.execute("SELECT * FROM epubs WHERE file_hash = ?", (fhash,)).fetchone()
    if row:
        print(f"{row['status']} (gescannt: {row['scanned_at']}, Zitate: {row['quotes_found']})")
    else:
        print("pending (nicht in DB)")

def show_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM epubs").fetchone()[0]
    done = db.execute("SELECT COUNT(*) FROM epubs WHERE status='done'").fetchone()[0]
    errors = db.execute("SELECT COUNT(*) FROM epubs WHERE status='error'").fetchone()[0]
    quotes = db.execute("SELECT COALESCE(SUM(quotes_found),0) FROM epubs").fetchone()[0]
    high = db.execute("SELECT COALESCE(SUM(quotes_high),0) FROM epubs").fetchone()[0]
    medium = db.execute("SELECT COALESCE(SUM(quotes_medium),0) FROM epubs").fetchone()[0]
    
    print(f"📊 Tracking DB Stats")
    print(f"   Registriert: {total}")
    print(f"   Verarbeitet: {done}")
    print(f"   Fehler:      {errors}")
    print(f"   Zitate:      {quotes} (HIGH: {high}, MEDIUM: {medium})")
    print(f"   Bob-Katalog: ~55.744 ePubs")
    print(f"   Fortschritt: {done/557.44:.1f}%" if done else "   Fortschritt: 0%")

def list_pending_from_bob(n=20):
    """Get N random unprocessed ePubs from Bob via SSH."""
    db = get_db()
    # Get all known hashes
    known = set(r[0] for r in db.execute("SELECT filepath FROM epubs").fetchall())
    
    # Get random ePubs from Bob
    cmd = f'ssh {BOB_HOST} "find {BOB_EPUB_BASE} -name \'*.epub\' | shuf | head -{n*3}"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        candidates = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
    except Exception as e:
        print(f"❌ SSH-Fehler: {e}")
        return []
    
    # Filter already processed
    pending = [c for c in candidates if c not in known][:n]
    for p in pending:
        author, title = extract_metadata_from_path(p)
        label = f"{author} — {title}" if author and title else Path(p).stem
        print(f"  📖 {label}")
    
    print(f"\n{len(pending)} ePubs verfügbar")
    return pending

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == 'init':
        init_db()
    elif cmd == 'add' and len(sys.argv) >= 3:
        add_epub(sys.argv[2])
    elif cmd == 'status' and len(sys.argv) >= 3:
        check_status(sys.argv[2])
    elif cmd == 'stats':
        show_stats()
    elif cmd == 'pending':
        n = int(sys.argv[2]) if len(sys.argv) >= 3 else 20
        list_pending_from_bob(n)
    elif cmd == 'list':
        db = get_db()
        for r in db.execute("SELECT author, title, status, quotes_found FROM epubs ORDER BY scanned_at DESC LIMIT 20"):
            print(f"  {r['author']} — {r['title']}: {r['status']} ({r['quotes_found']} Zitate)")
    else:
        print(__doc__)
