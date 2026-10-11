import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

type TestMap = {
  getLayer: (layerId: string) => unknown;
  getZoom: () => number;
  isMoving: () => boolean;
  project: (coordinates: [number, number]) => { x: number; y: number };
  queryRenderedFeatures: (
    point: { x: number; y: number },
    options: { layers: string[] },
  ) => Array<{ properties?: { name?: string } }>;
};

async function clickRenderedPoint(
  page: Page,
  layerId: string,
  coordinates: [number, number],
  name: string,
) {
  const canvas = page.locator(".map-canvas");
  await expect.poll(() => canvas.evaluate((element, args) => {
    const map = (element as HTMLDivElement & { __geobizMap?: TestMap }).__geobizMap;
    if (!map || !map.getLayer(args.layerId) || map.isMoving()) return false;
    const point = map.project(args.coordinates);
    return map.queryRenderedFeatures(point, { layers: [args.layerId] })
      .some((feature) => feature.properties?.name === args.name);
  }, { layerId, coordinates, name }), { timeout: 20_000 }).toBe(true);
  const position = await canvas.evaluate((element, pointCoordinates) =>
    (element as HTMLDivElement & { __geobizMap: TestMap }).__geobizMap.project(pointCoordinates),
  coordinates);
  await canvas.click({ position });
}

test("expands an education cluster without changing the analysis location", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.route("**/api/businesses?**", (route) => route.fulfill({ json: {
    type: "FeatureCollection", features: [],
  } }));
  await page.route("**/api/layers/points?layer=education&limit=10000", (route) => route.fulfill({ json: {
    type: "FeatureCollection",
    features: ["Test School A", "Test School B"].map((name, index) => ({
      type: "Feature",
      id: 920001 + index,
      geometry: { type: "Point", coordinates: [106.8372, -6.1854] },
      properties: { name, item_type: "school", source_record_id: String(920001 + index) },
    })),
  } }));
  await page.goto("/");
  await page.getByText("Layers", { exact: true }).click();
  await Promise.all([
    page.waitForResponse((response) => response.url().includes("/api/layers/points?layer=education")),
    page.locator(".layer-options").getByLabel("Education").check(),
  ]);
  await page.getByText("Layers", { exact: true }).click();
  const canvas = page.locator(".map-canvas");
  const coordinates: [number, number] = [106.8372, -6.1854];
  await expect.poll(() => canvas.evaluate((element, pointCoordinates) => {
    const map = (element as HTMLDivElement & { __geobizMap?: TestMap }).__geobizMap;
    if (!map || !map.getLayer("education-clusters") || map.isMoving()) return false;
    const point = map.project(pointCoordinates);
    return map.queryRenderedFeatures(point, { layers: ["education-clusters"] })
      .some((feature) => Number((feature.properties as { point_count?: number })?.point_count) === 2);
  }, coordinates), { timeout: 20_000 }).toBe(true);
  const { position, zoomBefore } = await canvas.evaluate((element, pointCoordinates) => {
    const map = (element as HTMLDivElement & { __geobizMap: TestMap }).__geobizMap;
    return { position: map.project(pointCoordinates), zoomBefore: map.getZoom() };
  }, coordinates);
  await canvas.click({ position });
  await expect.poll(() => canvas.evaluate((element) =>
    (element as HTMLDivElement & { __geobizMap: TestMap }).__geobizMap.getZoom(),
  )).toBeGreaterThan(zoomBefore);
  await expect(page.locator(".map-hint strong")).toContainText("-6.17540, 106.82720");
});

