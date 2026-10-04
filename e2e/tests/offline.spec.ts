import { expect, test } from "@playwright/test";

test("renders the complete local map without internet", async ({ page }) => {
  const externalRequests: string[] = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "frontend") await route.continue();
    else {
      externalRequests.push(url.href);
      await route.abort("blockedbyclient");
    }
  });
  await page.goto("/");
  await expect(page.getByLabel("Peta interaktif bisnis DKI Jakarta")).toBeVisible();
  await expect(page.getByText("Offline map")).toBeVisible();
  await expect(page.getByText("Location score")).toBeVisible();
  await expect.poll(() => externalRequests).toEqual([]);
});
