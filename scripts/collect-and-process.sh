#!/bin/bash
# collect-and-process.sh — Collect stray ePubs from /tmp, then run the processing pipeline.
# Designed as cron entry point to catch ePubs that were downloaded in chat sessions
# but never moved to inbox/.
set -euo pipefail

REPO="/home/wintermute/LiteratureClock"
INBOX="$REPO/inbox"
COLLECTED=0

# 1. Collect any ePubs from /tmp (Telegram downloads land here)
for epub in /tmp/pg*.epub /tmp/*.epub; do
    [ -f "$epub" ] || continue
    base=$(basename "$epub")
    # Skip if already in inbox or processed
    if [ -f "$INBOX/$base" ] || [ -f "$REPO/processed/$base" ]; then
        continue
    fi
    # Also skip if the fingerprint matches a processed file (different name, same content)
    hash=$(md5sum "$epub" | cut -d' ' -f1)
    if find "$REPO/processed/" -name "*.epub" -exec md5sum {} + 2>/dev/null | grep -q "$hash"; then
        continue
    fi
    cp "$epub" "$INBOX/$base"
    COLLECTED=$((COLLECTED + 1))
done

echo "Collected $COLLECTED new ePub(s) from /tmp"

# 2. Run the processing pipeline
cd "$REPO"
python3 scripts/process-inbox.py

# 3. Deploy if there were changes
if [ $COLLECTED -gt 0 ] || [ -s "$REPO/data/review-queue.json" ]; then
    bash scripts/deploy.sh
fi
