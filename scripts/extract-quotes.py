#!/usr/bin/env python3
"""
extract-quotes.py — Find time references in ePub files for the Literature Clock.

Scans ePub books for sentences containing time-of-day references and outputs
them as CSV (TimeSinceMidnightInMinutes,Quote,Title,Author) ready for import.

Usage:
    python3 extract-quotes.py book.epub
    python3 extract-quotes.py /path/to/library/    # scan all .epub files
    python3 extract-quotes.py *.epub --output found-quotes.csv

Dependencies:
    pip install ebooklib beautifulsoup4 lxml
"""

import argparse
import csv
import hashlib
import re
import sys
import os
import warnings
from pathlib import Path
from dataclasses import dataclass, field

try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install ebooklib beautifulsoup4 lxml")
    sys.exit(1)


@dataclass
class TimeQuote:
    minutes: int          # minutes since midnight
    quote: str
    title: str
    author: str
    time_match: str       # the matched time expression
    confidence: str = ""  # high / medium / low


# ── Time-matching patterns ──────────────────────────────────────────────

# 12-hour times: "3:45 AM", "three o'clock", "half past seven", "quarter to nine"
PATTERNS = [
    # ── HIGH confidence (unambiguous) ──
    # Digital: 3:45, 11:07 AM/PM, 03:45
    (r'\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?|AM|PM|A\.M\.|P\.M\.)\b', 'digital_ampm'),
    # Military/24h: 0800h, 2215h, 0300 hours
    (r'\b(\d{2})(\d{2})\s*(?:h\.?|hrs?\.?|hours)\b', 'military'),
    # "it was midnight", "it was noon"
    (r"\bit\s+was\s+(midnight|noon|midday)\b", 'noon_midnight'),

    # ── MEDIUM confidence (real time refs, may need AM/PM) ──
    # Digital without AM/PM (contextual): "at 3:45" "by 11:07"
    (r'(?:at|by|around|about|nearly|past|before|after|until|till|struck|striking|says?|read|said|showed?|clock\s+said|watch\s+said)\s+(\d{1,2}):(\d{2})', 'digital_context'),
    # "X o'clock and Y minutes" — must match before plain o'clock
    (r"\b(\w+)\s+o['\u2019]?\s*clock\s+and\s+(\w+[\w-]*)\s+minutes?\b", 'oclock_and_minutes'),
    # "X o'clock" with optional AM/PM
    (r"\b(\w+)\s+o['\u2019]?\s*clock(?:\s+(?:in the|at)\s+(?:morning|afternoon|evening|night))?\b", 'oclock'),
    # "half past X", "half-past X"  — MUST be before word_time to take priority
    (r"\bhalf[\s-]past\s+(\w+)\b", 'half_past'),
    # "quarter past X", "quarter to X", "quarter before X"
    (r"\bquarter\s+(past|to|before|after)\s+(\w+)\b", 'quarter'),
    # "X minutes past/to Y"
    (r"\b(\w+)\s+minutes?\s+(past|to|before|after|of)\s+(\w+)\b", 'minutes_past_to'),
    # "twenty to nine", "ten past three" (common sub-hour words)
    (r"\b(five|ten|twenty|twenty-five)\s+(past|to|before|after|of)\s+(\w+)\b", 'word_past_to'),
    # Struck/striking: "the clock struck twelve", "striking nine"
    (r"\b(?:struck|striking|strikes?|chim(?:ed?|ing))\s+(\w+)\b", 'struck'),

    # ── LOW confidence (often false positives like "by one arm") ──
    # Specific written times: "at seven", "by nine" (only with preposition)
    (r"\b(?:at|by|until|till|before|after|nearly|almost|just|past|about|around|approaching|nearing)\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)(?:\s+(?:in the|at|that)\s+(?:morning|afternoon|evening|night))?\b", 'word_time'),
]

WORD_TO_NUM = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
    'midnight': 0, 'noon': 12, 'midday': 12,
    'thirteen': 13,  # 1984 :)
}

