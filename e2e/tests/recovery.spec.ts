import { expect, test } from "@playwright/test";

test("recovers analysis without losing the selected workspace", async ({ page }) => {
  let failed = false;
  await page.route("**/api/analyze-location", async (route) => {
    if (!failed) {
      failed = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: { message: "temporary failure" } }) });
    } else await route.continue();
  });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Retry analysis" })).toBeVisible();
  await page.getByRole("button", { name: "Retry analysis" }).click();
  await expect(page.getByText("dari 100")).toBeVisible({ timeout: 20_000 });
});

test("offers map recovery while preserving a computed score", async ({ page }) => {
  await page.route("**/tiles/releases/*.pmtiles", (route) => route.abort("failed"));
  await page.goto("/");
  await expect(page.getByText("dari 100")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Retry map" })).toBeVisible();
  await expect(page.getByText("Location score")).toBeVisible();
});
