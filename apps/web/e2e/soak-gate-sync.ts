/** Soak test for the gate's outbox (lib/gate/sync.ts + db.ts): 5,000 scans
 * queued over a simulated 72-hour span with connectivity flapping on and
 * off, asserting the outbox drains completely with no duplicate and no
 * dropped rows. Not part of `pnpm test` — run explicitly with
 * `pnpm soak:gate`. Drives the real sync module against a fake IndexedDB
 * (no browser needed) and a mocked API client (no live backend needed) —
 * the actual server-side idempotency behavior this simulates is already
 * covered for real against the live API by
 * attendance/tests/test_services.py's test_batch_replay_is_idempotent_zero_new_duplicates
 * and by e2e/gate-offline-sync.spec.ts; this script's job is purely to
 * soak the client-side queue through many more cycles and volume than
 * either of those runs.
 */
import "fake-indexeddb/auto";
import { randomUUID } from "node:crypto";
import { describe, expect, it, vi } from "vitest";

// Node's built-in `navigator` global has no `onLine` — replace it with a
// controllable stand-in so sync.ts's `navigator.onLine` check actually
// reflects this script's simulated connectivity flaps.
Object.defineProperty(globalThis, "navigator", {
  value: { onLine: true },
  writable: true,
  configurable: true,
});

const serverAccepted = vi.hoisted(() => new Set<string>());

vi.mock("@fitkhata/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@fitkhata/api-client")>();
  return {
    ...actual,
    postCheckinsBatch: async (_token: string, checkins: { client_uuid: string }[]) => {
      if (!(globalThis.navigator as { onLine: boolean }).onLine) {
        throw new Error("simulated network down");
      }
      const accepted: string[] = [];
      const duplicates: string[] = [];
      for (const row of checkins) {
        if (serverAccepted.has(row.client_uuid)) {
          duplicates.push(row.client_uuid);
        } else {
          serverAccepted.add(row.client_uuid);
          accepted.push(row.client_uuid);
        }
      }
      return { accepted, duplicates, rejected: [] };
    },
  };
});

vi.mock("../lib/gate/auth", () => ({
  getDeviceAuth: () => ({ device_id: 1, gym_id: "soak-gym", token: "soak-device-token" }),
  setDeviceAuth: () => {},
  clearDeviceAuth: () => {},
}));

const TOTAL_SCANS = 5_000;
const SIMULATED_HOURS = 72;
const SCANS_PER_TICK = Math.ceil(TOTAL_SCANS / SIMULATED_HOURS);
// Offline for a stretch every 4 simulated hours — roughly a quarter of
// the 72h span spent disconnected, the kind of flap pattern a kiosk on
// unreliable power/internet would actually see.
const isOfflineTick = (hour: number) => hour % 4 === 0;

describe("gate outbox soak", () => {
  it(`drains ${TOTAL_SCANS} scans over ${SIMULATED_HOURS}h of connectivity flaps with zero duplicates or drops`, async () => {
    const { enqueueCheckin, pendingCheckins, pendingCount } = await import("../lib/gate/db");
    const { syncOutbox } = await import("../lib/gate/sync");

    let queued = 0;
    const simulatedClockStart = Date.parse("2026-10-01T00:00:00Z");

    for (let hour = 0; hour < SIMULATED_HOURS; hour++) {
      (globalThis.navigator as { onLine: boolean }).onLine = !isOfflineTick(hour);

      for (let i = 0; i < SCANS_PER_TICK && queued < TOTAL_SCANS; i++, queued++) {
        await enqueueCheckin({
          client_uuid: randomUUID(),
          member_code: "SOAK-0001",
          check_in_at: new Date(simulatedClockStart + hour * 3_600_000 + i * 1_000).toISOString(),
          source: "qr_gate",
        });
      }

      await syncOutbox();
    }

    // Drain tail: force online and keep syncing until nothing's left, with
    // a safety cap so a real regression fails the test instead of hanging.
    (globalThis.navigator as { onLine: boolean }).onLine = true;
    for (let attempt = 0; attempt < 20 && (await pendingCount()) > 0; attempt++) {
      await syncOutbox();
    }

    expect(queued).toBe(TOTAL_SCANS);
    expect(await pendingCount()).toBe(0);
    expect(serverAccepted.size).toBe(TOTAL_SCANS);

    // Nothing left unaccounted for either direction.
    expect(await pendingCheckins()).toEqual([]);
  });
});
