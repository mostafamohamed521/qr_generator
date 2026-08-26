/**
 * QR Forge Service Worker
 * Strategy: stale-while-revalidate for static assets, network-first for pages.
 */
// Bumped from v1 -- the old cache-first strategy below served style.css /
// app.js from cache forever with no revalidation, so any CSS/JS deploy
// (like this project's full redesign) was invisible to anyone who'd
// loaded the site even once before, no matter how hard they refreshed --
// service worker caches aren't cleared by a normal browser hard-reload.
// Bumping CACHE_NAME forces the activate handler below to drop the old
// cache immediately for anyone already running the previous worker.
const CACHE_NAME  = 'qr-forge-v2';
const SHELL_URLS  = [
  '/app/',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/manifest.json',
];

// ── Install: pre-cache the app shell ─────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(SHELL_URLS.map(url =>
        cache.add(url).catch(() => { /* skip missing */ })
      ));
    }).then(() => self.skipWaiting())
  );
});

// ── Activate: purge old caches ────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch strategy ────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Skip: non-GET, cross-origin, API calls, admin
  if (request.method !== 'GET') return;
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/app/api/') ||
      url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/admin/') ||
      url.pathname.startsWith('/r/')) return;

  // 2. Static assets — stale-while-revalidate: serve the cached copy
  // instantly (fast, works offline), but always kick off a network fetch
  // in the background to refresh the cache. This means a deploy is at
  // most one extra load away from showing up, instead of invisible until
  // the cache name is manually bumped (which is exactly what happened
  // here — this file itself is one of the cached assets).
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache =>
        cache.match(request).then(cached => {
          const network = fetch(request).then(res => {
            cache.put(request, res.clone());
            return res;
          }).catch(() => cached);
          return cached || network;
        })
      )
    );
    return;
  }

  // 3. HTML pages — network-first, fallback to cache
  event.respondWith(
    fetch(request)
      .then(res => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(c => c.put(request, clone));
        return res;
      })
      .catch(() => caches.match(request).then(cached => {
        if (cached) return cached;
        // offline fallback
        return caches.match('/app/');
      }))
  );
});
