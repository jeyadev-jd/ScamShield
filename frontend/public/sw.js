// Minimal service worker: makes the app installable (needed for the Android
// share target) and serves the app shell offline. API calls always go to the
// network; nothing a user submits is cached.
const CACHE = 'scamshield-v1'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon-192.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()))
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/') || url.origin !== location.origin) return
  if (e.request.mode === 'navigate') {
    // SPA routes (/case/..., /?text=... from the share sheet) -> network first, shell offline.
    e.respondWith(fetch(e.request).catch(() => caches.match('/index.html')))
    return
  }
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
    if (res.ok && url.pathname.startsWith('/assets/')) {
      const copy = res.clone()
      caches.open(CACHE).then((c) => c.put(e.request, copy))
    }
    return res
  })))
})
