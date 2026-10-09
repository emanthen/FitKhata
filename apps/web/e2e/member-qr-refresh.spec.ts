import { execSync } from "node:child_process";
import path from "node:path";
import { devices, expect, test } from "@playwright/test";

/** Requires the real stack (make dev) running. Skips itself cleanly when
 * the API isn't up, same pattern as gate-offline-sync.spec.ts.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_DIR = path.resolve(__dirname, "../../api");
const WINDOW_SECONDS = 30;

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

test.use({ ...devices["Pixel 5"] });

test("the QR payload rotates every 30s window", async ({ page }) => {
  // The in-test wait below is WINDOW_SECONDS+2 (32s) on its own, which
  // already exceeds Playwright's 30s default per-test timeout before
  // accounting for setup/assertions — needs real headroom.
  test.setTimeout(60_000);
  test.skip(
    !(await apiIsUp()),
    `API isn't reachable at ${API_URL} — start the stack ("make dev") to run this spec.`
  );

  const fixture = seedFixture();

  await page.goto(`/m/pass/${fixture.token}`);
  await page.waitForURL("**/m");

  const qr = page.getByTestId("qr-payload");
  await expect(qr).toHaveAttribute("data-payload", /.+/);
  const first = await qr.getAttribute("data-payload");

  // Wait past the next WINDOW_SECONDS boundary, with margin for scheduling
  // jitter, then confirm the payload actually changed.
  await page.waitForTimeout((WINDOW_SECONDS + 2) * 1000);
  await expect.poll(() => qr.getAttribute("data-payload")).not.toBe(first);
});
