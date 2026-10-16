import { mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const showcaseDir = fileURLToPath(new URL("../../showcase/", import.meta.url));
const videoDir = join(tmpdir(), "geobiz-showcase-video");
const baseURL = process.env.GEOBIZ_SHOWCASE_URL ?? "http://localhost:5173";

await mkdir(showcaseDir, { recursive: true });
await mkdir(videoDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 1,
  recordVideo: { dir: videoDir, size: { width: 1600, height: 900 } },
});
const page = await context.newPage();
const video = page.video();

try {
  await page.goto(baseURL, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Peta interaktif bisnis DKI Jakarta").waitFor();
  await page.locator(".score-number").waitFor();
  await page.locator(".map-mode-badge").waitFor();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${showcaseDir}/01-map-explorer.png` });
  await page.waitForTimeout(2200);

  const search = page.getByPlaceholder(/Search Senayan/);
  await search.click();
  await search.pressSequentially("Senayan", { delay: 85 });
  const firstResult = page.getByRole("listbox", { name: "Search results" })
    .getByRole("option").first();
  await firstResult.waitFor();
  await page.waitForTimeout(850);
  await firstResult.click();
  await page.locator(".score-number").waitFor({ timeout: 30_000 });
  await page.waitForTimeout(1300);

  const inspectBusiness = page.getByRole("button", { name: /^Inspect .+ on map$/ }).first();
  await inspectBusiness.waitFor();
  await inspectBusiness.click();
  await page.locator(".business-popup").waitFor();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await page.waitForTimeout(1400);
  await page.waitForTimeout(2200);

  await page.getByRole("link", { name: "Analytics" }).click();
  await page.getByRole("heading", { name: "Opportunity analytics" }).waitFor();
  await page.waitForTimeout(1100);
  await page.screenshot({ path: `${showcaseDir}/02-analytics.png` });
  await page.waitForTimeout(3000);

  await page.getByRole("link", { name: "Demographics" }).click();
  await page.getByRole("heading", { name: "People behind the place." }).waitFor();
  await page.locator(".demographics-map").waitFor();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${showcaseDir}/03-demographics.png` });
  await page.waitForTimeout(3000);

  await page.getByRole("link", { name: "Methodology" }).click();
  await page.getByRole("heading", { name: "How GeoBiz builds a score" }).waitFor();
  await page.waitForTimeout(2600);

  await page.getByRole("link", { name: "Map Explorer" }).click();
  await page.locator(".score-number").waitFor();
  await page.waitForTimeout(2200);
} finally {
  await context.close();
  await browser.close();
}

console.log(`Screenshots: ${showcaseDir}`);
console.log(`Raw video: ${await video.path()}`);