MINUTE_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
    'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
    'nineteen': 19, 'twenty': 20, 'twenty-one': 21, 'twenty-two': 22,
    'twenty-three': 23, 'twenty-four': 24, 'twenty-five': 25,
    'twenty-six': 26, 'twenty-seven': 27, 'twenty-eight': 28,
    'twenty-nine': 29, 'thirty': 30, 'thirty-one': 31, 'thirty-two': 32,
    'thirty-three': 33, 'thirty-four': 34, 'thirty-five': 35,
    'thirty-six': 36, 'thirty-seven': 37, 'thirty-eight': 38,
    'thirty-nine': 39, 'forty': 40, 'forty-one': 41, 'forty-two': 42,
    'forty-three': 43, 'forty-four': 44, 'forty-five': 45,
    'forty-six': 46, 'forty-seven': 47, 'forty-eight': 48,
    'forty-nine': 49, 'fifty': 50, 'fifty-one': 51, 'fifty-two': 52,
    'fifty-three': 53, 'fifty-four': 54, 'fifty-five': 55,
    'fifty-six': 56, 'fifty-seven': 57, 'fifty-eight': 58,
    'fifty-nine': 59, 'half': 30, 'quarter': 15,
}

AFTERNOON_HINTS = re.compile(
    r'afternoon|evening|night(?:time)?|pm|p\.m\.|supper|dinner|dusk|sunset|'
    r'dark(?:ness)?|twilight|moonlight|moon(?:rise)?|starlight|stars?\b|'
    r'cocktail|nightcap|pub|bar\b|wine|whiskey|brandy|'
    r'\bbed(?:time)?\b|\bsleep\b|\btired\b|\bweary\b|\byawn\b|'
    r'\blight\s+off\b|\bturned?\s+off\s+the\s+light\b|\blights?\s+out\b|'
    r'\blate\s+(?:in the|at)\b|\bafter\s+dark\b|\bgetting\s+dark\b|sun\s+(?:had\s+)?set',
    re.IGNORECASE
)
MORNING_HINTS = re.compile(
    r'\bmorning\b|\bdawn\b|\bsunrise\b|\bbreakfast\b|\bam\b|\ba\.m\.\b|'
    r'\bwoke\b|\bwaking\b|\balarm\s+clock\b|\bcoffee\b|\btoast\b|\bcereal\b|\beggs?\b|'
    r'\bearly\s+(?:in the|hours)\b|\bfirst\s+light\b|\bdaybreak\b|\bcockcrow\b|\brooster\b|'
    r'\bschool\b|\bcommute\b|\boffice\b|\bwork\b.*(?:start|begin)|'
    r'sun\s+(?:had\s+)?(?:just\s+)?risen|sun\s+was\s+(?:just\s+)?rising',
    re.IGNORECASE
)


# ── Time jitter for qualifying words ─────────────────────────────────────

QUALIFIER_PATTERNS = [
    # "a little after", "shortly after", "just after"
    (re.compile(r'(a little|shortly|just|slightly) after', re.I), 1, 5),
    # "a little before", "shortly before", "just before"
    (re.compile(r'(a little|shortly|just|slightly) before', re.I), -5, -1),
    # "nearly X o'clock"
    (re.compile(r'nearly \w+ o.clock|nearly \w+$', re.I), -5, -1),
    # "almost X"
    (re.compile(r'almost \w+ o.clock', re.I), -5, -1),
    # "about X o'clock", "about X in the"
    (re.compile(r'about \w+ o.clock|about \w+ in the', re.I), -5, 5),
    # "a few minutes past/after"
    (re.compile(r'(few minutes|a little) (past|after) \w+', re.I), 1, 5),
    # "after X o'clock", "after X" (bare, no other qualifier already matched)
    (re.compile(r'\bafter\s+\w+\s+o.clock\b|\bafter\s+(?:midnight|noon|midday)\b', re.I), 1, 10),
    (re.compile(r'\b(?:it was|was)\s+after\s+\w+\b', re.I), 1, 10),
    # "before X o'clock", "before X"
    (re.compile(r'\bbefore\s+\w+\s+o.clock\b|\bbefore\s+(?:midnight|noon|midday)\b', re.I), -10, -1),
    (re.compile(r'\b(?:it was|was)\s+before\s+\w+\b', re.I), -10, -1),
    # "past X" (as in "past midnight", "past noon")
    (re.compile(r'\bpast\s+(?:midnight|noon|midday)\b', re.I), 1, 10),
]


