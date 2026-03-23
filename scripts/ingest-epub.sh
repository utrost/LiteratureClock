#!/bin/bash
# ingest-epub.sh — Sofortige Verarbeitung eines ePub-Uploads.
# Usage: ingest-epub.sh /path/to/book.epub
#
# Pipeline:
#   1. Copy ePub → inbox/
#   2. process-inbox.py (HIGH→auto-merge, MEDIUM→review, LOW→discard)
#   3. Deploy to simiono.com/clock/
#
# Designed to be called immediately when a user uploads an ePub via Telegram.
set -euo pipefail

REPO="/home/wintermute/LiteratureClock"
INBOX="$REPO/inbox"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <epub-file>" >&2
    exit 1
fi

EPUB="$1"
if [ ! -f "$EPUB" ]; then
    echo "ERROR: File not found: $EPUB" >&2
    exit 1
fi

BASE=$(basename "$EPUB")
mkdir -p "$INBOX" "$REPO/processed"

# Skip if already processed (by content hash)
HASH=$(md5sum "$EPUB" | cut -d' ' -f1)
if find "$REPO/processed/" -name "*.epub" -exec md5sum {} + 2>/dev/null | grep -q "$HASH"; then
    echo "SKIP: Already processed (duplicate content)"
    exit 0
fi

# Copy to inbox
cp "$EPUB" "$INBOX/$BASE"
echo "Copied to inbox: $BASE"

# Process
cd "$REPO"
python3 scripts/process-inbox.py --all 2>&1

# Deploy
bash scripts/deploy.sh 2>&1

# Report final count
TOTAL=$(python3 -c "import json; print(len(json.load(open('data/quotes.json'))))")
REVIEW=$(python3 -c "import json; print(len(json.load(open('data/review-queue.json'))))")
echo "RESULT: $TOTAL quotes total, $REVIEW pending review"
