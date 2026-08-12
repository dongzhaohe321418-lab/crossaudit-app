/* A/B/C comparative review shots (VISUAL_DECISION_SYSTEM.md section 6).
   A = most restrained, B = most complete (current), C = most expressive. */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const dir = fileURLToPath(new URL("../.shots/abc/", import.meta.url));
await mkdir(dir, { recursive: true });
const base = "http://localhost:3001";

const freeze = `
  .dw-msg,.dw-state,.dw-file,.dw-findings,.dw-pass,.dw-deliver,.demo-rounds span,.dwc::after,
  .demo-role-g::before,.demo-role-a::before{animation-duration:10000s !important;animation-delay:-9000s !important}
`;

const variants = {
  A: `${freeze}
    .flow-events,.hero-caps,.fcb-flow,.flow-map-head i{display:none !important}
    .flow-now{display:none !important}
    .demo-shell figcaption{display:none !important}
  `,
  B: freeze,
  C: `${freeze}
    .fc-card.active{box-shadow:0 0 0 1px rgba(94,160,255,.25), 0 10px 34px rgba(31,72,138,.35) !important}
    .fc-a.active{box-shadow:0 0 0 1px rgba(154,124,255,.3), 0 10px 34px rgba(90,60,160,.35) !important}
    .fcb-main{stroke-width:3 !important}
    .demo-window{box-shadow:0 40px 110px rgba(0,0,0,.7), 0 0 0 1px rgba(94,160,255,.14), inset 0 1px 0 rgba(255,255,255,.07) !important}
    .flow-canvas{background-color:#0b0f16 !important}
  `,
};

const browser = await chromium.launch();
for (const [name, css] of Object.entries(variants)) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(base, { waitUntil: "networkidle" });
  await page.addStyleTag({ content: css });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${dir}/${name}-hero.png` });
  await page.evaluate(() => {
    document.querySelector('[data-flow-step="5"]')?.scrollIntoView({ block: "center", behavior: "instant" });
  });
  await page.waitForTimeout(1400);
  await page.screenshot({ path: `${dir}/${name}-flow.png` });
  await page.close();
}
await browser.close();
console.log("done:", dir);