test("completes the DKI map exploration journey", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await expect(page.getByLabel("Peta interaktif bisnis DKI Jakarta")).toBeVisible();
  const business = page.getByRole("combobox", { name: "Bisnis", exact: true });
  for (const category of ["fnb", "retail", "services"]) {
    await business.selectOption(category);
    await expect(business).toHaveValue(category);
  }
  await business.selectOption("fnb");

  const search = page.getByPlaceholder(/Search Senayan/);
  await search.fill("Senayan");
  const result = page.getByRole("listbox", { name: "Search results" }).getByRole("option").first();
  await expect(result).toBeVisible({ timeout: 20_000 });
  await result.click();
  await expect(search).toHaveValue(/SENAYAN/i);

  await page.getByRole("button", { name: /^Inspect .+ on map$/ }).first().click();
  await expect(page.locator(".business-popup")).toContainText("OSM");

  const radius = page.getByRole("combobox", { name: "Radius", exact: true });
  await radius.selectOption("2000");
  await expect(radius).toHaveValue("2000");
  await page.getByText("Layers", { exact: true }).click();
  const toggles = page.locator(".layer-options").getByRole("checkbox");
  for (let index = 0; index < await toggles.count(); index += 1) {
    await toggles.nth(index).check();
  }
  await page.getByText("Layers", { exact: true }).click();
  await page.getByText("Filters", { exact: true }).click();
  await page.locator(".filter-options").getByLabel("Minimum score").selectOption("40");
  await page.getByText("Filters", { exact: true }).click();

  const compare = page.getByRole("checkbox", { name: /^Compare / });
  await expect(compare.first()).toBeVisible({ timeout: 30_000 });
  await compare.nth(0).check();
  await compare.nth(1).check();
  await compare.nth(2).check();
  await expect(compare.nth(3)).toBeDisabled();
  await expect(page.getByLabel("Area comparison")).toContainText("3/3 pinned");
});

