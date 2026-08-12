/* Final-design review shots (VISUAL_DECISION_SYSTEM section 7).
   Usage: node scripts/final-shots.mjs [iter] [url]
   Writes 1440x1000 hero / flow / thesis, 430x932 hero, ZH hero, and a
   reduced-motion hero to website/.shots/<iter>/ with computed metrics. */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const iter = process.argv[2] ?? "final";
const base = process.argv[3] ?? "http://localhost:3001";
const dir = fileURLToPath(new URL(`../.shots/${iter}/`, import.meta.url));
await mkdir(dir, { recursive: true });

/* Freeze the demo-window loop near its completed state so screenshots are
   comparable between rounds. */
const freezeCss = `
  .dw-msg,.dw-state,.dw-file,.dw-findings,.dw-pass,.dw-deliver,.demo-rounds span,.dwc::after,
  .demo-role-g::before,.demo-role-a::before{animation-duration:10000s !important;animation-delay:-9000s !important}
`;

const browser = await chromium.launch();

const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.goto(base, { waitUntil: "networkidle" });
await page.addStyleTag({ content: freezeCss });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(1400);
await page.screenshot({ path: `${dir}/hero-1440.png` });

await page.evaluate(() => {
  document.querySelector('[data-flow-step="4"]')?.scrollIntoView({ block: "center", behavior: "instant" });
});
await page.waitForTimeout(1500);
await page.screenshot({ path: `${dir}/flow-1440.png` });

await page.evaluate(() => {
  document.getElementById("thesis")?.scrollIntoView({ block: "start", behavior: "instant" });
});
await page.waitForTimeout(1100);
await page.screenshot({ path: `${dir}/thesis-1440.png` });

await page.evaluate(() => {
  document.getElementById("audit")?.scrollIntoView({ block: "start", behavior: "instant" });
});
await page.waitForTimeout(1100);
await page.screenshot({ path: `${dir}/statement-1440.png` });

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
    overflow: document.documentElement.scrollWidth > innerWidth
      ? `${document.documentElement.scrollWidth}>${innerWidth}` : "none",
    h1: probe(document.querySelector("h1")),
    sectionH2: probe(document.querySelector(".section-heading h2")),
    intro: probe(document.querySelector(".hero-intro")),
    mono: probe(document.querySelector(".hero-meta")),
    loadedFonts: [...new Set([...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family))],
  };
});
console.log("1440", JSON.stringify(metrics));

/* ZH hero at the widest viewport */
await page.evaluate(() => {
  window.scrollTo({ top: 0, behavior: "instant" });
  document.querySelector(".text-control")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
});
await page.waitForTimeout(1100);
await page.screenshot({ path: `${dir}/hero-zh-1440.png` });
await page.close();

/* mobile hero */
const mobile = await browser.newPage({ viewport: { width: 430, height: 932 } });
await mobile.goto(base, { waitUntil: "networkidle" });
await mobile.addStyleTag({ content: freezeCss });
await mobile.waitForTimeout(1300);
await mobile.screenshot({ path: `${dir}/hero-430.png` });
const mobileOverflow = await mobile.evaluate(() =>
  document.documentElement.scrollWidth > innerWidth
    ? `${document.documentElement.scrollWidth}>${innerWidth}` : "none");
console.log("430 overflow:", mobileOverflow);
await mobile.close();

/* reduced-motion settle check */
const rm = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await rm.emulateMedia({ reducedMotion: "reduce" });
await rm.goto(base, { waitUntil: "networkidle" });
await rm.waitForTimeout(800);
await rm.screenshot({ path: `${dir}/hero-reduced-1440.png` });
const settled = await rm.evaluate(() => {
  const opacity = (sel) => {
    const el = document.querySelector(sel);
    return el ? getComputedStyle(el).opacity : "missing";
  };
  const transform = (sel) => {
    const el = document.querySelector(sel);
    return el ? getComputedStyle(el).transform : "missing";
  };
  return {
    h1Line: transform(".hero-copy h1 > span"),
    intro: opacity(".hero-intro"),
    deliver: opacity(".dw-deliver"),
    statementLine: transform(".indep-statement h2 > span"),
  };
});
console.log("reduced-motion:", JSON.stringify(settled));
await rm.close();

await browser.close();
console.log("done:", dir);