def apply_qualifier_jitter(minutes: int, quote: str) -> int:
    """Apply deterministic time jitter based on qualifying words in the quote.

    Rules:
        "about"           → ±1–5 min
        "nearly/almost"   → -1–5 min (slightly before)
        "a little after"  → +1–5 min
        "a little before" → -1–5 min

    Jitter is deterministic: seeded from the quote text, so the same quote
    always produces the same offset.
    """
    for pattern, min_off, max_off in QUALIFIER_PATTERNS:
        if pattern.search(quote):
            h = int(hashlib.sha256(quote.encode()).hexdigest(), 16)
            spread = max_off - min_off + 1
            offset = min_off + (h % spread)
            return max(0, min(1439, minutes + offset))
    return minutes


def word_to_hour(w: str) -> int | None:
    """Convert a word like 'seven' to an integer hour, or return None."""
    w = w.lower().strip()
    return WORD_TO_NUM.get(w) or (int(w) if w.isdigit() and 0 <= int(w) <= 23 else None)


def guess_ampm(hour: int, context: str, match_pos: int = -1) -> int:
    """Guess whether an ambiguous hour (1-12) is AM or PM from surrounding text.
    
    Uses proximity-weighted scoring: hints closer to the time reference
    carry more weight than distant ones.
    
    Args:
        hour: The hour (1-12) to disambiguate
        context: Full quote/sentence text
        match_pos: Character position of the time match in context (-1 = unknown)
    
    Priority:
    1. Explicit 'in the morning/afternoon/evening/night' or 'a.m./p.m.' (weight 100)
    2. Proximity-weighted contextual hints (weight decays with distance)
    3. Default: AM interpretation
    """
    if hour == 0:
        return hour  # midnight unambiguous
    if hour == 12:
        if re.search(r'\bnight\b|\bmidnight\b|\bdark\b|\bcold\b.*\bnight\b', context, re.I):
            return 0
        return hour

    # --- Explicit phrases (highest priority, weight=100) ---
    EXPLICIT_AM = re.compile(
        r'\bin the morning\b|\bin the early hours\b|\bbefore dawn\b|\ba\.m\.\b|\bam\b(?=[\s,;.]|$)',
        re.I)
    EXPLICIT_PM = re.compile(
        r'\bin the afternoon\b|\bin the evening\b|\bat night\b|\bin the night\b|\bp\.m\.\b|\bpm\b(?=[\s,;.]|$)',
        re.I)

    am_score = 0.0
    pm_score = 0.0

    def proximity_weight(hint_pos, ref_pos, base_weight=10.0):
        """Closer hints get higher weight. Max at distance 0, decays over ~200 chars."""
        if ref_pos < 0:
            return base_weight * 0.5  # unknown position: flat mid-weight
        dist = abs(hint_pos - ref_pos)
        return base_weight * max(0.1, 1.0 - dist / 200.0)

    # Explicit AM/PM (very high weight, still proximity-aware)
    for m in EXPLICIT_AM.finditer(context):
        am_score += proximity_weight(m.start(), match_pos, 100.0)
    for m in EXPLICIT_PM.finditer(context):
        pm_score += proximity_weight(m.start(), match_pos, 100.0)

    # Broader contextual hints (lower base weight)
    for m in MORNING_HINTS.finditer(context):
        am_score += proximity_weight(m.start(), match_pos, 10.0)
    for m in AFTERNOON_HINTS.finditer(context):
        pm_score += proximity_weight(m.start(), match_pos, 10.0)

    if pm_score > am_score and pm_score > 5.0:
        # Edge case: hours 1-3 with "night" context usually means past midnight (AM)
        # e.g., "at two at night" = 02:00, not 14:00
        if hour <= 3 and re.search(r'\bat night\b|\bin the night\b', context, re.I):
            return hour  # keep as AM (post-midnight)
        return hour + 12 if hour < 12 else hour
    if am_score > pm_score and am_score > 5.0:
        return hour

    # Both similar or neither → default AM
    return hour


