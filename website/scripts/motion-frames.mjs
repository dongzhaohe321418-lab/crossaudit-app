/* Hero demo-window loop, sampled as a deterministic frame sequence.
   Every 11 s loop animation is paused via the Web Animations API with an
   exact currentTime, so each frame is a precise point of the supervised run.
   Frames land in website/.shots/motion/.
   Usage: node scripts/motion-frames.mjs [url] */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const base = process.argv[2] ?? "http://localhost:3001";
const dir = fileURLToPath(new URL("../.shots/final-motion/", import.meta.url));
await mkdir(dir, { recursive: true });

/* [seconds into the loop, label] */
const frames = [
  [0.3, "01-prompt-arrives"],
  [1.0, "02-understanding"],
  [2.8, "03-working-file"],
  [5.0, "04-auditor-findings"],
  [7.0, "05-revising"],
  [8.6, "06-second-check"],
  [9.9, "07-review-passed"],
  [10.5, "08-deliverable"],
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.goto(base, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(900);

const box = await page.locator(".demo-window").boundingBox();
for (const [t, label] of frames) {
  await page.evaluate((seconds) => {
    for (const animation of document.getAnimations()) {
      const timing = animation.effect?.getTiming();
      if (timing?.duration === 11000) {
        animation.pause();
        animation.currentTime = seconds * 1000;
      }
    }
  }, t);
  await page.waitForTimeout(120);
  await page.screenshot({
    path: `${dir}/${label}.png`,
    clip: { x: box.x - 12, y: box.y - 12, width: box.width + 24, height: box.height + 24 },
  });
}
await browser.close();
console.log("done:", dir);
