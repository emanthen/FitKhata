import { execSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { expect, type Page, test } from "@playwright/test";

/** Requires the real stack (make dev) running: a live Django API + Postgres
 * + Redis at NEXT_PUBLIC_API_URL (default http://localhost:8000). This is
 * the one spec that genuinely needs it — smoke.spec.ts doesn't touch the
 * backend at all. Skips itself cleanly when the API isn't up rather than
 * failing CI runs that only start the web server.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_DIR = path.resolve(__dirname, "../../api");
const SCAN_COUNT = 500;

interface Fixture {
  gym_id: string;
  member_code: string;
  qr_secret_hex: string;
  device_id: number;
  device_token: string;
}

interface OutboxRow {
  client_uuid: string;
  member_code: string;
  check_in_at: string;
  source: "qr_gate";
}

function runManageCommand(args: string): string {
  return execSync(`uv run python manage.py ${args}`, { cwd: API_DIR, encoding: "utf-8" });
}

function seedFixture(): Fixture {
  return JSON.parse(runManageCommand("seed_gate_e2e seed").trim()) as Fixture;
}

function countAttendanceRows(memberCode: string): number {
  const output = runManageCommand(`seed_gate_e2e count --member-code=${memberCode}`);
  return (JSON.parse(output.trim()) as { count: number }).count;
}

async function apiIsUp(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/healthz`);
    return res.ok;
  } catch {
    return false;
  }
}

/** Writes rows straight into the gate's "fitkhata-gate" IndexedDB outbox
 * table — the same table lib/gate/db.ts's enqueueCheckin writes to — via
 * raw IndexedDB rather than importing app TS modules into the page. This
 * exercises exactly the sync/idempotency path the acceptance criteria is
 * about (lib/gate/sync.ts's syncOutbox, driven by useGateSync on an
 * online/interval tick) without needing to physically render 500 camera
 * frames through a mocked video device.
 */
async function seedOutbox(page: Page, rows: OutboxRow[]): Promise<void> {
  await page.evaluate(async (rows) => {
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("fitkhata-gate");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("outbox", "readwrite");
      const store = tx.objectStore("outbox");
      for (const row of rows) store.put(row);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  }, rows);
}

/** Waits until Dexie has created the "fitkhata-gate" database's schema —
 * i.e. useGateSync's first tick has run — without depending on any
 * rendered (locale-dependent) UI text. Racing a bare indexedDB.open()
 * ahead of Dexie's own first open can otherwise create the DB with no
 * object stores at all, which Dexie then never fixes (same version
 * number, so no upgrade fires on its later open).
 */
async function waitForGateDbReady(page: Page): Promise<void> {
  await page.waitForFunction(async () => {
    const databases = await indexedDB.databases();
    if (!databases.some((d) => d.name === "fitkhata-gate")) return false;
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("fitkhata-gate");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    const ready = db.objectStoreNames.contains("outbox");
    db.close();
    return ready;
  });
}

async function pendingOutboxCount(page: Page): Promise<number> {
  return page.evaluate(async () => {
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("fitkhata-gate");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    const count = await new Promise<number>((resolve, reject) => {
      const req = db.transaction("outbox", "readonly").objectStore("outbox").count();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    db.close();
    return count;
  });
}

function makeScanRows(memberCode: string, count: number): OutboxRow[] {
  const base = Date.now();
  return Array.from({ length: count }, (_, i) => ({
    client_uuid: randomUUID(),
    member_code: memberCode,
    check_in_at: new Date(base + i * 1000).toISOString(),
    source: "qr_gate" as const,
  }));
}

test("500 offline scans sync once online, then replay with zero duplicates", async ({
  page,
  context,
}) => {
  test.skip(
    !(await apiIsUp()),
    `API isn't reachable at ${API_URL} — start the stack ("make dev") to run this spec.`
  );

  const fixture = seedFixture();

  await context.addInitScript(
    ({ gymId, deviceId, token }) => {
      localStorage.setItem(
        "fitkhata.gate.device",
        JSON.stringify({ device_id: deviceId, gym_id: gymId, token })
      );
    },
    { gymId: fixture.gym_id, deviceId: fixture.device_id, token: fixture.device_token }
  );

  const rows = makeScanRows(fixture.member_code, SCAN_COUNT);

  // Load the kiosk while still online (a real kiosk is already running
  // before its network drops) — offline-page-shell caching is Serwist's
  // concern, not this spec's; this spec is about the outbox/sync logic
  // once the app is already up.
  await page.goto("/gate");
  await waitForGateDbReady(page);
  await context.setOffline(true);
  await seedOutbox(page, rows);
  expect(await pendingOutboxCount(page)).toBe(SCAN_COUNT);

  await context.setOffline(false);
  await expect
    .poll(() => pendingOutboxCount(page), { timeout: 20_000, intervals: [500] })
    .toBe(0);

  expect(countAttendanceRows(fixture.member_code)).toBe(SCAN_COUNT);

  // Replay the identical outbox: the server dedupes on client_uuid, so
  // this must land zero new rows.
  await seedOutbox(page, rows);
  await expect
    .poll(() => pendingOutboxCount(page), { timeout: 20_000, intervals: [500] })
    .toBe(0);

  expect(countAttendanceRows(fixture.member_code)).toBe(SCAN_COUNT);
});
