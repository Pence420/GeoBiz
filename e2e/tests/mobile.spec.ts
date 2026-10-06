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

  const layers = page.getByLabel("Map layers");
  const filters = page.getByLabel("Opportunity filters");
  await expect(layers).toBeVisible();
  await expect(filters).toBeVisible();

  const [layersBox, filtersBox] = await Promise.all([
    layers.boundingBox(),
    filters.boundingBox(),
  ]);
  expect(layersBox).not.toBeNull();
  expect(filtersBox).not.toBeNull();
  expect(layersBox!.x + layersBox!.width).toBeLessThanOrEqual(filtersBox!.x);

  const mapStatus = page.locator(".map-mode-badge");
  await expect(mapStatus).toBeVisible();
  const statusBox = await mapStatus.boundingBox();
  expect(statusBox).not.toBeNull();
  const statusOverlapsFilters = !(
    statusBox!.x + statusBox!.width <= filtersBox!.x
    || statusBox!.x >= filtersBox!.x + filtersBox!.width
    || statusBox!.y + statusBox!.height <= filtersBox!.y
    || statusBox!.y >= filtersBox!.y + filtersBox!.height
  );
  expect(statusOverlapsFilters).toBe(false);

  await page.getByRole("combobox", { name: "Bisnis", exact: true }).selectOption("retail");
  await expect(page.getByRole("combobox", { name: "Bisnis", exact: true })).toHaveValue("retail");

  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Opportunity analytics" })).toBeVisible();
  await page.getByRole("link", { name: "Methodology" }).click();
  await expect(page.getByRole("heading", { name: "How GeoBiz builds a score" })).toBeVisible();
  await page.getByRole("link", { name: "Map explorer" }).click();
  await expect(page.getByLabel("Peta interaktif bisnis DKI Jakarta")).toBeVisible();
});

test("keeps resident demographics readable and selectable on a phone viewport", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await page.getByRole("link", { name: "Demographics" }).click();

  await expect(page.getByRole("heading", { name: "People behind the place." })).toBeVisible();
  await expect(page.getByRole("img", { name: "Peta kepadatan penduduk per kelurahan Jakarta daratan" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Peta kepadatan penduduk Kepulauan Seribu" })).toBeVisible();
  await expect.poll(async () => page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))).toEqual({ clientWidth: 390, scrollWidth: 390 });

  await page.getByLabel("Fokus peta").selectOption("KAB. ADM. KEP. SERIBU");
  await expect(page.getByRole("img", { name: "Peta kepadatan penduduk per kelurahan Kepulauan Seribu" })).toBeVisible();
  await page.getByLabel("Kelurahan", { exact: true }).selectOption({ label: "PULAU TIDUNG · KEPULAUAN SERIBU SELATAN" });
  await expect(page.locator(".selected-demographic strong")).toContainText("penduduk");
});
