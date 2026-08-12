/* Section-by-section shots for the lower-page review pass. */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const iter = process.argv[2] ?? "sections";
const dir = fileURLToPath(new URL(`../.shots/${iter}/`, import.meta.url));
await mkdir(dir, { recursive: true });
const ids = ["thesis", "loop", "workspace", "audit", "capabilities", "science", "security", "download"];

const browser = await chromium.launch();
for (const [name, width, height] of [["1440x1000", 1440, 1000], ["430x932", 430, 932]]) {
  const page = await browser.newPage({ viewport: { width, height } });
  await page.goto("http://localhost:3001", { waitUntil: "networkidle" });
  for (const id of ids) {
    await page.evaluate((sid) => {
      document.getElementById(sid)?.scrollIntoView({ block: "start", behavior: "instant" });
      window.scrollBy({ top: -70, behavior: "instant" });
    }, id);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${dir}/${name}-${id}.png` });
  }
  await page.close();
}
await browser.close();
console.log("done:", dir);
