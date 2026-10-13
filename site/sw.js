const CACHE_NAME = 'sse-community-v5-20261014';
const APP_FILES = ['./', './index.html', './community.js', './manifest.webmanifest', './app-icon.svg'];
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_FILES)).catch(() => {}));
});
self.addEventListener('activate', event => {
  event.waitUntil(Promise.all([
    self.clients.claim(),
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  ]));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || new URL(event.request.url).origin !== self.location.origin) return;
  // Always fetch the latest HTML shell first; only fall back to cached HTML when the network is unavailable.
  const isPage = event.request.mode === 'navigate' || new URL(event.request.url).pathname.endsWith('/index.html');
  const request = isPage ? new Request(event.request, { cache: 'no-store' }) : event.request;
  event.respondWith(fetch(request).then(response => {
    if (response && response.ok) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => caches.match(event.request).then(cached => cached || caches.match('./index.html'))));
});