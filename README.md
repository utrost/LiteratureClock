# Literature Clock

**Time, told through fiction.**

A minimal web clock that displays a literary quote matching the current time. Every minute, a new passage — drawn from novels, poetry, and stories — where the exact time appears in the text.

> *"It was half past twelve when James Bond turned the corner."*
> — Ian Fleming, *Casino Royale*

## Concept

A single screen. The time. A quote. The book. The author. Nothing else.

The clock cycles through curated literary excerpts where the current time is explicitly mentioned. At 07:30, you might read Hemingway. At 23:15, perhaps Murakami. Every minute of the day has its own literary moment.

## Design

```
┌─────────────────────────────────────────────┐
│                                             │
│                                             │
│   "It was five minutes past five in the     │
│    afternoon when the train pulled in."     │
│                                             │
│              — Graham Greene                │
│           The Orient Express                │
│                                             │
│                  17:05                       │
│                                             │
└─────────────────────────────────────────────┘
```

- **Typography-first.** The quote is the hero. Large, elegant serif font.
- **Dark mode default.** Warm off-white text on deep black. Easy on the eyes at 3 AM.
- **No UI chrome.** No buttons, no menus. Click/tap for next quote at same time.
- **Responsive.** From phone nightstand to wall-mounted display.

## Features (Planned)

- Multiple quotes per minute — random selection or cycle
- Smooth fade transitions between minutes
- Fullscreen mode (ideal for screensaver use)
- Language support (English primary, German secondary)
- PWA — installable, works offline
- Optional: ambient background color shift through the day (dawn warm → noon bright → night cool)

## Data Format

Quotes stored as JSON:

```json
{
  "time": "17:05",
  "quote": "It was five minutes past five in the afternoon when the train pulled in.",
  "author": "Graham Greene",
  "title": "The Orient Express",
  "language": "en"
}
```

## Roadmap

- [ ] Import existing quote collection → JSON
- [ ] Static site with time-based quote display
- [ ] Typography selection (serif candidates: Libre Baskerville, Cormorant, EB Garamond)
- [ ] Fade transitions
- [ ] Multiple quotes per time slot
- [ ] PWA manifest + service worker for offline
- [ ] Screensaver builds (macOS, Windows)
- [ ] Deploy to simiono.com

## Inspirations

The idea of a literary clock isn't new — but the execution matters. This version focuses on typographic craft, a curated personal collection, and the quiet pleasure of seeing time through the eyes of fiction.

## License

AGPL-3.0 — see [LICENSE](LICENSE).

## Author

[simiono](https://simiono.com) · Uwe Trostheide
