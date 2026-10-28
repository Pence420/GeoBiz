import { mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright";

const videoDir = join(tmpdir(), "geobiz-map-demo-video");
const baseURL = process.env.GEOBIZ_SHOWCASE_URL ?? "http://localhost:5173";

await mkdir(videoDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 1,
  recordVideo: { dir: videoDir, size: { width: 1600, height: 900 } },
});
const page = await context.newPage();
const video = page.video();

async function waitForLocationScore() {
  await page.locator(".score-number").waitFor({ timeout: 30_000 });
  await page.waitForTimeout(450);
}

try {
  await page.goto(baseURL, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Peta interaktif bisnis DKI Jakarta").waitFor();
  await page.locator(".map-mode-badge").waitFor();
  await waitForLocationScore();
  await page.waitForTimeout(1100);

  await page.getByText("Layers", { exact: true }).click();
  const layerOptions = page.locator(".layer-options");
  await page.waitForTimeout(750);
  await layerOptions.getByLabel("Competitors").uncheck();
  await page.waitForTimeout(800);
  await layerOptions.getByLabel("Transit").check();
  await page.waitForTimeout(800);
  await layerOptions.getByLabel("Population").check();
  await page.waitForTimeout(950);
  await page.getByText("Layers", { exact: true }).click();
  await page.waitForTimeout(800);

  await page.getByText("Filters", { exact: true }).click();
  await page.waitForTimeout(750);
  const filterOptions = page.locator(".filter-options");
  await filterOptions.getByLabel("Minimum score").selectOption("60");
  await page.waitForTimeout(900);
  await filterOptions.getByLabel("Population").selectOption("10000");
  await page.waitForTimeout(1000);
  await page.getByText("Filters", { exact: true }).click();
  await page.waitForTimeout(1600);
} finally {
  await context.close();
  await browser.close();
}

console.log(`Raw map demo video: ${await video.path()}`);
