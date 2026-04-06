# ePub-Mining Pipeline

## Konzept
Die LiteratureClock zeigt zu jeder Minute ein passendes literarisches Zitat. Aktuell 2.454 Zitate, 452/1.440 Minuten abgedeckt (31%). Ziel: >90% Abdeckung.

Uwes Calibre-Bibliothek auf Bob enthält **55.686 ePubs** — ein riesiger, unerschlossener Korpus. Die Pipeline verarbeitet diese automatisiert in Nightly-Batches.

## Architektur

```
Bob (Calibre SQLite)          Wintermute (Pipeline)
┌──────────────────┐          ┌─────────────────────────┐
│ metadata.db      │◄─SSH────►│ epub_feeder.py          │
│ 55.686 ePubs     │   Query  │   ├─ Calibre-DB Query   │
│ /media/uwe/      │          │   ├─ SCP ePub holen     │
│  eBooks/         │◄─SCP─────│   ├─ ingest-epub.sh     │
│  eBooks_calibre/ │          │   │   ├─ extract-quotes  │
└──────────────────┘          │   │   ├─ process-inbox   │
                              │   │   └─ deploy          │
                              │   └─ tracking_db.py      │
                              └─────────────────────────┘
```

## Schlüsselentscheidungen

### Sequentiell nach Calibre-ID statt Random/Index
- **Problem:** 55k OPF-Dateien indizieren dauert >5 Min via SSH
- **Lösung:** Sequentiell nach `books.id` aus Calibre SQLite, Position merken
- **Vorteil:** Deterministisch, kein Overhead, keine Duplikate, jederzeit resumable

### Calibre SQLite statt eigener Metadaten-Index
- Calibre hat bereits: Titel, Autor, Sprache, Tags (Fiction/Non-Fiction), ISBN
- Direkt-Query via `ssh bob "sqlite3 metadata.db '...'"` — kein Index-Build nötig
- Filter `--fiction` und `--english` nutzen Calibre-Tags (`dc:subject`)

### Confidence: MEDIUM → Auto-Merge
- **Analyse (2026-04-03):** 906 MEDIUM-Zitate, davon 904 korrekt (99,8%)
- Fehlerquote MEDIUM: 0,2% — de facto gleiche Qualität wie HIGH
- MEDIUM basiert auf Regex-Pattern "digital_context", "oclock", "half_past" etc.
- LOW bleibt verworfen (zu viele "by one arm"-False-Positives)
- Bereinigung: 65 Altlasten ohne Zeitreferenz entfernt (Backup: `removed-no-timeref.json`)

### Nightly Batch statt Bulk
- 20 ePubs/Nacht (System-Cron 03:00, kein LLM nötig)
- Gemini API-Kosten: ~0 (extract-quotes.py nutzt Regex, kein LLM)
- Hochrechnung: ~73.000 Zitate/Jahr, volle Bibliothek in ~7,5 Jahren
- Könnte auf 100/Nacht erhöht werden ohne Performance-Impact

## Dateien
| Datei | Zweck |
|---|---|
| `scripts/epub_feeder.py` | Hauptscript: Batch von Bob holen + verarbeiten |
| `scripts/tracking_db.py` | SQLite-Tracking (welche ePubs verarbeitet) |
| `scripts/ingest-epub.sh` | Einzelnes ePub durch Pipeline |
| `scripts/extract-quotes.py` | Regex-basierte Zitat-Extraktion |
| `scripts/process-inbox.py` | Confidence-Routing (HIGH+MEDIUM → merge, LOW → drop) |
| `data/tracking.db` | Tracking-DB (72 legacy + laufende Einträge) |
| `data/feeder-state.json` | Position (letzte Calibre-ID) |
| `data/quotes.json` | Zitat-Bestand |

## Monitoring
- Log: `/tmp/openclaw/epub-feeder.log`
- Status: `python3 scripts/epub_feeder.py --status`
- Cron: System-Crontab `0 3 * * *`
