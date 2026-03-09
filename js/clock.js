(() => {
  'use strict';

  let allQuotes = [];
  let quotesByTime = {};
  let currentTime = '';
  let idleTimer = null;

  // --- Format time as HH:MM ---
  function formatTime(date) {
    return String(date.getHours()).padStart(2, '0') + ':' +
           String(date.getMinutes()).padStart(2, '0');
  }

  // --- Index quotes by time ---
  function indexQuotes(quotes) {
    const map = {};
    quotes.forEach(q => {
      if (!map[q.time]) map[q.time] = [];
      map[q.time].push(q);
    });
    return map;
  }

  // --- Pick a random quote for a time ---
  function pickQuote(time) {
    const candidates = quotesByTime[time];
    if (!candidates || candidates.length === 0) return null;
    return candidates[Math.floor(Math.random() * candidates.length)];
  }

  // --- Find nearest time if exact match missing ---
  function findNearest(time) {
    if (quotesByTime[time]) return time;

    const [h, m] = time.split(':').map(Number);
    const totalMin = h * 60 + m;
    
    let bestTime = null;
    let bestDist = Infinity;
    
    for (const t of Object.keys(quotesByTime)) {
      const [th, tm] = t.split(':').map(Number);
      const tMin = th * 60 + tm;
      const dist = Math.abs(tMin - totalMin);
      if (dist < bestDist) {
        bestDist = dist;
        bestTime = t;
      }
    }
    return bestTime;
  }

  // --- Display a quote with fade transition ---
  function displayQuote(quote) {
    const container = document.getElementById('quote-container');
    const quoteEl = document.getElementById('quote');
    const authorEl = document.getElementById('author');
    const titleEl = document.getElementById('title');
    const timeEl = document.getElementById('time-display');

    // Fade out
    container.classList.remove('visible');

    setTimeout(() => {
      if (quote) {
        // Truncate very long quotes
        let text = quote.quote;
        if (text.length > 500) {
          text = text.substring(0, 497) + '…';
        }
        
        quoteEl.textContent = text;
        quoteEl.classList.toggle('long', text.length > 300);
        authorEl.textContent = quote.author || '';
        titleEl.textContent = quote.title || '';
      } else {
        quoteEl.textContent = '';
        authorEl.textContent = '';
        titleEl.textContent = '';
      }

      timeEl.textContent = currentTime;

      // Fade in
      container.classList.add('visible');
    }, 600);
  }

  // --- Check time and update ---
  function tick() {
    const now = new Date();
    const time = formatTime(now);

    if (time !== currentTime) {
      currentTime = time;
      const matchTime = findNearest(time);
      const quote = pickQuote(matchTime);
      displayQuote(quote);
    }
  }

  // --- Idle cursor hide ---
  function resetIdle() {
    document.body.classList.remove('idle');
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      document.body.classList.add('idle');
    }, 5000);
  }

  // --- Click for next quote at same time ---
  function nextQuote() {
    const matchTime = findNearest(currentTime);
    const candidates = quotesByTime[matchTime];
    if (candidates && candidates.length > 1) {
      const quote = pickQuote(matchTime);
      displayQuote(quote);
    }
  }

  // --- Init ---
  async function init() {
    try {
      const res = await fetch('data/quotes.json');
      allQuotes = await res.json();
    } catch (e) {
      console.error('Failed to load quotes:', e);
      return;
    }

    quotesByTime = indexQuotes(allQuotes);

    // Initial display
    currentTime = '';
    tick();

    // Check every second
    setInterval(tick, 1000);

    // Click/tap for next quote
    document.getElementById('clock').addEventListener('click', nextQuote);

    // Idle cursor
    document.addEventListener('mousemove', resetIdle);
    document.addEventListener('touchstart', resetIdle);
    resetIdle();

    // Fullscreen on double-click
    document.addEventListener('dblclick', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