test("keeps the dashboard within desktop and tablet viewport widths", async ({ page }) => {
  await page.goto("/");
  for (const viewport of [{ width: 1440, height: 900 }, { width: 768, height: 1024 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByLabel("Peta interaktif bisnis DKI Jakarta")).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("opens a competitor from a cluster without changing the analysis location", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.route("**/api/businesses?**", async (route) => {
    const features = ["Burger King", "McDonald's"].map((name, index) => ({
      type: "Feature",
      id: 900001 + index,
      geometry: { type: "Point", coordinates: [106.8372, -6.1854] },
      properties: {
        name,
        category: "fnb",
        source_type: "node",
        source_record_id: String(900001 + index),
        business_subtype: "fast_food",
        taxonomy_version: "v2.0.0",
      },
    }));
    await route.fulfill({ json: { type: "FeatureCollection", features } });
  });
  await page.goto("/");
  await expect(page.getByText(/2 titik peta/)).toBeVisible();
  await expect(page.locator(".score-number")).toBeVisible({ timeout: 30_000 });
  const selectedLocation = page.locator(".map-hint strong");
  await expect(selectedLocation).toContainText("-6.17540, 106.82720");
  const before = await selectedLocation.innerText();
  const canvas = page.locator(".maplibregl-canvas");
  await expect(canvas).toBeVisible();
  await page.getByRole("button", { name: "Reset Jakarta" }).click();
  await page.waitForTimeout(700);
  const bounds = await canvas.boundingBox();
  expect(bounds).not.toBeNull();
  await canvas.click({ position: { x: bounds!.width / 2 + 24, y: bounds!.height / 2 - 35 } });
  await expect(selectedLocation).toHaveText(before);
  await page.waitForTimeout(700);
  await canvas.click({ position: { x: bounds!.width / 2, y: bounds!.height / 2 } });
  await expect(page.locator(".business-popup")).toContainText(/Burger King|McDonald's/);
  await expect(selectedLocation).toHaveText(before);
});

for (const layer of [
  { id: "transport", label: "Transit", itemType: "bus_stop" },
  { id: "commercial", label: "Commercial", itemType: "marketplace" },
  { id: "education", label: "Education", itemType: "school" },
  { id: "office", label: "Offices", itemType: "office" },
] as const) {
  test(`opens a point in ${layer.id} without changing the analysis location`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.route("**/api/businesses?**", (route) => route.fulfill({ json: {
      type: "FeatureCollection", features: [],
    } }));
    const name = `Test ${layer.label} Point`;
    await page.route(`**/api/layers/points?layer=${layer.id}&limit=10000`, async (route) => {
      await route.fulfill({ json: {
        type: "FeatureCollection",
        features: [{
          type: "Feature",
          id: 910001,
          geometry: { type: "Point", coordinates: [106.8372, -6.1854] },
          properties: { name, item_type: layer.itemType, source_record_id: "910001" },
        }],
      } });
    });
    await page.goto("/");
    await expect(page.getByText(/0 titik peta/)).toBeVisible({ timeout: 30_000 });
    await page.getByText("Layers", { exact: true }).click();
    await Promise.all([
      page.waitForResponse((response) => response.url().includes(`/api/layers/points?layer=${layer.id}`)),
      page.locator(".layer-options").getByLabel(layer.label).check(),
    ]);
    await page.getByText("Layers", { exact: true }).click();
    const selectedLocation = page.locator(".map-hint strong");
    await expect(selectedLocation).toContainText("-6.17540, 106.82720");
    await clickRenderedPoint(page, `${layer.id}-points`, [106.8372, -6.1854], name);
    await expect(page.locator(".point-popup")).toContainText(name);
    await expect(page.locator(".point-popup")).toContainText("OSM ID 910001");
    await expect(selectedLocation).toContainText("-6.17540, 106.82720");
  });
}

test("keeps a competitor point visible after business data loads", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.route("**/api/businesses?**", async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    await route.fulfill({ json: {
      type: "FeatureCollection",
      features: offset === 0 ? [{
        type: "Feature",
        id: 900001,
        geometry: { type: "Point", coordinates: [106.8372, -6.1854] },
        properties: {
          name: "Test Competitor",
          category: "fnb",
          source_type: "node",
          source_record_id: "900001",
          business_subtype: "cafe",
          taxonomy_version: "v2.0.0",
        },
      }] : [],
    } });
  });
  await page.goto("/");
  await expect(page.getByText(/1 titik peta/)).toBeVisible({ timeout: 30_000 });
  const selectedLocation = page.locator(".map-hint strong");
  await expect(selectedLocation).toContainText("-6.17540, 106.82720");
  await clickRenderedPoint(page, "business-points", [106.8372, -6.1854], "Test Competitor");
  await expect(page.locator(".business-popup")).toContainText("Test Competitor");
  await expect(selectedLocation).toContainText("-6.17540, 106.82720");
});

test("switches competitor category without leaving the old popup", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.route("**/api/businesses?**", async (route) => {
    const url = new URL(route.request().url());
    const category = url.searchParams.get("category");
    const offset = Number(url.searchParams.get("offset"));
    await route.fulfill({ json: {
      type: "FeatureCollection",
      features: offset === 0 ? [{
        type: "Feature",
        id: category === "fnb" ? 900001 : category === "retail" ? 900002 : 900003,
        geometry: { type: "Point", coordinates: [106.8372, -6.1854] },
        properties: {
          name: `Test ${category} Business`,
          category,
          source_type: "node",
          source_record_id: "900001",
          business_subtype: "shop",
          taxonomy_version: "v2.0.0",
        },
      }] : [],
    } });
  });
  await page.goto("/");
  const categoryControl = page.getByRole("combobox", { name: "Bisnis", exact: true });
  for (const category of ["fnb", "retail", "services"] as const) {
    if (category !== "fnb") {
      await categoryControl.selectOption(category);
      await expect(page.locator(".business-popup")).toHaveCount(0);
    }
    const name = `Test ${category} Business`;
    await clickRenderedPoint(page, "business-points", [106.8372, -6.1854], name);
    await expect(page.locator(".business-popup")).toContainText(name);
  }
});
