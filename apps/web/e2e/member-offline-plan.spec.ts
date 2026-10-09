import { execSync } from "node:child_process";
import path from "node:path";
import { devices, expect, test } from "@playwright/test";

/** Requires the real stack (make dev) running. Skips itself cleanly when
 * the API isn't up, same pattern as gate-offline-sync.spec.ts.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_DIR = path.resolve(__dirname, "../../api");

interface Fixture {
  token: string;
}

function seedFixture(): Fixture {
  const output = execSync("uv run python manage.py seed_member_e2e seed", {
    cwd: API_DIR,
    encoding: "utf-8",
  });
  return JSON.parse(output.trim()) as Fixture;
}

async function apiIsUp(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/healthz`);
    return res.ok;
  } catch {
    return false;
  }
}

/** Waits until Dexie has created the "fitkhata-member" database's
 * "workoutPlan" table — same waiting idiom as gate-offline-sync.spec.ts's
 * waitForGateDbReady, pointed at the member DB instead.
 */
async function waitForMemberDbReady(page: import("@playwright/test").Page): Promise<void> {
  await page.waitForFunction(async () => {
    const databases = await indexedDB.databases();
    if (!databases.some((d) => d.name === "fitkhata-member")) return false;
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("fitkhata-member");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    const ready = db.objectStoreNames.contains("workoutPlan");
    db.close();
    return ready;
  });
}

test.use({ ...devices["Pixel 5"] });

test("the assigned workout plan renders from cache while offline", async ({ page, context }) => {
  test.skip(
    !(await apiIsUp()),
    `API isn't reachable at ${API_URL} — start the stack ("make dev") to run this spec.`
  );

  const fixture = seedFixture();

  await page.goto(`/m/pass/${fixture.token}`);
  await page.waitForURL("**/m");

  // Load the plan page once online so lib/member/db.ts's write-through
  // cache populates — offline-page-shell precaching is Serwist's concern
  // (covered by sw.ts's catch handler), not this spec's.
  await page.goto("/m/coaching");
  await waitForMemberDbReady(page);
  const exerciseRow = page.getByTestId("workout-exercise").first();
  await expect(exerciseRow).toBeVisible();
  const onlineText = await exerciseRow.textContent();

  await context.setOffline(true);
  await page.reload();

  const offlineExerciseRow = page.getByTestId("workout-exercise").first();
  await expect(offlineExerciseRow).toBeVisible();
  expect(await offlineExerciseRow.textContent()).toBe(onlineText);
});
