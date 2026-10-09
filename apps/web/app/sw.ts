/// <reference lib="webworker" />

/** Service worker for the gate kiosk + member pass PWAs. The gate kiosk's
 * own Dexie-backed outbox (lib/gate/sync.ts) is the primary offline queue —
 * it's what the Playwright offline-sync test exercises and what runs while
 * the tab is open. The BackgroundSyncPlugin route below is a second,
 * belt-and-suspenders layer: if the kiosk tab is closed while offline, the
 * browser itself retries any check-in POST that failed, once connectivity
 * returns, via the OS-level Background Sync API — no app code running.
 */
import { defaultCache } from "@serwist/next/worker";
import {
  BackgroundSyncPlugin,
  NetworkOnly,
  Route,
  Serwist,
  StaleWhileRevalidate,
} from "serwist";
import type { PrecacheEntry, SerwistGlobalConfig } from "serwist";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}
declare const self: ServiceWorkerGlobalScope;

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching: defaultCache,
});

const checkinsBackgroundSync = new BackgroundSyncPlugin("gate-checkins-queue", {
  // A week is generous — the app-level outbox retry loop (lib/gate/sync.ts)
  // is expected to drain the queue long before this, this is only a
  // fallback for "kiosk left offline over a long weekend".
  maxRetentionTime: 7 * 24 * 60,
});

serwist.registerRoute(
  new Route(
    ({ url, request }) =>
      request.method === "POST" && url.pathname === "/api/v1/gate/checkins:batch",
    new NetworkOnly({ plugins: [checkinsBackgroundSync] }),
    "POST"
  )
);

// Member PWA (FR-8.1): read-only GET calls the /m pages depend on get
// StaleWhileRevalidate so they still render from cache offline, refreshing
// in the background when a connection exists. Everything mutating (renew/
// booking/freeze/feedback/OTP/quick-log — any POST) is deliberately left
// unmatched here, which Workbox already treats as network-only by default.
serwist.registerRoute(
  new Route(
    ({ url, request }) =>
      request.method === "GET" &&
      (url.pathname.startsWith("/api/v1/m/pass/") ||
        url.pathname.startsWith("/api/v1/coaching/exercises") ||
        url.pathname.startsWith("/api/v1/coaching/food-items")),
    new StaleWhileRevalidate({ cacheName: "member-api-cache" }),
    "GET"
  )
);

// Offline fallback (FR-8.1): /m/offline is a static page, so it's already
// in the precache (precachePrerendered defaults to true) — this just wires
// a failed /m/** navigation to it instead of the browser's own error page.
serwist.setCatchHandler(async ({ request }) => {
  if (request.destination === "document" && new URL(request.url).pathname.startsWith("/m")) {
    const cached = await serwist.matchPrecache("/m/offline");
    if (cached) return cached;
  }
  return Response.error();
});

serwist.addEventListeners();

// Web Push (FR-6's push channel) — the backend's notifications/providers/
// push.py sends {"title", "body"} as the payload's JSON data, nothing more.
self.addEventListener("push", (event: PushEvent) => {
  const data = event.data?.json() as { title?: string; body?: string } | undefined;
  event.waitUntil(
    self.registration.showNotification(data?.title ?? "FitKhata", {
      body: data?.body ?? "",
      icon: "/icons/icon.svg",
    })
  );
});

self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("/m"));
});
