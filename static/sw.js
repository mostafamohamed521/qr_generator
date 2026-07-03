/**
 * QR Forge Service Worker — Sprint 7
 * Strategy: cache-first for static assets, network-first for API/pages.
 */
const CACHE_NAME  = 'qr-forge-v1';
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

  // 2. Static assets — cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(res => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(c => c.put(request, clone));
        return res;
      }))
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
