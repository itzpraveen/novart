{% load static %}
const CACHE_VERSION = 'v2';
const STATIC_CACHE = `studioflow-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `studioflow-dynamic-${CACHE_VERSION}`;
const STATIC_ASSETS = [
  "{% static 'css/style.css' %}",
  "{% static 'img/novart.png' %}",
  "{% static 'favicon.ico' %}",
  "{% static 'pwa/icon-192.png' %}",
  "{% static 'pwa/icon-512.png' %}",
  "{% url 'manifest' %}",
  "{% url 'service_worker' %}"
];

const OFFLINE_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offline - StudioFlow</title>
  <style>
    :root { color-scheme: light; }
    body {
      margin: 0;
      font-family: "Inter", system-ui, -apple-system, sans-serif;
      background: #f8fafc;
      color: #0f172a;
    }
    .wrap {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    .card {
      max-width: 420px;
      width: 100%;
      background: #ffffff;
      border: 1px solid rgba(15, 23, 42, 0.08);
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
      text-align: center;
    }
    .title {
      font-size: 20px;
      font-weight: 600;
      margin-bottom: 8px;
    }
    .text {
      color: #475569;
      margin-bottom: 16px;
    }
    .btn {
      display: inline-block;
      padding: 10px 16px;
      background: #0d9488;
      color: #ffffff;
      text-decoration: none;
      border-radius: 10px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="title">You're offline</div>
      <div class="text">Reconnect to continue using StudioFlow.</div>
      <a class="btn" href="/">Retry</a>
    </div>
  </div>
</body>
</html>`;

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys
        .filter(key => (key.startsWith('studioflow-static-') && key !== STATIC_CACHE) || (key.startsWith('studioflow-dynamic-') && key !== DYNAMIC_CACHE))
        .map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      networkThenCache(request).catch(() => new Response(OFFLINE_HTML, {
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      }))
    );
  }
});

async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response && response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

async function networkThenCache(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(DYNAMIC_CACHE);
    cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cache = await caches.open(DYNAMIC_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;
    throw err;
  }
}

// Allow clients to tell this worker to activate immediately
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
