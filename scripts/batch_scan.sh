#!/usr/bin/env bash
# LiteratureClock Batch ePub Scanner
# Fetches N ePubs from Bob, runs them through the pipeline.
# Usage: bash batch_scan.sh [N] [--fiction-only]
#
# Requires: ingest-epub.sh, tracking_db.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LITCLOCK_DIR="$(dirname "$SCRIPT_DIR")"
BOB_HOST="wintermute@bob"
BOB_EPUB_BASE="/media/uwe/eBooks/eBooks_calibre"
BATCH_DIR="/tmp/litclock-batch"
BATCH_SIZE="${1:-10}"
FICTION_ONLY="${2:-}"

echo "📚 LiteratureClock Batch Scan — $(date '+%Y-%m-%d %H:%M')"
echo "   Batch: $BATCH_SIZE ePubs"
echo ""

# Ensure batch dir
mkdir -p "$BATCH_DIR"

# Get list of already-processed filepaths from tracking DB
KNOWN_FILE=$(mktemp)
python3 "$SCRIPT_DIR/tracking_db.py" list 2>/dev/null | grep -oP '(?<=— ).*(?=:)' > "$KNOWN_FILE" || true

# Get random ePubs from Bob (3x batch for filtering headroom)
FETCH_COUNT=$((BATCH_SIZE * 3))
CANDIDATES=$(ssh "$BOB_HOST" "find $BOB_EPUB_BASE -name '*.epub' | shuf | head -$FETCH_COUNT" 2>/dev/null)

if [ -z "$CANDIDATES" ]; then
    echo "❌ Keine ePubs auf Bob gefunden (SSH-Problem?)"
    rm -f "$KNOWN_FILE"
    exit 1
fi

# Filter: skip already processed, optionally fiction-only
SELECTED=()
while IFS= read -r epub_path; do
    [ ${#SELECTED[@]} -ge "$BATCH_SIZE" ] && break
    
    filename=$(basename "$epub_path")
    
    # Skip if in tracking DB (check by filepath)
    if python3 -c "
import sqlite3
db = sqlite3.connect('$LITCLOCK_DIR/data/tracking.db')
r = db.execute('SELECT 1 FROM epubs WHERE filepath=?', ('$epub_path',)).fetchone()
exit(0 if r else 1)
" 2>/dev/null; then
        continue
    fi
    
    SELECTED+=("$epub_path")
done <<< "$CANDIDATES"

echo "📋 ${#SELECTED[@]} ePubs ausgewählt"
echo ""

# Process each ePub
PROCESSED=0
TOTAL_QUOTES=0
ERRORS=0

for epub_path in "${SELECTED[@]}"; do
    filename=$(basename "$epub_path")
    local_path="$BATCH_DIR/$filename"
    
    echo "→ $filename"
    
    # Fetch from Bob
    if ! scp "$BOB_HOST:$epub_path" "$local_path" 2>/dev/null; then
        echo "  ⚠️ SCP fehlgeschlagen, überspringe"
        ERRORS=$((ERRORS + 1))
        continue
    fi
    
    # Run through pipeline
    RESULT=$(bash "$SCRIPT_DIR/ingest-epub.sh" "$local_path" 2>&1) || true
    
    # Parse result for quote counts
    QUOTES=$(echo "$RESULT" | grep -oP '\d+ (?=quotes?)' | head -1 || echo "0")
    HIGH=$(echo "$RESULT" | grep -oP '\d+ (?=HIGH)' | head -1 || echo "0")
    MEDIUM=$(echo "$RESULT" | grep -oP '\d+ (?=MEDIUM)' | head -1 || echo "0")
    
    # Register in tracking DB
    python3 -c "
import sqlite3, hashlib, os, re
from datetime import datetime
from pathlib import Path

db = sqlite3.connect('$LITCLOCK_DIR/data/tracking.db')

# Hash
h = hashlib.sha256()
with open('$local_path', 'rb') as f:
    h.update(f.read(65536))
size = os.path.getsize('$local_path')
h.update(str(size).encode())
fhash = h.hexdigest()[:16]

# Metadata from path
parts = Path('$epub_path').parts
author = parts[-3] if len(parts) >= 3 and parts[-3] != 'eBooks_calibre' else None
title = re.sub(r'\s*\(\d+\)$', '', parts[-2]) if len(parts) >= 2 else None

db.execute('''INSERT OR REPLACE INTO epubs 
    (file_hash, filename, filepath, author, title, scanned_at, 
     quotes_found, quotes_high, quotes_medium, status, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'done', 'bob')''',
    (fhash, '$filename', '$epub_path', author, title,
     datetime.now().isoformat(), int('${QUOTES:-0}'), int('${HIGH:-0}'), int('${MEDIUM:-0}')))
db.commit()
" 2>/dev/null
    
    PROCESSED=$((PROCESSED + 1))
    TOTAL_QUOTES=$((TOTAL_QUOTES + ${QUOTES:-0}))
    
    # Cleanup
    rm -f "$local_path"
    
    echo "  ✅ ${QUOTES:-0} Zitate"
done

echo ""
echo "📊 Ergebnis: $PROCESSED verarbeitet, $TOTAL_QUOTES Zitate, $ERRORS Fehler"

rm -f "$KNOWN_FILE"
