// ==============================================================================
// File: frontend/sw.js
// Description: Advanced Offline-First Service Worker for Google Photos Local:
//              - Instant App Shell caching
//              - Stale-While-Revalidate & LRU Cache for photo thumbnails (/api/thumbnails/*)
//              - Network-First with Cache Fallback for timeline hierarchy (/api/timeline)
//              - Resilient 100% offline browsing capability
// ==============================================================================

const APP_CACHE = "google-photos-app-v2";
const THUMB_CACHE = "google-photos-thumbs-v2";
const DATA_CACHE = "google-photos-data-v2";

const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/favicon.svg",
  "/manifest.webmanifest"
];

const MAX_THUMBNAIL_ENTRIES = 600;

async function trimCache(cacheName, maxEntries) {
  try {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length > maxEntries) {
      const keysToDelete = keys.slice(0, keys.length - maxEntries);
      await Promise.all(keysToDelete.map((key) => cache.delete(key)));
    }
  } catch (e) {
    // Non-fatal cache trim error
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (![APP_CACHE, THUMB_CACHE, DATA_CACHE].includes(key)) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Bypass WebSocket
  if (url.pathname.startsWith("/ws/")) return;

  // 1. Photo Thumbnails: Stale-While-Revalidate with LRU Cache
  if (url.pathname.startsWith("/api/thumbnails/")) {
    event.respondWith(
      caches.open(THUMB_CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        const fetchPromise = fetch(req).then((networkRes) => {
          if (networkRes && networkRes.status === 200) {
            cache.put(req, networkRes.clone());
            trimCache(THUMB_CACHE, MAX_THUMBNAIL_ENTRIES);
          }
          return networkRes;
        }).catch(() => cached);

        return cached || fetchPromise;
      })
    );
    return;
  }

  // 2. Timeline Hierarchy & Categories: Network-First with Cache Fallback
  if (url.pathname === "/api/timeline" || url.pathname === "/api/categories" || url.pathname === "/api/collections/smart") {
    event.respondWith(
      fetch(req).then((networkRes) => {
        if (networkRes && networkRes.status === 200) {
          const clone = networkRes.clone();
          caches.open(DATA_CACHE).then((cache) => cache.put(req, clone));
        }
        return networkRes;
      }).catch(async () => {
        const cached = await caches.match(req);
        return cached || new Response(JSON.stringify({ error: "Offline mode", timeline: [] }), {
          headers: { "Content-Type": "application/json" }
        });
      })
    );
    return;
  }

  // 3. Static App Shell: Cache-First with Background Network Update
  if (!url.pathname.startsWith("/api/")) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const fetchPromise = fetch(req).then((networkRes) => {
          if (networkRes && networkRes.status === 200) {
            caches.open(APP_CACHE).then((cache) => cache.put(req, networkRes.clone()));
          }
          return networkRes;
        }).catch(() => cached);

        return cached || fetchPromise;
      })
    );
  }
});
