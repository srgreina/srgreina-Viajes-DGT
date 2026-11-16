// Service worker mínimo: hace la app instalable y permite abrirla sin conexión.
// Los datos de la DGT, las rutas y los mapas nunca se cachean aquí: siempre van a la red.
const CACHE = 'viajes-dgt-v16';
const SHELL = ['./', 'index.html', 'manifest.json', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  // Red primero (siempre la última versión de la app); la caché solo si no hay conexión.
  e.respondWith(
    fetch(req, { cache: 'no-store' }) // sin la caché HTTP de Pages (10 min): si no, se sirve la versión vieja
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req))
  );
});
