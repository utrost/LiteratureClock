#!/bin/bash
# Deploy Literature Clock to simiono.com/clock/
set -euo pipefail

FTP_HOST="www458.your-server.de"
FTP_USER="trosth_1"
FTP_PASS='d8$XW#Lo;]QM'
LOCAL_DIR="/home/wintermute/LiteratureClock"

lftp -u "$FTP_USER","$FTP_PASS" "$FTP_HOST" -e "
  put $LOCAL_DIR/data/quotes.json -o /clock/data/quotes.json;
  put $LOCAL_DIR/data/review-queue.json -o /clock/data/review-queue.json;
  put $LOCAL_DIR/index.html -o /clock/index.html;
  put $LOCAL_DIR/review.html -o /clock/review.html;
  quit
" 2>/dev/null

echo "Literature Clock deployed to simiono.com/clock/"
