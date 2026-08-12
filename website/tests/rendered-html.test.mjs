import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the CrossAudit product story and real download path", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>CrossAudit \| Build with an agent\. Ship with evidence\.<\/title>/i);
  assert.match(html, /Build with an agent/);
  assert.match(html, /Ship with evidence/);
  assert.match(html, /See the complete path from instruction to admission/);
  assert.match(html, /AUDITED EXECUTION GRAPH/);
  assert.match(html, /Prompt and files/);
  assert.match(html, /Human admission/);
  assert.match(html, /More capability, without a busier interface/);
  assert.match(html, /Files in and out/);
  assert.equal([...html.matchAll(/<section\b/g)].length, 6);
  assert.match(html, /Download macOS/);
  assert.match(html, /dongzhaohe321418-lab\/crossaudit_v4\/releases\/latest/);
  assert.match(html, /community build is ad-hoc signed/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Your site is taking shape/i);
});

test("keeps accessibility, release fallback, and responsive safeguards in source", async () => {
  const [page, component, css, layout, packageJson] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/CrossAuditLanding.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
    readFile(new URL("app/layout.tsx", root), "utf8"),
    readFile(new URL("package.json", root), "utf8"),
  ]);

  assert.match(page, /<CrossAuditLanding \/>/);
  assert.match(component, /className="skip-link"/);
  assert.match(component, /aria-live="polite"/);
  assert.match(component, /IntersectionObserver/);
  assert.match(component, /data-reveal/);
  assert.match(component, /className="flow-scroll-layout"/);
  assert.match(component, /data-flow-step/);
  assert.match(component, /className="capability-grid"/);
  assert.match(component, /t\.flowSteps\[auditState\]/);
  assert.match(component, /api\.github\.com\/repos\/dongzhaohe321418-lab\/crossaudit_v4\/releases\/latest/);
  assert.match(component, /assets\.dmg\?\.browser_download_url \?\? RELEASES/);
  assert.match(component, /document\.documentElement\.lang/);
  assert.doesNotMatch(component, /crossaudit-site-theme|setTheme|theme-control/);
  assert.match(component, /crossaudit-workspace\.png/);
  assert.match(component, /crossaudit-workspace-1600\.png/);
  assert.match(component, /crossaudit-audit\.png/);
  assert.match(component, /crossaudit-audit-1600\.png/);
  assert.match(component, /width=\{2704\}\s+height=\{1824\}/);
  assert.match(component, /srcSet=/);
  assert.doesNotMatch(component, /from "next\/image"/);
  assert.doesNotMatch(component, /[—–]/);
  assert.doesNotMatch(component, /demo-topbar|window-dots|fake terminal/i);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /@keyframes flow-detail-in/);
  assert.match(css, /@keyframes flow-scan/);
  assert.match(css, /\.flow-map-sticky/);
  assert.match(css, /\.flow-node\.active/);
  assert.match(css, /\[data-reveal\]\.is-visible/);
  assert.match(css, /prefers-reduced-transparency:\s*reduce/);
  assert.match(css, /prefers-contrast:\s*more/);
  assert.doesNotMatch(css, /data-theme="light"|color-scheme:\s*light/);
  assert.match(css, /@media \(max-width: 34rem\)/);
  assert.match(layout, /openGraph:/);
  assert.match(layout, /https:\/\/crossaudit-v4\.vercel\.app/);
  assert.match(layout, /Space_Grotesk/);
  assert.match(layout, /DM_Sans/);
  assert.match(layout, /IBM_Plex_Mono/);
  assert.match(layout, /<html[\s\S]*className=/);
  assert.doesNotMatch(layout, /codex-preview|Starter Project/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
