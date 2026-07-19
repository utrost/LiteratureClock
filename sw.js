// Literature Clock — Service Worker
// Offline-first: cache all assets, serve from cache, update in background

const CACHE_NAME = 'lit-clock-v2';
const PRECACHE_URLS = [
  '/clock/',
  '/clock/index.html',
  '/clock/css/style.css',
  '/clock/js/clock.js',
  '/clock/data/quotes.json',
  '/clock/favicon.svg',
  '/clock/manifest.json',
  '/clock/docs/app-icon-512.png',
  '/clock/docs/screenshot-pwa-android.jpg',
];

// Install: pre-cache all assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Fetch: cache-first, network fallback, background update
self.addEventListener('fetch', (event) => {
  const requestUrl = new URL(event.request.url);
  // Only handle same-origin /clock/ requests.
  if (requestUrl.origin !== self.location.origin || !requestUrl.pathname.startsWith('/clock/')) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (!cached && event.request.mode === 'navigate') {
        return fetch(event.request).catch(() => caches.match('/clock/index.html'));
      }
      // Return cached version immediately
      const fetchPromise = fetch(event.request)
        .then((response) => {
          // Update cache with fresh version
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() => cached); // Network failed, cached is all we have

      return cached || fetchPromise;
    })
  );
});
