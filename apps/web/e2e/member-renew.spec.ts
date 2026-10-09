import { execSync } from "node:child_process";
import path from "node:path";
import { devices, expect, test } from "@playwright/test";

/** Requires the real stack (make dev) running: a live Django API + Postgres
 * + Redis. Skips itself cleanly when the API isn't up, same pattern as
 * gate-offline-sync.spec.ts.
 *
 * Does NOT attempt a live eSewa sandbox round-trip (no reachable, stable
 * external dependency in CI) — it intercepts the auto-submitted redirect
 * form's own navigation request and asserts the request itself is formed
 * correctly (the right sandbox URL, the right product_code/signed fields),
 * which is entirely this app's own code. The actual gateway round-trip is
 * exercised manually/at staging, same as the "sandbox" wording implies.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_DIR = path.resolve(__dirname, "../../api");

interface Fixture {
  token: string;
  plan_id: number;
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

test("renew via eSewa sandbox builds the correct gateway redirect request", async ({ page }) => {
  test.skip(
    !(await apiIsUp()),
    `API isn't reachable at ${API_URL} — start the stack ("make dev") to run this spec.`
  );

  const fixture = seedFixture();

  let captured: { url: string; postData: string | null } | null = null;
  await page.route("https://rc-epay.esewa.com.np/**", async (route) => {
    captured = { url: route.request().url(), postData: route.request().postData() };
    await route.fulfill({ status: 200, body: "" });
  });

  await page.goto(`/m/pass/${fixture.token}`);
  await page.waitForURL("**/m");

  await page.goto("/m/renew");
  await page.locator('form button[type="submit"]').click();

  await expect.poll(() => captured !== null, { timeout: 10_000 }).toBe(true);
  expect(captured!.url).toBe("https://rc-epay.esewa.com.np/api/epay/main/v2/form");
  expect(captured!.postData).toContain("product_code=EPAYTEST");
  expect(captured!.postData).toContain("total_amount=1000.00");
});
