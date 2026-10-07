import { expect, test } from "@playwright/test";

test("keeps the location workflow usable on a phone viewport", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");

  await expect(page.getByLabel("Peta interaktif bisnis DKI Jakarta")).toBeVisible();
  await expect(page.getByText("Location score")).toBeVisible();
  await expect.poll(async () => page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))).toEqual({ clientWidth: 390, scrollWidth: 390 });

  const layers = page.getByText("Layers", { exact: true });
  const filters = page.getByText("Filters", { exact: true });
  await expect(layers).toBeVisible();
  await expect(filters).toBeVisible();

  const [layersBox, filtersBox] = await Promise.all([
    layers.boundingBox(),
    filters.boundingBox(),
  ]);
  expect(layersBox).not.toBeNull();
  expect(filtersBox).not.toBeNull();
  expect(layersBox!.x + layersBox!.width).toBeLessThanOrEqual(filtersBox!.x);

  await layers.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".layer-options").getByText("Map layers")).toBeVisible();
  await layers.click();
  await filters.click();
  await expect(page.locator(".filter-options").getByText("Opportunity filters")).toBeVisible();
  await filters.click();
  await expect(page.locator(".map-mode-badge")).toBeVisible();

  await page.getByRole("combobox", { name: "Bisnis", exact: true }).selectOption("retail");
  await expect(page.getByRole("combobox", { name: "Bisnis", exact: true })).toHaveValue("retail");

  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Opportunity analytics" })).toBeVisible();
  await page.getByRole("link", { name: "Methodology" }).click();
  await expect(page.getByRole("heading", { name: "How GeoBiz builds a score" })).toBeVisible();
  await page.getByRole("link", { name: "Map Explorer" }).click();
  await expect(page.getByLabel("Peta interaktif bisnis DKI Jakarta")).toBeVisible();
});

test("keeps resident demographics readable and selectable on a phone viewport", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await page.getByRole("link", { name: "Demographics" }).click();

  await expect(page.getByRole("heading", { name: "People behind the place." })).toBeVisible();
  await expect(page.locator(".demographics-map")).toBeVisible();
  await expect(page.locator(".demographics-island-inset svg")).toBeVisible();
  await expect(page.getByText(/gunakan daftar Kelurahan dengan keyboard/)).toBeVisible();
  await expect.poll(async () => page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))).toEqual({ clientWidth: 390, scrollWidth: 390 });

  await page.getByLabel("Fokus peta").selectOption("KAB. ADM. KEP. SERIBU");
  await expect(page.locator(".demographics-map")).toBeVisible();
  await page.locator(".demographics-map .demographics-island-marker").filter({ hasText: "PULAU TIDUNG" }).click();
  await expect(page.getByLabel("Kelurahan", { exact: true }).locator("option:checked"))
    .toHaveText("PULAU TIDUNG · KEPULAUAN SERIBU SELATAN");
  await expect(page.locator(".selected-demographic strong")).toContainText("penduduk");
  await expect.poll(() => page.locator(".selected-demographic strong").evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).fontSize),
  )).toBeGreaterThanOrEqual(28);
});
