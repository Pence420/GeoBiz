import { expect, test } from "@playwright/test";

test("shows release-scoped analytics and methodology", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Opportunity analytics" })).toBeVisible();
  await expect(page.getByText("Subtype composition")).toBeVisible();
  await expect(page.getByText(/267 representative observations/)).toBeVisible();
  await expect(page.getByText(/Release .*taxonomy v2\.0\.0/)).toBeVisible();
  await expect(page.getByText(/^Revenue$/i)).toHaveCount(0);

  await page.getByRole("link", { name: "Methodology" }).click();
  await expect(page.getByRole("heading", { name: "How GeoBiz builds a score" })).toBeVisible();
  await expect(page.getByText("Umbrella taxonomy mappings")).toBeVisible();
  await expect(page.getByText("OpenStreetMap").first()).toBeVisible();
  await expect(page.getByText(/ODbL|Open Database License/).first()).toBeVisible();
  await expect(page.getByText("PMTiles SHA-256")).toBeVisible();
  await expect(page.locator(".view-provenance").getByText(/dataset fingerprint/)).toBeVisible();
  await expect(page.getByText("Interpretation limits")).toBeVisible();
});
