// Bump this on every index.html change, or installed PWAs keep serving the
// old shell from the previous cache and your changes appear to do nothing.
const CACHE = 'ncmf-v4';
const ASSETS = [
  '/',
  '/index.html',
  '/data/cache.json',
  '/data/watchlist.json',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png'
];

// Install — cache core assets individually. addAll() is all-or-nothing: one
// missing file (a not-yet-committed watchlist.json, a renamed icon) aborts the
// whole install and leaves the app with no service worker at all.
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      Promise.all(ASSETS.map(url =>
        c.add(url).catch(err => console.warn('SW: skipped', url, err))
      ))
    )
  );
  self.skipWaiting();
});

// Activate — delete old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — network first for cache.json (always want fresh data),
// cache first for everything else
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Always go network-first for data so prices — and the watchlist the last
  // fetch ran against — stay current.
  if (url.pathname.endsWith('cache.json') || url.pathname.endsWith('watchlist.json')) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Cache-first for everything else (shell, icons, manifest)
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      });
    })
  );
});