def parse_time(match, pattern_type: str, context: str) -> int | None:
    """Parse a regex match into minutes-since-midnight. Returns None if unparseable."""
    groups = match.groups()
    mpos = match.start()  # position for proximity-based AM/PM guessing

    if pattern_type == 'digital_ampm':
        h, m, ampm = int(groups[0]), int(groups[1]), groups[2].lower().replace('.', '')
        if 'pm' in ampm and h != 12:
            h += 12
        elif 'am' in ampm and h == 12:
            h = 0
        return h * 60 + m

    elif pattern_type == 'digital_context':
        h, m = int(groups[0]), int(groups[1])
        if h > 23 or m > 59:
            return None
        if h <= 12:
            h = guess_ampm(h, context, mpos)
        return h * 60 + m

    elif pattern_type == 'military':
        h, m = int(groups[0]), int(groups[1])
        if h > 23 or m > 59:
            return None
        return h * 60 + m

    elif pattern_type == 'oclock_and_minutes':
        h = word_to_hour(groups[0])
        if h is None or h > 12:
            return None
        m_word = groups[1].lower()
        mins = MINUTE_WORDS.get(m_word)
        if mins is None:
            mins = word_to_hour(m_word)
        if mins is None:
            return None
        h = guess_ampm(h, context, mpos)
        return h * 60 + mins

    elif pattern_type == 'oclock':
        h = word_to_hour(groups[0])
        if h is None or h > 12:
            return None
        h = guess_ampm(h, context, mpos)
        return h * 60

    elif pattern_type == 'half_past':
        h = word_to_hour(groups[0])
        if h is None or h > 12:
            return None
        h = guess_ampm(h, context, mpos)
        return h * 60 + 30

    elif pattern_type == 'quarter':
        direction = groups[0].lower()
        h = word_to_hour(groups[1])
        if h is None or h > 12:
            return None
        h = guess_ampm(h, context, mpos)
        if direction in ('past', 'after'):
            return h * 60 + 15
        else:  # to, before
            return (h - 1) * 60 + 45 if h > 0 else 23 * 60 + 45

    elif pattern_type in ('minutes_past_to', 'word_past_to'):
        min_word = groups[0]
        direction = groups[1].lower()
        h = word_to_hour(groups[2])
        if h is None or h > 12:
            return None
        mins = MINUTE_WORDS.get(min_word.lower()) or word_to_hour(min_word)
        if mins is None:
            return None
        h = guess_ampm(h, context, mpos)
        if direction in ('past', 'after'):
            return h * 60 + mins
        else:  # to, before, of
            total = h * 60 - mins
            return total if total >= 0 else total + 1440

    elif pattern_type == 'struck':
        h = word_to_hour(groups[0])
        if h is None or h > 12:
            return None
        h = guess_ampm(h, context, mpos)
        return h * 60

    elif pattern_type == 'noon_midnight':
        w = groups[0].lower()
        return WORD_TO_NUM.get(w, 0) * 60

    elif pattern_type == 'word_time':
        h = word_to_hour(groups[0])
        if h is None or h > 12:
            return None
        h = guess_ampm(h, context, mpos)
        return h * 60

    return None


# ── ePub text extraction ────────────────────────────────────────────────

def extract_text_from_epub(epub_path: str) -> tuple[str, str, str]:
    """Extract full text, title, and author from an ePub file."""
    book = epub.read_epub(epub_path, options={'ignore_ncx': True})

    title = book.get_metadata('DC', 'title')
    title = title[0][0] if title else Path(epub_path).stem

    author = book.get_metadata('DC', 'creator')
    author = author[0][0] if author else ''

    texts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), 'lxml')
        text = soup.get_text(separator=' ', strip=True)
        if text:
            texts.append(text)

    return '\n\n'.join(texts), title, author


