/* Savora service worker.
 *
 * - App shell and static assets: cached, so the installed app opens offline.
 * - Pages: network first, cached copy when offline, else the /offline page.
 * - /api (the FastAPI backend, possibly another origin): never cached. Plans, cravings
 *   and swaps are personal and need a live connection (DESIGN_SYSTEM: generation and AI
 *   inference require connectivity).
 */
const VERSION = "savora-v4";
const SHELL = `${VERSION}-shell`;
const RUNTIME = `${VERSION}-runtime`;
const PRECACHE = ["/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

/** The offline page plus every build asset it loads, so it renders with no network. */
async function precacheOfflinePage(cache) {
  const response = await fetch("/offline", { cache: "reload" });
  if (!response.ok) throw new Error(`offline page: ${response.status}`);
  const html = await response.clone().text();
  await cache.put("/offline", response);
  const assets = new Set();
  for (const match of html.matchAll(/(?:src|href)="(\/_next\/static\/[^"]+)"/g)) assets.add(match[1]);
  await cache.addAll([...assets]);
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((cache) => Promise.all([cache.addAll(PRECACHE), precacheOfflinePage(cache)]))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isStatic(url) {
  return url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/") || /\.(?:woff2?|png|svg|ico)$/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api")) return;

  if (isStatic(url)) {
    // Hashed build assets never change: cache first.
    event.respondWith(
      caches.match(request, { ignoreVary: true }).then(
        (hit) =>
          hit ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(RUNTIME).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(RUNTIME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        // Next.js pages vary on router headers; match the stored page regardless. A page
        // never visited redirects to /offline: serving that HTML under another URL would
        // make the Next.js router fetch the missing route and show its error screen.
        .catch(async () => {
          const cached = await caches.match(request, { ignoreVary: true });
          if (cached) return cached;
          if (url.pathname === "/offline") return Response.error();
          return Response.redirect("/offline", 302);
        }),
    );
  }
});
