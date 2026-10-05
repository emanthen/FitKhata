import { expect, test } from "@playwright/test";

test("home page renders the marketing hero", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});
