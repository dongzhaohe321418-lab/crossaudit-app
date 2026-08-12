/* Screenshot harness for the visual-review loop.
   Usage: node scripts/shots.mjs iter-1 [url]
   Writes PNGs to website/.shots/<iter>/ and prints overflow + font metrics. */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const iter = process.argv[2] ?? "iter-0";
const base = process.argv[3] ?? "http://localhost:3001";
const dir = fileURLToPath(new URL(`../.shots/${iter}/`, import.meta.url));
await mkdir(dir, { recursive: true });

const viewports = [
  ["1440x1000", 1440, 1000],
  ["1280x900", 1280, 900],
  ["1024x768", 1024, 768],
  ["430x932", 430, 932],
];

/* Freeze the demo-window loop near its completed state so screenshots are
   comparable between rounds. */
const freezeCss = `
  .dw-msg,.dw-state,.dw-file,.dw-findings,.dw-pass,.dw-deliver,.demo-rounds span,.dwc::after,
  .demo-role-g::before,.demo-role-a::before{animation-duration:10000s !important;animation-delay:-9000s !important}
`;

const browser = await chromium.launch();
for (const [name, width, height] of viewports) {
  const page = await browser.newPage({ viewport: { width, height } });
  await page.goto(base, { waitUntil: "networkidle" });
  await page.addStyleTag({ content: freezeCss });
  await page.waitForTimeout(1300);
  await page.screenshot({ path: `${dir}/${name}-1-hero.png` });

  await page.evaluate(() => {
    document.querySelector('[data-flow-step="4"]')?.scrollIntoView({ block: "center", behavior: "instant" });
  });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${dir}/${name}-2-flow.png` });

  if (width === 1440) {
    /* extended matrix at the widest viewport: ZH and Reduce Motion */
    await page.evaluate(() => {
      window.scrollTo({ top: 0, behavior: "instant" });
      document.querySelector(".text-control")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${dir}/${name}-3-hero-zh.png` });
    await page.evaluate(() => {
      document.querySelector(".text-control")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    await page.screenshot({ path: `${dir}/${name}-4-hero-reduced.png` });
    await page.emulateMedia({ reducedMotion: "no-preference" });
  }

  const metrics = await page.evaluate(() => {
    const h1 = document.querySelector("h1");
    const mono = document.querySelector(".hero-meta") ?? document.querySelector("code");
    const probe = (el) => {
      if (!el) return null;
      const s = getComputedStyle(el);
      return { family: s.fontFamily.split(",")[0], size: s.fontSize, weight: s.fontWeight };
    };
    return {
      overflow: document.documentElement.scrollWidth > innerWidth
        ? `${document.documentElement.scrollWidth}>${innerWidth}` : "none",
      body: probe(document.body),
      h1: probe(h1),
      mono: probe(mono),
      loadedFonts: [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family),
    };
  });
  console.log(name, JSON.stringify(metrics));
  await page.close();
}
await browser.close();
console.log("done:", dir);
