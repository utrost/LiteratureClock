# LiteratureClock — Scripts Reference

## Aktive Scripts

### Pipeline (Kern)
| Script | Zweck | Aufruf |
|---|---|---|
| `ingest-epub.sh` | Einzelnes ePub verarbeiten (Upload-Trigger) | `ingest-epub.sh <path.epub>` |
| `extract-quotes.py` | Regex-basierte Zitat-Extraktion aus ePub-Text | Intern von process-inbox.py |
| `process-inbox.py` | Confidence-Routing: HIGH+MEDIUM → merge, LOW → drop | Intern von ingest-epub.sh |
| `deploy.sh` | Deploy quotes.json + Review-UI → simiono.com/clock/ | Intern von ingest-epub.sh |

### Batch-Processing (Bob)
| Script | Zweck | Aufruf |
|---|---|---|
| `epub_feeder.py` | Batch-ePubs von Bob holen + verarbeiten (Calibre-DB) | `epub_feeder.py --batch 20 --english` |
| `tracking_db.py` | Tracking welche ePubs verarbeitet wurden (SQLite) | `tracking_db.py stats/init/pending` |

### Review & Merge
| Script | Zweck | Aufruf |
|---|---|---|
| `merge-decisions.py` | Review-Entscheidungen aus JSON in quotes.json mergen | `merge-decisions.py <decisions.json>` |

Workflow: Uwe exportiert Entscheidungen aus Review-UI (simiono.com/clock/review.html) → JSON → `merge-decisions.py` wendet sie an.

### Hilfsjobs
| Script | Zweck | Aufruf |
|---|---|---|
| `collect-and-process.sh` | Streunende ePubs aus /tmp einsammeln (Cron-Fallback) | Cron 03:00 (OpenClaw litclock-epub) |

## Obsolete Scripts (durch epub_feeder.py ersetzt)
| Script | Ersetzt durch | Grund |
|---|---|---|
| `batch_scan.sh` | `epub_feeder.py` | Random statt sequentiell, kein Calibre-DB-Zugriff, keine Tracking-DB |

## Cron-Jobs
| Schedule | Script | System |
|---|---|---|
| 03:00 täglich | `epub_feeder.py --batch 20 --english` | System-Crontab |
| 03:00 täglich | `collect-and-process.sh` (via OpenClaw litclock-epub) | OpenClaw Cron |
