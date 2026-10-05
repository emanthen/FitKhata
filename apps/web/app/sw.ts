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
import { BackgroundSyncPlugin, NetworkOnly, Route, Serwist } from "serwist";
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

serwist.addEventListeners();
