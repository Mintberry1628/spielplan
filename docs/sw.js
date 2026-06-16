/* =========================================================
   Service Worker – macht die App offline-fähig.
   Speichert die App-Hülle + die zuletzt geladenen Daten,
   damit auch ohne Internet die letzten Spiele angezeigt werden.
   ========================================================= */

const CACHE = "spielplan-v3";
const SHELL = [
  "./index.html",
  "./styles.css?v=3",
  "./app.js?v=3",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-maskable.svg",
];

// Beim Installieren: App-Hülle in den Cache legen
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

// Alte Caches aufräumen
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Abruf-Strategie:
//  - data.json: zuerst Netzwerk (frische Daten), bei Fehler aus Cache (offline)
//  - alles andere: zuerst Cache (schnell), parallel Netzwerk-Aktualisierung
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.endsWith("data.json")) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

// Erinnerungen über die Notification-API (best effort, solange SW lebt)
self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "schedule-reminder") {
    const delay = data.fireAt - Date.now();
    if (delay <= 0) return;
    // setTimeout im SW ist nicht garantiert langlebig – daher zusätzlich
    // der Kalender-Export in der App als zuverlässige Erinnerung.
    setTimeout(() => {
      self.registration.showNotification(data.title, {
        body: data.body,
        icon: "./icons/icon.svg",
        badge: "./icons/icon.svg",
        tag: data.tag,
      });
    }, Math.min(delay, 2147483647));
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("./index.html"));
});