def extract_sentences(text: str) -> list[str]:
    """Split text into sentence-like chunks."""
    # Split on sentence-ending punctuation, keeping some context
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def find_time_quotes(text: str, title: str, author: str) -> list[TimeQuote]:
    """Find all time references in text and return as TimeQuote objects."""
    sentences = extract_sentences(text)
    results = []
    seen = set()  # dedup by (minutes, first_50_chars)

    for sentence in sentences:
        # Track matched character ranges to let higher-priority patterns win
        matched_ranges = []

        # Provide surrounding context for AM/PM guessing
        for pattern, ptype in PATTERNS:
            for match in re.finditer(pattern, sentence, re.IGNORECASE):
                # Skip if a higher-priority pattern already claimed this text region
                m_start, m_end = match.start(), match.end()
                if any(m_start < er and m_end > sr for sr, er in matched_ranges):
                    continue

                context = sentence  # use full sentence as context
                minutes = parse_time(match, ptype, context)
                if minutes is None:
                    continue

                # Mark this range as claimed
                matched_ranges.append((m_start, m_end))

                # Extract a reasonable quote (up to ~300 chars around the match)
                start = max(0, match.start() - 120)
                end = min(len(sentence), match.end() + 180)
                quote = sentence[start:end].strip()

                # Clean up: ensure we start/end at word boundaries
                if start > 0:
                    quote = '…' + quote[quote.find(' ') + 1:] if ' ' in quote[:20] else '…' + quote
                if end < len(sentence):
                    last_space = quote.rfind(' ', -30)
                    if last_space > len(quote) - 40:
                        quote = quote[:last_space] + '…'

                dedup_key = (minutes, quote[:50])
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Confidence based on pattern type
                if ptype in ('digital_ampm', 'military', 'noon_midnight'):
                    confidence = 'high'
                elif ptype in ('digital_context', 'oclock', 'half_past', 'quarter'):
                    confidence = 'medium'
                else:
                    confidence = 'low'

                results.append(TimeQuote(
                    minutes=minutes,
                    quote=quote,
                    title=title,
                    author=author,
                    time_match=match.group(),
                    confidence=confidence,
                ))

    return results


# ── Main ────────────────────────────────────────────────────────────────

def process_path(path: str) -> list[TimeQuote]:
    """Process a single ePub file or a directory of ePubs."""
    p = Path(path)
    all_quotes = []

    if p.is_file() and p.suffix.lower() == '.epub':
        files = [p]
    elif p.is_dir():
        files = sorted(p.rglob('*.epub'))
    else:
        print(f"Skipping: {path} (not an epub or directory)", file=sys.stderr)
        return []

    for epub_file in files:
        try:
            print(f"Scanning: {epub_file.name}...", file=sys.stderr)
            text, title, author = extract_text_from_epub(str(epub_file))
            quotes = find_time_quotes(text, title, author)
            print(f"  Found {len(quotes)} time references", file=sys.stderr)
            all_quotes.extend(quotes)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)

    return all_quotes


def main():
    parser = argparse.ArgumentParser(
        description='Extract time-of-day quotes from ePub files for the Literature Clock.'
    )
    parser.add_argument('paths', nargs='+', help='ePub files or directories to scan')
    parser.add_argument('-o', '--output', default='-', help='Output CSV file (default: stdout)')
    parser.add_argument('-c', '--confidence', default='all',
                        choices=['all', 'high', 'medium', 'low'],
                        help='Minimum confidence level (default: all)')
    parser.add_argument('--json', action='store_true', help='Output as JSON instead of CSV')
    args = parser.parse_args()

    all_quotes = []
    for path in args.paths:
        all_quotes.extend(process_path(path))

    # Filter by confidence
    if args.confidence != 'all':
        levels = {'high': ['high'], 'medium': ['high', 'medium'], 'low': ['high', 'medium', 'low']}
        all_quotes = [q for q in all_quotes if q.confidence in levels[args.confidence]]

    # Sort by time
    all_quotes.sort(key=lambda q: q.minutes)

    # Output
    out = sys.stdout if args.output == '-' else open(args.output, 'w', newline='', encoding='utf-8')

    # Apply qualifier jitter (deterministic offset for "about", "nearly", etc.)
    for q in all_quotes:
        q.minutes = apply_qualifier_jitter(q.minutes, q.quote)

    # Re-sort after jitter
    all_quotes.sort(key=lambda q: q.minutes)

    if args.json:
        import json
        data = [{
            'time': f"{q.minutes // 60:02d}:{q.minutes % 60:02d}",
            'quote': q.quote,
            'title': q.title,
            'author': q.author,
            'time_match': q.time_match,
            'confidence': q.confidence,
        } for q in all_quotes]
        json.dump(data, out, indent=2, ensure_ascii=False)
    else:
        writer = csv.writer(out)
        writer.writerow(['TimeSinceMidnightInMinutes', 'Quote', 'Title', 'Author', 'TimeMatch', 'Confidence'])
        for q in all_quotes:
            writer.writerow([q.minutes, q.quote, q.title, q.author, q.time_match, q.confidence])

    if args.output != '-':
        out.close()
        print(f"\nWrote {len(all_quotes)} quotes to {args.output}", file=sys.stderr)
    else:
        print(f"\nTotal: {len(all_quotes)} quotes found", file=sys.stderr)


if __name__ == '__main__':
    main()
