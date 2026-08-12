/* Typography direction review shots (VISUAL_DECISION_SYSTEM sections 6-7).
   Three complete directions rendered from the same build:
     a = Apple system stack   b = Space Grotesk + DM Sans   c = Geist at full intent
   Usage: node scripts/type-shots.mjs [url]
   Writes 1440x1000 hero / flow / thesis PNGs to website/.shots/type-<v>/
   and prints computed font metrics for each direction. */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3001";

/* Freeze the demo-window loop near its completed state so screenshots are
   comparable between directions. */
const freezeCss = `
  .dw-msg,.dw-state,.dw-file,.dw-findings,.dw-pass,.dw-deliver,.demo-rounds span,.dwc::after,
  .demo-role-g::before,.demo-role-a::before{animation-duration:10000s !important;animation-delay:-9000s !important}
`;

const browser = await chromium.launch();
for (const variant of ["a", "b", "c"]) {
  const dir = fileURLToPath(new URL(`../.shots/type-${variant}/`, import.meta.url));
  await mkdir(dir, { recursive: true });

  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${base}/?type=${variant}`, { waitUntil: "networkidle" });
  await page.addStyleTag({ content: freezeCss });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1300);
  await page.screenshot({ path: `${dir}/hero.png` });

  await page.evaluate(() => {
    document.querySelector('[data-flow-step="4"]')?.scrollIntoView({ block: "center", behavior: "instant" });
  });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${dir}/flow.png` });

  await page.evaluate(() => {
    document.getElementById("thesis")?.scrollIntoView({ block: "start", behavior: "instant" });
  });
  await page.waitForTimeout(1100);
  await page.screenshot({ path: `${dir}/thesis.png` });

  const metrics = await page.evaluate(() => {
    const probe = (el) => {
      if (!el) return null;
      const s = getComputedStyle(el);
      return {
        family: s.fontFamily.split(",")[0],
        size: s.fontSize,
        weight: s.fontWeight,
        tracking: s.letterSpacing,
        lineHeight: s.lineHeight,
      };
    };
    return {
      variant: document.documentElement.getAttribute("data-type-variant") ?? "a(default)",
      overflow: document.documentElement.scrollWidth > innerWidth
        ? `${document.documentElement.scrollWidth}>${innerWidth}` : "none",
      h1: probe(document.querySelector("h1")),
      sectionH2: probe(document.querySelector(".section-heading h2")),
      intro: probe(document.querySelector(".hero-intro")),
      mono: probe(document.querySelector(".hero-meta")),
      loadedFonts: [...new Set([...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family))],
    };
  });
  console.log(`type-${variant}`, JSON.stringify(metrics));
  await page.close();
}
await browser.close();
console.log("done");
