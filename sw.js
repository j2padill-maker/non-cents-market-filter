const CACHE = 'ncmf-v1';
const ASSETS = [
  '/non-cents-market-filter/',
  '/non-cents-market-filter/index.html',
  '/non-cents-market-filter/data/cache.json',
  '/non-cents-market-filter/manifest.json',
  '/non-cents-market-filter/icons/icon-192.png',
  '/non-cents-market-filter/icons/icon-512.png'
];

// Install — cache all core assets
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS))
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

  // Always go network-first for data so prices stay current
  if (url.pathname.endsWith('cache.json')) {
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
