import { expect, test } from "@playwright/test";

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
