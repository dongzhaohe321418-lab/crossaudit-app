"""The local CrossAudit workspace.

One centre of gravity: conversation and deliverables.  A narrow left rail
holds pins, recent chats and search; the centre is one chronological run that
narrates six user-visible states (understanding, working, checking, revising,
completed, needs your decision) projected from typed run-journal events; a
right context panel surfaces files, audit evidence, models, usage and compute
on demand.  The ledger remains the source of truth; the page only reshapes
committed evidence and ephemeral in-flight progress, and the independent
review stays collapsed until the person asks for the full record.

There is still one task write path. The composer uploads explicitly confirmed
files in bounded chunks, then posts only one opaque batch ID to ``/api/say``;
every task is routed through the same code as ``crossaudit talk``. Generated
files are downloadable only when the ledger's generator history names that
exact project-relative path.
"""
from __future__ import annotations

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CrossAudit</title>
<style>
/* CrossAudit console design system.
   Dark is the primary visual; light is a complete first-class variant.
   One centre of gravity: conversation and deliverables. Glass is reserved
   for navigation and transient chrome; work, evidence and deliverables stay
   on calm opaque surfaces so the audit record remains legible. */
:root,:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#0C0F14;--panel:rgba(19,24,32,.72);--surface:#161B23;--surface-2:#1E242E;
  --surface-3:#262D39;--text:#EDF0F5;--text-2:#A6AEBB;--text-3:#6E7684;
  --line:rgba(228,237,248,.09);--line-strong:rgba(228,237,248,.18);
  --hover:rgba(148,178,224,.10);--scrim-bg:rgba(6,9,14,.52);
  --state-understand:#98A1B0;--state-understand-bg:rgba(152,161,176,.12);
  --state-work:#6CA8F8;--state-work-bg:rgba(108,168,248,.14);
  --state-check:#AD97F4;--state-check-bg:rgba(173,151,244,.14);
  --state-revise:#5EC4DE;--state-revise-bg:rgba(94,196,222,.13);
  --state-done:#57C795;--state-done-bg:rgba(87,199,149,.13);
  --state-decide:#E9B45C;--state-decide-bg:rgba(233,180,92,.14);
  --pass:#57C795;--pass-bg:rgba(87,199,149,.13);
  --blocked:#F27E72;--blocked-bg:rgba(242,126,114,.14);
  --escalated:#E9B45C;--escalated-bg:rgba(233,180,92,.14);
  --role-g:#6CA8F8;--role-g-bg:rgba(108,168,248,.14);
  --role-a:#AD97F4;--role-a-bg:rgba(173,151,244,.14);
  --accent:#6CA8F8;--accent-bg:rgba(108,168,248,.14);
  --shadow-1:0 1px 2px rgba(4,8,16,.28);
  --shadow-2:0 2px 6px rgba(4,8,16,.28),0 8px 24px rgba(4,8,16,.24);
  --shadow-3:0 4px 12px rgba(3,6,12,.32),0 16px 48px rgba(3,6,12,.30);
  --shadow-4:0 8px 24px rgba(2,4,10,.38),0 32px 90px rgba(2,4,10,.34);
  --edge-highlight:inset 0 1px 0 rgba(255,255,255,.07);
  --glass-nav-bg:rgba(19,24,32,.72);--glass-sheet-bg:rgba(22,27,36,.80);
  --glass-palette-bg:rgba(24,30,39,.86);--glass-border:rgba(255,255,255,.09);
  --tint-a:rgba(82,151,255,.10);--tint-b:rgba(139,112,226,.07);
  /* Legacy aliases: ported flows resolve to the same token system. */
  --muted:var(--text-2);--faint:var(--text-3);
  --blue:var(--accent);--blue-bg:var(--accent-bg);
  --green:var(--pass);--green-bg:var(--pass-bg);
  --red:var(--blocked);--red-bg:var(--blocked-bg);
  --amber:var(--escalated);--amber-bg:var(--escalated-bg);
  --violet:var(--role-a);--violet-bg:var(--role-a-bg);
  --header-bg:var(--glass-nav-bg);--audit-border:rgba(173,151,244,.20);
  --glass:var(--glass-nav-bg);--glass-strong:var(--surface-2);
  --glass-edge:var(--glass-border);
  --glass-shadow:var(--edge-highlight),var(--shadow-3);
  --shadow:var(--shadow-2);--inverse:#EDF0F5;--inverse-text:#161B23;
  --send-hover:color-mix(in srgb,var(--accent) 86%,#fff);
  --font-ui:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display","Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  --font-mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --fs-caption:0.6875rem;--fs-label:0.75rem;--fs-body:0.8125rem;--fs-prose:0.875rem;
  --fs-title:0.9375rem;--fs-h2:1.125rem;--fs-h1:1.375rem;--fs-display:1.75rem;
  --sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-5:20px;--sp-6:24px;
  --sp-7:32px;--sp-8:40px;--sp-9:56px;--sp-10:72px;
  --r-xs:6px;--r-sm:8px;--r-md:10px;--r-lg:14px;--r-xl:18px;--r-pill:999px;
  --radius:var(--r-lg);
  --dur-instant:100ms;--dur-fast:180ms;--dur-base:240ms;--dur-slow:320ms;--dur-story:480ms;
  --ease-out:cubic-bezier(0.16,1,0.3,1);--ease-in:cubic-bezier(0.55,0,0.85,0.4);
  --spring:cubic-bezier(0.22,0.9,0.28,1);--spring-soft:cubic-bezier(0.3,1.12,0.3,1);
  --rail-w:264px;--ctx-w:320px;--topbar-h:52px;--thread-max:760px;
  --sidebar:var(--rail-w);--inspector:0px;--topbar-height:var(--topbar-h);
  --z-content:1;--z-chrome:40;--z-composer:50;--z-overlay:100;
  --z-sheet:60;--z-palette:80;--z-toast:90;
}
:root[data-theme="light"]{
  color-scheme:light;
  --bg:#EEF1F6;--panel:rgba(248,250,253,.74);--surface:#FFFFFF;--surface-2:#F2F5F9;
  --surface-3:#E8ECF2;--text:#1A1F27;--text-2:#5C6472;--text-3:#8C94A2;
  --line:rgba(52,64,84,.11);--line-strong:rgba(52,64,84,.22);
  --hover:rgba(38,92,178,.07);--scrim-bg:rgba(18,24,34,.38);
  --state-understand:#5F6875;--state-understand-bg:rgba(95,104,117,.10);
  --state-work:#2266D4;--state-work-bg:rgba(34,102,212,.10);
  --state-check:#6A4FC9;--state-check-bg:rgba(106,79,201,.10);
  --state-revise:#0E7E9E;--state-revise-bg:rgba(14,126,158,.10);
  --state-done:#177A53;--state-done-bg:rgba(23,122,83,.10);
  --state-decide:#96650E;--state-decide-bg:rgba(150,101,14,.10);
  --pass:#177A53;--pass-bg:rgba(23,122,83,.10);
  --blocked:#C33D33;--blocked-bg:rgba(195,61,51,.10);
  --escalated:#96650E;--escalated-bg:rgba(150,101,14,.10);
  --role-g:#2266D4;--role-g-bg:rgba(34,102,212,.10);
  --role-a:#6A4FC9;--role-a-bg:rgba(106,79,201,.10);
  --accent:#2266D4;--accent-bg:rgba(34,102,212,.10);
  --shadow-1:0 1px 2px rgba(38,50,70,.08);
  --shadow-2:0 2px 6px rgba(38,50,70,.07),0 8px 24px rgba(38,50,70,.07);
  --shadow-3:0 4px 12px rgba(30,42,62,.09),0 16px 48px rgba(30,42,62,.10);
  --shadow-4:0 8px 24px rgba(24,34,52,.12),0 32px 90px rgba(24,34,52,.14);
  --edge-highlight:inset 0 1px 0 rgba(255,255,255,.70);
  --glass-nav-bg:rgba(248,250,253,.74);--glass-sheet-bg:rgba(250,252,254,.82);
  --glass-palette-bg:rgba(252,253,255,.88);--glass-border:rgba(255,255,255,.65);
  --tint-a:rgba(73,145,246,.09);--tint-b:rgba(134,107,217,.06);
  --audit-border:rgba(106,79,201,.20);
  --inverse:#1A1F27;--inverse-text:#FFFFFF;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0;height:100%;overflow:hidden}
html{background:var(--bg)}
body{color:var(--text);background:
  radial-gradient(72% 62% at 88% -8%,var(--tint-a),transparent 66%),
  radial-gradient(55% 54% at -8% 96%,var(--tint-b),transparent 70%),var(--bg);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",
    "Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  font-size:13px;line-height:1.55;font-optical-sizing:auto;-webkit-font-smoothing:antialiased}
button,textarea,input,select{font:inherit;color:inherit}
button{cursor:pointer}
button,input,select,textarea{-webkit-tap-highlight-color:transparent;touch-action:manipulation}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,
a:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0,0,0,0);white-space:nowrap;border:0}
.spacer{margin-left:auto}
::selection{background:var(--accent-bg)}

/* A single outline icon language avoids font-dependent symbols in application chrome. */
.ui-icon,#hub-settings,#settings-open,#hub-theme,#theme-toggle,#sidebar-toggle,#back-projects,
#current-project-pin,#inspect-toggle,#inspect-close,#palette-open,.pin-button,.project-pin,.nav-icon,
.new-task>span:first-child,.hpc-host-intro-icon,.project-delete,.task-delete,.project-arrow,
[data-preview].artifact-action,.artifact-action[download],.pill-glyph,.review-mark,.review-chevron,
.deliverable-icon,.group-chevron,.decision-glyph,.banner-glyph,.rail-search-icon,.attach-glyph,
.send-glyph,.stop-glyph{font-size:0}
.ui-icon:before,#hub-settings:before,#settings-open:before,#hub-theme:before,#theme-toggle:before,
#sidebar-toggle:before,#back-projects:before,#current-project-pin:before,#inspect-toggle:before,
#inspect-close:before,#palette-open:before,.pin-button:before,.project-pin:before,.nav-icon:before,
.new-task>span:first-child:before,.hpc-host-intro-icon:before,.project-delete:before,
.task-delete:before,.project-arrow:before,[data-preview].artifact-action:before,
.artifact-action[download]:before,.pill-glyph:before,.review-mark:before,.review-chevron:before,
.deliverable-icon:before,.group-chevron:before,.decision-glyph:before,.banner-glyph:before,
.rail-search-icon:before,.attach-glyph:before,.send-glyph:before,.stop-glyph:before,
.top-project:after{content:"";display:block;width:17px;height:17px;background:currentColor;
  -webkit-mask:var(--ui-icon) center/contain no-repeat;mask:var(--ui-icon) center/contain no-repeat}
#hub-settings,#settings-open{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cpath d='M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.09A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3v-4h.09A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.09A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.14.36.35.7.6 1 .28.28.66.42 1.1.4H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z'/%3E%3C/svg%3E")}
#hub-theme,#theme-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M20.7 15.1A9 9 0 1 1 8.9 3.3a7 7 0 0 0 11.8 11.8Z'/%3E%3C/svg%3E")}
:root[data-theme="dark"] #hub-theme,:root[data-theme="dark"] #theme-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'/%3E%3C/svg%3E")}
#sidebar-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M4 6h16M4 12h11M4 18h16'/%3E%3C/svg%3E")}
#back-projects{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m15 18-6-6 6-6'/%3E%3C/svg%3E")}
#current-project-pin,.pin-button,.project-pin{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m14 4 6 6-3 1-4 4-1 5-3-3-3-3 5-1 4-4 1-3Z'/%3E%3Cpath d='m5 19 4-4'/%3E%3C/svg%3E")}
#inspect-toggle{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='4' width='18' height='16' rx='3'/%3E%3Cpath d='M15 4v16'/%3E%3C/svg%3E")}
#inspect-close{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M6 6l12 12M18 6 6 18'/%3E%3C/svg%3E")}
#palette-open,.rail-search-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='6'/%3E%3Cpath d='m20 20-4.2-4.2'/%3E%3C/svg%3E")}
.new-task>span:first-child{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M12 5v14M5 12h14'/%3E%3C/svg%3E")}
.top-project{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E")}.top-project:after{width:13px;height:13px}
.nav-item[data-view="artifacts"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'%3E%3Cpath d='M6 3h8l4 4v14H6V3Z'/%3E%3Cpath d='M14 3v5h4M9 12h6M9 16h6'/%3E%3C/svg%3E")}
.nav-item[data-view="audits"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 19 6v5c0 4.5-2.8 7.9-7 10-4.2-2.1-7-5.5-7-10V6l7-3Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E")}
.nav-item[data-view="models"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='6' y='6' width='12' height='12' rx='2'/%3E%3Cpath d='M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4'/%3E%3C/svg%3E")}
.nav-item[data-view="usage"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M5 19V9M12 19V5M19 19v-7'/%3E%3C/svg%3E")}
.nav-item[data-view="compute"] .nav-icon,.hpc-host-intro-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='4' width='18' height='16' rx='3'/%3E%3Cpath d='m7 9 3 3-3 3M13 15h4'/%3E%3C/svg%3E")}
.nav-item[data-view="tools"] .nav-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Ccircle cx='7' cy='7' r='3'/%3E%3Ccircle cx='17' cy='7' r='3'/%3E%3Ccircle cx='7' cy='17' r='3'/%3E%3Cpath d='M14 17h6M17 14v6'/%3E%3C/svg%3E")}
.project-delete,.task-delete{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6'/%3E%3C/svg%3E")}
.project-arrow{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 6 6 6-6 6'/%3E%3C/svg%3E")}
[data-preview].artifact-action{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 12s3.3-6 9-6 9 6 9 6-3.3 6-9 6-9-6-9-6Z'/%3E%3Ccircle cx='12' cy='12' r='2.5'/%3E%3C/svg%3E")}
.artifact-action[download]{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3v12M7 10l5 5 5-5M5 20h14'/%3E%3C/svg%3E")}
.pill-understand .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'%3E%3Cpath d='M5 5h14v11H9l-4 3V5Z'/%3E%3Cpath d='M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01'/%3E%3C/svg%3E")}
.pill-work .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M13 5.5 18.5 11 8 21.5H2.5V16L13 5.5Z'/%3E%3Cpath d='m15.5 3 5.5 5.5'/%3E%3C/svg%3E")}
.pill-check .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 19 6v5c0 4.5-2.8 7.9-7 10-4.2-2.1-7-5.5-7-10V6l7-3Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E")}
.pill-revise .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 11a8 8 0 0 0-14.9-3M4 13a8 8 0 0 0 14.9 3'/%3E%3Cpath d='M5 4v4h4M19 20v-4h-4'/%3E%3C/svg%3E")}
.pill-done .pill-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m5 13 4 4L19 7'/%3E%3C/svg%3E")}
.pill-decide .pill-glyph,.decision-glyph,.banner-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 11V6a1.5 1.5 0 0 1 3 0v4V4.5a1.5 1.5 0 0 1 3 0V10V6a1.5 1.5 0 0 1 3 0v5l2.2-2.2a1.4 1.4 0 0 1 2 2L16 15.5c-1 3-2.5 5-6 5-4 0-6-3-6-7V8a1.5 1.5 0 0 1 3 0v3'/%3E%3C/svg%3E")}
.review-mark{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 19 6v5c0 4.5-2.8 7.9-7 10-4.2-2.1-7-5.5-7-10V6l7-3Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E")}
.review-chevron,.group-chevron{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E")}
.deliverable-icon{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'%3E%3Cpath d='M8 6h6l4 4v10H8V6Z'/%3E%3Cpath d='M14 6v4h4M5 3h7'/%3E%3C/svg%3E")}
.attach-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M12 5v14M5 12h14'/%3E%3C/svg%3E")}
.send-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 19V5M6 11l6-6 6 6'/%3E%3C/svg%3E")}
.stop-glyph{--ui-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='black' stroke='none'%3E%3Crect x='7' y='7' width='10' height='10' rx='1.5'/%3E%3C/svg%3E")}
/* Application shell: glass chrome around one opaque centre of gravity. */
.app{height:100vh;display:grid;grid-template-columns:var(--sidebar) minmax(0,1fr);
  grid-template-rows:var(--topbar-h) minmax(0,1fr);background:transparent}
.topbar,.hub-bar{display:flex;align-items:center;gap:var(--sp-2);min-width:0;
  background:var(--glass-nav-bg);border:1px solid var(--glass-border);border-radius:var(--r-xl);
  box-shadow:var(--edge-highlight),var(--shadow-2);
  -webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%)}
.topbar{grid-column:1/-1;height:44px;margin:8px 8px 0;padding:0 var(--sp-3);z-index:var(--z-chrome)}
.hub-bar{height:48px;margin:8px 8px 0;padding:0 var(--sp-4);position:sticky;top:8px;z-index:var(--z-chrome)}
.brand{display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:-.01em}
.brand-button{border:0;background:transparent;padding:0 var(--sp-2) 0 3px;height:34px;
  display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:-.01em;border-radius:var(--r-md);
  transition:background var(--dur-instant) ease}
.brand-button:hover{background:var(--hover)}.brand-button:active{transform:scale(.97)}
.brand-mark{width:26px;height:26px;border-radius:var(--r-sm);display:grid;place-items:center;
  background:var(--surface-2);border:1px solid var(--line);box-shadow:var(--shadow-1)}
.brand-mark,.welcome-mark{font-size:0}.brand-mark:before,.welcome-mark:before{content:"";width:11px;height:11px;
  border:1.8px solid var(--accent);border-radius:4px;transform:rotate(45deg)}
.version{font-size:var(--fs-caption);font-family:var(--font-mono);color:var(--text-2);
  padding:2px 7px;border-radius:var(--r-pill);background:var(--surface-2)}
.top-project{height:32px;margin-left:2px;padding:0 var(--sp-3);border:0;border-radius:var(--r-md);
  background:transparent;display:flex;align-items:center;gap:6px;color:var(--text-2);cursor:pointer;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.top-project:hover{background:var(--hover);color:var(--text)}
.top-project b{color:var(--text);font-weight:500;overflow:hidden;text-overflow:ellipsis}
.icon-button{border:0;background:transparent;border-radius:var(--r-sm);width:32px;height:32px;
  display:grid;place-items:center;color:var(--text-2);flex:none;
  transition:background var(--dur-instant) ease,color var(--dur-instant) ease}
.icon-button:hover{background:var(--hover);color:var(--text)}
.icon-button:active{transform:scale(.97)}
.icon-button.pinned,.pin-button.pinned,.project-pin.pinned{color:var(--accent)}
.icon-button:disabled,.nav-item:disabled,.secondary:disabled{cursor:not-allowed;opacity:.45}
#hub-locale,#locale-toggle{width:auto;min-width:40px;padding:0 var(--sp-2);white-space:nowrap;font-size:var(--fs-caption);font-weight:500}
.live-pill{height:28px;display:flex;align-items:center;gap:6px;padding:0 10px;flex:none;
  border:1px solid var(--line);border-radius:var(--r-pill);color:var(--text-2);font-size:var(--fs-caption)}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--text-3)}
.live-dot.on{background:var(--pass)}

/* Decision banner: protocol state is never hidden or transient. */
.decision-banner{grid-column:1/-1;display:flex;align-items:center;gap:var(--sp-3);
  margin:6px 8px 0;padding:var(--sp-2) var(--sp-4);min-height:40px;
  background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--state-decide);
  border-radius:var(--r-md);box-shadow:var(--shadow-1);z-index:var(--z-chrome)}
.decision-banner .banner-glyph{color:var(--state-decide)}
.decision-banner b{font-weight:500}
.decision-banner button{margin-left:auto}
.app:has(.decision-banner:not([hidden])){grid-template-rows:var(--topbar-h) auto minmax(0,1fr)}

/* Left rail: projects, pins, recent chats, search. Nav glass shell. */
.sidebar,.inspector{min-width:0;display:flex;flex-direction:column;overflow:hidden}
.sidebar{grid-row:-2;margin:8px 0 8px 8px;padding:var(--sp-3) 10px var(--sp-3);
  background:var(--glass-nav-bg);border:1px solid var(--glass-border);border-radius:var(--r-xl);
  box-shadow:var(--edge-highlight),var(--shadow-2);
  -webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%)}
.rail-search{position:relative;display:flex;align-items:center;margin-bottom:var(--sp-2)}
.rail-search-icon{position:absolute;left:9px;color:var(--text-3);pointer-events:none}
.rail-search-icon:before{width:14px;height:14px}
.rail-search input{width:100%;height:34px;border:1px solid transparent;border-radius:var(--r-sm);
  background:color-mix(in srgb,var(--surface-2) 60%,transparent);padding:0 40px 0 30px;outline:0;
  font-size:var(--fs-body);color:var(--text)}
.rail-search input::placeholder{color:var(--text-3)}
.rail-search input:focus{border-color:var(--line-strong);background:var(--surface-2)}
.rail-search kbd{position:absolute;right:9px;font:var(--fs-caption) var(--font-mono);
  color:var(--text-3);pointer-events:none}
.new-task{height:38px;border:1px solid var(--line);background:var(--surface-2);flex:none;
  border-radius:var(--r-md);padding:0 var(--sp-3);display:flex;align-items:center;gap:var(--sp-2);
  font-weight:500;box-shadow:var(--shadow-1);transition:background var(--dur-instant) ease}
.new-task:hover{background:var(--surface-3)}.new-task:active{transform:scale(.985)}
.new-task span:last-child{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption);
  font-family:var(--font-mono)}
.side-label{font-size:var(--fs-caption);color:var(--text-3);padding:var(--sp-5) 10px var(--sp-1);
  font-weight:600}
.task-list{overflow:auto;min-height:0;flex:1;margin-top:var(--sp-1)}
.task{min-height:40px;padding:var(--sp-2) 6px var(--sp-2) 10px;border-radius:var(--r-md);
  margin-bottom:2px;display:flex;align-items:center;gap:8px;cursor:pointer}
.task:hover{background:var(--hover)}
.task.active{background:var(--surface);box-shadow:var(--shadow-1)}
.task.active .task-title{font-weight:500}
.task-copy{min-width:0;flex:1;display:flex;align-items:center;gap:8px}
.task-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:var(--fs-body);min-width:0;flex:1}
.task-meta{display:flex;align-items:center;gap:6px;color:var(--text-3);font-size:var(--fs-caption);flex:none}
.pin-button,.task-delete{width:28px;height:28px;border:0;border-radius:var(--r-xs);background:transparent;
  color:var(--text-3);opacity:0;flex:none;display:grid;place-items:center}
.pin-button:before,.task-delete:before{width:14px;height:14px}
.task:hover .pin-button,.task.active .pin-button,.pin-button.pinned,.task:focus-within .pin-button,
.task:hover .task-delete,.task.active .task-delete,.task:focus-within .task-delete{opacity:1}
.pin-button:hover{background:var(--hover);color:var(--text)}
.task-delete:hover{background:var(--blocked-bg);color:var(--blocked)}
.state-dot{width:6px;height:6px;border-radius:50%;background:transparent;flex:none;
  transition:background var(--dur-base) ease}
.state-dot.understand{background:var(--state-understand)}
.state-dot.work,.state-dot.running{background:var(--state-work)}
.state-dot.check{background:var(--state-check)}
.state-dot.revise{background:var(--state-revise)}
.state-dot.done,.state-dot.passed,.state-dot.consumed,.state-dot.PASSED,.state-dot.CONSUMED{background:var(--state-done)}
.state-dot.decide,.state-dot.escalated,.state-dot.ESCALATED{background:var(--state-decide)}
.state-dot.blocked,.state-dot.BLOCKED{background:var(--blocked)}
.sidebar-foot{margin-top:auto;border-top:1px solid var(--line);padding:10px 10px 0;flex:none;
  color:var(--text-2);font-size:var(--fs-caption)}
.sidebar-foot b{display:block;color:var(--text);font-weight:500;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}

/* Centre: one chronological run on an opaque surface. */
.workspace{grid-row:-2;min-width:0;min-height:0;display:flex;flex-direction:column;position:relative;
  z-index:var(--z-content);margin:8px 8px 8px;border:1px solid var(--line);
  border-radius:var(--r-xl);background:var(--surface);overflow:hidden;box-shadow:var(--shadow-1)}
.thread-head{min-height:56px;flex:none;display:flex;align-items:center;padding:0 var(--sp-6);gap:var(--sp-3);
  position:relative}
.thread-head:after{content:"";position:absolute;left:0;right:0;bottom:-24px;height:24px;
  pointer-events:none;background:linear-gradient(var(--surface),transparent)}
.thread-title{min-width:0}
.thread-title h1{font-size:var(--fs-title);line-height:1.35;margin:0;font-weight:600;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.01em}
.runtime-button{height:30px;border:1px solid var(--line);border-radius:var(--r-sm);background:var(--surface);
  color:var(--text-2);padding:0 10px;font-size:var(--fs-label);white-space:nowrap;flex:none}
.runtime-button:hover{background:var(--hover);color:var(--text)}

/* Six-state indicator: the one element that answers "what is happening". */
.state-pill{display:inline-flex;align-items:center;height:26px;padding:0 10px 0 8px;gap:6px;
  border-radius:var(--r-pill);font-size:var(--fs-label);font-weight:500;flex:none;
  background:var(--surface-2);color:var(--text-2);border:1px solid transparent;
  transition:background var(--dur-base) ease,color var(--dur-base) ease}
.state-pill .pill-glyph{width:14px;height:14px;flex:none}
.state-pill .pill-glyph:before{width:14px;height:14px}
.state-pill .pill-detail{font-family:var(--font-mono);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums;opacity:.8}
.state-pill.pill-understand{background:var(--state-understand-bg);color:color-mix(in srgb,var(--state-understand) 55%,var(--text))}
.state-pill.pill-work{background:var(--state-work-bg);color:color-mix(in srgb,var(--state-work) 55%,var(--text))}
.state-pill.pill-check{background:var(--state-check-bg);color:color-mix(in srgb,var(--state-check) 55%,var(--text))}
.state-pill.pill-revise{background:var(--state-revise-bg);color:color-mix(in srgb,var(--state-revise) 55%,var(--text))}
.state-pill.pill-done{background:var(--state-done-bg);color:color-mix(in srgb,var(--state-done) 55%,var(--text))}
.state-pill.pill-decide{background:var(--state-decide-bg);color:color-mix(in srgb,var(--state-decide) 55%,var(--text));
  border-color:var(--state-decide)}
.state-pill.pill-understand .pill-glyph{color:var(--state-understand)}
.state-pill.pill-work .pill-glyph{color:var(--state-work)}
.state-pill.pill-check .pill-glyph{color:var(--state-check)}
.state-pill.pill-revise .pill-glyph{color:var(--state-revise)}
.state-pill.pill-done .pill-glyph{color:var(--state-done)}
.state-pill.pill-decide .pill-glyph{color:var(--state-decide)}
.state-pill.pill-live .pill-glyph{animation:breathe 2.4s ease-in-out infinite}
@keyframes breathe{0%,100%{opacity:.55}50%{opacity:1}}
.pill-swap{animation:pill-in var(--dur-base) var(--ease-out)}
@keyframes pill-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

.thread{flex:1;overflow:auto;min-height:0;scrollbar-gutter:stable;overscroll-behavior:contain;
  scroll-padding-bottom:var(--composer-clearance,180px);scrollbar-width:thin;
  scrollbar-color:color-mix(in srgb,var(--text-2) 34%,transparent) transparent}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list){
  scrollbar-width:thin;scrollbar-color:color-mix(in srgb,var(--text-2) 34%,transparent) transparent}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list)::-webkit-scrollbar{width:10px;height:10px}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list)::-webkit-scrollbar-track{background:transparent}
:is(.project-hub,.thread,.task-list,.inspector,.panel-body,.wizard,.attachments,.preview-body,.palette-list)::-webkit-scrollbar-thumb{
  min-height:36px;border:3px solid transparent;border-radius:var(--r-pill);
  background:color-mix(in srgb,var(--text-2) 42%,transparent);background-clip:padding-box}
.thread-inner{width:min(var(--thread-max),calc(100% - 48px));margin:0 auto;
  padding:var(--sp-7) 0 calc(var(--composer-clearance,180px) + var(--sp-6))}
.welcome{padding:var(--sp-9) var(--sp-5) var(--sp-6);text-align:center}
.welcome-mark{width:40px;height:40px;margin:0 auto var(--sp-4);border-radius:var(--r-lg);
  background:var(--surface-2);border:1px solid var(--line);display:grid;place-items:center;
  box-shadow:var(--shadow-1)}
.welcome h2{font-size:var(--fs-h2);margin:0;letter-spacing:-.015em;font-weight:600}
.welcome p{color:var(--text-2);max-width:460px;margin:var(--sp-2) auto 0;line-height:1.6;font-size:var(--fs-prose)}

/* Message rows: a work record, not a chat app. */
.turn{margin-bottom:var(--sp-6)}
.turn.user{display:flex;justify-content:flex-end}
.turn.user .turn-main{max-width:85%;min-width:0}
.turn.user .turn-body{background:var(--surface-2);border-radius:var(--r-lg) var(--r-lg) 6px var(--r-lg);
  padding:var(--sp-3) var(--sp-4)}
.turn.user .turn-meta{justify-content:flex-end}
.turn-main{min-width:0}
.turn-meta{display:flex;align-items:center;gap:7px;margin-bottom:6px;
  font-size:var(--fs-caption);color:var(--text-3)}
.turn-meta b{color:var(--text);font-weight:600;font-size:var(--fs-label)}
.turn-time{margin-left:auto}
.turn.user .turn-time{margin-left:0}
.turn-body{font-size:var(--fs-prose);white-space:pre-wrap;word-break:break-word;line-height:1.6}
.turn-sub{margin-top:7px;color:var(--text-2);font-size:var(--fs-label)}
.role-mark{width:24px;height:24px;border-radius:var(--r-sm);display:grid;place-items:center;flex:none;
  font-size:10px;font-weight:600;background:var(--surface-2);color:var(--text-2)}
.role-mark.generator{background:var(--role-g-bg);color:var(--role-g)}
.role-mark.auditor{background:var(--role-a-bg);color:var(--role-a)}
.avatar{width:24px;height:24px;border-radius:var(--r-sm);display:grid;place-items:center;flex:none;
  font-size:10px;font-weight:600;background:var(--surface-2);color:var(--text-2);border:0}
.turn.audit .avatar{background:var(--role-a-bg);color:var(--role-a)}
.direct-mark{font-size:var(--fs-caption);padding:2px 6px;border-radius:var(--r-xs);
  background:var(--accent-bg);color:var(--accent);font-weight:500}
.route-note{margin-top:8px;padding:8px 10px;border-left:2px solid var(--line-strong);
  color:var(--text-2);font-size:var(--fs-label);white-space:pre-wrap;word-break:break-word}

/* Verdict badges: real ledger words, colored and always labelled. */
.status{font-size:var(--fs-caption);line-height:1;padding:5px 8px;border-radius:var(--r-xs);
  font-weight:600;background:var(--surface-2);color:var(--text-2);white-space:nowrap}
.status.PASS,.status.PASSED,.status.CONSUMED,.status.passed,.status.consumed,.status.completed,.status.complete{background:var(--pass-bg);color:var(--pass)}
.status.BLOCKED,.status.blocked,.status.failed,.status.refused{background:var(--blocked-bg);color:var(--blocked)}
.status.ESCALATED,.status.escalated{background:var(--escalated-bg);color:var(--escalated)}
.status.running{background:var(--state-work-bg);color:var(--state-work)}

/* Independent review card: invisible by default, expandable in full. */
.review-card{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--surface);
  box-shadow:var(--shadow-1);margin:var(--sp-2) 0 var(--sp-6);overflow:hidden}
.review-summary{width:100%;border:0;background:transparent;text-align:left;padding:var(--sp-4);
  display:block;color:inherit}
.review-summary:hover{background:var(--hover)}
.review-top{display:flex;align-items:center;gap:10px}
.review-mark{width:22px;height:22px;border-radius:var(--r-xs);display:grid;place-items:center;
  background:var(--role-a-bg);color:var(--role-a);flex:none}
.review-mark:before{width:14px;height:14px}
.review-top b{font-size:var(--fs-title);font-weight:600;flex:1;min-width:0}
.review-chevron{color:var(--text-3);transition:transform var(--dur-fast) var(--ease-out)}
.review-card.open .review-chevron{transform:rotate(180deg)}
.review-checks{margin:var(--sp-3) 0 0;padding:0;list-style:none;display:grid;gap:5px}
.review-checks li{display:flex;align-items:baseline;gap:8px;font-size:var(--fs-body);color:var(--text-2)}
.review-checks li:before{content:"";width:12px;height:12px;flex:none;background:var(--pass);
  align-self:center;
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m5 13 4 4L19 7'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m5 13 4 4L19 7'/%3E%3C/svg%3E") center/contain no-repeat}
.review-rounds{margin-top:var(--sp-3);font-size:var(--fs-caption);color:var(--text-3)}
.review-rounds b{font-family:var(--font-mono);font-weight:500;color:var(--text-2)}
.review-detail{display:grid;grid-template-rows:0fr;transition:grid-template-rows var(--dur-base) var(--spring)}
.review-card.open .review-detail{grid-template-rows:1fr}
.review-detail-inner{min-height:0;overflow:hidden}
.review-section{border-top:1px solid var(--line);padding:var(--sp-4)}
.review-section-title{font-size:var(--fs-caption);font-weight:600;color:var(--text-3);margin-bottom:var(--sp-2)}
.review-round-row{display:flex;align-items:baseline;gap:10px;padding:4px 0;font-size:var(--fs-body)}
.review-round-row .round-n{font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text-3);flex:none}
.review-record{display:grid;gap:6px}
.review-record-row{display:flex;align-items:center;gap:8px;font-size:var(--fs-label)}
.review-record-row span:first-child{color:var(--text-2);min-width:88px}
.review-record-row code{font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text);
  overflow-wrap:anywhere}
.review-actions{border-top:1px solid var(--line);padding:var(--sp-2) var(--sp-3);display:flex;
  justify-content:flex-end}
.review-action{border:0;background:transparent;color:var(--text-2);font-size:var(--fs-label);
  padding:6px 8px;border-radius:var(--r-xs)}
.review-action:hover{background:var(--hover);color:var(--text)}
.finding{margin-top:9px;border:1px solid var(--line);border-radius:var(--r-md);padding:10px 12px;
  background:var(--surface)}
.finding-head{display:flex;align-items:center;gap:7px;font-size:var(--fs-caption);color:var(--text-2)}
.severity{font-weight:600;color:var(--blocked)}
.finding p{margin:5px 0 0;line-height:1.5;font-size:var(--fs-body)}

/* Deliverables: opaque cards, pass-gated, grouped when plural. */
.output-files{margin-top:var(--sp-3)}
.output-head{display:flex;align-items:center;gap:7px;margin-bottom:6px;
  color:var(--text-2);font-size:var(--fs-caption);font-weight:600}
.output-count{font-weight:400;color:var(--text-3);font-family:var(--font-mono)}
.artifact-list{display:grid;gap:6px}
.output-file{min-width:0;border:1px solid var(--line);border-radius:var(--r-lg);padding:0;
  display:flex;align-items:stretch;gap:0;background:var(--surface);color:inherit;
  text-decoration:none;box-shadow:var(--shadow-1);position:relative;
  transition:border-color var(--dur-instant) ease,box-shadow var(--dur-instant) ease,transform var(--dur-instant) ease}
.output-file:hover{border-color:var(--line-strong);box-shadow:var(--shadow-2);transform:translateY(-1px)}
.output-file.passed:before,.output-file.consumed:before{content:"";position:absolute;left:0;top:8px;bottom:8px;
  width:3px;border-radius:0 3px 3px 0;background:var(--pass)}
.output-file.unavailable{opacity:.62;box-shadow:none}
.output-file.unavailable:hover{border-color:var(--line);transform:none;box-shadow:none}
.artifact-main{display:flex;align-items:center;gap:10px;min-width:0;flex:1;padding:10px 12px;
  color:inherit;text-decoration:none;border:0;background:transparent;text-align:left;cursor:pointer;
  border-radius:var(--r-lg) 0 0 var(--r-lg)}
.artifact-actions{display:flex;align-items:center;gap:2px;padding:0 6px;border-left:1px solid var(--line)}
.artifact-icon{width:34px;height:34px;flex:none;border-radius:var(--r-sm);background:var(--surface-2);
  color:var(--text-2);display:grid;place-items:center;font-size:8.5px;font-weight:600;
  font-family:var(--font-mono);letter-spacing:.02em}
.artifact-copy{min-width:0}
.artifact-name{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-family:var(--font-mono);font-size:var(--fs-body)}
.artifact-context{display:block;font-size:var(--fs-caption);color:var(--text-3);margin-top:2px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.artifact-action{width:32px;height:32px;display:grid;place-items:center;flex:none;color:var(--text-2);
  text-decoration:none;border-radius:var(--r-xs);border:0;background:transparent}
.artifact-action:hover{background:var(--hover);color:var(--text)}
.output-more{margin-top:6px;padding:2px 0;border:0;background:transparent;color:var(--accent);
  font:inherit;font-size:var(--fs-label);cursor:pointer}
.output-more:hover{text-decoration:underline}
.deliverable-group{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--surface);
  box-shadow:var(--shadow-1);overflow:hidden}
.group-head{width:100%;border:0;background:transparent;display:flex;align-items:center;gap:10px;
  padding:10px 12px;min-height:56px;text-align:left;color:inherit}
.group-head:hover{background:var(--hover)}
.group-title{min-width:0;flex:1}
.group-title b{display:block;font-size:var(--fs-body);font-weight:500}
.group-title span{display:block;font-size:var(--fs-caption);color:var(--text-3);margin-top:2px}
.group-chevron{color:var(--text-3);transition:transform var(--dur-fast) var(--ease-out)}
.deliverable-group.open .group-chevron{transform:rotate(180deg)}
.group-detail{display:grid;grid-template-rows:0fr;transition:grid-template-rows var(--dur-base) var(--spring)}
.deliverable-group.open .group-detail{grid-template-rows:1fr}
.group-detail-inner{min-height:0;overflow:hidden}
.group-detail-inner .output-file{border:0;border-top:1px solid var(--line);border-radius:0;
  box-shadow:none;margin:0}
.group-detail-inner .output-file:hover{transform:none;box-shadow:none;background:var(--hover)}
.deliverable-icon{width:34px;height:34px;border-radius:var(--r-sm);background:var(--surface-2);
  color:var(--text-2);display:grid;place-items:center;flex:none}

/* Delivery status band and stop banners. */
.delivery-status{margin:2px 0 var(--sp-6);border:1px solid var(--line);border-radius:var(--r-md);
  padding:10px var(--sp-3);background:var(--surface);display:flex;align-items:center;gap:9px;
  color:var(--text-2);font-size:var(--fs-label)}
.delivery-status .delivery-dot{width:7px;height:7px;border-radius:50%;background:var(--state-work);flex:none}
.delivery-status.passed .delivery-dot,.delivery-status.consumed .delivery-dot{background:var(--pass)}
.delivery-status.blocked .delivery-dot{background:var(--blocked)}
.delivery-status.escalated .delivery-dot,.delivery-status.provider_unavailable .delivery-dot{background:var(--state-decide)}
.delivery-status b{color:var(--text);font-weight:500}
.delivery-status button{margin-left:auto;border:0;background:transparent;color:var(--text-2);
  font-size:var(--fs-label);flex:none}
.delivery-status button:hover{color:var(--text)}
.interrupted{margin-bottom:var(--sp-5);padding:var(--sp-3) var(--sp-4);background:var(--surface);
  border:1px solid var(--line);border-left:3px solid var(--escalated);color:var(--text);
  border-radius:var(--r-md);font-size:var(--fs-body);display:none;box-shadow:var(--shadow-1)}
.interrupted.on{display:block}
.interrupted b{color:var(--escalated)}
.interrupted-detail{display:block;margin:7px 0;padding:7px 8px;border-radius:var(--r-xs);
  background:var(--surface-2);color:var(--text);font-size:var(--fs-label);line-height:1.45;
  overflow-wrap:anywhere}
.interrupted-actions{display:flex;gap:7px;margin-top:9px}
.interrupted-actions button{height:30px;border-radius:var(--r-sm);border:1px solid var(--line-strong);
  background:var(--surface);color:var(--text);padding:0 10px;cursor:pointer;font-size:var(--fs-label)}
.interrupted-actions button:hover{background:var(--hover)}
/* Live run card: six-state progress over the audited gate pipeline. */
.run-card{border:1px solid var(--line);margin:var(--sp-1) 0 var(--sp-6);overflow:hidden;
  box-shadow:var(--shadow-2)}
.run-card{border-color:var(--line);border-radius:var(--r-lg);background:var(--surface)}
.run-overview{padding:var(--sp-4) var(--sp-4) var(--sp-3);border-bottom:1px solid var(--line)}
.run-top{display:flex;align-items:center;gap:8px}
.run-eyebrow{font-size:var(--fs-caption);color:var(--text-3);font-weight:600}
.run-top .status{margin-left:auto}
.run-task{font-size:var(--fs-title);line-height:1.35;font-weight:600;letter-spacing:-.01em;
  margin:8px 0 7px;overflow-wrap:anywhere}
.run-meta{display:flex;align-items:center;gap:var(--sp-3);color:var(--text-3);font-size:var(--fs-caption)}
.run-meta span{display:flex;align-items:center;gap:4px}
.run-meta strong{color:var(--text-2);font-weight:500;font-family:var(--font-mono);
  font-variant-numeric:tabular-nums}
.run-handoff{position:relative;height:8px;margin-top:10px;display:none}
.run-card[data-handoff] .run-handoff{display:block}
.run-handoff i{position:absolute;top:0;left:0;width:8px;height:8px;border-radius:50%;background:var(--role-g)}
.run-card[data-handoff="check"] .run-handoff i{animation:handoff var(--dur-story) var(--spring-soft) both}
.run-card[data-handoff="revise"] .run-handoff i{left:auto;right:0;background:var(--role-a);
  animation:handoff-back var(--dur-story) var(--spring-soft) both}
@keyframes handoff{from{transform:translateX(0);opacity:0}20%{opacity:1}to{transform:translateX(120px);opacity:1}}
@keyframes handoff-back{from{transform:translateX(0);opacity:0}20%{opacity:1}to{transform:translateX(-120px);opacity:1}}
.run-meter{height:3px;border-radius:var(--r-pill);background:var(--surface-2);overflow:hidden;margin-top:11px}
.run-meter i{height:100%;display:block;border-radius:inherit;background:var(--accent);
  transition:width var(--dur-fast) linear}
.run-card.passed .run-meter i,.run-card.consumed .run-meter i{background:var(--pass)}
.run-card.blocked .run-meter i,.run-card.refused .run-meter i{background:var(--blocked)}
.run-card.escalated .run-meter i{background:var(--state-decide)}
.loop{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));padding:var(--sp-4) var(--sp-4) var(--sp-3);gap:0}
.loop-step{min-width:0;position:relative;padding-right:12px}
.loop-step:last-child{padding-right:0}
.loop-track{height:24px;position:relative}
.loop-step:not(:last-child) .loop-track:after{content:'';position:absolute;top:11px;left:27px;right:4px;
  height:1px;background:var(--line-strong)}
.loop-step.done:not(:last-child) .loop-track:after{background:var(--pass)}
.loop-mark{position:relative;z-index:1;width:22px;height:22px;border-radius:50%;background:var(--surface);
  border:1.5px solid var(--line-strong);display:grid;place-items:center;font-size:9px;color:var(--text-3);
  font-weight:600;box-shadow:0 0 0 3px var(--surface)}
.loop-step.done .loop-mark{background:var(--pass);border-color:var(--pass);color:var(--surface)}
.loop-step.failed .loop-mark{background:var(--blocked);border-color:var(--blocked);color:var(--surface)}
.loop-step.current .loop-mark{background:var(--accent);border-color:var(--accent);color:var(--surface)}
.loop-name{font-size:var(--fs-label);margin-top:7px;font-weight:500;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.loop-detail{font-size:var(--fs-caption);color:var(--text-3);margin-top:3px;line-height:1.35;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:26px}
.loop-state{font-size:var(--fs-caption);margin-top:5px;color:var(--text-3);font-weight:500}
.loop-step.done .loop-state{color:var(--pass)}
.loop-step.failed .loop-state{color:var(--blocked)}
.loop-step.current .loop-state{color:var(--accent)}
.loop-focus{margin:0 var(--sp-4) var(--sp-4);padding:10px 12px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface-2);display:grid;
  grid-template-columns:88px minmax(0,1fr);gap:8px 12px;align-items:start}
.loop-focus-label{font-size:var(--fs-caption);color:var(--text-3);font-weight:600;padding-top:2px}
.loop-focus-copy b{display:block;font-size:var(--fs-label);font-weight:600}
.loop-focus-copy p{margin:2px 0 0;color:var(--text-2);font-size:var(--fs-caption);line-height:1.45}
.loop-focus.current{border-color:color-mix(in srgb,var(--accent) 40%,var(--line));background:var(--accent-bg)}
.loop-focus.failed{border-color:color-mix(in srgb,var(--blocked) 40%,var(--line));background:var(--blocked-bg)}
.loop-focus.done{border-color:color-mix(in srgb,var(--pass) 40%,var(--line));background:var(--pass-bg)}
.activity{border-top:1px solid var(--line);padding:var(--sp-3) var(--sp-4) var(--sp-4);background:var(--surface)}
.activity-head{display:flex;align-items:center;margin-bottom:7px;font-size:var(--fs-caption);
  font-weight:600;color:var(--text-2)}
.activity-head span{margin-left:auto;color:var(--text-3);font-weight:400}
.activity-list{display:grid;gap:2px;max-height:190px;overflow:auto}
.audit-event{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:9px;align-items:start;
  padding:6px 5px;border-radius:var(--r-xs)}
.audit-event:hover{background:var(--hover)}
.event-mark{width:22px;height:22px;border-radius:var(--r-xs);display:grid;place-items:center;
  background:var(--surface-2);color:var(--text-2);font-size:8.5px;font-weight:600}
.event-mark.generator{background:var(--role-g-bg);color:var(--role-g)}
.event-mark.auditor{background:var(--role-a-bg);color:var(--role-a)}
.event-mark.compute{background:var(--escalated-bg);color:var(--escalated)}
.event-mark.tool,.event-mark.done{background:var(--pass-bg);color:var(--pass)}
.event-main{min-width:0}
.event-line{font-size:var(--fs-label);line-height:1.35}
.event-line b{font-weight:600;margin-right:6px}
.event-detail{color:var(--text-3);font-size:var(--fs-caption);line-height:1.4;margin-top:2px;
  white-space:pre-wrap;overflow-wrap:anywhere}
.event-time{color:var(--text-3);font-size:var(--fs-caption);font-family:var(--font-mono);padding-top:2px}
.activity-empty{padding:6px 4px;color:var(--text-3);font-size:var(--fs-label);line-height:1.45}
.audit-evidence-head{display:flex;align-items:baseline;gap:8px;margin:var(--sp-6) 0 var(--sp-3);padding-top:1px}
.audit-evidence-head h3{margin:0;font-size:var(--fs-body);font-weight:600}
.audit-evidence-head span{color:var(--text-3);font-size:var(--fs-caption)}

/* Composer: the one write path, floating Nav glass over the thread. */
.composer-wrap{position:absolute;left:var(--sidebar);right:var(--inspector);bottom:0;
  padding:var(--sp-7) var(--sp-5) var(--sp-4);pointer-events:none;z-index:var(--z-composer)}
.composer-wrap.view-hidden{display:none}
.composer{width:min(var(--thread-max),100%);margin:0 auto;pointer-events:auto;
  border:1px solid var(--glass-border);border-radius:var(--r-xl);background:var(--glass-nav-bg);
  box-shadow:var(--edge-highlight),var(--shadow-3);padding:var(--sp-2);
  -webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%);
  transition:border-color var(--dur-fast) ease,box-shadow var(--dur-fast) ease}
.composer:focus-within{border-color:color-mix(in srgb,var(--accent) 42%,var(--glass-border))}
.composer.drag{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg),var(--shadow-3)}
.contract-preview{display:none;margin:1px 3px 7px;padding:7px 9px;border-radius:var(--r-sm);
  background:var(--accent-bg);color:var(--text-2);font-size:var(--fs-caption);line-height:1.4}
.contract-preview.on{display:block}
.contract-preview b{color:var(--accent)}
.attachments{display:none;gap:6px;padding:3px 3px 8px;max-height:172px;overflow:auto}
.attachments.on{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr))}
.attachment{position:relative;display:grid;grid-template-columns:28px minmax(0,1fr) 20px;align-items:center;
  gap:7px;background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-md);
  padding:7px;min-width:0;overflow:hidden}
.attachment-type{width:28px;height:28px;border-radius:var(--r-xs);background:var(--surface);
  border:1px solid var(--line);display:grid;place-items:center;color:var(--text-2);font-size:8px;
  font-weight:600;font-family:var(--font-mono)}
.attachment-copy{min-width:0}
.attachment-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-size:var(--fs-caption);font-weight:500}
.attachment-state{display:block;color:var(--text-3);font-size:var(--fs-caption);margin-top:1px}
.attachment button{border:0;background:none;color:var(--text-3);padding:0;width:20px;height:20px;
  border-radius:5px}
.attachment button:hover{background:var(--hover);color:var(--text)}
.attachment-progress{position:absolute;left:0;right:0;bottom:0;height:2px;background:transparent}
.attachment-progress i{display:block;height:100%;background:var(--accent);
  transition:width var(--dur-fast) linear}
.attachment.failed{border-color:var(--blocked)}
.attachment.failed .attachment-state{color:var(--blocked)}
.attachment-note{grid-column:1/-1;color:var(--text-2);font-size:var(--fs-caption);padding:1px 2px;
  display:flex;gap:7px;align-items:center}
.attachment-note b{color:var(--text);font-weight:500}
.attachment-more{color:var(--accent)}
.audience-bar{display:flex;align-items:center;gap:5px;padding:1px 3px 5px}
.audience-label{font-size:var(--fs-caption);color:var(--text-3);margin-right:2px}
.audience-chip{height:24px;border:1px solid transparent;border-radius:var(--r-xs);background:transparent;
  color:var(--text-2);padding:0 8px;font-size:var(--fs-caption)}
.audience-chip:hover{background:var(--hover)}
.audience-chip.active{background:var(--surface-2);color:var(--text);border-color:var(--line-strong);font-weight:500}
.audience-chip[data-audience="generator"].active{background:var(--role-g-bg);color:var(--role-g);border-color:transparent}
.audience-chip[data-audience="auditor"].active{background:var(--role-a-bg);color:var(--role-a);border-color:transparent}
.compose-row{display:flex;align-items:flex-end;gap:7px}
.compose-well{flex:1;min-width:0;display:flex;background:var(--surface-2);border-radius:var(--r-md)}
textarea{border:0;outline:0;resize:none;min-height:44px;max-height:160px;flex:1;
  padding:12px 10px 10px;background:transparent;line-height:1.5;font-size:var(--fs-prose)}
textarea::placeholder{color:var(--text-3)}
.compose-button{border:0;background:transparent;width:34px;height:34px;border-radius:var(--r-sm);
  display:grid;place-items:center;color:var(--text-2);flex:none;margin-bottom:5px;
  transition:background var(--dur-fast) ease,color var(--dur-fast) ease}
.compose-button:hover{background:var(--hover);color:var(--text)}
.compose-button:active{transform:scale(.97)}
.send{background:var(--accent);color:var(--inverse-text)}
.send:hover{background:var(--send-hover);color:var(--inverse-text)}
.send:disabled{opacity:.35;cursor:default}
.stop{background:var(--blocked);color:var(--inverse-text)}
.stop:hover{background:color-mix(in srgb,var(--blocked) 86%,#fff);color:var(--inverse-text)}
.stop:disabled{opacity:.62;cursor:wait}
.composer-meta{display:flex;align-items:center;gap:var(--sp-2);padding:5px 5px 1px;
  color:var(--text-3);font-size:var(--fs-caption)}
#model-summary{border:0;background:transparent;padding:0;color:var(--text-2);
  font-family:var(--font-mono);font-size:var(--fs-caption);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:220px;cursor:pointer}
#model-summary:hover{color:var(--text)}
.autonomy-summary{display:inline-flex;align-items:center;gap:4px;border-left:1px solid var(--line);
  padding-left:8px;color:var(--text-2)}
.autonomy-summary:hover{color:var(--text)}
.route{display:none;margin:7px 3px 0;padding:7px 9px;border-radius:var(--r-sm);background:var(--surface-2);
  color:var(--text-2);font-size:var(--fs-label);white-space:pre-wrap;word-break:break-word}
.route.on{display:block}
.route b{color:var(--text)}
.route .ask{color:var(--escalated)}
.drop-overlay{position:fixed;inset:0;z-index:var(--z-overlay);display:none;place-items:center;padding:26px;
  pointer-events:none;background:var(--scrim-bg);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px)}
.drop-overlay.on{display:grid}
.drop-target{width:min(560px,calc(100vw - 52px));min-height:240px;border:2px dashed var(--accent);
  border-radius:var(--r-xl);background:var(--glass-palette-bg);
  box-shadow:var(--edge-highlight),var(--shadow-4);display:flex;flex-direction:column;
  align-items:center;justify-content:center;text-align:center;padding:36px;
  -webkit-backdrop-filter:blur(34px) saturate(170%);backdrop-filter:blur(34px) saturate(170%)}
.drop-icon{width:48px;height:48px;border-radius:var(--r-lg);background:var(--accent-bg);color:var(--accent);
  display:grid;place-items:center;font-size:24px;margin-bottom:14px}
.drop-target b{font-size:var(--fs-h2)}
.drop-target span{color:var(--text-2);font-size:var(--fs-label);margin-top:6px;max-width:380px}

/* Right context panel: five tabs, on demand, never squeezing the centre. */
.inspector{position:fixed;right:8px;top:calc(var(--topbar-h) + 14px);bottom:8px;width:var(--ctx-w);
  z-index:var(--z-sheet);border:1px solid var(--line);border-radius:var(--r-xl);
  background:var(--surface);box-shadow:var(--shadow-2);
  transform:translateX(calc(100% + 16px));visibility:hidden;
  transition:transform var(--dur-slow) var(--spring),visibility 0s var(--dur-slow)}
.inspector.open{transform:translateX(0);visibility:visible;transition:transform var(--dur-slow) var(--spring)}
.inspect-head{display:flex;align-items:center;min-height:48px;padding:0 var(--sp-3) 0 var(--sp-4);flex:none}
.inspect-head h2{font-size:var(--fs-body);margin:0;font-weight:600}
.panel-tabs{display:flex;gap:2px;padding:0 var(--sp-2) var(--sp-2);flex:none}
.panel-tabs .nav-item{flex:1;min-width:0;height:40px;padding:0 2px;border:0;border-radius:var(--r-sm);
  background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:2px;color:var(--text-2);font-size:var(--fs-caption);text-align:center}
.panel-tabs .nav-item:hover{background:var(--hover);color:var(--text)}
.panel-tabs .nav-item.active{background:var(--surface-2);color:var(--text);font-weight:500}
.panel-tabs .nav-icon{width:15px;height:15px;color:currentColor}
.panel-tabs .nav-icon:before{width:15px;height:15px}
.panel-body{flex:1;min-height:0;overflow:auto;padding:0 var(--sp-4) var(--sp-4)}
.panel-pane{min-width:0}
.inspect-section{border-top:1px solid var(--line);padding:var(--sp-4) 1px}
.inspect-section:first-of-type{border-top:0;padding-top:var(--sp-2)}
.inspect-title{font-size:var(--fs-caption);color:var(--text-3);font-weight:600;margin-bottom:9px}
.kv{display:flex;gap:10px;padding:4px 0;font-size:var(--fs-label)}
.kv span:first-child{color:var(--text-2)}
.kv span:last-child{margin-left:auto;text-align:right;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;max-width:175px;font-family:var(--font-mono);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums}
.model{padding:9px 10px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  margin-bottom:6px;display:flex;align-items:center;gap:10px}
.model .role-mark{width:22px;height:22px}
.model-copy{min-width:0;flex:1}
.model-role{font-size:var(--fs-caption);color:var(--text-3)}
.model-name{font-size:var(--fs-caption);font-family:var(--font-mono);margin-top:2px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.model-actions-row{display:flex;gap:6px;margin-top:var(--sp-2)}
.model-actions-row .secondary{flex:1;height:30px;font-size:var(--fs-caption)}
.contract{font-family:var(--font-mono);font-size:var(--fs-caption);padding:4px 0;color:var(--text-2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mini-metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.mini-metric{border:1px solid var(--line);background:var(--surface);border-radius:var(--r-sm);padding:8px}
.mini-value{font-size:var(--fs-h2);font-weight:600;letter-spacing:-.02em;font-family:var(--font-mono);
  font-variant-numeric:tabular-nums}
.mini-label{font-size:var(--fs-caption);color:var(--text-3)}
.escalation{padding:9px 10px;background:var(--state-decide-bg);border-radius:var(--r-sm);margin-bottom:6px}
.escalation b{font-size:var(--fs-label);color:var(--state-decide)}
.escalation p{font-size:var(--fs-caption);color:var(--text-2);margin:3px 0 0}
.escalation small{color:var(--text-3);font-size:var(--fs-caption)}
.escalation-actions{display:flex;gap:5px;margin-top:8px}
.escalation-actions button{height:26px;font-size:var(--fs-caption);padding:0 8px}
.empty{color:var(--text-3);font-size:var(--fs-label);padding:var(--sp-5) var(--sp-4);
  border:1px dashed var(--line-strong);border-radius:var(--r-md);text-align:center}
.files{white-space:pre-wrap;word-break:break-word}
.mobile-sidebar{display:none}
.scrim{display:none;position:fixed;inset:0;z-index:calc(var(--z-sheet) - 1);border:0;
  background:var(--scrim-bg);padding:0}
.scrim.on{display:block}

/* Command palette: navigation and common actions on Cmd+K. */
.palette-shell{align-items:flex-start!important;padding-top:16vh!important}
.palette{width:min(560px,calc(100vw - 32px));max-height:min(430px,60vh);display:flex;flex-direction:column;
  border:1px solid var(--glass-border);border-radius:var(--r-xl);background:var(--glass-palette-bg);
  box-shadow:var(--edge-highlight),var(--shadow-4);overflow:hidden;
  -webkit-backdrop-filter:blur(34px) saturate(170%);backdrop-filter:blur(34px) saturate(170%)}
.palette-input{height:48px;border:0;outline:0;background:transparent;padding:0 var(--sp-4);
  font-size:var(--fs-title);color:var(--text);border-bottom:1px solid var(--line);flex:none;
  border-radius:0}
.palette-input::placeholder{color:var(--text-3)}
.palette-list{flex:1;min-height:0;overflow:auto;padding:var(--sp-2)}
.palette-section{font-size:var(--fs-caption);font-weight:600;color:var(--text-3);
  padding:var(--sp-2) var(--sp-2) var(--sp-1)}
.palette-row{display:flex;align-items:center;gap:10px;width:100%;min-height:40px;border:0;
  border-radius:var(--r-md);background:transparent;padding:0 var(--sp-3);color:var(--text);
  text-align:left;font-size:var(--fs-body);position:relative}
.palette-row .palette-context{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:40%}
.palette-row kbd{color:var(--text-3);font:var(--fs-caption) var(--font-mono);margin-left:8px}
.palette-row.selected{background:var(--hover)}
.palette-row.selected:before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:2px;
  border-radius:2px;background:var(--accent)}
.palette-empty{padding:var(--sp-5);text-align:center;color:var(--text-3);font-size:var(--fs-body)}

/* Human decision screen: what was wanted, tried, blocked, and suggested. */
.decision{display:none;position:fixed;left:var(--sidebar);right:0;top:calc(var(--topbar-h) + 14px);
  bottom:0;z-index:var(--z-sheet);background:var(--surface);overflow:auto;
  margin:0 8px 8px;border:1px solid var(--line);border-radius:var(--r-xl)}
.decision.on{display:block}
body.deciding .composer-wrap{display:none}
.decision-body{width:min(640px,calc(100% - 40px));margin:0 auto;padding:var(--sp-7) 0 var(--sp-9)}
.decision-head{display:flex;align-items:flex-start;gap:var(--sp-3);margin-bottom:var(--sp-6)}
.decision-glyph{width:36px;height:36px;border-radius:var(--r-md);background:var(--state-decide-bg);
  color:var(--state-decide);display:grid;place-items:center;flex:none}
.decision-glyph:before{width:20px;height:20px}
.decision-head h1{font-size:var(--fs-h1);line-height:1.2;margin:0;letter-spacing:-.02em;font-weight:600}
.decision-head p{margin:6px 0 0;color:var(--text-2);font-size:var(--fs-prose);line-height:1.6}
.decision-flag{display:inline-flex;align-items:center;gap:6px;color:var(--state-decide);
  font-size:var(--fs-caption);font-weight:600;margin-bottom:6px}
.decision-block{margin-bottom:var(--sp-6)}
.decision-label{font-size:var(--fs-caption);text-transform:uppercase;letter-spacing:.06em;
  color:var(--text-3);font-weight:600;margin-bottom:var(--sp-2)}
.decision-goal{margin:0;font-size:var(--fs-prose);line-height:1.6;overflow-wrap:anywhere}
.decision-limit{display:flex;gap:12px;align-items:flex-start;padding:var(--sp-3) var(--sp-4);
  border:1px solid var(--line);background:var(--surface-2);border-radius:var(--r-md)}
.decision-limit-mark{display:grid;place-items:center;flex:none;width:28px;height:28px;
  border-radius:var(--r-sm);background:var(--state-decide-bg);color:var(--state-decide);font-weight:600}
.decision-limit b{display:block;font-size:var(--fs-body)}
.decision-limit p{margin:3px 0 0;color:var(--text-2);font-size:var(--fs-label);line-height:1.45}
.decision-attempts{margin-top:var(--sp-2);display:grid;gap:2px}
.decision-attempt{display:flex;align-items:baseline;gap:10px;padding:5px 2px;font-size:var(--fs-body)}
.decision-attempt .round-n{font-family:var(--font-mono);font-size:var(--fs-caption);color:var(--text-3);flex:none}
.decision-attempt .verdict-word{margin-left:auto;font-weight:600;font-size:var(--fs-caption)}
.decision-attempt .verdict-word.passed{color:var(--pass)}
.decision-attempt .verdict-word.blocked{color:var(--blocked)}
.decision-title-row{display:flex;align-items:center;gap:8px;font-size:var(--fs-body);font-weight:600;
  margin-bottom:9px}
.decision-count{border-radius:var(--r-pill);background:var(--blocked-bg);color:var(--blocked);
  padding:2px 7px;font-size:var(--fs-caption);font-family:var(--font-mono)}
.decision-issues{display:grid;gap:7px}
.decision-issue{border:1px solid var(--line);border-radius:var(--r-md);padding:10px 12px;
  background:var(--surface)}
.decision-issue-head{display:flex;gap:7px;align-items:center;font-size:var(--fs-caption);color:var(--text-3)}
.decision-issue-head span:first-child{color:var(--blocked);font-weight:600}
.decision-issue-head b{color:var(--text);font-size:var(--fs-caption)}
.decision-issue p{margin:5px 0 0;font-size:var(--fs-body);line-height:1.5;color:var(--text)}
.decision-issue small{display:block;margin-top:5px;color:var(--text-3);font-size:var(--fs-caption);
  font-family:var(--font-mono);overflow-wrap:anywhere}
.decision-empty{border:1px solid var(--line);border-radius:var(--r-md);padding:11px;color:var(--text-2);
  font-size:var(--fs-label);line-height:1.5;background:var(--surface-2)}
.decision-request{color:var(--text-2);font-size:var(--fs-body);line-height:1.5;margin:0 0 10px}
.decision-secondary{display:flex;gap:7px;margin-bottom:10px;flex-wrap:wrap}
.decision-options{display:grid;grid-template-columns:1fr;gap:9px}
.decision-option{position:relative;display:flex;gap:10px;padding:var(--sp-3) var(--sp-4);
  border:1px solid var(--line-strong);border-radius:var(--r-md);background:var(--surface);cursor:pointer}
.decision-option:hover{background:var(--hover)}
.decision-option:has(input:checked){border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg)}
.decision-option input{margin-top:2px;accent-color:var(--accent)}
.decision-option b{display:block;font-size:var(--fs-body);font-weight:600}
.decision-option small{display:block;margin-top:3px;color:var(--text-2);font-size:var(--fs-label);line-height:1.45}
.suggested-tag{display:inline-block;margin-left:8px;padding:2px 6px;border-radius:var(--r-xs);
  background:var(--state-decide-bg);color:var(--state-decide);font-size:var(--fs-caption);font-weight:600}
.decision-guidance{margin-top:var(--sp-3)}
.decision-guidance textarea{min-height:86px}
.decision-ledger-note{display:flex;gap:6px;align-items:center;color:var(--text-2);
  font-size:var(--fs-caption);margin-top:8px}
.decision-ledger-note b{color:var(--text)}
.decision-actions{display:flex;align-items:center;gap:9px;margin-top:var(--sp-5)}
.decision-actions .stop-task{border:0;background:transparent;color:var(--blocked);font-size:var(--fs-label);
  padding:0}
.decision-actions .primary{margin-left:auto}
/* Panel views: files, audit, usage, compute, tools. Compact and opaque. */
.view-heading{padding:var(--sp-2) 0 var(--sp-4)}
.view-heading h2{font-size:var(--fs-body);margin:0;font-weight:600;letter-spacing:-.01em}
.view-heading p{margin:4px 0 0;color:var(--text-3);font-size:var(--fs-caption);line-height:1.5}
.artifact-grid{display:grid;grid-template-columns:1fr;gap:8px}
.artifact-grid .output-file{margin:0;min-width:0}
.finding,.output-file,.usage-card,.usage-role,.usage-bars{border-color:var(--line)}
.usage-note{display:flex;align-items:flex-start;gap:9px;margin:0 0 var(--sp-4);padding:10px 11px;
  border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface-2);
  color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.usage-note b{color:var(--text);font-weight:600}
.usage-note span:first-child{color:var(--accent)}
.usage-cards{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:var(--sp-5)}
.usage-card{border:1px solid var(--line);border-radius:var(--r-md);padding:var(--sp-3);
  background:var(--surface);min-width:0}
.usage-card-label{font-size:var(--fs-caption);color:var(--text-3);font-weight:600}
.usage-card-value{font-size:var(--fs-h2);font-weight:600;letter-spacing:-.02em;margin-top:6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--font-mono);
  font-variant-numeric:tabular-nums}
.usage-card-detail{font-size:var(--fs-caption);color:var(--text-2);margin-top:3px}
.usage-section{margin:0 0 var(--sp-5)}
.usage-section-head{display:flex;align-items:baseline;gap:8px;margin-bottom:10px}
.usage-section-head h3{font-size:var(--fs-label);margin:0;font-weight:600}
.usage-section-head span{color:var(--text-3);font-size:var(--fs-caption)}
.usage-bars{height:110px;display:grid;grid-template-columns:repeat(7,1fr);gap:5px;align-items:end;
  padding:12px 10px 8px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface)}
.usage-day{height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;
  gap:5px;min-width:0}
.usage-day-value{font-size:var(--fs-caption);color:var(--text-3);white-space:nowrap;display:none}
.usage-bar-track{height:62px;width:100%;max-width:24px;display:flex;align-items:flex-end;
  border-radius:5px;background:var(--surface-2);overflow:hidden}
.usage-bar{width:100%;min-height:2px;border-radius:5px;background:var(--accent)}
.usage-day-label{font-size:var(--fs-caption);color:var(--text-3)}
.usage-roles{display:grid;grid-template-columns:1fr;gap:8px}
.usage-role{border:1px solid var(--line);border-radius:var(--r-md);padding:11px 12px;background:var(--surface)}
.usage-role-top{display:flex;align-items:center;gap:7px}
.usage-role-top b{font-size:var(--fs-label);text-transform:capitalize;font-weight:600}
.usage-role-top span{margin-left:auto;color:var(--text-2);font-size:var(--fs-caption);
  font-family:var(--font-mono)}
.usage-role-meter{height:4px;background:var(--surface-2);border-radius:var(--r-pill);overflow:hidden;
  margin:9px 0 5px}
.usage-role-meter i{height:100%;display:block;background:var(--role-g);border-radius:inherit}
.usage-role.auditor i{background:var(--role-a)}
.usage-role small{color:var(--text-3);font-size:var(--fs-caption)}
.usage-table{border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden;background:var(--surface)}
.usage-row{display:grid;grid-template-columns:minmax(90px,1fr) 64px 64px;gap:8px;align-items:center;
  padding:9px 10px;border-bottom:1px solid var(--line);font-size:var(--fs-caption);
  font-variant-numeric:tabular-nums}
.usage-row>*:nth-child(3),.usage-row>*:nth-child(5){display:none}
.usage-row:last-child{border-bottom:0}
.usage-row.head{background:var(--surface-2);color:var(--text-3);font-weight:600}
.usage-model{min-width:0}
.usage-model b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  font-family:var(--font-mono);font-size:var(--fs-caption);font-weight:500}
.usage-model small{color:var(--text-3);text-transform:capitalize}
.usage-quality{display:inline-flex;width:max-content;padding:3px 5px;border-radius:var(--r-xs);
  background:var(--pass-bg);color:var(--pass);font-size:var(--fs-caption);font-weight:600}
.usage-quality.estimated{background:var(--escalated-bg);color:var(--escalated)}
.usage-quality.unpriced{background:var(--surface-2);color:var(--text-2)}
.usage-recent{display:grid;gap:3px}
.usage-call{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:9px;align-items:center;
  padding:8px;border-radius:var(--r-sm)}
.usage-call:hover{background:var(--hover)}
.usage-call-mark{width:22px;height:22px;border-radius:var(--r-xs);display:grid;place-items:center;
  background:var(--role-g-bg);color:var(--role-g);font-size:8px;font-weight:600}
.usage-call-mark.auditor{background:var(--role-a-bg);color:var(--role-a)}
.usage-call-main{min-width:0}
.usage-call-main b{display:block;font-size:var(--fs-caption);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;font-family:var(--font-mono);font-weight:500}
.usage-call-main span{font-size:var(--fs-caption);color:var(--text-3)}
.usage-call-value{text-align:right;font-variant-numeric:tabular-nums}
.usage-call-value b{display:block;font-size:var(--fs-caption);font-family:var(--font-mono)}
.usage-call-value span{display:block;color:var(--text-3);font-size:var(--fs-caption)}
.compute-toolbar{display:flex;align-items:center;gap:8px;margin-bottom:var(--sp-4);flex-wrap:wrap}
.compute-toolbar .spacer{flex:1}
.compute-note{display:flex;gap:9px;padding:11px 12px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface-2);color:var(--text-2);
  font-size:var(--fs-caption);line-height:1.5;margin-bottom:var(--sp-4)}
.compute-note b{color:var(--text)}
.compute-message{display:none;margin:-8px 0 var(--sp-4);padding:9px 11px;border-radius:var(--r-sm);
  background:var(--blocked-bg);color:var(--blocked);font-size:var(--fs-caption)}
.compute-message.on{display:block}
.compute-grid{display:grid;grid-template-columns:1fr;gap:14px;align-items:start}
.compute-section{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  overflow:hidden}
.compute-section-head{display:flex;align-items:center;gap:8px;padding:11px 12px;
  border-bottom:1px solid var(--line)}
.compute-section-head b{font-size:var(--fs-label);font-weight:600}
.compute-section-head span{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption)}
.compute-empty{padding:24px 14px;text-align:center;color:var(--text-3);font-size:var(--fs-label)}
.host-row{padding:11px 12px;border-bottom:1px solid var(--line)}
.host-row:last-child{border-bottom:0}
.host-top{display:flex;align-items:center;gap:7px}
.host-top b{font-size:var(--fs-label);font-weight:600}
.host-kind{margin-left:auto;color:var(--text-2);background:var(--surface-2);padding:3px 6px;
  border-radius:var(--r-xs);font-size:var(--fs-caption)}
.host-detail{margin-top:5px;color:var(--text-2);font-size:var(--fs-caption);line-height:1.45;
  overflow-wrap:anywhere}
.host-resources{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
.host-resource{border:1px solid var(--line);border-radius:var(--r-xs);padding:2px 5px;
  color:var(--text-3);font-size:var(--fs-caption)}
.host-actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.host-actions button{height:26px;font-size:var(--fs-caption);padding:0 8px}
.hpc-job{padding:12px;border-bottom:1px solid var(--line)}
.hpc-job:last-child{border-bottom:0}
.hpc-job-top{display:flex;align-items:center;gap:8px}
.hpc-job-top b{font-size:var(--fs-label);min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-weight:600}
.hpc-job-top .status{margin-left:auto}
.hpc-job-meta{display:flex;flex-wrap:wrap;gap:9px;color:var(--text-3);font-size:var(--fs-caption);
  margin-top:5px;font-family:var(--font-mono)}
.hpc-job-detail{color:var(--text-2);font-size:var(--fs-caption);margin-top:6px}
.hpc-connection-error{color:var(--escalated);font-size:var(--fs-caption);margin-top:5px}
.hpc-job-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.hpc-job-actions button,.hpc-job-actions a{height:26px;font-size:var(--fs-caption);padding:0 8px}
.hpc-console{display:none;margin-top:9px;border:1px solid var(--line);border-radius:var(--r-sm);
  overflow:hidden}
.hpc-console.on{display:block}
.hpc-console-tabs{display:flex;align-items:center;gap:4px;padding:6px 7px;background:var(--surface-2);
  border-bottom:1px solid var(--line);font-size:var(--fs-caption);color:var(--text-3)}
.hpc-console-tabs .bad{color:var(--blocked)}
.hpc-console pre{margin:0;padding:9px;max-height:240px;overflow:auto;background:var(--surface-2);
  color:var(--text);font:var(--fs-caption)/1.5 var(--font-mono);white-space:pre-wrap}
.hpc-output-list{display:grid;gap:5px;padding:8px}
.hpc-output{display:flex;align-items:center;gap:8px;border:1px solid var(--line);
  border-radius:var(--r-sm);padding:7px 8px;color:var(--text);text-decoration:none;
  font-size:var(--fs-caption)}
.hpc-output:hover{background:var(--hover)}
.hpc-output span:last-child{margin-left:auto;color:var(--text-3)}
.mcp-tool-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
.mcp-tool{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);
  border-radius:var(--r-xs);padding:4px 6px;font-size:var(--fs-caption);color:var(--text-2)}
.mcp-tool.approved{border-color:color-mix(in srgb,var(--pass) 45%,var(--line));color:var(--pass)}
.mcp-call{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;padding:10px 12px;
  border-bottom:1px solid var(--line)}
.mcp-call:last-child{border-bottom:0}
.mcp-call b{font-size:var(--fs-caption);font-weight:600}
.mcp-call small{color:var(--text-3);font-size:var(--fs-caption)}
.skill-row{padding:11px 12px;border-bottom:1px solid var(--line)}
.skill-row:last-child{border-bottom:0}
.skill-row b{font-size:var(--fs-label);font-weight:600}
.skill-row p{margin:4px 0 0;color:var(--text-2);font-size:var(--fs-caption)}
.tools-grid .compute-section:last-child{grid-column:auto}

/* Project hub: the quiet control plane. */
.project-hub{display:none;height:100vh;overflow:auto;background:transparent}
body.hub-mode .app{display:none}
body.hub-mode .project-hub{display:block}
.hub-main{width:min(1100px,calc(100% - 48px));margin:0 auto;padding:44px 0 var(--sp-10)}
.hub-heading{display:flex;gap:18px;align-items:flex-end;margin-bottom:var(--sp-6)}
.hub-heading h1{margin:0;font-size:var(--fs-display);letter-spacing:-.025em;font-weight:600}
.hub-heading p{margin:5px 0 0;color:var(--text-2)}
.hub-summary{margin-left:auto;color:var(--text-2);font-size:var(--fs-label)}
.hub-tools{display:flex;gap:9px;margin-bottom:14px}
.hub-search{height:38px;min-width:280px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);padding:0 12px;outline:0;color:var(--text)}
.hub-search:focus{border-color:var(--accent)}
.primary{height:34px;border:0;border-radius:var(--r-sm);padding:0 13px;background:var(--accent);
  color:var(--inverse-text);font-weight:500;transition:filter var(--dur-instant) ease}
.primary:hover{filter:brightness(1.06)}
.primary:active{transform:scale(.97)}
.primary:disabled{opacity:.45;cursor:not-allowed}
.secondary{height:34px;border:1px solid var(--line-strong);border-radius:var(--r-sm);padding:0 12px;
  background:var(--surface);display:inline-flex;align-items:center;justify-content:center;
  text-decoration:none;color:var(--text)}
.secondary:hover{background:var(--hover)}
.project-table{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--surface);
  overflow:hidden;box-shadow:var(--shadow-2)}
.project-row{width:100%;border:0;border-bottom:1px solid var(--line);background:transparent;
  display:grid;grid-template-columns:minmax(220px,1.5fr) minmax(220px,1fr) 92px 100px 116px 28px 28px 28px;
  align-items:center;gap:14px;padding:15px 18px;text-align:left;cursor:pointer;color:inherit}
.project-row:last-child{border-bottom:0}
.project-row:hover{background:var(--hover)}
.project-pin{width:28px;height:28px;border:0;border-radius:var(--r-xs);background:transparent;
  color:var(--text-3);display:grid;place-items:center}
.project-pin:hover{background:var(--hover);color:var(--text)}
.project-delete{width:28px;height:28px;border:0;border-radius:var(--r-xs);background:transparent;
  color:var(--text-3);display:grid;place-items:center}
.project-delete:hover{background:var(--blocked-bg);color:var(--blocked)}
.project-name{display:block;font-weight:600;font-size:var(--fs-body)}
.project-path{display:block;font-size:var(--fs-caption);color:var(--text-3);margin-top:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--font-mono)}
.project-models{font-size:var(--fs-caption);color:var(--text-2);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;font-family:var(--font-mono)}
.project-stat{font-size:var(--fs-caption);color:var(--text-2)}
.project-arrow{color:var(--text-3)}
.paired-mark{font-size:var(--fs-caption);color:var(--text-2);background:var(--surface-2);
  border-radius:var(--r-xs);padding:4px 6px;width:max-content}
.project-live{display:flex;align-items:center;gap:7px;margin-top:7px;min-width:0;color:var(--accent);
  font-size:var(--fs-caption)}
.project-progress{position:relative;display:block;width:8px;height:8px;flex:none;border-radius:50%;
  background:var(--accent)}
.project-progress i{display:block;width:100%;height:100%;border-radius:inherit;background:inherit;
  animation:breathe 2.4s ease-in-out infinite}
.project-live-copy{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.project-live-time{color:var(--text-3);flex:none;font-family:var(--font-mono)}
.project-recovery{display:flex;align-items:center;gap:7px;margin-top:7px;color:var(--blocked);
  font-size:var(--fs-caption)}
.retry-setup{border:1px solid var(--blocked);border-radius:var(--r-xs);background:var(--surface);
  color:var(--blocked);padding:3px 7px;font-size:var(--fs-caption);font-weight:600}
.retry-setup:hover{background:var(--blocked-bg)}
.project-interrupted{display:block;margin-top:7px;color:var(--escalated);font-size:var(--fs-caption)}
.hub-empty{padding:50px 20px;text-align:center;color:var(--text-2)}
.job-panel{display:none;margin:0 0 var(--sp-4);border:1px solid color-mix(in srgb,var(--accent) 40%,var(--line));
  border-radius:var(--r-md);background:var(--accent-bg);padding:14px 16px}
.job-panel.on{display:flex;gap:13px;align-items:flex-start}
.job-spinner{width:12px;height:12px;border-radius:50%;background:var(--accent);margin-top:4px;flex:none;
  animation:breathe 2.4s ease-in-out infinite;display:grid;place-items:center}
.job-panel.failed{border-color:color-mix(in srgb,var(--blocked) 40%,var(--line));background:var(--blocked-bg)}
.job-panel.complete{border-color:color-mix(in srgb,var(--pass) 40%,var(--line));background:var(--pass-bg)}
.job-panel.failed .job-spinner,.job-panel.complete .job-spinner{animation:none;background:transparent;
  width:16px;height:16px}
.job-panel.failed .job-spinner:after{content:'×';color:var(--blocked);font-weight:600;font-size:14px}
.job-panel.complete .job-spinner:after{content:'✓';color:var(--pass);font-weight:600;font-size:13px}
.job-copy{min-width:0;flex:1}
.job-copy b{display:block}
.job-copy span{font-size:var(--fs-label);color:var(--text-2)}
.job-steps{margin:8px 0 0;padding:0;list-style:none;display:grid;gap:3px}
.job-steps li{font-size:var(--fs-caption);color:var(--text-2)}
.job-steps li:before{content:'✓';color:var(--pass);margin-right:6px}
/* Modal flows: guided setup on Palette-tier glass; forms stay opaque wells. */
.project-modal{display:none;position:fixed;inset:0;z-index:var(--z-overlay);background:var(--scrim-bg);
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);
  padding:28px;align-items:center;justify-content:center}
.project-modal.on{display:flex}
.wizard{width:min(720px,100%);max-height:calc(100vh - 40px);overflow:auto;
  background:var(--glass-palette-bg);border:1px solid var(--glass-border);border-radius:var(--r-xl);
  box-shadow:var(--edge-highlight),var(--shadow-4);
  -webkit-backdrop-filter:blur(34px) saturate(170%);backdrop-filter:blur(34px) saturate(170%)}
.project-modal.on .wizard{transform-origin:50% 14%;animation:materialize var(--dur-base) var(--spring) both}
@keyframes materialize{from{opacity:0;transform:translateY(10px) scale(.975)}to{opacity:1;transform:none}}
.wizard-head{padding:21px 24px 17px;display:flex;gap:12px;align-items:flex-start;
  border-bottom:1px solid var(--line)}
.wizard-head h2{font-size:var(--fs-h2);margin:0;letter-spacing:-.015em;font-weight:600}
.wizard-head p{margin:4px 0 0;color:var(--text-2);font-size:var(--fs-label);line-height:1.5}
.wizard-body{padding:22px 24px}
.wizard-foot{padding:15px 24px;border-top:1px solid var(--line);display:flex;align-items:center;gap:9px}
.wizard-foot span{font-size:var(--fs-caption);color:var(--text-2);margin-right:auto;max-width:390px}
.form-section{margin-bottom:25px}
.form-section:last-child{margin:0}
.form-title{font-size:var(--fs-label);font-weight:600;margin-bottom:11px;color:var(--text-2)}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}
.field{display:block}
.field.full{grid-column:1/-1}
.field span{display:block;font-size:var(--fs-label);color:var(--text-2);margin-bottom:6px}
.field input,.field select,.field textarea,.fallback-row select,.fallback-row input{
  width:100%;min-height:38px;border:1px solid var(--line-strong);border-radius:var(--r-md);
  background:var(--surface);padding:9px 10px;outline:0;color:var(--text)}
.field textarea{resize:vertical;min-height:74px}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--accent);
  box-shadow:0 0 0 3px var(--accent-bg)}
.path-picker{display:flex;gap:8px;align-items:center}
.path-picker input{min-width:0;flex:1;font-family:var(--font-mono);font-size:var(--fs-caption)}
.path-picker button{white-space:nowrap}
.path-preview{display:block;margin-top:6px;color:var(--text-3);font-size:var(--fs-caption);
  overflow-wrap:anywhere}
.role-card{border:1px solid var(--line);border-radius:var(--r-lg);padding:13px;background:var(--surface)}
.role-card b{display:block;margin-bottom:9px}
.role-card .field+.field{margin-top:10px}
.runtime-role-head{display:flex;align-items:flex-start;gap:9px;margin-bottom:11px}
.runtime-role-head b{margin:0}
.runtime-role-head span{margin-left:auto;color:var(--text-3);font-size:var(--fs-caption)}
.runtime-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.runtime-note{margin-top:12px;padding:10px 11px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface-2);color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.runtime-note b{color:var(--text)}
.effort-help{display:block;color:var(--text-3);font-size:var(--fs-caption);margin-top:6px;line-height:1.4}
.runtime-saved{color:var(--pass)}
.model-actions{display:flex;justify-content:flex-end;margin-top:6px}
.model-actions button{height:27px;font-size:var(--fs-caption)}
.fallback-list{display:grid;gap:8px}
.fallback-row{display:grid;grid-template-columns:130px minmax(0,1fr) 92px 28px;gap:7px;align-items:center}
.fallback-row select,.fallback-row input{min-height:34px;padding:6px 8px;font-size:var(--fs-caption)}
.fallback-remove{height:30px;border:1px solid var(--line);border-radius:var(--r-xs);
  background:var(--surface);color:var(--text-2);cursor:pointer}
.fallback-empty{color:var(--text-3);font-size:var(--fs-caption);padding:8px 0}
.guardrail-state{font-size:var(--fs-caption);color:var(--text-2);margin-top:8px}
.custom-model.off{display:none}
.conditional-field.off{display:none}
.delete-summary{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface-2);
  padding:12px 13px;display:grid;gap:5px;font-size:var(--fs-label)}
.delete-summary b{font-size:var(--fs-body)}
.delete-summary code{font-family:var(--font-mono);color:var(--text-2);overflow-wrap:anywhere}
.delete-warning{border:1px solid color-mix(in srgb,var(--blocked) 32%,var(--line));
  background:var(--blocked-bg);color:var(--blocked);border-radius:var(--r-md);padding:11px 12px;
  font-size:var(--fs-label);line-height:1.5}
.delete-detail{color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.danger-button{height:34px;border:0;border-radius:var(--r-sm);padding:0 13px;background:var(--blocked);
  color:var(--inverse-text);font-weight:600}
.danger-button:hover{filter:brightness(.94)}
.danger-button:disabled{opacity:.4;cursor:not-allowed}
.runtime-wizard{width:min(980px,100%);height:min(740px,calc(100vh - 40px));display:flex;
  flex-direction:column;overflow:hidden}
.runtime-wizard>.wizard-head,.runtime-wizard>.wizard-foot{flex:none}
.runtime-shell{min-height:0;flex:1;padding:0;display:grid;grid-template-columns:200px minmax(0,1fr);
  overflow:hidden}
.runtime-nav{display:flex;flex-direction:column;gap:5px;padding:13px;border-right:1px solid var(--line)}
.runtime-nav-button{width:100%;min-height:48px;padding:8px 10px;border:0;border-radius:var(--r-md);
  background:transparent;color:var(--text-2);text-align:left;
  transition:background var(--dur-instant) ease}
.runtime-nav-button:hover{background:var(--hover);color:var(--text)}
.runtime-nav-button:active{transform:scale(.98)}
.runtime-nav-button.active{background:var(--surface-2);color:var(--text);box-shadow:var(--shadow-1)}
.runtime-nav-button b{display:block;font-size:var(--fs-label);font-weight:600}
.runtime-nav-button small{display:block;margin-top:2px;color:var(--text-3);font-size:var(--fs-caption)}
.runtime-content{min-width:0;overflow:auto;padding:24px 25px}
.runtime-pane[hidden]{display:none}
.runtime-pane-heading{margin:0 0 17px}
.runtime-pane-heading h3{margin:0;font-size:var(--fs-title);letter-spacing:-.01em;font-weight:600}
.runtime-pane-heading p{margin:4px 0 0;color:var(--text-2);font-size:var(--fs-caption);line-height:1.5}
.runtime-advanced{margin-top:14px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);overflow:hidden}
.runtime-advanced>summary{min-height:46px;padding:0 13px;display:flex;align-items:center;gap:8px;
  cursor:pointer;list-style:none;color:var(--text);font-size:var(--fs-label);font-weight:500}
.runtime-advanced>summary::-webkit-details-marker{display:none}
.runtime-advanced>summary:after{content:"";width:14px;height:14px;margin-left:auto;background:var(--text-3);
  transition:transform var(--dur-fast) var(--spring);
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat}
.runtime-advanced[open]>summary:after{transform:rotate(180deg)}
.runtime-advanced-body{border-top:1px solid var(--line);padding:13px}
.runtime-content>.wizard-error{margin-top:12px}
.github-box{border:1px solid var(--line);border-radius:var(--r-md);padding:14px;background:var(--surface)}
.toggle-line{display:flex;align-items:flex-start;gap:10px}
.toggle-line input{margin-top:3px;accent-color:var(--accent)}
.toggle-line b{display:block}
.toggle-line small{display:block;color:var(--text-2);margin-top:2px}
.github-fields{margin-top:14px}
.github-fields.off{display:none}
.connection{font-size:var(--fs-label);margin:10px 0 0;color:var(--text-2)}
.connection.ok{color:var(--pass)}
.connection.bad{color:var(--blocked)}
.github-connect{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.github-connect .secondary{height:30px}
.github-device{margin-top:9px;padding:10px;border:1px solid var(--line);border-radius:var(--r-sm);
  background:var(--surface);color:var(--text)}
.github-device b{font-size:var(--fs-body)}
.device-code{font-family:var(--font-mono);letter-spacing:.12em;padding:4px 7px;
  border-radius:var(--r-xs);background:var(--surface-2);user-select:all}
.github-device-actions{display:flex;gap:7px;margin-top:8px;align-items:center}
.github-device a{color:var(--accent);font-weight:500;text-decoration:none}
.github-device small{display:block;color:var(--text-2);margin-top:5px}
.repo-actions{display:flex;align-items:center;gap:8px;margin-top:11px}
.repo-actions .secondary{height:29px}
.repo-check{font-size:var(--fs-caption);color:var(--text-2)}
.repo-check.ok{color:var(--pass)}
.repo-check.warn{color:var(--escalated)}
.job-guidance{display:none;margin-top:10px;padding:10px;
  border:1px solid color-mix(in srgb,var(--blocked) 30%,var(--line));border-radius:var(--r-sm);
  background:var(--surface)}
.job-guidance.on{display:block}
.job-guidance b{font-size:var(--fs-label)}
.job-guidance p{margin:4px 0 8px;color:var(--text-2);font-size:var(--fs-caption)}
.guidance-actions{display:flex;gap:7px;flex-wrap:wrap}
.guidance-actions a,.guidance-actions button{height:28px;font-size:var(--fs-caption)}
.recovery-note{padding:11px;border:1px solid color-mix(in srgb,var(--escalated) 42%,var(--line));
  background:var(--escalated-bg);border-radius:var(--r-md);color:var(--text);
  font-size:var(--fs-label);line-height:1.5;margin-bottom:14px}
.recovery-note b{display:block;margin-bottom:3px}
.wizard-error{display:none;color:var(--blocked);background:var(--blocked-bg);border-radius:var(--r-sm);
  padding:9px 11px;margin-top:14px;font-size:var(--fs-label)}
.wizard-error.on{display:block}
.wizard-error a{color:inherit;font-weight:600;margin-left:7px}
.credential-card{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  padding:0;overflow:hidden}
.credential-head{display:flex;align-items:center;gap:8px}
.credential-head b{font-size:var(--fs-body)}
.credential-state{margin-left:auto;font-size:var(--fs-caption);color:var(--text-3)}
.credential-state.ok{color:var(--pass)}
details.credential-card>.credential-head{min-height:52px;margin:0;padding:10px 13px;cursor:pointer;
  list-style:none}
details.credential-card>.credential-head::-webkit-details-marker{display:none}
details.credential-card>.credential-head:after{content:"";width:14px;height:14px;margin-left:3px;
  background:var(--text-3);transition:transform var(--dur-fast) var(--spring);
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat}
details.credential-card[open]>.credential-head:after{transform:rotate(180deg)}
.credential-body{padding:0 13px 14px;border-top:1px solid var(--line)}
.credential-body>.connection-method,.credential-body>.provider-note{margin-top:12px}
.secret-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:end}
.secret-row .toggle-line{padding-bottom:9px}
.connection-method{display:flex;align-items:center;gap:12px;padding:11px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface-2);margin-bottom:11px}
.connection-method-copy{min-width:0;flex:1}
.connection-method-copy b{display:block;font-size:var(--fs-label)}
.connection-method-copy small{display:block;color:var(--text-2);margin-top:3px;line-height:1.4}
.connection-method .secondary{flex:none}
.provider-note{padding:9px 10px;border-radius:var(--r-sm);background:var(--escalated-bg);
  color:var(--text-2);font-size:var(--fs-caption);line-height:1.45;margin-bottom:11px}
.provider-note b{color:var(--escalated)}
.login-link{color:var(--accent);font-weight:500;text-decoration:none}
.field-help{display:block!important;margin-top:5px;color:var(--text-3);font-size:var(--fs-caption);
  line-height:1.4}
.settings-readiness{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.readiness-item{border:1px solid var(--line);border-radius:var(--r-sm);padding:10px;
  background:var(--surface);font-size:var(--fs-label)}
.readiness-item span{float:right;color:var(--pass)}
.readiness-item span.bad{color:var(--blocked)}
.doctor-panel{margin-top:12px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);overflow:hidden}
.doctor-head{display:flex;align-items:center;gap:10px;padding:12px 13px;border-bottom:1px solid var(--line)}
.doctor-head-copy{min-width:0;flex:1}
.doctor-head-copy b{display:block;font-size:var(--fs-body)}
.doctor-head-copy small{display:block;margin-top:2px;color:var(--text-2);font-size:var(--fs-caption)}
.doctor-state{width:8px;height:8px;border-radius:50%;background:var(--text-3);flex:none}
.doctor-state.ready{background:var(--pass)}
.doctor-state.blocked,.doctor-state.failed{background:var(--blocked)}
.doctor-state.attention{background:var(--escalated)}
.doctor-state.running{background:var(--accent);animation:breathe 2.4s ease-in-out infinite}
.doctor-head .secondary{height:29px;flex:none}
.doctor-list{display:grid}
.doctor-empty{padding:18px;color:var(--text-2);font-size:var(--fs-label);text-align:center}
.doctor-check{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:9px;padding:11px 13px;
  border-bottom:1px solid var(--line);align-items:start}
.doctor-check:last-child{border-bottom:0}
.doctor-mark{width:17px;height:17px;border-radius:50%;display:grid;place-items:center;font-size:9px;
  font-weight:600;background:var(--pass-bg);color:var(--pass);margin-top:1px}
.doctor-check.missing .doctor-mark,.doctor-check.outdated .doctor-mark{background:var(--blocked-bg);
  color:var(--blocked)}
.doctor-check.warning .doctor-mark,.doctor-check.unknown .doctor-mark,.doctor-check.waiting .doctor-mark{
  background:var(--escalated-bg);color:var(--escalated)}
.doctor-copy{min-width:0}
.doctor-copy b{display:block;font-size:var(--fs-label)}
.doctor-copy small{display:block;color:var(--text-2);font-size:var(--fs-caption);line-height:1.4;
  margin-top:2px;overflow-wrap:anywhere}
.doctor-version{color:var(--text-3);font-family:var(--font-mono);font-size:var(--fs-caption);
  margin-top:2px;white-space:nowrap}
.doctor-action{grid-column:2/4;display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.doctor-action .secondary{height:27px;font-size:var(--fs-caption);text-decoration:none}
.doctor-identity{display:grid;grid-template-columns:1fr 1fr auto;gap:7px;width:100%}
.doctor-identity input{min-width:0;border:1px solid var(--line-strong);border-radius:var(--r-xs);
  background:var(--surface);padding:7px 8px;font-size:var(--fs-caption)}
.doctor-message{display:none;margin:0 13px 12px;padding:9px 10px;border-radius:var(--r-sm);
  background:var(--accent-bg);color:var(--accent);font-size:var(--fs-caption)}
.doctor-message.on{display:block}
.doctor-message.bad{background:var(--blocked-bg);color:var(--blocked)}
.doctor-panel:not(.expanded) .doctor-list{display:none}
.doctor-details-toggle{min-width:86px}
#provider-credentials{display:grid;grid-template-columns:1fr;gap:10px;margin-top:10px}
#provider-credentials .credential-card{margin:0;min-width:0}
#provider-credentials .provider-note{min-height:58px}

/* Project creation: a short guided flow, not a wall of configuration. */
.project-wizard{width:min(800px,100%);height:min(760px,calc(100vh - 40px));display:flex;
  flex-direction:column;overflow:hidden}
.project-wizard .wizard-head{flex:none}
.wizard-progress{position:relative;flex:none;display:grid;grid-template-columns:repeat(3,1fr);gap:0;
  margin:0;padding:15px 25px 14px;list-style:none;border-bottom:1px solid var(--line)}
.wizard-progress li{position:relative;z-index:1;display:grid;grid-template-columns:28px minmax(0,1fr);
  grid-template-rows:auto auto;column-gap:9px;color:var(--text-3)}
.wizard-progress li:not(:last-child):after{content:"";position:absolute;z-index:-1;top:13px;left:28px;
  right:8px;height:1px;background:var(--line-strong)}
.wizard-progress li>span{grid-row:1/3;width:28px;height:28px;border:1px solid var(--line-strong);
  border-radius:50%;display:grid;place-items:center;background:var(--surface);font-size:var(--fs-caption);
  font-weight:600;font-family:var(--font-mono)}
.wizard-progress li>b{align-self:end;font-size:var(--fs-label);color:var(--text-2);font-weight:500}
.wizard-progress li>small{align-self:start;font-size:var(--fs-caption);white-space:nowrap}
.wizard-progress li.active>span,.wizard-progress li.complete>span{border-color:var(--accent);
  background:var(--accent);color:var(--inverse-text)}
.wizard-progress li.active>b{color:var(--text)}
.wizard-progress li.complete:not(:last-child):after{background:var(--accent)}
.project-wizard-body{min-height:0;flex:1;overflow:auto}
.project-step{margin:0}
.project-step[hidden]{display:none}
.project-step:not([hidden]){animation:step-arrive var(--dur-base) var(--spring) both}
@keyframes step-arrive{from{opacity:0;transform:translateX(8px)}to{opacity:1;transform:none}}
.step-heading{margin-bottom:21px}
.step-heading>span{display:block;margin-bottom:5px;color:var(--accent);font-size:var(--fs-caption);
  font-weight:600}
.step-heading h3{margin:0;font-size:var(--fs-h2);line-height:1.2;letter-spacing:-.015em;font-weight:600}
.step-heading p{max-width:610px;margin:6px 0 0;color:var(--text-2);font-size:var(--fs-label);line-height:1.55}
.advanced-options{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface-2);
  overflow:hidden}
.advanced-options summary{height:42px;display:flex;align-items:center;padding:0 13px;cursor:pointer;
  color:var(--text-2);font-size:var(--fs-label);font-weight:500;list-style:none}
.advanced-options summary::-webkit-details-marker{display:none}
.advanced-options summary:after{content:"+";margin-left:auto;color:var(--text-3);font-size:17px;font-weight:400}
.advanced-options[open] summary:after{content:"−"}
.advanced-options-body{padding:2px 13px 14px;border-top:1px solid var(--line)}
.advanced-options-body>.field{margin-top:12px}
.role-choice-grid{align-items:start}
.role-card-head{display:flex;align-items:center;gap:10px;margin-bottom:13px}
.role-card-head b{margin:0}
.role-card-head small{display:block;margin-top:2px;color:var(--text-2);font-size:var(--fs-caption)}
.role-index{width:28px;height:28px;border-radius:var(--r-sm);display:grid;place-items:center;
  background:var(--role-g-bg);color:var(--role-g);font-size:var(--fs-caption);font-weight:600}
.role-index.auditor{background:var(--role-a-bg);color:var(--role-a)}
.role-details{margin-top:11px;border-top:1px solid var(--line);padding-top:9px}
.role-details>summary{min-height:28px;display:flex;align-items:center;gap:7px;color:var(--text-2);
  cursor:pointer;list-style:none;font-size:var(--fs-caption);font-weight:500}
.role-details>summary::-webkit-details-marker{display:none}
.role-details>summary:after{content:"";width:12px;height:12px;margin-left:auto;background:var(--text-3);
  transition:transform var(--dur-fast) var(--spring);
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m8 10 4 4 4-4'/%3E%3C/svg%3E") center/contain no-repeat}
.role-details[open]>summary:after{transform:rotate(180deg)}
.role-details-body{padding-top:5px}
.role-details-body>.field+.field{margin-top:10px}
.project-review{margin-top:14px;border:1px solid var(--line);border-radius:var(--r-lg);
  background:var(--surface);padding:13px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.project-review-item{min-width:0}
.project-review-item span{display:block;color:var(--text-3);font-size:var(--fs-caption)}
.project-review-item b{display:block;margin-top:3px;font-size:var(--fs-label);font-weight:500;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.project-wizard-foot{flex:none}

/* Settings: macOS preference-window pattern, category rail + one pane. */
.settings-wizard{width:min(980px,100%);height:min(740px,calc(100vh - 40px));display:flex;
  flex-direction:column;overflow:hidden}
.settings-wizard>.wizard-head,.settings-wizard>.wizard-foot{flex:none}
.settings-shell{min-height:0;flex:1;padding:0;display:grid;grid-template-columns:210px minmax(0,1fr);
  overflow:hidden}
.settings-nav{display:flex;flex-direction:column;gap:5px;padding:13px;border-right:1px solid var(--line)}
.settings-nav-button{position:relative;width:100%;min-height:52px;padding:8px 9px;border:0;
  border-radius:var(--r-md);display:grid;grid-template-columns:28px minmax(0,1fr) auto;
  align-items:center;gap:9px;background:transparent;color:var(--text-2);text-align:left;
  transition:background var(--dur-instant) ease}
.settings-nav-button:hover{background:var(--hover);color:var(--text)}
.settings-nav-button:active{transform:scale(.98)}
.settings-nav-button.active{background:var(--surface-2);color:var(--text);box-shadow:var(--shadow-1)}
.settings-nav-button b{display:block;font-size:var(--fs-label);font-weight:600}
.settings-nav-button small{display:block;margin-top:2px;color:var(--text-3);font-size:var(--fs-caption)}
.settings-nav-button i{min-width:20px;padding:2px 5px;border-radius:var(--r-pill);
  background:var(--surface-2);color:var(--text-2);font-size:var(--fs-caption);font-style:normal;
  text-align:center;font-family:var(--font-mono)}
.settings-nav-button i.ok{background:var(--pass-bg);color:var(--pass)}
.settings-nav-button i.bad{background:var(--blocked-bg);color:var(--blocked)}
.settings-nav-button i.attention{background:var(--escalated-bg);color:var(--escalated)}
.settings-nav-icon{width:28px;height:28px;border-radius:var(--r-sm);display:grid;place-items:center;
  background:var(--surface-2);color:var(--text-2)}
.settings-nav-icon:before{content:"";width:15px;height:15px;background:currentColor;
  -webkit-mask:var(--settings-icon) center/contain no-repeat;mask:var(--settings-icon) center/contain no-repeat}
.settings-nav-icon.general{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M4 6h10M18 6h2M4 12h2M10 12h10M4 18h7M15 18h5'/%3E%3Ccircle cx='16' cy='6' r='2'/%3E%3Ccircle cx='8' cy='12' r='2'/%3E%3Ccircle cx='13' cy='18' r='2'/%3E%3C/svg%3E")}
.settings-nav-icon.providers{--settings-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='3' width='16' height='7' rx='2'/%3E%3Crect x='4' y='14' width='16' height='7' rx='2'/%3E%3Cpath d='M8 6.5h.01M8 17.5h.01M12 6.5h4M12 17.5h4'/%3E%3C/svg%3E")}
.settings-content{min-width:0;overflow:auto;padding:24px 25px}
.settings-pane{margin:0}
.settings-pane[hidden]{display:none}
.settings-heading{margin-bottom:20px}

/* Remote compute host wizard and job submission. */
.hpc-host-wizard{width:min(820px,100%);overflow:hidden;display:flex;flex-direction:column}
.hpc-host-wizard .wizard-body{overflow:auto}
.hpc-host-intro{display:flex;align-items:flex-start;gap:10px;padding:11px 12px;margin-bottom:14px;
  border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  color:var(--text-2);font-size:var(--fs-caption);line-height:1.55}
.hpc-host-intro b{display:block;color:var(--text);font-size:var(--fs-label);margin-bottom:2px}
.hpc-host-intro-icon{width:28px;height:28px;flex:none;border-radius:var(--r-sm);
  background:var(--accent-bg);color:var(--accent);display:grid;place-items:center}
.hpc-setup-section{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  padding:15px;margin-bottom:12px}
.hpc-setup-section:last-child{margin-bottom:0}
.hpc-section-head{display:grid;grid-template-columns:25px minmax(0,1fr);gap:9px;align-items:start;
  margin-bottom:13px}
.hpc-section-index{width:24px;height:24px;border-radius:var(--r-xs);background:var(--surface-2);
  color:var(--text-2);display:grid;place-items:center;font-size:var(--fs-caption);font-weight:600;
  font-family:var(--font-mono)}
.hpc-section-head b{display:block;font-size:var(--fs-body)}
.hpc-section-head p{margin:2px 0 0;color:var(--text-2);font-size:var(--fs-caption);line-height:1.5;
  max-width:620px}
.hpc-connection-grid{display:grid;grid-template-columns:1fr 1.4fr 110px;gap:11px}
.hpc-connection-grid .field.full{grid-column:1/-1}
.hpc-permission{display:flex;align-items:flex-start;gap:10px;padding:11px 12px;
  border:1px solid var(--line-strong);border-radius:var(--r-md);background:var(--surface);cursor:pointer}
.hpc-permission:has(input:checked){border-color:var(--accent);background:var(--accent-bg)}
.hpc-permission input{margin-top:2px;accent-color:var(--accent)}
.hpc-permission b{display:block;font-size:var(--fs-label);color:var(--text)}
.hpc-permission small{display:block;margin-top:3px;color:var(--text-2);font-size:var(--fs-caption);
  line-height:1.45}
.hpc-policy{margin-top:13px;padding-top:13px;border-top:1px solid var(--line)}
.hpc-policy.off{display:none}
.hpc-policy-title{display:flex;align-items:baseline;gap:7px;margin-bottom:9px;
  font-size:var(--fs-label);font-weight:600}
.hpc-policy-title span{color:var(--text-3);font-size:var(--fs-caption);font-weight:400}
.hpc-limit-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.hpc-advanced{margin-top:10px;border-top:1px solid var(--line);padding-top:10px}
.hpc-advanced summary{cursor:pointer;color:var(--text-2);font-size:var(--fs-caption);user-select:none}
.hpc-advanced .hpc-limit-grid{margin-top:10px}
.hpc-host-key{display:flex;align-items:flex-start;gap:9px;font-size:var(--fs-caption);color:var(--text-2)}
.hpc-host-key input{margin-top:2px;accent-color:var(--accent)}
.hpc-host-key b{display:block;color:var(--text);font-size:var(--fs-label)}
.hpc-host-key small{display:block;margin-top:2px;line-height:1.45}
.hpc-host-wizard .wizard-foot{flex:none}
.hpc-input-list{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}
.hpc-input{display:inline-flex;align-items:center;gap:5px;max-width:100%;border:1px solid var(--line);
  border-radius:var(--r-xs);padding:4px 6px;color:var(--text-2);font-size:var(--fs-caption)}
.hpc-input b{max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)}
.hpc-input button{border:0;background:transparent;color:var(--text-3);cursor:pointer;padding:0 2px;
  font-size:12px}
.hpc-script{min-height:180px!important;font:var(--fs-caption)/1.5 var(--font-mono)!important}
.hpc-confirm{display:flex;align-items:flex-start;gap:9px;padding:10px;
  border:1px solid color-mix(in srgb,var(--escalated) 50%,var(--line));border-radius:var(--r-sm);
  background:var(--escalated-bg);font-size:var(--fs-caption);color:var(--text-2)}
.hpc-confirm input{margin-top:2px;accent-color:var(--accent)}
.hpc-confirm b{display:block;color:var(--escalated)}
.mcp-transport-fields.off{display:none}

/* File preview: rendered locally, audited from the final binary. */
.preview-wizard{width:min(1040px,calc(100% - 32px));height:min(820px,calc(100vh - 40px));
  display:flex;flex-direction:column;overflow:hidden}
.preview-wizard .wizard-head{flex:none}
.preview-body{min-height:0;flex:1;overflow:auto;background:var(--surface-2);padding:18px;
  display:grid;place-items:center}
.preview-loading,.preview-unavailable{color:var(--text-2);font-size:var(--fs-label);text-align:center;
  max-width:560px;line-height:1.6}
.preview-frame{width:100%;height:100%;min-height:520px;border:1px solid var(--line);
  border-radius:var(--r-md);background:var(--surface)}
.preview-image{display:block;max-width:100%;max-height:100%;object-fit:contain;
  border-radius:var(--r-sm);box-shadow:var(--shadow-2)}
.preview-code,.preview-document,.preview-markdown{width:min(820px,100%);min-height:100%;margin:0;
  padding:28px 32px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);
  color:var(--text);box-shadow:var(--shadow-1)}
.preview-code{white-space:pre-wrap;word-break:break-word;font:var(--fs-label)/1.62 var(--font-mono)}
.preview-document{white-space:pre-wrap;word-break:break-word;font:var(--fs-prose)/1.7 ui-serif,Georgia,serif}
.preview-markdown{font-size:var(--fs-prose);line-height:1.65}
.preview-markdown h1,.preview-markdown h2,.preview-markdown h3{line-height:1.25}
.preview-markdown pre{overflow:auto;padding:12px;border-radius:var(--r-sm);background:var(--surface-2)}
.preview-markdown code{font-family:var(--font-mono)}
.preview-markdown table{border-collapse:collapse;width:100%}
.preview-markdown th,.preview-markdown td{border:1px solid var(--line);padding:6px 8px;text-align:left}
.preview-markdown blockquote{margin-left:0;padding-left:12px;border-left:3px solid var(--line-strong);
  color:var(--text-2)}
.preview-note{min-height:34px;padding:9px 18px;border-top:1px solid var(--line);color:var(--text-2);
  font-size:var(--fs-caption)}
/* Responsive layout: the centre column always wins. */
@media(max-width:1280px){
  .inspector{width:min(400px,calc(100vw - 16px));background:var(--glass-sheet-bg);
    border-color:var(--glass-border);box-shadow:var(--edge-highlight),var(--shadow-3);
    -webkit-backdrop-filter:blur(28px) saturate(160%);backdrop-filter:blur(28px) saturate(160%)}
}
@media(min-width:1281px){
  .scrim.inspector-open:not(.sidebar-open){display:none}
}
@media(max-width:840px){
  .hpc-connection-grid{grid-template-columns:1fr 1fr}
  .hpc-connection-grid .field:nth-child(2){grid-column:1/-1}
  .hpc-limit-grid{grid-template-columns:1fr 1fr}
}
@media(max-width:760px){
  .hub-bar{padding:0 14px}
  .hub-main{width:calc(100% - 24px);padding-top:26px}
  .hub-heading{align-items:flex-start;flex-direction:column}
  .hub-summary{margin-left:0}
  .project-row{grid-template-columns:minmax(0,1fr) 58px 62px 28px 28px 16px;gap:8px}
  .project-models,.project-tier{display:none}
  .form-grid{grid-template-columns:1fr}
  .field.full{grid-column:auto}
  .project-modal{padding:8px}
  .wizard{max-height:calc(100vh - 16px)}
  #provider-credentials{grid-template-columns:1fr}
  .doctor-check{grid-template-columns:18px minmax(0,1fr)}
  .doctor-version{grid-column:2}
  .doctor-action{grid-column:2}
  .doctor-identity{grid-template-columns:1fr}
  .doctor-head{align-items:flex-start}
  .runtime-grid{grid-template-columns:1fr}
  .fallback-row{grid-template-columns:minmax(0,1fr) 92px 28px}
  .fallback-row [data-fallback-model]{grid-column:1/-1;grid-row:2}
  .path-picker{align-items:stretch;flex-direction:column}
  .path-picker button{width:100%}
  .repo-actions{align-items:flex-start;flex-direction:column}
  .hub-tools,.hub-search{width:100%;min-width:0}
}
@media(max-width:720px){
  .icon-button,.compose-button{min-width:44px;min-height:44px}
  .nav-item,.new-task,.primary,.secondary,.runtime-button,.palette-row{min-height:44px}
  .brand-button{min-width:44px;min-height:44px}
  .panel-tabs .nav-item{min-height:48px}
  :root{--sidebar:0px}
  .app{grid-template-columns:1fr}
  .topbar{height:48px;margin:6px 6px 0}
  .decision-banner{margin:6px 6px 0}
  .sidebar{position:fixed;left:0;top:calc(var(--topbar-h) + 10px);bottom:6px;
    width:min(280px,calc(100vw - 44px));margin:0 0 0 6px;z-index:var(--z-sheet);
    transform:translateX(calc(-100% - 12px));visibility:hidden;
    transition:transform var(--dur-slow) var(--spring),visibility 0s var(--dur-slow)}
  .sidebar.open{transform:translateX(0);visibility:visible;
    transition:transform var(--dur-slow) var(--spring)}
  .mobile-sidebar{display:grid}
  .workspace{margin:6px 6px 6px}
  .thread-head{padding:0 var(--sp-4)}
  .thread-inner{width:calc(100% - 28px)}
  .composer-wrap{left:0;padding:24px 12px 10px}
  .decision{left:0;margin:0 6px 6px}
  .loop-detail{display:none}
  .hub-main{width:calc(100% - 24px);padding-top:30px}
  .settings-shell{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}
  .settings-nav{flex-direction:row;padding:8px;border-right:0;border-bottom:1px solid var(--line);
    overflow-x:auto}
  .settings-nav-button{min-width:160px;flex:1}
  .settings-content{padding:19px 17px}
  .runtime-wizard{height:min(760px,calc(100vh - 16px))}
  .runtime-shell{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}
  .runtime-nav{flex-direction:row;padding:8px;border-right:0;border-bottom:1px solid var(--line);
    overflow-x:auto}
  .runtime-nav-button{min-width:136px;flex:1}
  .runtime-content{padding:19px 17px}
  .project-wizard{height:min(760px,calc(100vh - 16px))}
  .wizard-progress{padding:12px 17px}
  #branch-label{display:none}
  .top-project{max-width:180px}
}
@media(max-width:560px){
  .topbar{padding:0 8px;gap:4px}
  .brand-button{padding-right:3px;font-size:0;gap:0}
  .top-project,#current-project-pin,.live-pill,.version{display:none}
  .thread-head{min-height:52px}
  .thread-inner{padding-top:20px}
  .composer{border-radius:var(--r-xl)}
  .composer-meta #model-summary{display:none}
  .turn-meta{flex-wrap:wrap}
  .finding-head{flex-wrap:wrap}
  .finding-head .spacer{display:none}
  .finding-head span:last-child{width:100%;overflow-wrap:anywhere}
  .run-overview{padding:13px 12px}
  .run-task{font-size:var(--fs-body)}
  .run-meta{flex-wrap:wrap}
  .loop{grid-template-columns:1fr;gap:0;padding:14px 12px 7px}
  .loop-step{display:grid;grid-template-columns:31px minmax(0,1fr) auto;grid-template-rows:auto auto;
    padding:0 0 11px;align-items:start}
  .loop-track{grid-row:1/3;height:auto;align-self:stretch}
  .loop-step:not(:last-child) .loop-track:after{top:25px;bottom:-8px;left:11px;right:auto;
    width:1px;height:auto}
  .loop-name{grid-column:2;grid-row:1;margin:3px 0 0}
  .loop-state{grid-column:3;grid-row:1;margin:4px 0 0 8px}
  .loop-detail{display:block;grid-column:2/4;grid-row:2;margin:3px 0 0;min-height:0;-webkit-line-clamp:3}
  .loop-focus{margin:0 12px 12px;grid-template-columns:1fr;gap:3px}
  .activity{padding:11px 12px 13px}
  .audit-event{grid-template-columns:24px minmax(0,1fr)}
  .event-time{grid-column:2;margin-top:-2px}
  .inspector{top:auto;right:6px;left:6px;bottom:6px;width:auto;max-height:min(560px,78vh);
    transform:translateY(calc(100% + 12px))}
  .inspector.open{transform:translateY(0)}
  .palette-shell{padding-top:8vh!important;padding-left:8px!important;padding-right:8px!important}
  .palette{width:100%}
  .decision-body{width:calc(100% - 32px)}
  .project-modal{padding:0}
  .wizard{max-height:100vh;height:100vh;border-radius:0;border-left:0;border-right:0}
  .wizard-head{padding:18px 17px 15px}
  .wizard-body{padding:18px 17px}
  .wizard-foot{padding:13px 17px;padding-bottom:max(13px,env(safe-area-inset-bottom))}
  .project-wizard,.settings-wizard{height:100dvh;max-height:100dvh}
  .project-wizard-body{padding:18px 17px}
  .wizard-progress li{grid-template-columns:26px minmax(0,1fr);column-gap:7px}
  .wizard-progress li>span{width:26px;height:26px}
  .wizard-progress li>small{display:none}
  .wizard-progress li:not(:last-child):after{top:12px;left:26px}
  .settings-shell{padding:0}
  .settings-nav{padding:7px}
  .settings-nav-button{min-width:0;min-height:48px;grid-template-columns:26px minmax(0,1fr);padding:7px}
  .settings-nav-button i,.settings-nav-button small{display:none}
  .settings-nav-icon{width:26px;height:26px}
  .settings-content{padding:18px 17px}
  .doctor-head{flex-wrap:wrap}
  .doctor-head .doctor-details-toggle{margin-left:27px}
  .role-choice-grid{grid-template-columns:1fr}
  .project-review{grid-template-columns:1fr}
  .project-wizard-foot>span{display:none}
  .project-row{grid-template-columns:minmax(0,1fr) auto 44px 44px;gap:8px;padding:14px}
  .project-row>span:first-child{grid-column:1/-1}
  .project-row>.project-stat:not(.project-tier){grid-column:1}
  .project-row>.status{grid-column:2}
  .project-row>.project-pin{grid-column:3}
  .project-row>.project-delete{grid-column:4}
  .project-pin,.project-delete,.artifact-action{width:44px;height:44px}
  .project-arrow{display:none}
  .preview-wizard{width:100%;height:100vh;max-height:none;border-radius:0}
  .preview-body{padding:8px}
  .preview-code,.preview-document,.preview-markdown{padding:18px 16px;border-radius:var(--r-sm)}
  .preview-frame{min-height:420px}
  .hpc-connection-grid,.hpc-limit-grid{grid-template-columns:1fr}
  .hpc-connection-grid .field:nth-child(2){grid-column:auto}
  .hpc-setup-section{padding:12px}
  .hpc-host-wizard .wizard-head p{max-width:280px}
  .runtime-grid,.runtime-content .form-grid{grid-template-columns:1fr}
  .runtime-wizard>.wizard-head p{display:none}
}
@media(max-width:380px){
  .composer-wrap{padding-left:8px;padding-right:8px}
  .thread-inner{width:calc(100% - 20px)}
  .thread-head{padding:0 10px}
  .state-pill .pill-detail{display:none}
}

/* Degradation matrix: every row is a testable contract. */
@media(prefers-contrast:more){
  :root,:root[data-theme="dark"]{--line:rgba(228,237,248,.28);--line-strong:rgba(228,237,248,.36);
    --text-3:#A6AEBB;--glass-border:rgba(255,255,255,.32)}
  :root[data-theme="light"]{--line:rgba(52,64,84,.34);--line-strong:rgba(52,64,84,.44);
    --text-3:#5C6472;--glass-border:rgba(31,38,50,.26)}
  .topbar,.hub-bar,.sidebar,.workspace,.inspector,.composer,.wizard,.palette,.project-table{border-width:2px}
  .state-pill{border:1px solid currentColor}
}
@media(prefers-reduced-motion:reduce){
  *,*:before,*:after{scroll-behavior:auto!important;animation-duration:.001ms!important;
    animation-iteration-count:1!important;transition-duration:.001ms!important}
  .state-pill.pill-live .pill-glyph{animation:none;opacity:1}
  .job-spinner,.project-progress i,.doctor-state.running{animation:none}
}
@media(prefers-reduced-transparency:reduce){
  .topbar,.hub-bar,.sidebar,.inspector,.composer,.wizard,.palette,.project-table,.drop-target{
    -webkit-backdrop-filter:none!important;backdrop-filter:none!important;
    background:var(--surface)!important}
  .project-modal,.drop-overlay{-webkit-backdrop-filter:none;backdrop-filter:none;
    background:rgba(6,9,14,.62)}
  body{background:var(--bg)}
}
@supports not ((-webkit-backdrop-filter:blur(1px)) or (backdrop-filter:blur(1px))){
  .topbar,.hub-bar,.sidebar,.inspector,.composer,.wizard,.palette,.project-table,.drop-target{
    background:var(--surface)}
}
@media(forced-colors:active){
  .topbar,.hub-bar,.sidebar,.inspector,.composer,.wizard,.palette,.project-table,.run-card,
  .review-card,.decision-banner{border:1px solid CanvasText}
  .primary,.compose-button.send{forced-color-adjust:none;background:Highlight;color:HighlightText}
}
</style></head>
<body>
<section class="project-hub" id="project-hub" aria-label="Projects">
  <header class="hub-bar"><button class="brand-button" id="hub-brand"><span class="brand-mark" aria-hidden="true">◇</span>
    CrossAudit <span class="version" id="hub-version">V4.14.0</span></button><span class="spacer"></span>
    <button class="icon-button" id="hub-locale" aria-label="Switch to Chinese" title="Switch language">中文</button>
    <button class="icon-button" id="hub-settings" aria-label="Settings" title="Settings">⚙</button>
    <button class="icon-button" id="hub-theme" aria-label="Switch theme">◐</button>
    <button class="primary" id="create-project">＋ New project</button></header>
  <main class="hub-main"><div class="hub-heading"><div><h1>Projects</h1>
    <p>Local project folders, each with its own files and individual chats.</p></div><div class="hub-summary" id="workspace-label">Discovering workspace…</div></div>
    <div class="job-panel" id="project-job"><span class="job-spinner"></span><div class="job-copy">
      <b id="job-title">Creating project</b><span id="job-detail">Validating settings…</span>
      <ul class="job-steps" id="job-steps"></ul><div class="job-guidance" id="job-guidance"></div></div>
      <button class="secondary" id="open-created" hidden>Open project</button></div>
    <div class="hub-tools"><input class="hub-search" id="project-search" placeholder="Search projects…"></div>
    <div class="project-table" id="project-list"><div class="hub-empty">Loading projects…</div></div>
  </main>
</section>

<div class="project-modal" id="project-modal" role="dialog" aria-modal="true" aria-labelledby="wizard-title">
  <form class="wizard project-wizard" id="project-form"><div class="wizard-head"><div><h2 id="wizard-title">Create a supervised project</h2>
    <p>Set up the workspace first, then choose the independent model team and GitHub delivery.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-project-modal" aria-label="Close">×</button></div>
    <ol class="wizard-progress" id="project-progress" aria-label="Project setup progress">
      <li class="active" data-project-indicator="1" aria-current="step"><span>1</span><b>Project</b><small>Name and workspace</small></li>
      <li data-project-indicator="2"><span>2</span><b>Model team</b><small>Generator and auditor</small></li>
      <li data-project-indicator="3"><span>3</span><b>GitHub</b><small>Delivery and review</small></li>
    </ol>
    <div class="wizard-body project-wizard-body"><section class="form-section project-step" data-project-step="1" tabindex="-1"><div class="step-heading"><span>Step 1 of 3</span><h3>Start with the project</h3><p>Choose where the work lives and describe the result you expect.</p></div><div class="form-grid">
      <label class="field"><span>Project name</span><input name="name" id="project-name" maxlength="80" required placeholder="chem-agent"></label>
      <label class="field full"><span>Local project folder</span><div class="path-picker"><input id="project-workspace" readonly required aria-label="Selected local project folder"><button type="button" class="secondary" id="choose-project-workspace">Choose folder…</button></div><small class="path-preview" id="project-path-preview">Choose the exact folder CrossAudit should use. The project name will not create another subfolder.</small></label>
      <label class="field full"><span>Project type</span><select name="project_type" id="project-type">
        <option value="general" selected>General work - documents, reviews, code</option>
        <option value="science">Scientific / data workflow - structured experiment outputs</option></select></label>
      <label class="field full"><span>What are you building, and what would count as a mistake?</span>
        <textarea name="description" maxlength="4000" required placeholder="A user-facing review that must be accurate, balanced, and delivered as one clear document."></textarea></label>
      <div class="field full"><span id="project-contract-hint">General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.</span></div>
      <details class="advanced-options field full"><summary>Advanced audit settings</summary><div class="advanced-options-body">
        <label class="field"><span>Automatic revision limit</span><select name="max_rounds" id="max-rounds-choice"><option value="1">1 - quick stop</option><option value="3" selected>3 - recommended</option><option value="5">5 - persistent</option><option value="10">10 - maximum</option></select><small class="field-help" id="round-limit-help">Up to 3 generator → auditor rounds, then the task pauses for you. It never auto-passes.</small></label>
      </div></details>
    </div></section>
    <section class="form-section project-step" data-project-step="2" tabindex="-1" hidden><div class="step-heading"><span>Step 2 of 3</span><h3>Choose the independent model team</h3><p>The generator creates the work. A different provider audits it before delivery.</p></div><div class="form-grid role-choice-grid">
      <div class="role-card"><div class="role-card-head"><span class="role-index">G</span><div><b>Generator</b><small>Creates and revises the work</small></div></div><label class="field"><span>Provider</span><select name="generator_vendor" id="generator-vendor"></select></label>
        <label class="field"><span>Connection</span><select name="generator_connection" id="generator-connection" required></select></label>
        <label class="field"><span>Model</span><select name="generator_model_choice" id="generator-model"></select></label>
        <details class="role-details" id="generator-details"><summary>Connection details</summary><div class="role-details-body">
          <label class="field"><span>API region</span><select name="generator_endpoint" id="generator-endpoint"></select><small class="field-help">The region must match the API key.</small></label>
          <label class="field custom-model off" id="generator-custom-wrap"><span>Custom model ID</span><input id="generator-custom" maxlength="120" placeholder="Model available to your account"></label>
          <div class="model-actions"><button type="button" class="secondary" data-refresh-models="generator">Refresh from provider</button></div>
        </div></details></div>
      <div class="role-card"><div class="role-card-head"><span class="role-index auditor">A</span><div><b>Independent auditor</b><small>Checks the result and cannot generate it</small></div></div><label class="field"><span>Provider</span><select name="auditor_vendor" id="auditor-vendor"></select></label>
        <label class="field"><span>Connection</span><select name="auditor_connection" id="auditor-connection" required></select></label>
        <label class="field"><span>Model</span><select name="auditor_model_choice" id="auditor-model"></select></label>
        <details class="role-details" id="auditor-details"><summary>Connection details</summary><div class="role-details-body">
          <label class="field"><span>API region</span><select name="auditor_endpoint" id="auditor-endpoint"></select><small class="field-help">The region must match the API key.</small></label>
          <label class="field custom-model off" id="auditor-custom-wrap"><span>Custom model ID</span><input id="auditor-custom" maxlength="120" placeholder="Model available to your account"></label>
          <div class="model-actions"><button type="button" class="secondary" data-refresh-models="auditor">Refresh from provider</button></div>
        </div></details></div>
    </div></section>
    <section class="form-section project-step" data-project-step="3" tabindex="-1" hidden><div class="step-heading"><span>Step 3 of 3</span><h3>Choose delivery and review</h3><p>GitHub pairing is optional. Review the local and model setup before creating anything.</p></div><div class="github-box">
      <label class="toggle-line"><input type="checkbox" name="github" id="github-toggle" checked><span><b>Create and connect two repositories</b>
        <small>The work repository holds deliverables. The audit repository holds rules, reports and the auditor secret.</small></span></label>
      <div class="connection" id="github-connection">Checking GitHub connection…</div>
      <div class="github-fields" id="github-fields"><div class="form-grid">
        <label class="field"><span>Work repository name</span><input name="science_repo" id="science-repo" maxlength="161" placeholder="owner/project"></label>
        <label class="field"><span>Audit repository name</span><input name="audit_repo" id="audit-repo" maxlength="161" placeholder="owner/project-audit"></label>
        <label class="toggle-line full"><input type="checkbox" name="adopt_existing" id="adopt-existing"><span><b>Use accessible repositories if these names already exist</b><small>Off by default. Leave it off when you want two new repositories.</small></span></label>
        <label class="toggle-line full"><input type="checkbox" name="public"><span><b>Public repositories</b><small>Off by default. Private is safer for a new project.</small></span></label>
      </div><div class="repo-actions"><button type="button" class="secondary" id="check-repositories">Check names</button><span class="repo-check" id="repo-check">Names will be checked again before anything is created.</span></div></div></div>
      <div class="project-review" id="project-review" aria-live="polite"></div></section><div class="wizard-error" id="wizard-error" role="alert"></div></div>
    <div class="wizard-foot project-wizard-foot"><span id="project-foot-note">Nothing is created until the final step.</span>
      <button type="button" class="secondary" id="cancel-project">Cancel</button><button type="button" class="secondary" id="project-back" hidden>Back</button>
      <button type="button" class="primary" id="project-next">Continue</button><button class="primary" id="submit-project" hidden>Create project</button></div>
  </form>
</div>

<div class="project-modal" id="recovery-modal" role="dialog" aria-modal="true" aria-labelledby="recovery-title">
  <form class="wizard" id="recovery-form"><div class="wizard-head"><div><h2 id="recovery-title">Finish GitHub setup</h2>
    <p>Correct the repository settings and continue from the last durable step.</p></div><span class="spacer"></span>
    <button type="button" class="icon-button" id="close-recovery" aria-label="Close">×</button></div>
    <div class="wizard-body"><div class="recovery-note" id="recovery-note"></div><input type="hidden" id="recovery-root">
      <div class="form-grid"><label class="field"><span>Work repository</span><input id="recovery-science" maxlength="161" required></label>
        <label class="field"><span>Audit repository</span><input id="recovery-audit" maxlength="161" required></label></div>
      <div class="connection" id="recovery-connection"></div>
      <div class="repo-actions"><button type="button" class="secondary" id="recovery-connect-github">Connect GitHub</button>
        <a class="secondary" id="recovery-help" target="_blank" rel="noopener" hidden>Open GitHub help ↗</a></div>
      <div class="wizard-error" id="recovery-error"></div></div>
    <div class="wizard-foot"><span>Retry is idempotent: repositories created before the interruption are reused, not duplicated.</span>
      <button type="button" class="secondary" id="cancel-recovery">Cancel</button><button class="primary" id="retry-recovery">Retry setup</button></div>
  </form>
</div>

<div class="project-modal" id="delete-project-modal" role="dialog" aria-modal="true" aria-labelledby="delete-project-title">
  <form class="wizard" id="delete-project-form"><div class="wizard-head"><div><h2 id="delete-project-title">Delete project</h2>
    <p>Review the local and GitHub impact before anything is changed.</p></div><span class="spacer"></span>
    <button type="button" class="icon-button" id="close-delete-project" aria-label="Close">×</button></div>
    <div class="wizard-body"><input type="hidden" id="delete-project-root">
      <div class="delete-summary"><b id="delete-project-name">Project</b><code id="delete-project-path"></code>
        <span id="delete-project-impact" class="delete-detail">Checking project state…</span></div>
      <div class="delete-warning" style="margin-top:12px">The local folder will move to CrossAudit Trash and can be recovered. GitHub repositories remain untouched unless you explicitly select permanent deletion below.</div>
      <label class="field" style="margin-top:14px"><span>Type the project name to confirm</span>
        <input id="delete-project-confirmation" autocomplete="off" required></label>
      <label class="toggle-line" style="margin-top:14px"><input type="checkbox" id="delete-working-repository"><span><b>Permanently delete working repository</b>
        <small id="delete-working-repository-name">No working repository detected.</small></span></label>
      <label class="toggle-line" style="margin-top:10px"><input type="checkbox" id="delete-audit-repository"><span><b>Permanently delete audit repository</b>
        <small id="delete-audit-repository-name">No audit repository detected.</small></span></label>
      <label class="field conditional-field off" id="delete-github-confirm-wrap" style="margin-top:12px"><span>Type DELETE GITHUB</span>
        <input id="delete-github-confirmation" autocomplete="off" placeholder="DELETE GITHUB"></label>
      <div class="connection" id="delete-github-authorization"></div>
      <button type="button" class="secondary" id="authorize-delete-repositories" hidden>Authorize GitHub deletion</button>
      <div class="wizard-error" id="delete-project-error"></div></div>
    <div class="wizard-foot"><span>Running tasks and remote compute block deletion.</span>
      <button type="button" class="secondary" id="cancel-delete-project">Cancel</button>
      <button class="danger-button" id="confirm-delete-project" disabled>Move project to Trash</button></div>
  </form>
</div>

<div class="project-modal" id="delete-chat-modal" role="dialog" aria-modal="true" aria-labelledby="delete-chat-title">
  <form class="wizard" id="delete-chat-form"><div class="wizard-head"><div><h2 id="delete-chat-title">Delete chat?</h2>
    <p id="delete-chat-name">This chat will disappear from the project sidebar.</p></div><span class="spacer"></span>
    <button type="button" class="icon-button" id="close-delete-chat" aria-label="Close">×</button></div>
    <div class="wizard-body"><input type="hidden" id="delete-chat-id">
      <div class="delete-warning">Audit reports, receipts, commits and delivered files are preserved in the project ledger. Deleting a chat never rewrites evidence that may already have admitted a result.</div>
      <p class="delete-detail" id="delete-chat-impact" style="margin:12px 0 0"></p>
      <div class="wizard-error" id="delete-chat-error"></div></div>
    <div class="wizard-foot"><span>This only removes the individual chat from navigation.</span>
      <button type="button" class="secondary" id="cancel-delete-chat">Cancel</button>
      <button class="danger-button" id="confirm-delete-chat">Delete chat</button></div>
  </form>
</div>

<div class="project-modal" id="file-preview-modal" role="dialog" aria-modal="true" aria-labelledby="file-preview-title">
  <section class="wizard preview-wizard"><div class="wizard-head"><div><h2 id="file-preview-title">File preview</h2>
    <p id="file-preview-meta">Preparing preview…</p></div><span class="spacer"></span>
    <a class="secondary" id="file-preview-download" download>Download</a>
    <button type="button" class="icon-button" id="close-file-preview" aria-label="Close preview">×</button></div>
    <div class="preview-body" id="file-preview-body"><div class="preview-loading">Loading audited deliverable…</div></div>
    <div class="preview-note" id="file-preview-note">The complete file remains available to download.</div>
  </section>
</div>

<div class="project-modal" id="runtime-modal" role="dialog" aria-modal="true" aria-labelledby="runtime-title">
  <form class="wizard runtime-wizard" id="runtime-form"><div class="wizard-head"><div><h2 id="runtime-title">Project controls</h2>
    <p>Choose how this project works. Changes apply to the next provider call.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-runtime" aria-label="Close">×</button></div>
    <div class="wizard-body runtime-shell"><nav class="runtime-nav" aria-label="Project control categories">
      <button type="button" class="runtime-nav-button active" data-runtime-panel="models" aria-pressed="true"><b>Models</b><small>Team & reasoning</small></button>
      <button type="button" class="runtime-nav-button" data-runtime-panel="automation" aria-pressed="false"><b>Automation</b><small>Audit & recovery</small></button>
      <button type="button" class="runtime-nav-button" data-runtime-panel="budgets" aria-pressed="false"><b>Budgets</b><small>Limits & warnings</small></button>
      <button type="button" class="runtime-nav-button" data-runtime-panel="instructions" aria-pressed="false"><b>Instructions</b><small>Project guidance</small></button>
    </nav><div class="runtime-content">
      <section class="runtime-pane" data-runtime-pane="models" tabindex="-1"><div class="runtime-pane-heading"><h3>Models, reasoning & audit loop</h3><p>Choose one model to do the work and a different provider to review it independently.</p></div>
        <div class="runtime-grid"><section class="role-card" id="runtime-generator-card"><div class="runtime-role-head"><b>Generator</b><span id="runtime-generator-vendor">…</span></div>
          <label class="field"><span>Model</span><select id="runtime-generator-model"></select></label>
          <label class="field custom-model off" id="runtime-generator-custom-wrap"><span>Custom model ID</span><input id="runtime-generator-custom" maxlength="120" placeholder="Exact provider model ID"></label>
          <label class="field"><span>Reasoning effort</span><select id="runtime-generator-effort"></select><small class="effort-help" id="runtime-generator-effort-help"></small></label>
          <div class="model-actions"><button type="button" class="secondary" data-runtime-refresh="generator">Refresh models</button></div>
        </section><section class="role-card" id="runtime-auditor-card"><div class="runtime-role-head"><b>Independent auditor</b><span id="runtime-auditor-vendor">…</span></div>
          <label class="field"><span>Model</span><select id="runtime-auditor-model"></select></label>
          <label class="field custom-model off" id="runtime-auditor-custom-wrap"><span>Custom model ID</span><input id="runtime-auditor-custom" maxlength="120" placeholder="Exact provider model ID"></label>
          <label class="field"><span>Reasoning effort</span><select id="runtime-auditor-effort"></select><small class="effort-help" id="runtime-auditor-effort-help"></small></label>
          <div class="model-actions"><button type="button" class="secondary" data-runtime-refresh="auditor">Refresh models</button></div>
        </section></div><div class="runtime-note" id="runtime-note"><b>Safe handoff.</b> A running audit keeps the models and controls it started with. These changes apply to the next call.</div>
      </section>
      <section class="runtime-pane" data-runtime-pane="automation" tabindex="-1" hidden><div class="runtime-pane-heading"><h3>Audit automation</h3><p>CrossAudit revises automatically, then pauses for you instead of silently accepting an unresolved result.</p></div>
        <section class="form-section"><div class="form-title">Audit loop</div><label class="field"><span>Automatic revision limit</span><select id="runtime-max-rounds"><option value="1">1 - quick stop</option><option value="3">3 - recommended</option><option value="5">5 - persistent</option><option value="10">10 - maximum</option></select><small class="field-help">After this many generator → auditor rounds, the task pauses and explains what needs your decision. It never auto-passes.</small></label></section>
        <details class="runtime-advanced"><summary>Advanced provider recovery</summary><div class="runtime-advanced-body"><div class="form-title">Automatic provider recovery</div>
          <div class="runtime-grid"><div class="role-card"><div class="runtime-role-head"><b>Generator fallback chain</b><span>in order</span></div><div class="fallback-list" id="runtime-generator-fallbacks"></div><div class="model-actions"><button type="button" class="secondary" data-add-fallback="generator">＋ Add fallback</button></div></div>
          <div class="role-card"><div class="runtime-role-head"><b>Auditor fallback chain</b><span>in order</span></div><div class="fallback-list" id="runtime-auditor-fallbacks"></div><div class="model-actions"><button type="button" class="secondary" data-add-fallback="auditor">＋ Add fallback</button></div></div></div>
          <div class="form-grid" style="margin-top:13px"><label class="field"><span>Attempts per route</span><input id="runtime-max-attempts" type="number" min="1" max="10"></label>
            <label class="field"><span>Initial retry delay (seconds)</span><input id="runtime-initial-backoff" type="number" min="0" max="60" step="0.1"></label>
            <label class="field"><span>Maximum retry delay (seconds)</span><input id="runtime-max-backoff" type="number" min="0" max="300" step="0.1"></label>
            <label class="field"><span>Honor Retry-After up to (seconds)</span><input id="runtime-retry-after-cap" type="number" min="0" max="900" step="1"></label>
            <label class="field"><span>Open circuit after failures</span><input id="runtime-circuit-failures" type="number" min="1" max="20"></label>
            <label class="field"><span>Circuit cooldown (seconds)</span><input id="runtime-circuit-cooldown" type="number" min="1" max="3600" step="1"></label></div>
          <small class="field-help">Retries stay inside one provider call and do not consume Generator → Auditor revision rounds. Fallback routes run only after the route before them fails.</small>
        </div></details>
      </section>
      <section class="runtime-pane" data-runtime-pane="budgets" tabindex="-1" hidden><div class="runtime-pane-heading"><h3>Usage guardrails</h3><p>Optional local warnings and stops. Your provider remains the authority for billing.</p></div>
        <div class="form-grid"><label class="field"><span>Daily token warning</span><input id="runtime-daily-token-warning" type="number" min="1" placeholder="No warning"></label>
          <label class="field"><span>Daily token hard limit</span><input id="runtime-daily-token-limit" type="number" min="1" placeholder="No limit"></label>
          <label class="field"><span>Monthly API-value warning (USD)</span><input id="runtime-monthly-cost-warning" type="number" min="0.01" step="0.01" placeholder="No warning"></label>
          <label class="field"><span>Monthly API-value hard limit (USD)</span><input id="runtime-monthly-cost-limit" type="number" min="0.01" step="0.01" placeholder="No limit"></label></div>
        <div class="guardrail-state" id="runtime-guardrail-state">Limits are local safeguards; provider billing remains authoritative.</div>
      </section>
      <section class="runtime-pane" data-runtime-pane="instructions" tabindex="-1" hidden><div class="runtime-pane-heading"><h3>Generator guidance</h3><p>Reusable project instructions shape the work without weakening the independent audit rules.</p></div>
        <div class="form-grid"><label class="field"><span>Edit guidance</span><select id="runtime-skill-select"><option value="__new__">Create new guidance…</option></select></label>
          <label class="field"><span>Name</span><input id="runtime-skill-name" maxlength="60" placeholder="house-style"></label>
          <label class="field full"><span>Applies to paths (optional)</span><input id="runtime-skill-scope" maxlength="500" placeholder="work/reports, work/data"><small class="field-help">Comma-separated project-relative prefixes. Leave blank to apply on every task.</small></label>
          <label class="field full"><span>Instructions for the generator</span><textarea id="runtime-skill-body" maxlength="60000" placeholder="Describe the tone, output shape, conventions or checklist this project should follow."></textarea><small class="field-help">Guidance changes how the generator works. It never changes the Constitution or what the independent auditor enforces.</small></label></div>
        <div class="model-actions"><button type="button" class="secondary" id="save-runtime-skill">Save guidance</button><span class="repo-check" id="runtime-skill-status"></span></div>
      </section>
      <div class="wizard-error" id="runtime-error"></div>
    </div></div>
    <div class="wizard-foot"><span id="runtime-foot">Automatic means the provider chooses its documented default.</span>
      <button type="button" class="secondary" id="cancel-runtime">Cancel</button><button class="primary" id="save-runtime">Save for next call</button></div>
  </form>
</div>

<div class="decision" id="resolution-modal" aria-label="Human decision">
  <form class="decision-body" id="resolution-form"><header class="decision-head">
    <span class="decision-glyph" aria-hidden="true"></span><div>
    <div class="decision-flag" id="resolution-flag">Automatic loop paused</div>
    <h1 id="resolution-title">The audit needs your decision</h1>
    <p id="resolution-summary">CrossAudit stopped safely. Nothing will continue or be admitted until you decide.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-resolution" aria-label="Review later" title="Review later">×</button></header>
    <input type="hidden" id="resolution-cycle"><input type="hidden" id="resolution-action">
    <section class="decision-block"><div class="decision-label">Goal</div>
      <p class="decision-goal" id="resolution-goal">The task this conversation asked for.</p></section>
    <section class="decision-block"><div class="decision-label">Attempted</div>
      <div class="decision-limit"><span class="decision-limit-mark" aria-hidden="true">!</span><div><b id="resolution-limit-title">Automatic audit limit reached</b>
        <p id="resolution-limit-copy">The configured rounds were used without a passing result.</p></div></div>
      <div class="decision-attempts" id="resolution-attempts"></div></section>
    <section class="decision-block"><div class="decision-label">Blocked on</div>
      <div class="decision-title-row">What is still blocking the result <span class="decision-count" id="resolution-issue-count">0</span></div>
      <div class="decision-issues" id="resolution-issues"></div></section>
    <section class="decision-block"><div class="decision-label">Recommendation</div>
      <p class="decision-request" id="resolution-request">Choose whether to provide concrete correction guidance for one more round or stop this task.</p>
      <div class="decision-secondary"><button type="button" class="secondary" id="resolution-open-settings" hidden>Review provider connection</button>
      <button type="button" class="secondary" id="resolution-open-runtime" hidden>Change model or fallback</button></div>
      <div class="decision-options">
        <label class="decision-option"><input type="radio" name="resolution-choice" value="reopen" required><span><b id="resolution-reopen-title">Revise and continue</b><i class="suggested-tag">Suggested</i><small id="resolution-reopen-copy">Give the generator specific correction guidance and unlock one additional audited round.</small></span></label>
        <label class="decision-option"><input type="radio" name="resolution-choice" value="close" required><span><b>Stop this task</b><small>Keep the current output unadmitted and close the audit cycle with your reason.</small></span></label>
      </div>
      <label class="field decision-guidance"><span id="resolution-reason-label">Your guidance or reason</span><textarea id="resolution-reason" maxlength="400" required placeholder="Select an action, then explain what CrossAudit should do."></textarea></label>
      <div class="decision-ledger-note"><b>Human decision required.</b> Your action and explanation become part of the durable audit ledger.</div>
      <div class="decision-ledger-note">The models cannot approve their own result or bypass this pause.</div>
      <div class="wizard-error" id="resolution-error"></div>
      <div class="decision-actions"><button type="button" class="secondary" id="cancel-resolution">Review later</button>
        <span class="spacer"></span><button class="primary" id="submit-resolution">Record human decision</button></div>
    </section>
  </form>
</div>

<div class="project-modal" id="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
  <form class="wizard settings-wizard" id="settings-form"><div class="wizard-head"><div><h2 id="settings-title">CrossAudit settings</h2>
    <p>Manage this Mac and model connections without using Terminal.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-settings" aria-label="Close settings">×</button></div>
    <div class="wizard-body settings-shell"><nav class="settings-nav" aria-label="Settings sections">
      <button type="button" class="settings-nav-button active" data-settings-panel="general" aria-pressed="true"><span class="settings-nav-icon general" aria-hidden="true"></span><span><b>General</b><small>Workspace and this Mac</small></span><i id="settings-general-state">…</i></button>
      <button type="button" class="settings-nav-button" data-settings-panel="providers" aria-pressed="false"><span class="settings-nav-icon providers" aria-hidden="true"></span><span><b>Model providers</b><small>Subscriptions and API keys</small></span><i id="settings-provider-count">0</i></button>
    </nav><div class="settings-content">
    <section class="form-section settings-pane" data-settings-pane="general" tabindex="-1"><div class="step-heading settings-heading"><span>General</span><h3>Workspace and application readiness</h3><p>CrossAudit checks required software and offers a direct recovery action when something needs attention.</p></div>
      <div class="settings-readiness"><div class="readiness-item">Git<span id="git-state">…</span></div>
        <div class="readiness-item">GitHub connection tool<span id="ghcli-state">…</span></div>
        <div class="readiness-item">Application build<span id="runtime-state">…</span></div>
        <div class="readiness-item">Code identity<span id="digest-state">…</span></div></div>
      <div class="doctor-panel"><div class="doctor-head"><span class="doctor-state" id="doctor-state"></span>
        <div class="doctor-head-copy"><b>Environment Doctor</b><small id="doctor-summary">Preparing checks…</small></div>
        <button type="button" class="secondary doctor-details-toggle" id="toggle-doctor-details" aria-expanded="false">Show details</button>
        <button type="button" class="secondary" id="run-doctor">Run check</button></div>
        <div class="doctor-list" id="doctor-checks"><div class="doctor-empty">Checking required software…</div></div>
        <div class="doctor-message" id="doctor-message"></div></div>
      <label class="field" style="margin-top:12px"><span>Project workspace</span><div class="path-picker"><input id="settings-workspace" readonly><button type="button" class="secondary" id="choose-settings-workspace">Choose folder…</button></div></label>
    </section><section class="form-section settings-pane" data-settings-pane="providers" tabindex="-1" hidden><div class="step-heading settings-heading"><span>Model providers</span><h3>Connect the services you use</h3><p>Open only the provider you want to configure. Existing secrets are never displayed again.</p></div>
      <div class="provider-note"><b>Developer access and consumer subscriptions are different products.</b> CrossAudit only offers web sign-in where the provider publishes a supported third-party inference flow. It never imports browser cookies or CLI session files.</div>
      <div id="provider-credentials"></div>
    </section><div class="wizard-error" id="settings-error" role="alert"></div></div></div>
    <div class="wizard-foot"><span id="settings-foot-note">API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.</span>
      <button type="button" class="secondary" id="cancel-settings">Cancel</button><button class="primary" id="save-settings">Save settings</button></div>
  </form>
</div>

<div class="project-modal" id="compute-host-modal" role="dialog" aria-modal="true" aria-labelledby="compute-host-title">
  <form class="wizard hpc-host-wizard" id="compute-host-form"><div class="wizard-head"><div><h2 id="compute-host-title">Add SSH compute host</h2>
    <p>Connect a workstation or Slurm cluster through your existing SSH setup.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-compute-host" aria-label="Close">×</button></div>
    <div class="wizard-body"><div class="hpc-host-intro"><span class="hpc-host-intro-icon">⌘</span><div><b>CrossAudit does not install anything on the cluster.</b>It uses OpenSSH config, keys, ssh-agent and ProxyJump already configured on this Mac, then runs a read-only capability check.</div></div>
      <section class="hpc-setup-section"><div class="hpc-section-head"><span class="hpc-section-index">1</span><div><b>Connection</b><p>Name the SSH target and choose a shared work directory for durable remote jobs.</p></div></div>
        <div class="hpc-connection-grid">
          <label class="field"><span>SSH alias</span><input name="alias" id="compute-alias" list="compute-aliases" maxlength="128" required placeholder="hpc-login"><datalist id="compute-aliases"></datalist><small class="field-help">Alias from ~/.ssh/config or a reachable hostname.</small></label>
          <label class="field"><span>Shared scratch directory</span><input name="scratch" maxlength="500" required placeholder="/scratch/your-user/crossaudit"><small class="field-help">For Slurm, login and compute nodes must both see this path.</small></label>
          <label class="field"><span>Parallel jobs</span><input name="concurrency" type="number" min="1" max="100" value="4" required><small class="field-help">Project limit</small></label>
          <label class="field full"><span>Cluster notes <small>optional</small></span><textarea name="details" maxlength="4000" placeholder="Approved partitions, module loads, environment activation, or account policy."></textarea></label>
        </div></section>
      <section class="hpc-setup-section"><div class="hpc-section-head"><span class="hpc-section-index">2</span><div><b>Generator access</b><p>Manual job submission is always available. Automatic access is optional and constrained by hard ceilings.</p></div></div>
        <label class="hpc-permission"><input name="agent_enabled" id="hpc-agent-enabled" type="checkbox"><span><b>Allow Generator to use this host automatically</b><small>The Generator can submit calculation scripts without per-job confirmation. Use a dedicated least-privilege SSH account.</small></span></label>
        <div class="hpc-policy off" id="hpc-agent-policy"><div class="hpc-policy-title">Generator compute policy <span>hard maximums per task</span></div>
          <div class="hpc-limit-grid">
            <label class="field"><span>Jobs per task</span><input name="agent_max_jobs" type="number" min="1" max="10" value="2" required></label>
            <label class="field"><span>Maximum nodes</span><input name="agent_max_nodes" type="number" min="1" max="64" value="1" required></label>
            <label class="field"><span>Maximum CPUs</span><input name="agent_max_cpus" type="number" min="1" max="4096" value="8" required></label>
            <label class="field"><span>Maximum GPUs</span><input name="agent_max_gpus" type="number" min="0" max="64" value="0" required></label>
            <label class="field"><span>Maximum memory</span><input name="agent_max_memory" value="16G" required></label>
            <label class="field"><span>Maximum wall time</span><input name="agent_max_walltime" value="01:00:00" required></label>
          </div><details class="hpc-advanced"><summary>Scheduler restrictions (optional)</summary><div class="hpc-limit-grid">
            <label class="field"><span>Fixed partition</span><input name="agent_partition" maxlength="128" placeholder="cpu"></label>
            <label class="field"><span>Fixed account</span><input name="agent_account" maxlength="128" placeholder="lab-account"></label>
            <label class="field"><span>Fixed QoS</span><input name="agent_qos" maxlength="128"></label>
          </div></details></div></section>
      <section class="hpc-setup-section"><div class="hpc-section-head"><span class="hpc-section-index">3</span><div><b>Host identity</b><p>Known host keys are required. A changed key always stops the connection.</p></div></div>
        <label class="hpc-host-key"><input name="trust_first_key" type="checkbox"><span><b>Trust a new host key once</b><small>Only select this after verifying the hostname with your cluster administrator. Existing or changed keys are never replaced.</small></span></label>
      </section><div class="wizard-error" id="compute-host-error"></div></div>
    <div class="wizard-foot"><span>Next: read-only connection and capability check.</span>
      <button type="button" class="secondary" id="cancel-compute-host">Cancel</button><button class="primary" id="save-compute-host">Probe & add</button></div>
  </form>
</div>

<div class="project-modal" id="compute-job-modal" role="dialog" aria-modal="true" aria-labelledby="compute-job-title">
  <form class="wizard" id="compute-job-form"><div class="wizard-head"><div><h2 id="compute-job-title">Submit remote job</h2>
    <p>Review the exact script and requested resources. The job runs as your SSH user outside the local sandbox.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-compute-job" aria-label="Close">×</button></div>
    <div class="wizard-body"><div class="form-grid">
      <label class="field"><span>Compute host</span><select name="host_id" id="compute-job-host" required></select></label>
      <label class="field"><span>Job name</span><input name="name" maxlength="80" value="CrossAudit job" required></label>
      <label class="field"><span>Partition</span><input name="partition" maxlength="128" placeholder="gpu"></label>
      <label class="field"><span>Account</span><input name="account" maxlength="128" placeholder="lab-account"></label>
      <label class="field"><span>Wall time</span><input name="walltime" value="00:30:00" required></label>
      <label class="field"><span>Memory</span><input name="memory" placeholder="16G"></label>
      <label class="field"><span>Nodes</span><input name="nodes" type="number" min="1" max="1024" value="1" required></label>
      <label class="field"><span>CPUs per task</span><input name="cpus" type="number" min="1" max="4096" value="1" required></label>
      <label class="field"><span>GPUs</span><input name="gpus" type="number" min="0" max="1024" value="0" required></label>
      <label class="field"><span>QoS</span><input name="qos" maxlength="128"></label>
      <label class="field full"><span>Job script</span><textarea class="hpc-script" name="script" required spellcheck="false" placeholder="module load python\npython analysis.py"></textarea></label>
      <div class="field full"><span>Input files</span><input id="compute-input-files" type="file" multiple hidden>
        <button type="button" class="secondary" id="add-compute-inputs">＋ Add files</button>
        <div class="field-help" id="compute-input-summary">Optional. Files are streamed to inputs/ on the remote host with no CrossAudit size or count quota.</div>
        <div class="hpc-input-list" id="compute-input-list"></div></div>
      <label class="hpc-confirm field full"><input name="approved" type="checkbox" required><span><b>I approve this remote execution</b>The script can access anything my account can read or write on this host. Closing CrossAudit will not stop it.</span></label>
    </div><div class="wizard-error" id="compute-job-error"></div></div>
    <div class="wizard-foot"><span>Slurm jobs use sbatch; workstations use a detached nohup process. Both survive connection loss.</span>
      <button type="button" class="secondary" id="cancel-compute-job">Cancel</button><button class="primary" id="submit-compute-job">Submit job</button></div>
  </form>
</div>

<div class="project-modal" id="mcp-modal" role="dialog" aria-modal="true" aria-labelledby="mcp-title">
  <form class="wizard" id="mcp-form"><div class="wizard-head"><div><h2 id="mcp-title">Add MCP server</h2>
    <p>Connect project tools through the official Model Context Protocol lifecycle.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-mcp" aria-label="Close">×</button></div>
    <div class="wizard-body"><input type="hidden" name="server_id" id="mcp-server-id"><div class="form-grid">
      <label class="field"><span>Server name</span><input name="name" id="mcp-name" maxlength="80" required placeholder="Research tools"></label>
      <label class="field"><span>Transport</span><select name="transport" id="mcp-transport"><option value="stdio">Local stdio</option><option value="http">Streamable HTTP</option></select></label>
      <div class="field full mcp-transport-fields" id="mcp-stdio-fields"><div class="form-grid">
        <label class="field"><span>Executable</span><input name="command" id="mcp-command" maxlength="1000" placeholder="npx" autocomplete="off"></label>
        <label class="field"><span>Arguments</span><textarea name="args_text" id="mcp-args" maxlength="32000" placeholder="-y&#10;@example/mcp-server"></textarea><small class="field-help">One argument per line. CrossAudit never invokes a shell.</small></label>
        <label class="hpc-confirm field full"><input name="approve_local_code" type="checkbox"><span><b>I approve this exact local command</b>A local MCP server runs with this app's user permissions and may access files or the network. Verify its publisher and arguments.</span></label>
      </div></div>
      <div class="field full mcp-transport-fields off" id="mcp-http-fields"><div class="form-grid">
        <label class="field full"><span>MCP endpoint</span><input name="url" id="mcp-url" maxlength="2000" placeholder="Secure MCP endpoint URL"></label>
        <label class="field"><span>Bearer token (optional)</span><input name="bearer_token" id="mcp-token" type="password" maxlength="16384" autocomplete="off" placeholder="Leave blank to keep saved token"></label>
        <label class="hpc-confirm field"><input name="allow_private_network" type="checkbox"><span><b>Allow a verified private-network server</b>Use only for an enterprise hostname you control. Public remote servers must use HTTPS.</span></label>
      </div></div>
      <label class="field"><span>Request timeout</span><input name="timeout" type="number" min="1" max="300" value="30" required></label>
      <label class="field"><span>Calls per task</span><input name="max_calls_per_task" type="number" min="1" max="20" value="5" required></label>
      <label class="field full"><span>Approved tool names</span><input name="allowed_tools_text" id="mcp-allowed-tools" maxlength="12000" placeholder="search, fetch_record"><small class="field-help">Comma-separated exact names. Save once without enabling to inspect advertised tools first.</small></label>
      <label class="hpc-confirm field full"><input name="allow_all_tools" type="checkbox"><span><b>Approve all tools advertised during this connection</b>Only the current list is approved. Tools added by the server later remain blocked until you review them.</span></label>
      <label class="hpc-confirm field full"><input name="enabled" type="checkbox"><span><b>Allow Generator to call the approved tools automatically</b>Calls appear live in the task loop. Tool output is treated as untrusted external data and never becomes an audit rule.</span></label>
      <div class="field full"><span>Advertised tools</span><div class="mcp-tool-list" id="mcp-tool-preview"><span class="field-help">Connect the server to discover tools.</span></div></div>
    </div><div class="wizard-error" id="mcp-error"></div></div>
    <div class="wizard-foot"><span>Bearer tokens are write-only Keychain items. Local commands are stored without secrets.</span>
      <button type="button" class="secondary" id="cancel-mcp">Cancel</button><button class="primary" id="save-mcp">Connect & save</button></div>
  </form>
</div>

<div class="drop-overlay" id="drop-overlay" aria-hidden="true"><div class="drop-target">
  <div class="drop-icon">＋</div><b>Drop files to add them</b>
  <span>No CrossAudit file-count or file-size quota. Available storage, filesystem limits and provider context still apply.</span>
</div></div>

<div class="project-modal palette-shell" id="palette" role="dialog" aria-modal="true" aria-labelledby="palette-title">
  <div class="palette"><h2 class="sr-only" id="palette-title">Command palette</h2>
    <input class="palette-input" id="palette-input" placeholder="Type a command or search…" autocomplete="off" aria-label="Command palette">
    <div class="palette-list" id="palette-list"></div></div>
</div>

<div class="app">
  <header class="topbar">
    <button class="icon-button mobile-sidebar" id="sidebar-toggle" aria-label="Open navigation"
      aria-controls="sidebar-panel" aria-expanded="false">☰</button>
    <button class="icon-button" id="back-projects" aria-label="Back to projects" title="Back to projects">←</button>
    <button class="brand-button" id="projects-home"><span class="brand-mark" aria-hidden="true">◇</span>CrossAudit
      <span class="version" id="version-badge">V4.14.0</span></button>
    <button class="top-project" id="project-switcher"><b id="proj">…</b> <span id="branch-label">/ project folder</span></button>
    <button class="icon-button" id="current-project-pin" aria-label="Pin project" title="Pin project">☆</button>
    <span class="spacer"></span>
    <div class="live-pill"><span class="live-dot" id="livedot"></span><span id="conn-text">connecting</span></div>
    <button class="icon-button" id="palette-open" aria-label="Command palette" title="Command palette">⌘</button>
    <button class="icon-button" id="locale-toggle" aria-label="Switch to Chinese" title="Switch language">中文</button>
    <button class="icon-button" id="settings-open" aria-label="Settings" title="Settings">⚙</button>
    <button class="icon-button" id="theme-toggle" aria-label="Switch to dark theme" title="Toggle theme">◐</button>
    <button class="icon-button" id="inspect-toggle" aria-label="Toggle context panel"
      aria-controls="inspector" aria-expanded="false">☷</button>
  </header>

  <div class="decision-banner" id="decision-banner" hidden><span class="banner-glyph" aria-hidden="true"></span>
    <b id="decision-banner-text">1 task needs your decision</b>
    <button type="button" class="secondary" id="decision-banner-review">Review</button></div>

  <button class="scrim" id="scrim" aria-label="Close open panel"></button>

  <aside class="sidebar" id="sidebar-panel" aria-label="Chats">
    <div class="rail-search"><span class="rail-search-icon" aria-hidden="true"></span>
      <input id="rail-search" placeholder="Search chats" aria-label="Search chats"><kbd>⌘K</kbd></div>
    <button class="new-task" id="new-task"><span aria-hidden="true">＋</span>New chat<span>⌘N</span></button>
    <div class="task-list" id="task-list"></div>
    <div class="sidebar-foot"><b id="side-project">…</b><span id="tier-label">local controller</span></div>
  </aside>

  <main class="workspace">
    <div class="thread-head"><div class="thread-title"><h1 id="thread-title">New task</h1></div><span class="spacer"></span>
      <span class="state-pill" id="thread-status"><span class="pill-glyph" aria-hidden="true"></span><span class="pill-label">ready</span><span class="pill-detail" hidden></span></span>
      <button type="button" class="runtime-button" id="runtime-open" title="Switch models, reasoning effort and audit loop settings">Project controls</button></div>
    <div class="thread" id="thread"><div class="thread-inner">
      <div class="interrupted" id="interrupted"></div><div id="conversation"></div>
    </div></div>
  </main>

  <div class="composer-wrap"><form class="composer" id="f" autocomplete="off">
    <input id="file-input" type="file" multiple hidden>
    <div class="contract-preview" id="contract-preview"></div>
    <div class="attachments" id="attachments"></div>
    <div class="audience-bar" aria-label="Message recipient"><span class="audience-label">To</span>
      <button type="button" class="audience-chip active" data-audience="auto">Auto</button>
      <button type="button" class="audience-chip" data-audience="generator">@ Generator</button>
      <button type="button" class="audience-chip" data-audience="auditor">@ Auditor</button></div>
    <div class="compose-row"><button type="button" class="compose-button" id="attach" aria-label="Add files" title="Add files"><span class="attach-glyph" aria-hidden="true"></span></button>
      <div class="compose-well"><textarea id="say" rows="1" placeholder="Message the group, or @ someone…"></textarea></div>
      <button type="button" id="stop-run" class="compose-button stop" aria-label="Cancel running task" title="Cancel running task" hidden><span class="stop-glyph" aria-hidden="true"></span></button>
      <button id="send" class="compose-button send" aria-label="Run task"><span class="send-glyph" aria-hidden="true"></span></button></div>
    <div class="composer-meta"><button type="button" id="model-summary">Generator → Auditor</button>
      <span class="autonomy-summary" title="Generator infers focus, format, tone, and structure unless you specify them.">Auto-planning</span><span class="spacer"></span>
      <span>Enter to send · Shift+Enter for new line</span></div><div class="route" id="route"></div>
  </form></div>

  <aside class="inspector" id="inspector" aria-label="Context panel">
    <div class="inspect-head"><h2 id="panel-title">Files</h2><span class="spacer"></span>
      <button class="icon-button" id="inspect-close" aria-label="Close context panel">×</button></div>
    <nav class="panel-tabs" id="workspace-tools" aria-label="Context tabs">
      <button type="button" class="nav-item" data-view="artifacts" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Files</button>
      <button type="button" class="nav-item" data-view="audits" aria-pressed="false" aria-label="Audit context"><span class="nav-icon" aria-hidden="true"></span>Audit</button>
      <button type="button" class="nav-item" data-view="models" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Models</button>
      <button type="button" class="nav-item" data-view="usage" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Usage</button>
      <button type="button" class="nav-item" data-view="compute" aria-pressed="false"><span class="nav-icon" aria-hidden="true"></span>Compute</button></nav>
    <div class="panel-body">
      <div class="panel-pane" id="panel-models" hidden>
        <section class="inspect-section"><div class="inspect-title">Models</div>
          <div class="model"><span class="role-mark generator" aria-hidden="true">G</span><div class="model-copy"><div class="model-role">Generator</div><div class="model-name" id="runtime-generator">…</div></div></div>
          <div class="model"><span class="role-mark auditor" aria-hidden="true">A</span><div class="model-copy"><div class="model-role">Independent auditor</div><div class="model-name" id="runtime-auditor">…</div></div></div>
          <div class="model-actions-row"><button type="button" class="secondary" id="panel-open-runtime">Change models</button>
            <button type="button" class="secondary" data-view="tools">Tools &amp; Skills</button></div></section>
        <section class="inspect-section"><div class="inspect-title">Loop parameters</div>
          <div class="kv"><span>Maximum rounds</span><span id="max-rounds">…</span></div>
          <div class="kv"><span>Current round</span><span id="current-round">-</span></div>
          <div class="kv"><span>Constitution</span><span id="rules-count">…</span></div>
          <div class="kv"><span>Admission tier</span><span id="tier-value">…</span></div></section>
        <section class="inspect-section"><div class="inspect-title">Deterministic checks</div>
          <div id="runtime-checks"></div></section>
        <section class="inspect-section"><div class="inspect-title">Ledger</div>
          <div class="mini-metrics" id="mini-metrics"></div></section>
        <section class="inspect-section"><div class="inspect-title">Needs attention</div>
          <div id="escalations"></div></section>
      </div>
      <div class="panel-pane" id="panel-dynamic"></div>
    </div>
  </aside>
</div>

<script>
const T = new URLSearchParams(location.search).get('t') || '';
const LOCALE_KEY='crossaudit-locale';
const LOCALE_COOKIE='crossaudit_v4_locale';
const ZH={
  "Projects":"项目","Local project folders, each with its own files and individual chats.":"本地项目文件夹，每个项目都有自己的文件和独立对话。",
  "Discovering workspace…":"正在发现工作区…","Creating project":"正在创建项目","Validating settings…":"正在验证设置…",
  "Open project":"打开项目","Search projects…":"搜索项目…","New project":"新建项目","＋ New project":"＋ 新建项目",
  "Create a supervised project":"创建受监督项目","Configure both roles and, if you choose, create the separated GitHub repositories.":"配置两个角色，并可选择创建相互隔离的 GitHub 仓库。",
  "Set up the workspace first, then choose the independent model team and GitHub delivery.":"先设置工作区，再选择相互独立的模型团队和 GitHub 交付方式。",
  "Project setup progress":"项目设置进度","Name and workspace":"名称和工作区","Model team":"模型团队","Generator and auditor":"生成者和审计者","Delivery and review":"交付与确认",
  "Step 1 of 3":"第 1 / 3 步","Step 2 of 3":"第 2 / 3 步","Step 3 of 3":"第 3 / 3 步",
  "Start with the project":"先定义项目","Choose where the work lives and describe the result you expect.":"选择工作所在位置，并描述你期望的结果。",
  "Advanced audit settings":"高级审计设置","Choose the independent model team":"选择相互独立的模型团队",
  "The generator creates the work. A different provider audits it before delivery.":"生成者负责完成工作，交付前由另一家供应商独立审计。",
  "Creates and revises the work":"创建并修订工作","Checks the result and cannot generate it":"检查结果，且不能参与生成",
  "Choose delivery and review":"选择交付方式并确认","GitHub pairing is optional. Review the local and model setup before creating anything.":"GitHub 配对是可选项。创建任何内容前，请确认本地与模型设置。",
  "Nothing is created until the final step.":"到最后一步前不会创建任何内容。","Back":"返回","Continue":"继续",
  "Project":"项目","Project name":"项目名称","Project type":"项目类型","General work - documents, reviews, code":"通用工作——文档、评审、代码",
  "Scientific / data workflow - structured experiment outputs":"科学 / 数据工作流——结构化实验输出",
  "General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.":"通用项目检查格式、引用、链接和完整性，不要求科学元数据附属文件。",
  "What are you building, and what would count as a mistake?":"你要构建什么？哪些情况应判定为错误？",
  "A user-facing review that must be accurate, balanced, and delivered as one clear document.":"一份面向用户、准确平衡且以单一清晰文档交付的评审。",
  "Automatic revision limit":"自动修订轮数上限","1 - quick stop":"1 - 快速停止","3 - recommended":"3 - 推荐",
  "5 - persistent":"5 - 持续修订","10 - maximum":"10 - 最大值",
  "Up to 3 generator → auditor rounds, then the task pauses for you. It never auto-passes.":"最多进行 3 轮生成者 → 审计者循环，随后暂停并等待你决定；绝不会自动通过。",
  "Local workspace folder":"本地工作区文件夹","Local project folder":"本地项目文件夹","Choose folder…":"选择文件夹…","Selected local workspace":"已选择的本地工作区","Selected local project folder":"已选择的本地项目文件夹",
  "Choose where this project's local folder will be created.":"选择创建该项目本地文件夹的位置。","Choose the exact folder CrossAudit should use. The project name will not create another subfolder.":"请选择 CrossAudit 直接使用的文件夹；项目名称不会再创建子文件夹。",
  "Independent roles":"独立角色","Generator":"生成者","Independent auditor":"独立审计者","Provider":"供应商","Connection":"连接方式",
  "Connection details":"连接详情","API region":"API 区域","The region must match the API key.":"区域必须与 API key 匹配。","Model":"模型",
  "Model available to your account":"你的账户可用的模型","Custom model ID":"自定义模型 ID","Exact provider model ID":"准确的供应商模型 ID",
  "Refresh from provider":"从供应商刷新","GitHub":"GitHub","Create and connect two repositories":"创建并连接两个仓库",
  "The work repository holds deliverables. The audit repository holds rules, reports and the auditor secret.":"工作仓库存放交付物；审计仓库存放规则、报告和审计密钥。",
  "Checking GitHub connection…":"正在检查 GitHub 连接…","Work repository name":"工作仓库名称","Audit repository name":"审计仓库名称",
  "Use accessible repositories if these names already exist":"若这些名称已存在，则使用可访问的仓库",
  "Off by default. Leave it off when you want two new repositories.":"默认关闭。需要创建两个新仓库时请保持关闭。",
  "Public repositories":"公开仓库","Off by default. Private is safer for a new project.":"默认关闭。新项目使用私有仓库更安全。",
  "Check names":"检查名称","Names will be checked again before anything is created.":"创建任何内容前都会再次检查名称。",
  "Creating may send the description to the auditor model and create repositories in your connected GitHub account.":"创建操作可能会把描述发送给审计模型，并在已连接的 GitHub 账户中创建仓库。",
  "Cancel":"取消","Create project":"创建项目","Finish GitHub setup":"完成 GitHub 设置",
  "Correct the repository settings and continue from the last durable step.":"修正仓库设置，并从最近的持久化步骤继续。",
  "Work repository":"工作仓库","Audit repository":"审计仓库","Connect GitHub":"连接 GitHub","Open GitHub help ↗":"打开 GitHub 帮助 ↗",
  "Retry setup":"重试设置","Retry is idempotent: repositories created before the interruption are reused, not duplicated.":"重试是幂等的：中断前已创建的仓库会被复用，不会重复创建。",
  "Project controls":"项目控制","Choose how this project works. Changes apply to the next provider call.":"选择此项目的工作方式；更改会从下一次供应商调用开始生效。",
  "Project control categories":"项目控制分类","Models":"模型","Team & reasoning":"团队与推理","Automation":"自动化","Audit & recovery":"审计与恢复",
  "Budgets":"预算","Limits & warnings":"上限与预警","Instructions":"指令","Project guidance":"项目指导",
  "Models, reasoning & audit loop":"模型、推理与审计循环","Choose one model to do the work and a different provider to review it independently.":"选择一个模型执行工作，并由另一家供应商的模型独立审查。",
  "Audit automation":"审计自动化","CrossAudit revises automatically, then pauses for you instead of silently accepting an unresolved result.":"CrossAudit 会自动修订；若问题仍未解决则暂停等待你决定，绝不会静默接受。",
  "Advanced provider recovery":"高级供应商恢复","Optional local warnings and stops. Your provider remains the authority for billing.":"可选的本地预警与停止线；最终计费仍以供应商为准。",
  "Reusable project instructions shape the work without weakening the independent audit rules.":"可复用的项目指令会规范工作方式，但不会削弱独立审计规则。",
  "Reasoning effort":"推理强度","Refresh models":"刷新模型","Audit loop":"审计循环",
  "Automatic provider recovery":"供应商自动恢复","Generator fallback chain":"生成者备用路由链","Auditor fallback chain":"审计者备用路由链","in order":"按顺序",
  "＋ Add fallback":"＋ 添加备用路由","Attempts per route":"每条路由尝试次数","Initial retry delay (seconds)":"首次重试延迟（秒）",
  "Maximum retry delay (seconds)":"最大重试延迟（秒）","Honor Retry-After up to (seconds)":"遵循 Retry-After 的最大秒数",
  "Open circuit after failures":"连续失败后打开熔断器","Circuit cooldown (seconds)":"熔断冷却时间（秒）",
  "Retries stay inside one provider call and never consume Generator → Auditor revision rounds. A fallback is used only after its earlier route fails.":"重试发生在单次供应商调用内部，不消耗生成者 → 审计者修订轮次；只有前序路由失败后才会使用备用路由。",
  "Usage guardrails":"用量保护线","Daily token warning":"每日 Token 预警","Daily token hard limit":"每日 Token 硬上限",
  "Monthly API-value warning (USD)":"每月 API 价值预警（美元）","Monthly API-value hard limit (USD)":"每月 API 价值硬上限（美元）",
  "No warning":"不预警","No limit":"不限制","Limits are local safeguards; provider billing remains authoritative.":"这些上限是本地保护措施，最终计费以供应商为准。",
  "No fallback. A provider failure pauses safely for you.":"未配置备用路由。供应商失败时会安全暂停并等待你处理。",
  "Project controls updated.":"项目控制已更新。","Recovery routes, usage guardrails, models and loop limits apply to the next provider call.":"恢复路由、用量保护线、模型和循环上限将在下一次供应商调用时生效。",
  "The selected effort is sent on the next provider request.":"所选推理强度会用于下一次供应商请求。",
  "After this many generator → auditor rounds, the task pauses for your explicit decision. It never auto-passes.":"达到该生成者 → 审计者轮数后，任务会暂停并等待你的明确决定，绝不会自动通过。",
  "Generator guidance":"生成者指导","Edit guidance":"编辑指导","Create new guidance…":"创建新指导…","Name":"名称",
  "Applies to paths (optional)":"适用路径（可选）","Comma-separated project-relative prefixes. Leave blank to apply on every task.":"以逗号分隔的项目相对路径前缀。留空则适用于所有任务。",
  "Instructions for the generator":"给生成者的说明","Describe the tone, output shape, conventions or checklist this project should follow.":"描述此项目应遵循的语气、输出形式、约定或检查清单。",
  "Guidance changes how the generator works. It never changes the Constitution or what the independent auditor enforces.":"指导只改变生成者的工作方式，不会修改 Constitution 或独立审计者执行的标准。",
  "Save guidance":"保存指导","Safe handoff.":"安全交接。",
  "A running audit keeps the models and controls it started with. These changes apply to the next call.":"运行中的审计会保持启动时的模型与控制设置；这些更改从下一次调用生效。",
  "Models and loop limits update crossaudit.yml; generator guidance is versioned in the project. A running audit keeps the controls it started with.":"模型和循环上限会更新 crossaudit.yml；生成者指导在项目中进行版本控制。运行中的审计保持启动时的控制设置。",
  "Automatic means the provider chooses its documented default.":"自动表示由供应商采用其文档规定的默认值。","Save for next call":"保存供下次调用使用",
  "Automatic loop paused":"自动循环已暂停","The audit needs your decision":"审计需要你作出决定",
  "CrossAudit stopped safely. Nothing will continue or be admitted until you decide.":"CrossAudit 已安全暂停。在你作出决定前，不会继续执行，也不会准入任何结果。",
  "Automatic audit limit reached":"已达自动审计轮数上限","The configured rounds were used without a passing result.":"已用完设定的轮数，但仍未获得通过结果。",
  "What is still blocking the result":"当前仍在阻止结果通过的问题","What CrossAudit needs from you":"CrossAudit 需要你处理什么",
  "Choose whether to provide concrete correction guidance for one more round or stop this task.":"请选择：提供具体修正指导并再进行一轮，或停止此任务。",
  "Revise and continue":"修订并继续","Give the generator specific correction guidance and unlock one additional audited round.":"向生成者提供具体修正指导，并解锁额外一轮受审计执行。",
  "Stop this task":"停止此任务","Keep the current output unadmitted and close the audit cycle with your reason.":"保持当前输出不准入，并附上原因关闭审计循环。",
  "Your guidance or reason":"你的指导或原因","Select an action, then explain what CrossAudit should do.":"先选择一项操作，再说明 CrossAudit 应该如何处理。",
  "Human decision required.":"需要人工决定。","Your action and explanation become part of the durable audit ledger.":"你的操作和说明会成为持久审计账本的一部分。",
  "The models cannot approve their own result or bypass this pause.":"模型无法自行批准结果，也无法绕过此暂停。","Review later":"稍后处理","Record human decision":"记录人工决定",
  "Correction guidance for the next round":"下一轮的修正指导","Describe exactly what should change before the next audit.":"具体说明下一次审计前应修改什么。",
  "Record guidance & unlock round":"记录指导并解锁一轮","Reason for stopping":"停止原因","Explain why this task should stop without admitting its current output.":"说明为什么应停止任务且不准入当前输出。",
  "Stop without admission":"停止且不准入","The automatic loop could not continue safely":"自动循环无法安全继续",
  "No structured findings were recorded. Review the stop reason above before continuing.":"未记录结构化问题。继续前请检查上方的停止原因。",
  "Choose whether to revise and continue, or stop this task.":"请选择修订并继续，或停止此任务。","Review issues & decide":"查看问题并决定",
  "Generator connection stopped":"生成者连接已停止","The task is waiting for a working Generator connection":"任务正在等待可用的生成者连接",
  "CrossAudit stopped before an audit began. No result was admitted and the original task is ready to retry.":"CrossAudit 在审计开始前已安全暂停。没有结果被准入，原任务可直接重试。",
  "No audit findings were created because the Generator stopped before producing a reviewable result.":"生成者在产出可审查结果前停止，因此没有生成审计问题。",
  "Retry the same task now, review the model connection first, or stop this task.":"立即重试同一任务、先检查模型连接，或停止此任务。",
  "Retry provider":"重试供应商","Use the current connection and rerun the original task.":"使用当前连接重新运行原任务。",
  "Review provider connection":"检查供应商连接","Change model or fallback":"更改模型或备用路由","Retry provider now":"立即重试供应商","Provider retry started.":"供应商重试已开始。",
  "Waiting for provider":"等待 provider","waiting for provider":"等待 provider","stalled":"已停滞",
  "no heartbeat was ever recorded for this run":"此任务从未记录过心跳",
  "The original task is running again; live progress will appear here.":"原任务已重新运行；实时进度会显示在这里。",
  "Retry note (optional)":"重试备注（可选）","Optional note for the audit ledger.":"可选：为审计账本添加备注。",
  "Open folder":"打开文件夹","Dismiss":"移除此提示","Project creation stopped":"项目创建已暂停",
  "Review local changes before setup":"设置前请检查本地改动","Checking the project again":"正在重新检查项目",
  "CrossAudit settings":"CrossAudit 设置","Check this Mac, repair setup issues, and connect model providers without using Terminal.":"检查此 Mac、修复设置问题并连接模型供应商，全程无需终端。",
  "Manage this Mac and model connections without using Terminal.":"管理此 Mac 与模型连接，全程无需终端。","Settings sections":"设置分类",
  "General":"通用","Workspace and this Mac":"工作区与此 Mac","Model providers":"模型供应商","Subscriptions and API keys":"订阅与 API key",
  "Workspace and application readiness":"工作区与应用就绪状态","CrossAudit checks required software and offers a direct recovery action when something needs attention.":"CrossAudit 会检查必需软件，并在发现问题时直接提供修复操作。",
  "Show details":"显示详情","Hide details":"隐藏详情","Connect the services you use":"连接你使用的服务",
  "Open only the provider you want to configure. Existing secrets are never displayed again.":"只展开需要配置的供应商；已保存的密钥永远不会再次显示。","Done":"完成",
  "Workspace changes apply immediately. Run Doctor after moving or updating this Mac.":"工作区修改会立即生效；迁移或更新此 Mac 后请再次运行环境诊断。",
  "Application readiness":"应用就绪状态","Git":"Git","GitHub connection tool":"GitHub 连接工具","Application build":"应用构建","Code identity":"代码身份",
  "Environment Doctor":"环境诊断","Preparing checks…":"正在准备检查…","Run check":"运行检查","Checking required software…":"正在检查所需软件…",
  "Project workspace":"项目工作区","Provider credentials":"供应商凭据",
  "Backup API key (optional)":"备用 API Key（可选）","Used only by an explicit fallback route":"仅由明确配置的备用路由使用",
  "Delete backup key":"删除备用 Key","Primary key":"主 Key","Backup key":"备用 Key",
  "Developer access and consumer subscriptions are different products.":"开发者 API 与消费者订阅是不同的产品。",
  "CrossAudit only offers web sign-in where the provider publishes a supported third-party inference flow. It never imports browser cookies or CLI session files.":"只有供应商公开支持第三方推理登录流程时，CrossAudit 才提供网页登录。它不会导入浏览器 Cookie 或 CLI 会话文件。",
  "API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.":"API key 以只写方式存入 macOS 钥匙串；订阅凭据始终由官方供应商运行时持有。",
  "Save settings":"保存设置","Add SSH compute host":"添加 SSH 计算主机",
  "Connect a workstation or Slurm cluster through your existing SSH setup.":"通过现有 SSH 配置连接工作站或 Slurm 集群。",
  "CrossAudit does not install anything on the cluster.":"CrossAudit 不会在集群上安装任何内容。",
  "It uses OpenSSH config, keys, ssh-agent and ProxyJump already configured on this Mac, then runs a read-only capability check.":"它使用此 Mac 已配置的 OpenSSH、密钥、ssh-agent 和 ProxyJump，然后执行只读能力检查。",
  "Connection":"连接","Name the SSH target and choose a shared work directory for durable remote jobs.":"指定 SSH 目标，并为可持续运行的远程任务选择共享工作目录。",
  "Alias from ~/.ssh/config or a reachable hostname.":"~/.ssh/config 中的别名或可访问的主机名。","For Slurm, login and compute nodes must both see this path.":"使用 Slurm 时，登录节点和计算节点必须都能访问此路径。",
  "Parallel jobs":"并行任务数","Project limit":"项目上限","Cluster notes":"集群说明","optional":"可选","Approved partitions, module loads, environment activation, or account policy.":"获准分区、模块加载、环境激活或账户政策。",
  "Generator access":"生成者权限","Manual job submission is always available. Automatic access is optional and constrained by hard ceilings.":"始终可以手动提交任务；自动权限为可选项，并受硬性上限约束。",
  "The Generator can submit calculation scripts without per-job confirmation. Use a dedicated least-privilege SSH account.":"生成者可无需逐个确认即提交计算脚本。请使用专用的最小权限 SSH 账户。",
  "hard maximums per task":"每个任务的硬性上限","Scheduler restrictions (optional)":"调度器限制（可选）",
  "Host identity":"主机身份","Known host keys are required. A changed key always stops the connection.":"必须使用已知主机密钥；密钥一旦变化，连接必定停止。",
  "Only select this after verifying the hostname with your cluster administrator. Existing or changed keys are never replaced.":"仅在与集群管理员核实主机名后选择。已有或发生变化的密钥绝不会被替换。",
  "Next: read-only connection and capability check.":"下一步：执行只读连接和能力检查。",
  "CrossAudit uses your existing OpenSSH config, keys, ssh-agent and ProxyJump. Nothing is installed remotely.":"CrossAudit 使用你现有的 OpenSSH 配置、密钥、ssh-agent 和 ProxyJump，不会在远端安装任何内容。",
  "SSH alias":"SSH 别名","A Host alias from ~/.ssh/config, or a directly reachable hostname.":"~/.ssh/config 中的 Host 别名，或可直接访问的主机名。",
  "Shared scratch directory":"共享临时目录","For Slurm this must be visible from login and compute nodes.":"使用 Slurm 时，该目录必须同时对登录节点和计算节点可见。",
  "Concurrent job limit":"并发任务上限","Host instructions":"主机说明",
  "Account code, approved partitions, module loads, environment activation, and local cluster policy.":"账户代码、获准分区、模块加载、环境激活和本地集群政策。",
  "Allow Generator to use this host automatically":"允许生成者自动使用此主机","The Generator may author and submit scripts without per-job confirmation, but only inside the resource and file policy below. Use a dedicated least-privilege SSH account.":"生成者可无需逐个确认即编写并提交脚本，但必须遵守下方资源和文件政策。请使用专用的最小权限 SSH 账户。",
  "Generator compute policy":"生成者计算政策","These are hard ceilings. SSH identity, scheduler policy and filesystem permissions remain the final boundary.":"以下是不可突破的上限；SSH 身份、调度器政策和文件系统权限仍是最终边界。",
  "Jobs per task":"每个任务的作业数","Maximum nodes":"最大节点数","Maximum CPUs":"最大 CPU 数","Maximum GPUs":"最大 GPU 数","Maximum memory":"最大内存","Maximum wall time":"最长运行时间",
  "Fixed partition":"固定分区","Fixed account":"固定账户","Fixed QoS":"固定 QoS",
  "Trust a new host key once":"仅一次信任新主机密钥","Use only after verifying the hostname with your cluster administrator. Existing or changed keys are never replaced.":"仅在与集群管理员核实主机名后使用。已有或发生变化的密钥绝不会被替换。",
  "Registration runs a read-only probe for CPU, memory, GPU, Slurm, modules, conda and Apptainer.":"注册过程会对 CPU、内存、GPU、Slurm、模块、conda 和 Apptainer 进行只读探测。","Probe & add":"探测并添加",
  "Submit remote job":"提交远程任务","Review the exact script and requested resources. The job runs as your SSH user outside the local sandbox.":"检查准确脚本和资源请求。任务会以你的 SSH 用户身份在本地沙箱之外运行。",
  "Compute host":"计算主机","Job name":"任务名称","Partition":"分区","QoS":"服务质量","Account":"账户","Nodes":"节点","CPUs per task":"每任务 CPU 数","Memory":"内存","GPUs":"GPU 数","Wall time":"运行时限",
  "Input files":"输入文件","Optional. Files are streamed to inputs/ on the remote host with no CrossAudit size or count quota.":"可选。文件会流式传输到远端主机的 inputs/，CrossAudit 不限制数量或大小。",
  "Job script":"任务脚本","I approve this remote execution":"我批准此次远程执行",
  "The script can access anything my account can read or write on this host. Closing CrossAudit will not stop it.":"脚本可访问我的账户在该主机上有权读写的所有内容。关闭 CrossAudit 不会停止它。","Submit job":"提交任务",
  "Tasks":"任务","New chat":"新对话","＋ New chat":"＋ 新对话","Workspace views":"工作区视图","Chat":"对话","Files":"文件","More":"更多",
  "Audit history":"审计记录","Usage":"用量","Remote compute":"远程计算","Tools & Skills":"工具与技能",
  "Back to projects":"返回项目列表","Pin project":"置顶项目","Settings":"设置","Switch theme":"切换主题","Toggle audit context":"切换审计上下文","Open navigation":"打开导航","Close open panel":"关闭面板",
  "You":"你","Auditor":"审计者","New task":"新任务","Project controls":"项目控制",
  "Message recipient":"消息接收方","To":"发送给","Auto":"自动","@ Generator":"@ 生成者","@ Auditor":"@ 审计者","Add files":"添加文件","＋ Add files":"＋ 添加文件",
  "Message the group, or @ someone…":"给群组发送消息，或 @ 某一方…","Run task":"运行任务","Generator → Auditor":"生成者 → 审计者","Auto-planning":"自动规划","Generator infers focus, format, tone, and structure unless you specify them.":"除非你明确指定，否则生成者会自动判断重点、格式、语气和结构。","Enter to send · Shift+Enter for new line":"Enter 发送 · Shift+Enter 换行",
  "What should CrossAudit work on?":"希望 CrossAudit 完成什么？","Describe what you need or add files. CrossAudit will do the work and independently check the result before showing it here.":"描述你的需求或添加文件。CrossAudit 会完成工作，并在结果显示到这里之前进行独立检查。",
  "Audit context":"审计上下文","Close audit context":"关闭审计上下文","Models":"模型","Loop parameters":"循环参数","Maximum rounds":"最大轮数","Current round":"当前轮次","Constitution":"审计章程","Admission tier":"准入级别","Deterministic checks":"确定性检查","Ledger":"账本","Needs attention":"需要处理",
  "Drop files to add them":"拖放文件以添加","No CrossAudit file-count or file-size quota. Available storage, filesystem limits and provider context still apply.":"CrossAudit 不限制文件数量或大小，但仍受可用存储、文件系统和供应商上下文限制。",
  "Rendered locally and audited from the final binary":"在本地渲染，并从最终二进制文件回读审计","File preview":"文件预览","Preparing preview…":"正在准备预览…","Loading audited deliverable…":"正在加载已审计的交付文件…","Download":"下载","Close preview":"关闭预览","The complete file remains available to download.":"完整文件始终可供下载。","Preview unavailable for this file type. Download the complete file to open it in a compatible app.":"此文件类型无法安全预览。请下载完整文件并使用兼容应用打开。","The reading preview is shortened for responsiveness; the download is complete.":"为保证界面流畅，阅读预览已截短；下载文件是完整的。","Preview is reconstructed from the final audited DOCX binary.":"预览内容从最终通过审计的 DOCX 二进制文件中重建。","HTML preview is isolated from the app and cannot access the network.":"HTML 预览与应用隔离，且无法访问网络。","ready":"就绪","connecting":"正在连接","Connected":"已连接","Not connected":"未连接","Checking…":"正在检查…","Loading projects…":"正在加载项目…","Something went wrong":"发生了错误","Open help ↗":"打开帮助 ↗",
  "Close":"关闭","Close settings":"关闭设置","No matching projects.":"没有匹配的项目。","Switch to dark theme":"切换到深色主题","Switch to light theme":"切换到浅色主题",
  "Delete project":"删除项目","Review the local and GitHub impact before anything is changed.":"更改任何内容前，请检查本地与 GitHub 影响。",
  "Checking project state…":"正在检查项目状态…","The local folder will move to CrossAudit Trash and can be recovered. GitHub repositories remain untouched unless you explicitly select permanent deletion below.":"本地文件夹会移到 CrossAudit 废纸篓并可恢复。除非你在下方明确选择永久删除，否则 GitHub 仓库保持不变。",
  "Type the project name to confirm":"输入项目名称以确认","Permanently delete working repository":"永久删除工作仓库","Permanently delete audit repository":"永久删除审计仓库",
  "No working repository detected.":"未检测到工作仓库。","No audit repository detected.":"未检测到审计仓库。","Type DELETE GITHUB":"输入 DELETE GITHUB","Running tasks and remote compute block deletion.":"运行中的任务和远程计算会阻止删除。",
  "Authorize GitHub deletion":"授权 GitHub 删除仓库","GitHub requires the delete_repo permission before it can delete a repository.":"GitHub 需要 delete_repo 权限才能删除仓库。","GitHub deletion authorized. Submit again.":"GitHub 删除权限已授权，请再次提交。","GitHub deletion authorized. Submit again to delete the selected repositories.":"GitHub 删除权限已授权，请再次提交以删除所选仓库。",
  "Move project to Trash":"将项目移到废纸篓","Delete chat?":"删除对话？","This chat will disappear from the project sidebar.":"此对话将从项目侧栏消失。",
  "Audit reports, receipts, commits and delivered files are preserved in the project ledger. Deleting a chat never rewrites evidence that may already have admitted a result.":"审计报告、收据、提交和交付文件会保留在项目账本中。删除对话绝不会重写可能已经准入结果的证据。",
  "This only removes the individual chat from navigation.":"此操作只会从导航中移除该独立对话。","Delete chat":"删除对话","Delete chat from project":"从项目中删除对话","Delete project from CrossAudit":"从 CrossAudit 删除项目",
  "Return to the main Projects window to delete this open project":"请返回主项目窗口后删除当前打开的项目","Move to Trash & delete selected GitHub repositories":"移到废纸篓并删除所选 GitHub 仓库","Deleting…":"正在删除…","Project moved to Trash":"项目已移到废纸篓",
  "ChatGPT subscription":"ChatGPT 订阅","Default":"默认","Enter a custom model ID…":"输入自定义模型 ID…",
  "highest capability":"最高能力","balanced · recommended":"均衡 · 推荐","fastest, lowest cost":"最快、成本最低",
  "API access.":"API 访问。","Use an official developer API key.":"请使用官方开发者 API key。",
  "This provider has no supported third-party subscription sign-in for model inference. Use an official developer API key.":"该供应商没有支持第三方模型推理的订阅登录流程，请使用官方开发者 API key。",
  "Anthropic does not permit Claude consumer subscriptions to be bound to third-party apps. Use an Anthropic API key or a separately implemented enterprise cloud route.":"Anthropic 不允许第三方应用绑定 Claude 消费者订阅。请使用 Anthropic API key 或单独实现的企业云连接。",
  "A Gemini consumer subscription is not an API credential. Google AI Studio API/auth keys are supported; Vertex AI IAM is a separate cloud connection.":"Gemini 消费者订阅不是 API 凭据。支持 Google AI Studio API/auth key；Vertex AI IAM 属于独立云连接。",
  "Qwen Code offers its own official Coding Plan login, but CrossAudit does not reuse CLI session files as general inference credentials. Use a Model Studio API key here.":"Qwen Code 提供官方 Coding Plan 登录，但 CrossAudit 不会把 CLI 会话文件复用为通用推理凭据。请在此使用 Model Studio API key。",
  "xAI's inference API supports API credentials (and documented OAuth tokens for approved integrations), but an X consumer subscription is not automatically an inference entitlement. API key is enabled here.":"xAI 推理 API 支持 API 凭据及获准集成的 OAuth token，但 X 消费者订阅不会自动获得推理权限。请在此使用 API key。",
  "New API key ·":"新 API key ·","Get key ↗":"获取 key ↗","API docs ↗":"API 文档 ↗","Leave blank to keep the saved key":"留空以保留已保存的 key",
  "Remove":"移除","Delete saved key":"删除已保存的 key","Official Codex sign-in.":"官方 Codex 登录。","Connect":"连接","Try again":"重试","Waiting…":"等待中…","Starting…":"正在启动…",
  "Environment has not been checked":"尚未检查环境","Checking this Mac…":"正在检查此 Mac…","Ready":"就绪","Missing":"缺失","Outdated":"版本过旧","Checking":"检查中",
  "Embedded Python":"内置 Python","Remote compute client":"远程计算客户端","ChatGPT connection runtime":"ChatGPT 连接运行时",
  "Secure network certificates":"安全网络证书","Project Git ledger":"项目 Git 账本","Git author identity":"Git 作者身份",
  "Add a name and email before creating commits.":"创建提交前请添加姓名和邮箱。","Git author name":"Git 作者姓名","Git author email":"Git 作者邮箱",
  "Save for this project":"保存到此项目","Project configuration":"项目配置","Audit rules":"审计规则","CrossAudit application":"CrossAudit 应用",
  "Everything required is ready":"所有必需项均已就绪","source":"源码构建","Unknown":"未知","Warning":"警告","Waiting":"等待中",
  "Install Git tools":"安装 Git 工具","Update Git tools":"更新 Git 工具","Open SSH setup guide":"打开 SSH 设置指南",
  "Reinstall CrossAudit":"重新安装 CrossAudit","Download latest":"下载最新版","Download update":"下载更新","Open Software Update":"打开软件更新",
  "Choose another folder":"选择其他文件夹","Initialize safely":"安全初始化","Run again":"重新运行",
  "Automatic · provider default":"自动 · 供应商默认","Not applicable":"不适用","Human-written changes":"人工编写的修改","Create reusable project guidance":"创建可复用的项目指导",
  "Editing committed guidance":"正在编辑已提交的指导","Saved and committed":"已保存并提交","Already up to date":"已是最新状态",
  "Allow another round":"再给一轮","Stop task":"停止任务","Review decision":"审查决定","Admit result":"准入结果","Nothing needs attention.":"没有需要处理的事项。"
  ,"Another audited attempt is unlocked.":"已解锁另一次受审计尝试。","Your guidance is in the composer. Review it, then press Run task.":"你的指导已放入输入框。检查后按“运行任务”。",
  "Task stopped.":"任务已停止。","The current output remains unadmitted and your reason was recorded.":"当前输出仍未准入，你的原因已记录。",
  "Add concrete guidance or a reason so the decision is auditable.":"请添加具体指导或原因，以便对该决定进行审计。",
  "The automatic audit loop stopped.":"自动审计循环已停止。","Review why the loop stopped, then decide whether to revise or stop.":"检查循环停止原因，再决定修订或停止。",
  "The audit controller paused this task.":"审计控制器已暂停此任务。","No explanation was recorded.":"未记录说明。","A human decision is required.":"需要人工决定。",
  "Tell the generator how to correct the remaining blockers, or stop the task without admitting its output.":"请告诉生成者如何修复剩余阻断问题，或停止任务且不准入其输出。",
  "Fix the provider, model, or credential setting before allowing another round, or stop the task.":"再给一轮前，请先修复供应商、模型或凭据设置；否则停止任务。",
  "Review why the loop stopped, then either give concrete guidance for one more round or stop the task.":"检查循环停止原因，然后提供具体指导再进行一轮，或停止任务。",
  "no model audit ran, so the result cannot pass":"没有运行模型审计，因此结果无法通过","the automatic audit loop stopped":"自动审计循环已停止"
  ,"/ project folder":"/ 项目文件夹","local controller":"本地控制器","No chats yet":"尚无对话",
  "What should CrossAudit work on?":"CrossAudit 应该处理什么？",
  "Describe a task in plain language. A generator will make the change, deterministic checks will run, and an independent model will audit every round before admission.":"用自然语言描述任务。生成者完成修改，系统运行确定性检查，并由独立模型在准入前审计每一轮。",
  "Working":"处理中","The result will appear here when it is ready.":"结果就绪后会显示在这里。",
  "The delivered files passed the independent review.":"交付文件已通过独立审查。","Needs revision":"需要修订",
  "The result did not pass review yet.":"结果尚未通过审查。","Needs your input":"需要你决定",
  "Ready for your correction":"已准备接收你的修正","Send the approved guidance to start the human-authorized audited attempt.":"发送已确认的指导，以启动由你授权的受审计尝试。",
  "CrossAudit needs a decision before it can continue.":"CrossAudit 需要你作出决定才能继续。","Stopped":"已停止",
  "The task did not complete.":"任务未完成。","View audit details":"查看审计详情",
  "Delivered files":"交付文件","Only final files that passed independent review.":"仅显示已通过独立审查的最终文件。",
  "No audited deliverables yet.":"尚无经审计的交付物。","Independent verdicts and findings reconstructed from the ledger.":"从账本重建的独立判定与发现。",
  "Audit evidence":"审计证据","No audit evidence yet.":"尚无审计证据。","Token usage":"Token 用量",
  "Project-level model consumption, updated with every completion.":"项目级模型用量，每次完成调用时更新。",
  "Today":"今日","This month":"本月","Model calls":"模型调用","Cached tokens":"缓存 Token","Last 7 days":"最近 7 天",
  "all roles":"全部角色","By role":"按角色","this month":"本月","Model":"模型","Tokens":"Token","Cached":"已缓存","Source":"来源",
  "Recent calls":"最近调用","counts only · no prompt content":"仅统计数量 · 不包含提示词内容","No model calls this month.":"本月尚无模型调用。",
  "Usage will appear after the first model completion.":"第一次模型调用完成后会显示用量。","No calls recorded yet.":"尚无调用记录。",
  "Reported":"已报告","Estimated":"估算","Unpriced":"未计价","Remote compute":"远程计算",
  "SSH workstations and Slurm clusters, detached from this Mac.":"与此 Mac 解耦运行的 SSH 工作站和 Slurm 集群。","SSH workstations and Slurm clusters for manual jobs or Generator calculations.":"用于手动作业或生成者计算的 SSH 工作站和 Slurm 集群。",
  "Remote-owned execution.":"远程主机负责执行。","＋ Add SSH host":"＋ 添加 SSH 主机","Refresh now":"立即刷新",
  "CrossAudit stores only host aliases and job identifiers. Keys remain with OpenSSH; remote work continues if the app closes, the Mac sleeps, or the network drops. A host marked as a Generator tool can receive model-authored jobs automatically within its saved policy.":"CrossAudit 只保存主机别名和任务标识；密钥始终由 OpenSSH 管理。即使应用关闭、Mac 休眠或网络中断，远程任务也会继续运行。标记为生成者工具的主机可在已保存政策范围内自动接收模型编写的任务。",
  "Remote compute":"远程计算","Generator tool":"生成者工具","Generator calculations":"生成者计算",
  "Compute hosts":"计算主机","Remote jobs":"远程任务","No SSH compute hosts yet.":"尚未添加 SSH 计算主机。",
  "No jobs submitted from this project.":"此项目尚未提交任务。","Probe":"探测","Run job":"运行任务","Live logs":"实时日志","Outputs":"输出",
  "Cancel job":"取消任务","Remote outputs":"远程输出","Updating…":"正在更新…","No remote output files found.":"未找到远程输出文件。",
  "Add MCP server":"添加 MCP 服务器","Configure MCP server":"配置 MCP 服务器","Connect project tools through the official Model Context Protocol lifecycle.":"通过官方 Model Context Protocol 生命周期连接项目工具。",
  "Server name":"服务器名称","Transport":"传输方式","Local stdio":"本地 stdio","Streamable HTTP":"Streamable HTTP","Executable":"可执行文件","Arguments":"参数",
  "One argument per line. CrossAudit never invokes a shell.":"每行一个参数。CrossAudit 绝不会调用 shell。","I approve this exact local command":"我批准此准确的本地命令","A local MCP server runs with this app's user permissions and may access files or the network. Verify its publisher and arguments.":"本地 MCP 服务器使用本应用的用户权限运行，可能访问文件或网络。请核实发布者和参数。",
  "MCP endpoint":"MCP 端点","Secure MCP endpoint URL":"安全的 MCP 端点 URL","Bearer token (optional)":"Bearer token（可选）","Leave blank to keep saved token":"留空以保留已保存的 token","Allow a verified private-network server":"允许已核实的专用网络服务器","Use only for an enterprise hostname you control. Public remote servers must use HTTPS.":"仅用于你所控制的企业主机名。公共远程服务器必须使用 HTTPS。",
  "Request timeout":"请求超时","Calls per task":"每个任务的调用次数","Approved tool names":"已批准的工具名称","Comma-separated exact names. Save once without enabling to inspect advertised tools first.":"使用逗号分隔准确名称。可先不启用并保存一次，以查看服务器公布的工具。",
  "Approve all tools advertised during this connection":"批准本次连接中公布的所有工具","Only the current list is approved. Tools added by the server later remain blocked until you review them.":"只批准当前列表。服务器以后新增的工具在你审核前仍保持阻止状态。",
  "Allow Generator to call the approved tools automatically":"允许生成者自动调用已批准的工具","Calls appear live in the task loop. Tool output is treated as untrusted external data and never becomes an audit rule.":"调用会实时显示在任务循环中。工具输出被视为不可信外部数据，绝不会成为审计规则。",
  "Advertised tools":"公布的工具","Connect the server to discover tools.":"连接服务器以发现工具。","Bearer tokens are write-only Keychain items. Local commands are stored without secrets.":"Bearer token 以只写方式存入钥匙串；本地命令不含秘密信息。","Connect & save":"连接并保存",
  "Project-scoped MCP capabilities and committed Generator guidance.":"项目级 MCP 能力与已提交的生成者指导。","Explicit capability boundaries.":"明确的能力边界。","MCP servers and Skills are invisible until you configure them. Approved MCP output remains untrusted data; Skills guide only the Generator and never change the Constitution.":"MCP 服务器和技能在你配置前不可见。已批准的 MCP 输出仍是不可信数据；技能只指导生成者，绝不会修改审计章程。",
  "＋ Add MCP server":"＋ 添加 MCP 服务器","Manage Skills":"管理技能","MCP servers":"MCP 服务器","Recent tool calls":"最近工具调用","Skills":"技能","No MCP servers connected to this project.":"此项目尚未连接 MCP 服务器。","No MCP tools called in this project.":"此项目尚未调用 MCP 工具。","No project Skills yet.":"此项目尚无技能。",
  "Generator enabled":"已为生成者启用","Manual only":"仅手动","Configure":"配置","Refresh tools":"刷新工具","No tools advertised.":"未公布工具。","Applies to every task":"适用于每个任务","MCP tool":"MCP 工具","calling MCP tool":"正在调用 MCP 工具","policy":"政策",
  "Last 64 KB · stdout + stderr":"最近 64 KB · 标准输出 + 标准错误","Remote process finished":"远程进程已完成","Submitted to Slurm":"已提交至 Slurm","Detached on host":"已在远程主机后台启动","Preparing remote job":"正在准备远程任务",
  "Passed":"已通过","Blocked":"已阻止","Waiting on you":"等待你决定","Admitted":"已准入","Complete":"已完成","Active":"正在进行","Pending":"等待中"
  ,"live":"实时","complete":"完成","completed":"已完成","failed":"失败","cancelled":"已取消","timeout":"超时","out_of_memory":"内存不足","queued":"排队中","running":"运行中","submitting":"提交中","unknown":"未知","declared":"已声明","internal":"内部","parseable":"可解析",
  "Use light theme":"使用亮色主题","Use dark theme":"使用暗色主题",
  "Switch models, reasoning effort and audit loop settings":"切换模型、推理强度和审计循环设置",
  "Understanding":"正在理解","Checking":"正在检查","Revising":"正在修订","Completed":"已完成",
  "Needs your decision":"需要你决定","Stopping":"正在停止",
  "Audit":"审计","Compute":"计算","Context tabs":"上下文标签","Context panel":"上下文面板",
  "Close context panel":"关闭上下文面板","Change models":"更换模型","Search chats":"搜索对话",
  "Command palette":"命令面板","Type a command or search…":"输入命令或搜索…","Actions":"操作",
  "Chats":"对话","No matching results.":"没有匹配的结果。","All projects":"全部项目",
  "Open settings":"打开设置","Run Doctor":"运行环境诊断","Switch language":"切换语言",
  "Stop current task":"停止当前任务","Review":"查看","Goal":"目标","Attempted":"已尝试",
  "Blocked on":"阻塞在","Recommendation":"建议","Suggested":"建议选项",
  "The task this conversation asked for.":"此对话所要求完成的任务。",
  "Independent review":"独立审查","Independent auditor approved the result":"独立审计者已批准该结果",
  "No blocking findings":"没有阻断性问题","Recorded in the audit ledger":"已记录到审计账本",
  "Findings":"发现的问题","Record":"记录","Commit":"提交","Cycle":"审计循环",
  "Open Files panel":"打开文件面板","now":"刚刚","Human decision":"人工决定"
};
const ZH_PATTERNS=[
  [/^(\d+) cycles?$/,m=>m[1]+' 个审计循环'],[/^(\d+) chats?$/,m=>m[1]+' 个对话'],
  [/^(\d+) required items? need fixing$/i,m=>m[1]+' 个必需项需要修复'],
  [/^(\d+) optional items? need attention$/i,m=>m[1]+' 个可选项需要处理'],
  [/^(\d+) trusted certificate authorities$/i,m=>m[1]+' 个受信任的证书颁发机构'],
  [/^round (\d+) of (\d+)$/i,m=>'第 '+m[1]+' / '+m[2]+' 轮'],[/^round (\d+)$/i,m=>'第 '+m[1]+' 轮'],
  [/^Updated (.+)$/i,m=>'更新于 '+m[1]],[/^Version (.+) is current\.$/i,m=>'版本 '+m[1]+' 已是最新版。'],
  [/^Version (.+) is available; this app is (.+)\.$/i,m=>'可用版本为 '+m[1]+'；当前应用为 '+m[2]+'。'],
  [/^Version (.+); the update server could not be reached\.$/i,m=>'版本 '+m[1]+'；无法连接更新服务器。'],
  [/^Version (.+)$/i,m=>'版本 '+m[1]],
  [/^Connected as (.+) · (.+)\. Usage follows this ChatGPT workspace and plan\.$/i,m=>'已连接为 '+m[1]+' · '+m[2]+'。用量遵循该 ChatGPT 工作区和套餐。'],
  [/^Connected as (.+)$/i,m=>'已连接为 '+m[1]],[/^Local project: (.+)$/i,m=>'本地项目：'+m[1]],
  [/^(\d+) attachment\(s\) received$/i,m=>'已收到 '+m[1]+' 个附件'],
  [/^(\d+) blocker rules?$/i,m=>m[1]+' 条阻断规则'],
  [/^(\d+) reports?$/i,m=>m[1]+' 份报告'],[/^(\d+) connected$/i,m=>'已连接 '+m[1]+' 个'],[/^(\d+) active$/i,m=>m[1]+' 个正在运行'],
  [/^(.+) · local controller$/i,m=>m[1]+' · 本地控制器'],
  [/^(.+) · updated (.+)$/i,m=>m[1]+' · 更新于 '+m[2]],
  [/^(\d+) projects?, (\d+)\/(\d+) active · (.+)$/i,m=>m[1]+' 个项目，'+m[2]+'/'+m[3]+' 活跃 · '+m[4]],
  [/^(.+) API key - connect in Settings$/i,m=>m[1]+' API key - 请先在设置中连接'],
  [/^Connect (.+) in Settings first$/i,m=>'请先在设置中连接 '+m[1]],
  [/^(.+) - highest capability$/i,m=>m[1]+' - 最高能力'],
  [/^(.+) - balanced · recommended$/i,m=>m[1]+' - 均衡 · 推荐'],
  [/^(.+) - fastest, lowest cost$/i,m=>m[1]+' - 最快、成本最低'],
  [/^CrossAudit used all (\d+) of (\d+) automatic rounds without a passing result\. Nothing will continue or be admitted until you decide\.$/i,m=>'CrossAudit 已用完 '+m[1]+' / '+m[2]+' 轮自动审计，但仍未通过。在你决定前，不会继续执行或准入任何结果。'],
  [/^Automatic rounds used: (\d+) \/ (\d+)$/i,m=>'已用自动轮数：'+m[1]+' / '+m[2]],
  [/^Round history: (.+)$/i,m=>'轮次记录：'+m[1].replace(/Round (\d+):/gi,'第 $1 轮：').replace(/BLOCKED/gi,'未通过').replace(/PASS/gi,'通过').replace(/(\d+) issues?/gi,'$1 个问题')],[/^Affects (.+)$/i,m=>'影响 '+m[1]],
  [/^(\d+) remaining issues?$/i,m=>'剩余 '+m[1]+' 个问题'],
  [/^Automatic limit reached · (\d+) \/ (\d+) rounds$/i,m=>'已达自动上限 · '+m[1]+' / '+m[2]+' 轮'],
  [/^(·\s*)?CrossAudit paused after (\d+) of (\d+) rounds with (\d+) issues? remaining\.$/i,m=>(m[1]?'· ':'')+'CrossAudit 在第 '+m[2]+' / '+m[3]+' 轮后暂停，仍有 '+m[4]+' 个问题。']
  ,[/^(\d+) remote jobs active$/i,m=>m[1]+' 个远程任务正在运行']
  ,[/^Generator tool · (\d+) jobs\/task · (\d+) CPU · (\d+) GPU$/i,m=>'生成者工具 · 每任务 '+m[1]+' 个作业 · '+m[2]+' CPU · '+m[3]+' GPU']
  ,[/^Offline view · (.+) · the remote job continues independently$/i,m=>'离线视图 · '+m[1]+' · 远程任务仍在独立运行']
  ,[/^(\d+) MCP servers · (\d+) Skills$/i,m=>m[1]+' 个 MCP 服务器 · '+m[2]+' 个技能']
  ,[/^(\d+) calls\/task$/i,m=>'每任务 '+m[1]+' 次调用']
  ,[/^(\d+) recorded$/i,m=>'已记录 '+m[1]+' 次']
  ,[/^(\d+) committed$/i,m=>'已提交 '+m[1]+' 个']
  ,[/^Applies to (.+)$/i,m=>'适用于 '+m[1]]
  ,[/^(.+) · server annotations are untrusted$/i,m=>m[1]+' · 服务器标注不可信']
  ,[/^(\d+) tasks? needs? your decision$/i,m=>m[1]+' 个任务需要你决定']
  ,[/^round (\d+)\/(\d+)$/i,m=>'第 '+m[1]+'/'+m[2]+' 轮']
  ,[/^(\d+) findings?$/i,m=>m[1]+' 项发现']
  ,[/^(\d+) deterministic checks? passed$/i,m=>m[1]+' 项确定性检查已通过']
  ,[/^(\d+) files$/i,m=>m[1]+' 个文件']
  ,[/^Waiting for provider · heartbeat (\d+)s ago$/i,m=>'等待 provider · 心跳 '+m[1]+' 秒前']
  ,[/^last heartbeat (\d+)s ago$/i,m=>'最后心跳 '+m[1]+' 秒前']
  ,[/^no heartbeat for (\d+)s$/i,m=>'已 '+m[1]+' 秒无心跳']
  ,[/^(\d+)([mhd])$/,m=>m[1]+({m:' 分钟前',h:' 小时前',d:' 天前'})[m[2]]]
];
let currentLocale='en';
const textSources=new WeakMap(),attributeSources=new WeakMap();
function storedLocale(){try{const row=document.cookie.split(';').map(value=>value.trim())
    .find(value=>value.startsWith(LOCALE_COOKIE+'='));if(row)return decodeURIComponent(row.slice(LOCALE_COOKIE.length+1));}catch(e){}
  try{return localStorage.getItem(LOCALE_KEY);}catch(e){return null;}}
function zhValue(value){const exact=ZH[value];if(exact)return exact;for(const [pattern,replace] of ZH_PATTERNS){const match=value.match(pattern);if(match)return replace(match);}return value;}
function translatePreservingSpace(value){const match=String(value).match(/^(\s*)([\s\S]*?)(\s*)$/);return match[1]+zhValue(match[2])+match[3];}
function renderLocaleText(node){if(!node.parentElement||['SCRIPT','STYLE'].includes(node.parentElement.tagName))return;
  let source=textSources.get(node);const translated=source===undefined?'':translatePreservingSpace(source);
  if(source===undefined||(node.data!==source&&node.data!==translated)){source=node.data;textSources.set(node,source);}
  const wanted=currentLocale==='zh'?translatePreservingSpace(source):source;if(node.data!==wanted)node.data=wanted;}
function renderLocaleAttributes(element){const names=['placeholder','title','aria-label'];let sources=attributeSources.get(element)||{};
  for(const name of names){if(!element.hasAttribute(name))continue;const value=element.getAttribute(name);const old=sources[name];
    if(old===undefined||(value!==old&&value!==zhValue(old)))sources[name]=value;const wanted=currentLocale==='zh'?zhValue(sources[name]):sources[name];
    if(value!==wanted)element.setAttribute(name,wanted);}attributeSources.set(element,sources);}
function localizeTree(root){if(root.nodeType===Node.TEXT_NODE){renderLocaleText(root);return;}if(root.nodeType!==Node.ELEMENT_NODE&&root!==document.body)return;
  if(root.nodeType===Node.ELEMENT_NODE)renderLocaleAttributes(root);const walker=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){const node=walker.currentNode;if(node.nodeType===Node.TEXT_NODE)renderLocaleText(node);else renderLocaleAttributes(node);}}
function applyLocale(locale,remember=true){currentLocale=locale==='zh'?'zh':'en';document.documentElement.lang=currentLocale==='zh'?'zh-CN':'en';
  for(const id of ['locale-toggle','hub-locale']){const button=document.getElementById(id);button.textContent=currentLocale==='zh'?'EN':'中文';
    button.setAttribute('aria-label',currentLocale==='zh'?'切换到英文':'Switch to Chinese');button.title=currentLocale==='zh'?'切换到英文':'Switch language';}
  localizeTree(document.body);if(remember){try{localStorage.setItem(LOCALE_KEY,currentLocale);}catch(e){}
    document.cookie=LOCALE_COOKIE+'='+encodeURIComponent(currentLocale)+'; Path=/; Max-Age=31536000; SameSite=Strict';}}
const localeObserver=new MutationObserver(records=>{for(const record of records){if(record.type==='characterData')renderLocaleText(record.target);
  else if(record.type==='attributes')renderLocaleAttributes(record.target);else for(const node of record.addedNodes)localizeTree(node);}});
localeObserver.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','title','aria-label']});
document.getElementById('locale-toggle').onclick=()=>applyLocale(currentLocale==='zh'?'en':'zh');
document.getElementById('hub-locale').onclick=document.getElementById('locale-toggle').onclick;
applyLocale(storedLocale()==='zh'?'zh':'en',false);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const at = t => t ? new Date(t*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '';
const MARK = {done:'✓',failed:'×',current:'·',pending:''};
let lastState = null;
let pendingContinuation={cycle:'',chat:''};
let pendingFiles = [];
let uploadProgress = new Map();
let transferBusy = false;
let activeView = 'artifacts';
let newTaskMode = false;
let activeChatId = '';
const expandedGroups = new Set();
const expandedReviews = new Set();
let lastPillKey = '';
let handoffDirection = '';
let handoffAt = 0;
function ago(t){if(!t)return '';const s=Math.max(0,Date.now()/1000-Number(t));
  if(s<60)return 'now';if(s<3600)return Math.floor(s/60)+'m';
  if(s<86400)return Math.floor(s/3600)+'h';return Math.floor(s/86400)+'d';}
const USER_STATES={DRAFT:'understand',QUEUED:'understand',GENERATING:'work',
  WAITING_FOR_PROVIDER:'work',WAITING_FOR_CAPABILITY:'work',AUDITING:'check',
  REVISING:'revise',PASSED:'done',WAITING_FOR_HUMAN:'decide',
  PROVIDER_UNAVAILABLE:'decide'};
const STATE_LABELS={understand:'Understanding',work:'Working',check:'Checking',
  revise:'Revising',done:'Completed',decide:'Needs your decision'};

const THEME_KEY = 'crossaudit-theme';
const themeButton = document.getElementById('theme-toggle');
const hubThemeButton = document.getElementById('hub-theme');
function storedTheme(){try{return localStorage.getItem(THEME_KEY);}catch(e){return null;}}
function applyTheme(theme, remember){
  const value = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme',value);
  themeButton.textContent = value === 'dark' ? '☀' : '◐';
  hubThemeButton.textContent = themeButton.textContent;
  themeButton.setAttribute('aria-label',value === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  themeButton.title = value === 'dark' ? 'Use light theme' : 'Use dark theme';
  if(remember){try{localStorage.setItem(THEME_KEY,value);}catch(e){}}
}
const savedTheme = storedTheme();
const systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
applyTheme(savedTheme || (systemDark ? 'dark' : 'light'),false);
themeButton.onclick = () => applyTheme(
  document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark',true);
hubThemeButton.onclick = themeButton.onclick;

const composerWrap=document.querySelector('.composer-wrap');
const threadScroller=document.getElementById('thread');
function syncComposerClearance(){
  const nearBottom=threadScroller.scrollHeight-threadScroller.scrollTop-threadScroller.clientHeight<96;
  const clearance=composerWrap.classList.contains('view-hidden')?0:Math.ceil(composerWrap.getBoundingClientRect().height);
  document.documentElement.style.setProperty('--composer-clearance',clearance+'px');
  if(nearBottom)requestAnimationFrame(()=>{threadScroller.scrollTop=threadScroller.scrollHeight;});
}
new ResizeObserver(syncComposerClearance).observe(composerWrap);
window.addEventListener('resize',syncComposerClearance);
syncComposerClearance();

async function api(path, body){
  const opt = body ? {method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify(body)} : {};
  const r = await fetch(path + '?t=' + encodeURIComponent(T), opt);
  const text=await r.text();let data=null;try{data=text?JSON.parse(text):{};}catch(e){}
  if(!r.ok){const error=new Error((data&&data.reason)||text||('Request failed ('+r.status+')'));
    if(data&&typeof data==='object')Object.assign(error,data);throw error;}
  return data||{};
}

let workspacePickerContext='project',selectedProjectFolder='';
function updateWorkspaceFields(path){
  const value=path||'Not selected';
  document.getElementById('project-workspace').value=selectedProjectFolder;
  document.getElementById('settings-workspace').value=value;
  document.getElementById('project-path-preview').textContent=selectedProjectFolder
    ?'Local project: '+selectedProjectFolder
    :'Choose the exact folder CrossAudit should use. The project name will not create another subfolder.';
}
function workspaceError(message){
  const id=workspacePickerContext==='settings'?'settings-error':'wizard-error';
  const box=document.getElementById(id);box.textContent=message;box.className='wizard-error on';
}
function showInlineError(id,error){
  const box=document.getElementById(id),message=error&&error.message?error.message:String(error||'Something went wrong');
  box.innerHTML=esc(message)+(error&&error.url?' <a href="'+esc(error.url)+'" target="_blank" rel="noopener">Open help ↗</a>':'');
  box.className='wizard-error on';
}
function chooseWorkspace(context){
  workspacePickerContext=context;
  const current=(context==='project'?selectedProjectFolder:'')||
    (projectState&&projectState.workspace)||document.getElementById('settings-workspace').value||'';
  const bridge=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.crossaudit;
  if(!bridge){workspaceError('Use the CrossAudit macOS app to choose a local folder. The browser console cannot read arbitrary folder paths.');return;}
  bridge.postMessage({action:'chooseWorkspace',current});
}
function revealProjectFolder(path){
  const bridge=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.crossaudit;
  if(!bridge||!path)return false;
  bridge.postMessage({action:'revealInFinder',path});return true;
}
window.crossauditWorkspaceSelected=async choice=>{
  if(!choice||!choice.path)return;
  try{const result=await api('/api/workspace/select',{path:choice.path});
    if(workspacePickerContext==='project')selectedProjectFolder=result.workspace;
    if(projectState)projectState.workspace=result.workspace;updateWorkspaceFields(result.workspace);syncProjectReview();
    await refreshProjects();
  }catch(e){showInlineError(workspacePickerContext==='settings'?'settings-error':'wizard-error',e);}
};

const settingsModal=document.getElementById('settings-modal');
const settingsForm=document.getElementById('settings-form');
let settingsSource=null;let settingsState=null;
let activeSettingsPanel='general';
function showSettingsPanel(name,focus=true){
  const next=name==='providers'?'providers':'general';activeSettingsPanel=next;
  document.querySelectorAll('[data-settings-panel]').forEach(button=>{const active=button.dataset.settingsPanel===next;
    button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  document.querySelectorAll('[data-settings-pane]').forEach(pane=>pane.hidden=pane.dataset.settingsPane!==next);
  const save=document.getElementById('save-settings');save.hidden=next!=='providers';
  document.getElementById('cancel-settings').textContent=currentLocale==='zh'?(next==='providers'?'取消':'完成'):(next==='providers'?'Cancel':'Done');
  document.getElementById('settings-foot-note').textContent=currentLocale==='zh'
    ?(next==='providers'?'API key 以只写方式存入 macOS 钥匙串；订阅凭据始终由官方供应商运行时持有。':'工作区修改会立即生效；迁移或更新此 Mac 后请再次运行环境诊断。')
    :(next==='providers'?'API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.':'Workspace changes apply immediately. Run Doctor after moving or updating this Mac.');
  if(focus)requestAnimationFrame(()=>document.querySelector('[data-settings-pane="'+next+'"]')?.focus());
}
document.querySelector('.settings-nav').onclick=ev=>{const button=ev.target.closest('[data-settings-panel]');
  if(button)showSettingsPanel(button.dataset.settingsPanel,false);};
function renderProviderCards(d){
  const host=document.getElementById('provider-credentials');
  const vendors=Object.keys(d.providers||{}).sort((a,b)=>{const rank=vendor=>vendor==='openai'?0:(d.providers[vendor]||{}).configured?1:2;
    return rank(a)-rank(b)||String((d.providers[a]||{}).label||a).localeCompare(String((d.providers[b]||{}).label||b));});
  if(host.getAttribute('data-vendors')===vendors.join(','))return;
  host.setAttribute('data-vendors',vendors.join(','));
  host.innerHTML=vendors.map(vendor=>{const p=d.providers[vendor]||{};const label=p.label||vendor;
    const subscription=vendor==='openai'
      ?'<div class="connection-method"><div class="connection-method-copy"><b>ChatGPT subscription</b><small id="chatgpt-detail">'+esc((p.subscription||{}).detail||'Official Codex sign-in.')+'</small></div><button type="button" class="secondary" id="connect-chatgpt">Connect</button></div>'
      :'<div class="provider-note"><b>API access.</b> '+esc((p.subscription||{}).detail||'Use an official developer API key.')+'</div>';
    const links=(p.console_url?'<a class="login-link" href="'+esc(p.console_url)+'" target="_blank" rel="noopener">Get key ↗</a> ':'')
      +(p.docs_url?'<a class="login-link" href="'+esc(p.docs_url)+'" target="_blank" rel="noopener">API docs ↗</a>':'');
    return '<details class="credential-card"'+(vendor==='openai'?' open':'')+'><summary class="credential-head"><b>'+esc(label)+'</b><span class="credential-state" id="'+esc(vendor)+'-state">Checking…</span></summary><div class="credential-body">'
      +subscription+'<div class="secret-row"><label class="field"><span>New API key · '+links+'</span><input type="password" id="'+esc(vendor)+'-key" data-provider-key="'+esc(vendor)+'" autocomplete="new-password" placeholder="Leave blank to keep the saved key"></label>'
      +'<label class="toggle-line"><input type="checkbox" id="remove-'+esc(vendor)+'" data-provider-remove="'+esc(vendor)+'"><span><b>Remove</b><small>Delete saved key</small></span></label></div>'
      +'<div class="secret-row"><label class="field"><span>Backup API key (optional)</span><input type="password" id="'+esc(vendor)+'-backup-key" data-provider-key="'+esc(vendor)+'_backup" autocomplete="new-password" placeholder="Used only by an explicit fallback route"></label>'
      +'<label class="toggle-line"><input type="checkbox" id="remove-'+esc(vendor)+'-backup" data-provider-remove="'+esc(vendor)+'_backup"><span><b>Remove</b><small>Delete backup key</small></span></label></div></div></details>';
  }).join('');
}
function renderDoctor(doctor){
  const value=doctor||{};const status=value.status||'idle';
  const state=document.getElementById('doctor-state');state.className='doctor-state '+status;
  document.getElementById('doctor-summary').textContent=value.summary||'Environment has not been checked';
  const run=document.getElementById('run-doctor');run.disabled=status==='running';
  run.textContent=status==='running'?'Checking…':'Run check';
  const rows=Array.isArray(value.checks)?value.checks:[];
  const marks={ready:'✓',missing:'!',outdated:'↑',warning:'!',unknown:'?',waiting:'·'};
  document.getElementById('doctor-checks').innerHTML=rows.length?rows.map(row=>{
    const repair=row.repair||{};let action='';
    if(repair.inputs){
      action='<div class="doctor-action"><div class="doctor-identity"><input data-doctor-name maxlength="100" placeholder="Git author name"><input data-doctor-email type="email" maxlength="200" placeholder="Git author email"><button type="button" class="secondary" data-doctor-action="'+esc(repair.action)+'">'+esc(repair.label||'Save')+'</button></div></div>';
    }else if(repair.url){
      action='<div class="doctor-action"><a class="secondary" href="'+esc(repair.url)+'" target="_blank" rel="noopener">'+esc(repair.label||'Open help')+' ↗</a></div>';
    }else if(repair.action){
      action='<div class="doctor-action"><button type="button" class="secondary" data-doctor-action="'+esc(repair.action)+'">'+esc(repair.label||'Fix')+'</button></div>';
    }
    const version=row.version?'<span class="doctor-version">v'+esc(row.version)+'</span>':'';
    return '<div class="doctor-check '+esc(row.status||'unknown')+'"><span class="doctor-mark">'+(marks[row.status]||'?')+'</span><div class="doctor-copy"><b>'+esc(row.label||row.id)+'</b><small>'+esc(row.detail||'')+'</small></div>'+version+action+'</div>';
  }).join(''):'<div class="doctor-empty">'+(status==='running'?'Checking required software…':'Run the check to inspect this Mac.')+'</div>';
  const panel=document.querySelector('.doctor-panel'),toggle=document.getElementById('toggle-doctor-details');
  if(['blocked','failed','attention'].includes(status))panel.classList.add('expanded');
  const expanded=panel.classList.contains('expanded');toggle.setAttribute('aria-expanded',String(expanded));
  toggle.textContent=currentLocale==='zh'?(expanded?'隐藏详情':'显示详情'):(expanded?'Hide details':'Show details');
}
function renderSettings(d){
  settingsState=d;
  renderProviderCards(d);
  for(const vendor of Object.keys(d.providers||{})){
    const provider=d.providers&&d.providers[vendor]||{};
    const apiConfigured=Boolean(provider.api_key&&provider.api_key.configured);
    const configured=Boolean(provider.configured);
    const state=document.getElementById(vendor+'-state');state.textContent=configured?'Connected':'Not connected';
    state.className='credential-state'+(configured?' ok':'');
    document.getElementById('remove-'+vendor).disabled=!apiConfigured;
    document.getElementById('remove-'+vendor+'-backup').disabled=!Boolean(provider.backup_api_key&&provider.backup_api_key.configured);
  }
  const openai=d.providers&&d.providers.openai||{};const chatgpt=openai.chatgpt||{};
  const login=d.provider_login||{};const button=document.getElementById('connect-chatgpt');
  const detail=document.getElementById('chatgpt-detail');
  if(chatgpt.connected){
    detail.textContent='Connected'+(chatgpt.email?' as '+chatgpt.email:'')+(chatgpt.plan?' · '+chatgpt.plan:'')
      +'. Usage follows this ChatGPT workspace and plan.';button.textContent='Connected';button.disabled=true;
  }else if(login.status==='running'){
    detail.innerHTML=esc(login.detail||'Complete sign in in your browser')
      +(login.url?' · <a class="login-link" href="'+esc(login.url)+'">Open ChatGPT ↗</a>':'');
    button.textContent='Waiting…';button.disabled=true;
  }else{
    detail.textContent=chatgpt.detail||'Use the official Codex login and an eligible ChatGPT plan. CrossAudit never receives the OAuth token.';
    button.textContent=login.status==='failed'?'Try again':'Connect';button.disabled=!chatgpt.available;
  }
  const deps=d.dependencies||{};const doctorRows=Object.fromEntries(((d.doctor&&d.doctor.checks)||[]).map(row=>[row.id,row]));
  for(const [id,key,value] of [['git-state','git',deps.git],['ghcli-state','github_cli',deps.github_cli]]){
    const el=document.getElementById(id),row=doctorRows[key];const status=row&&row.status;
    el.textContent=status==='outdated'?'Outdated':status==='missing'?'Missing':status==='ready'?'Ready':value?'Ready':'Checking';
    el.className=status==='outdated'||status==='missing'||(!status&&!value)?'bad':'';
  }
  updateWorkspaceFields(d.workspace||'Not selected');
  const runtime=d.runtime||{};document.getElementById('runtime-state').textContent=runtime.install_mode||'unknown';
  document.getElementById('digest-state').textContent=runtime.code_digest||'unavailable';
  const providerRows=Object.values(d.providers||{}),connected=providerRows.filter(row=>row.configured).length;
  document.getElementById('settings-provider-count').textContent=connected+'/'+providerRows.length;
  const doctorStatus=d.doctor&&d.doctor.status||'idle';const generalState=document.getElementById('settings-general-state');
  generalState.textContent=['blocked','failed'].includes(doctorStatus)?'!':doctorStatus==='attention'?'1':doctorStatus==='ready'?'✓':'…';
  generalState.className=['blocked','failed'].includes(doctorStatus)?'bad':doctorStatus==='attention'?'attention':doctorStatus==='ready'?'ok':'';
  renderDoctor(d.doctor);
}
async function openSettings(panel){
  const requested=typeof panel==='string'?panel:'general';showSettingsPanel(requested,false);
  settingsModal.className='project-modal on';document.getElementById('settings-error').className='wizard-error';
  try{renderSettings(await api('/api/settings'));if(!settingsSource){
    settingsSource=new EventSource('/api/settings/stream?t='+encodeURIComponent(T));
    settingsSource.onmessage=ev=>{try{renderSettings(JSON.parse(ev.data));}catch(e){}};
    settingsSource.onerror=()=>{};
  }}catch(e){const box=document.getElementById('settings-error');
    box.textContent=e.message;box.className='wizard-error on';}
}
function closeSettings(){settingsModal.className='project-modal';settingsForm.reset();}
document.getElementById('settings-open').onclick=openSettings;
document.getElementById('hub-settings').onclick=openSettings;
document.getElementById('close-settings').onclick=closeSettings;
document.getElementById('cancel-settings').onclick=closeSettings;
document.getElementById('choose-settings-workspace').onclick=()=>chooseWorkspace('settings');
document.getElementById('toggle-doctor-details').onclick=()=>{const panel=document.querySelector('.doctor-panel');
  panel.classList.toggle('expanded');const expanded=panel.classList.contains('expanded'),button=document.getElementById('toggle-doctor-details');
  button.setAttribute('aria-expanded',String(expanded));button.textContent=currentLocale==='zh'?(expanded?'隐藏详情':'显示详情'):(expanded?'Hide details':'Show details');};
function doctorMessage(text,bad=false){const box=document.getElementById('doctor-message');box.textContent=text||'';
  box.className='doctor-message'+(text?' on':'')+(bad?' bad':'');}
document.getElementById('run-doctor').onclick=async()=>{doctorMessage('');
  try{renderDoctor(await api('/api/doctor',{action:'scan'}));}
  catch(e){doctorMessage(e.message,true);}};
document.getElementById('doctor-checks').onclick=async ev=>{
  const button=ev.target.closest('[data-doctor-action]');if(!button)return;
  const action=button.getAttribute('data-doctor-action');
  if(action==='choose_workspace'){chooseWorkspace('settings');return;}
  const payload={action};const row=button.closest('.doctor-check');
  if(action==='set_git_identity'){
    payload.name=row.querySelector('[data-doctor-name]').value.trim();
    payload.email=row.querySelector('[data-doctor-email]').value.trim();
  }
  doctorMessage('');button.disabled=true;const before=button.textContent;button.textContent='Working…';
  try{const result=await api('/api/doctor',payload);doctorMessage(result.message||'Repair started. Doctor is checking again.');
    renderSettings(await api('/api/settings'));}
  catch(e){doctorMessage(e.message,true);button.disabled=false;button.textContent=before;}
};
settingsModal.addEventListener('click',ev=>{if(ev.target===settingsModal)closeSettings();});
document.getElementById('provider-credentials').onclick=async ev=>{if(!ev.target.closest('#connect-chatgpt'))return;
  const button=document.getElementById('connect-chatgpt');const error=document.getElementById('settings-error');
  button.disabled=true;button.textContent='Starting…';error.className='wizard-error';
  try{const result=await api('/api/providers/connect',{provider:'openai',method:'chatgpt'});
    if(result.url){const link=document.createElement('a');link.href=result.url;
      document.body.appendChild(link);link.click();link.remove();}
    renderSettings(await api('/api/settings'));
  }catch(e){error.textContent=e.message;error.className='wizard-error on';button.disabled=false;button.textContent='Connect';}
};
settingsForm.onsubmit=async ev=>{ev.preventDefault();const save=document.getElementById('save-settings');
  const error=document.getElementById('settings-error');error.className='wizard-error';save.disabled=true;
  const payload={};document.querySelectorAll('[data-provider-key]').forEach(el=>payload[el.getAttribute('data-provider-key')+'_key']=el.value);
  document.querySelectorAll('[data-provider-remove]').forEach(el=>payload['remove_'+el.getAttribute('data-provider-remove')]=el.checked);
  try{const state=await api('/api/settings',payload);settingsForm.reset();renderSettings(state);
    if(projectState)configureProjectForm();}
  catch(e){error.textContent=e.message;error.className='wizard-error on';}
  save.disabled=false;};

const runtimeModal=document.getElementById('runtime-modal');
const runtimeForm=document.getElementById('runtime-form');
let runtimeRoles={};let runtimeSkills=[];let runtimeFallbackCatalog=[];let runtimeCapabilityNonce={generator:0,auditor:0};
let activeRuntimePanel='models';
function showRuntimePanel(name,focus=true){
  const allowed=['models','automation','budgets','instructions'];const next=allowed.includes(name)?name:'models';
  activeRuntimePanel=next;document.querySelectorAll('[data-runtime-panel]').forEach(button=>{
    const active=button.dataset.runtimePanel===next;button.classList.toggle('active',active);
    button.setAttribute('aria-pressed',String(active));});
  document.querySelectorAll('[data-runtime-pane]').forEach(pane=>pane.hidden=pane.dataset.runtimePane!==next);
  if(focus)requestAnimationFrame(()=>document.querySelector('[data-runtime-pane="'+next+'"]')?.focus());
}
document.querySelector('.runtime-nav').onclick=ev=>{const button=ev.target.closest('[data-runtime-panel]');
  if(button)showRuntimePanel(button.dataset.runtimePanel,false);};
function runtimeEl(role,name){return document.getElementById('runtime-'+role+'-'+name);}
function runtimeModel(role){const select=runtimeEl(role,'model');return select.value==='__custom__'
  ?runtimeEl(role,'custom').value.trim():select.value;}
function renderRuntimeEfforts(role,row){const target=runtimeEl(role,'effort');const previous=target.value;
  target.innerHTML='<option value="">Automatic · provider default</option>'+(row.efforts||[]).map(item=>
    '<option value="'+esc(item.id)+'">'+esc(item.id)+' - '+esc(item.hint||'')+'</option>').join('');
  const wanted=row.reasoning_effort!==undefined?row.reasoning_effort:previous;
  if([...target.options].some(option=>option.value===wanted))target.value=wanted;else target.value='';
  runtimeEl(role,'effort-help').textContent=row.detail||((row.efforts||[]).length
    ?'Applies to the next provider request.':'This model uses its provider-controlled default.');
  target.disabled=!(row.efforts||[]).length;}
function renderRuntimeRole(role,row){runtimeRoles[role]=row;const card=runtimeEl(role,'card');
  const human=row.vendor==='human';card.classList.toggle('human',human);runtimeEl(role,'vendor').textContent=row.label||row.vendor;
  const select=runtimeEl(role,'model');const rows=row.models||[];select.innerHTML=rows.map(item=>
    '<option value="'+esc(item.id)+'">'+esc(item.id)+' - '+esc(item.hint||'available')+'</option>').join('')
    +(human?'':'<option value="__custom__">Enter a custom model ID…</option>');
  if(human){select.innerHTML='<option value="">Human-written changes</option>';select.disabled=true;
    runtimeEl(role,'custom-wrap').className='field custom-model off';runtimeEl(role,'effort').innerHTML='<option>Not applicable</option>';
    runtimeEl(role,'effort').disabled=true;runtimeEl(role,'effort-help').textContent=row.detail||'';return;}
  select.disabled=false;if([...select.options].some(option=>option.value===row.model))select.value=row.model;
  else{select.value='__custom__';runtimeEl(role,'custom').value=row.model||'';}
  runtimeEl(role,'custom-wrap').className='field custom-model'+(select.value==='__custom__'?'':' off');
  renderRuntimeEfforts(role,row);}
function fallbackChoices(role){const opposite=role==='generator'?'auditor':'generator';const blocked=(runtimeRoles[opposite]||{}).vendor;
  return runtimeFallbackCatalog.filter(row=>row.vendor!==blocked);}
function renderFallbacks(role,rows){const host=document.getElementById('runtime-'+role+'-fallbacks');const choices=fallbackChoices(role);
  if(!(rows||[]).length){host.innerHTML='<div class="fallback-empty">No fallback. A provider failure pauses safely for you.</div>';return;}
  host.innerHTML=rows.map((row,index)=>{const listId='fallback-models-'+role+'-'+index;
    const options=choices.map(item=>'<option value="'+esc(item.vendor)+'"'+(item.vendor===row.vendor?' selected':'')+'>'+esc(item.label)+(item.connected?' · connected':' · key needed')+'</option>').join('');
    const selected=choices.find(item=>item.vendor===row.vendor)||choices[0]||{models:[]};
    return '<div class="fallback-row" data-fallback-role="'+role+'"><select data-fallback-vendor>'+options+'</select>'
      +'<input data-fallback-model list="'+listId+'" maxlength="120" value="'+esc(row.model||((selected.models||[])[0]||{}).id||'')+'" placeholder="Exact model ID"><datalist id="'+listId+'">'
      +(selected.models||[]).map(model=>'<option value="'+esc(model.id)+'">'+esc(model.hint||'')+'</option>').join('')+'</datalist>'
      +'<select data-fallback-credential title="Credential"><option value="primary"'+(row.credential==='backup'?'':' selected')+'>Primary key</option><option value="backup"'+(row.credential==='backup'?' selected':'')+'>Backup key</option></select>'
      +'<button type="button" class="fallback-remove" data-remove-fallback title="Remove">×</button></div>';}).join('');}
function fallbackRows(role){return [...document.querySelectorAll('[data-fallback-role="'+role+'"]')].map(row=>({
  vendor:row.querySelector('[data-fallback-vendor]').value,model:row.querySelector('[data-fallback-model]').value.trim(),
  credential:row.querySelector('[data-fallback-credential]').value}));}
function syncRuntimeBusy(d){const busy=Boolean(d&&d.progress&&!d.progress.finished);const save=document.getElementById('save-runtime');
  save.disabled=busy;document.getElementById('save-runtime-skill').disabled=busy;document.getElementById('runtime-foot').textContent=busy
    ?'A loop is running. These controls unlock when its current model calls finish.'
    :'Automatic means the provider chooses its documented default.';}
async function updateRuntimeCapabilities(role){const model=runtimeModel(role);if(!model)return;
  const nonce=++runtimeCapabilityNonce[role];runtimeEl(role,'effort').disabled=true;
  runtimeEl(role,'effort-help').textContent='Checking this model…';
  try{const row=await api('/api/runtime/options',{role,model});if(nonce!==runtimeCapabilityNonce[role])return;
    row.models=runtimeRoles[role].models;row.reasoning_effort='';runtimeRoles[role]={...runtimeRoles[role],...row};renderRuntimeEfforts(role,row);}
  catch(e){if(nonce!==runtimeCapabilityNonce[role])return;runtimeEl(role,'effort').innerHTML='<option value="">Automatic · provider default</option>';
    runtimeEl(role,'effort').disabled=true;runtimeEl(role,'effort-help').textContent=e.message;}}
function openRuntime(){const config=lastState&&lastState.runtime_config;if(!config)return;
  document.getElementById('runtime-error').className='wizard-error';
  runtimeFallbackCatalog=config.fallback_catalog||[];
  for(const role of ['generator','auditor'])renderRuntimeRole(role,config.roles[role]);
  for(const role of ['generator','auditor'])renderFallbacks(role,(config.roles[role]||{}).fallbacks||[]);
  document.getElementById('runtime-max-rounds').value=String(config.max_rounds||lastState.max_rounds||3);
  const resilience=config.resilience||{};document.getElementById('runtime-max-attempts').value=resilience.max_attempts||3;
  document.getElementById('runtime-initial-backoff').value=resilience.initial_backoff_seconds??1;
  document.getElementById('runtime-max-backoff').value=resilience.max_backoff_seconds??20;
  document.getElementById('runtime-retry-after-cap').value=resilience.retry_after_cap_seconds??120;
  document.getElementById('runtime-circuit-failures').value=resilience.circuit_breaker_failures||3;
  document.getElementById('runtime-circuit-cooldown').value=resilience.circuit_breaker_cooldown_seconds||60;
  const budgets=config.budgets||{};document.getElementById('runtime-daily-token-warning').value=budgets.daily_token_warning||'';
  document.getElementById('runtime-daily-token-limit').value=budgets.daily_token_limit||'';
  document.getElementById('runtime-monthly-cost-warning').value=budgets.monthly_cost_warning_usd||'';
  document.getElementById('runtime-monthly-cost-limit').value=budgets.monthly_cost_limit_usd||'';
  const guard=lastState&&lastState.usage&&lastState.usage.budget||{};document.getElementById('runtime-guardrail-state').textContent=
    guard.state==='blocked'?(guard.reasons||[]).join(' '):guard.state==='warning'?(guard.warnings||[]).join(' '):'Limits are local safeguards; provider billing remains authoritative.';
  renderRuntimeSkills(config.skills||[]);
  if(config.skills_error)document.getElementById('runtime-skill-status').textContent=config.skills_error;
  showRuntimePanel('models',false);syncRuntimeBusy(lastState);runtimeModal.className='project-modal on';}
function closeRuntime(){runtimeModal.className='project-modal';runtimeForm.reset();}
for(const role of ['generator','auditor']){
  runtimeEl(role,'model').onchange=()=>{runtimeEl(role,'custom-wrap').className='field custom-model'
      +(runtimeEl(role,'model').value==='__custom__'?'':' off');if(runtimeEl(role,'model').value!=='__custom__')updateRuntimeCapabilities(role);};
  runtimeEl(role,'custom').onchange=()=>updateRuntimeCapabilities(role);
}
document.querySelectorAll('[data-add-fallback]').forEach(button=>button.onclick=()=>{const role=button.getAttribute('data-add-fallback');
  const rows=fallbackRows(role),choices=fallbackChoices(role),choice=choices.find(item=>item.vendor!==(runtimeRoles[role]||{}).vendor)||choices[0];if(!choice)return;
  rows.push({vendor:choice.vendor,model:(choice.models[0]||{}).id||'',credential:'primary'});renderFallbacks(role,rows);});
runtimeModal.addEventListener('click',ev=>{const button=ev.target.closest('[data-remove-fallback]');if(!button)return;
  const row=button.closest('[data-fallback-role]'),role=row.getAttribute('data-fallback-role');row.remove();
  if(!fallbackRows(role).length)renderFallbacks(role,[]);});
runtimeModal.addEventListener('change',ev=>{if(!ev.target.matches('[data-fallback-vendor]'))return;
  const row=ev.target.closest('[data-fallback-role]'),role=row.getAttribute('data-fallback-role'),rows=fallbackRows(role);
  const index=[...document.querySelectorAll('[data-fallback-role="'+role+'"]')].indexOf(row),choice=runtimeFallbackCatalog.find(x=>x.vendor===ev.target.value);
  if(choice)rows[index].model=(choice.models[0]||{}).id||'';renderFallbacks(role,rows);});
document.querySelectorAll('[data-runtime-refresh]').forEach(button=>button.onclick=async()=>{
  const role=button.getAttribute('data-runtime-refresh'),row=runtimeRoles[role];if(!row||row.vendor==='human')return;
  button.disabled=true;button.textContent='Refreshing…';
  try{const result=await api('/api/models/refresh',{role,vendor:row.vendor,method:row.connection,endpoint:row.endpoint||''});
    row.models=result.models.map(id=>({id,hint:'visible to this account'}));const selected=runtimeModel(role);
    renderRuntimeRole(role,{...row,model:selected});button.textContent='Models updated';}
  catch(e){showInlineError('runtime-error',e);button.textContent='Refresh failed';}
  finally{button.disabled=false;setTimeout(()=>button.textContent='Refresh models',2500);}
});
document.getElementById('runtime-open').onclick=openRuntime;
document.getElementById('close-runtime').onclick=closeRuntime;
document.getElementById('cancel-runtime').onclick=closeRuntime;
runtimeModal.addEventListener('click',ev=>{if(ev.target===runtimeModal)closeRuntime();});
function renderRuntimeSkills(rows){runtimeSkills=rows||[];const select=document.getElementById('runtime-skill-select');
  select.innerHTML='<option value="__new__">Create new guidance…</option>'+runtimeSkills.map(row=>
    '<option value="'+esc(row.name)+'">'+esc(row.name)+'</option>').join('');select.value='__new__';selectRuntimeSkill();}
function selectRuntimeSkill(){const name=document.getElementById('runtime-skill-select').value;
  const row=runtimeSkills.find(item=>item.name===name);document.getElementById('runtime-skill-name').value=row?row.name:'';
  document.getElementById('runtime-skill-name').disabled=Boolean(row);
  document.getElementById('runtime-skill-scope').value=row?(row.applies_to||[]).join(', '):'';
  document.getElementById('runtime-skill-body').value=row?row.body:'';
  document.getElementById('runtime-skill-status').textContent=row?'Editing committed guidance':'Create reusable project guidance';}
document.getElementById('runtime-skill-select').onchange=selectRuntimeSkill;
document.getElementById('save-runtime-skill').onclick=async()=>{const button=document.getElementById('save-runtime-skill');
  const error=document.getElementById('runtime-error');error.className='wizard-error';button.disabled=true;
  const payload={name:document.getElementById('runtime-skill-name').value.trim(),
    applies_to:document.getElementById('runtime-skill-scope').value.split(',').map(x=>x.trim()).filter(Boolean),
    body:document.getElementById('runtime-skill-body').value};
  try{const result=await api('/api/skills',payload);renderRuntimeSkills(result.skills||[]);
    document.getElementById('runtime-skill-select').value=payload.name;selectRuntimeSkill();
    document.getElementById('runtime-skill-status').textContent=result.changed?'Saved and committed':'Already up to date';
    if(lastState&&lastState.runtime_config)lastState.runtime_config.skills=result.skills||[];}
  catch(e){showInlineError('runtime-error',e);}
  finally{button.disabled=Boolean(lastState&&lastState.progress&&!lastState.progress.finished);}};
runtimeForm.onsubmit=async ev=>{ev.preventDefault();const save=document.getElementById('save-runtime');
  const error=document.getElementById('runtime-error');error.className='wizard-error';save.disabled=true;
  const payload={generator_model:runtimeModel('generator'),auditor_model:runtimeModel('auditor'),
    generator_reasoning_effort:runtimeEl('generator','effort').value||'',
    auditor_reasoning_effort:runtimeEl('auditor','effort').value||'',
    generator_fallbacks:fallbackRows('generator'),auditor_fallbacks:fallbackRows('auditor'),
    max_rounds:Number(document.getElementById('runtime-max-rounds').value),
    max_attempts:Number(document.getElementById('runtime-max-attempts').value),
    initial_backoff_seconds:Number(document.getElementById('runtime-initial-backoff').value),
    max_backoff_seconds:Number(document.getElementById('runtime-max-backoff').value),
    retry_after_cap_seconds:Number(document.getElementById('runtime-retry-after-cap').value),
    circuit_breaker_failures:Number(document.getElementById('runtime-circuit-failures').value),
    circuit_breaker_cooldown_seconds:Number(document.getElementById('runtime-circuit-cooldown').value),
    daily_token_warning:document.getElementById('runtime-daily-token-warning').value,
    daily_token_limit:document.getElementById('runtime-daily-token-limit').value,
    monthly_cost_warning_usd:document.getElementById('runtime-monthly-cost-warning').value,
    monthly_cost_limit_usd:document.getElementById('runtime-monthly-cost-limit').value};
  try{const result=await api('/api/runtime',payload);if(lastState)lastState.runtime_config=result;
    if(lastState)lastState.max_rounds=result.max_rounds;
    closeRuntime();route.className='route on';route.innerHTML='<b>Project controls updated.</b> Recovery routes, usage guardrails, models and loop limits apply to the next provider call.';}
  catch(e){showInlineError('runtime-error',e);syncRuntimeBusy(lastState);}
  finally{if(!lastState||!lastState.progress||lastState.progress.finished)save.disabled=false;}
};

const resolutionModal=document.getElementById('resolution-modal');
const resolutionForm=document.getElementById('resolution-form');
let activeResolution=null;
const promptedEscalations=new Set();
function currentEscalations(d){
  const rows=(d&&d.escalations)||[];
  const direct=rows.filter(row=>(row.chat_id||'history')===activeChatId);
  if(direct.length)return direct;
  const shas=new Set(chatCycles(d).map(row=>row.sha));
  return rows.filter(row=>shas.has(row.sha));
}
function resolutionChoice(action){
  document.getElementById('resolution-action').value=action||'';
  resolutionForm.querySelectorAll('input[name="resolution-choice"]').forEach(input=>input.checked=input.value===action);
  const label=document.getElementById('resolution-reason-label'),reason=document.getElementById('resolution-reason');
  const submit=document.getElementById('submit-resolution'),provider=Boolean(activeResolution&&activeResolution.kind==='provider');
  const guidance=reason.closest('label');guidance.hidden=provider&&action==='reopen';
  reason.required=!(provider&&action==='reopen');
  if(action==='reopen'&&provider){
    label.textContent='Retry note (optional)';
    reason.placeholder='Optional note for the audit ledger.';
    submit.textContent='Retry provider now';
  }else if(action==='reopen'){
    label.textContent='Correction guidance for the next round';
    reason.placeholder='Describe exactly what should change before the next audit.';
    submit.textContent='Record guidance & unlock round';
  }else if(action==='close'){
    label.textContent='Reason for stopping';
    reason.placeholder='Explain why this task should stop without admitting its current output.';
    submit.textContent='Stop without admission';
  }else{
    label.textContent='Your guidance or reason';
    reason.placeholder='Select an action, then explain what CrossAudit should do.';
    submit.textContent='Record human decision';
  }
}
// A stalled cycle (like a hard denial) names its remedies as typed
// RemediationAction values — errors.py, the same vocabulary slice one gave a
// parked run via waiting_reason. The modal decides which remediation
// affordance to show by reading that list, not by re-deriving it from the
// kind; these labels are the A40 contract strings, kept in one place.
const REMEDIATION={
  retry:{label:'Retry provider now'},
  validate_credential:{label:'Review provider connection',panel:'settings'},
  select_model:{label:'Change model or fallback',panel:'runtime'},
  stop:{label:'Stop this task'},
  revise:{label:'Revise and continue'}};
function hasRemediation(row,action){return ((row&&row.remediations)||[]).indexOf(action)>=0;}
function openResolution(value,action='',sha=''){
  let row=typeof value==='object'&&value?value:null;
  if(!row&&lastState)row=(lastState.escalations||[]).find(item=>item.cycle_id===value);
  row=row||{cycle_id:value,short_sha:sha,sha,round:1,max_rounds:lastState&&lastState.max_rounds||3,
    limit_reached:false,why:'The automatic audit loop stopped.',issues:[],attempts:[],
    requested:'Review why the loop stopped, then decide whether to revise or stop.'};
  activeResolution=row;promptedEscalations.add(row.cycle_id);
  document.getElementById('resolution-cycle').value=row.cycle_id||'';
  document.getElementById('resolution-reason').value='';
  const used=Number(row.round||0),maximum=Number(row.max_rounds||(lastState&&lastState.max_rounds)||0);
  const provider=row.kind==='provider';
  document.getElementById('resolution-flag').textContent=provider?'Generator connection stopped':row.limit_reached?'Automatic audit limit reached':'Automatic loop paused';
  document.getElementById('resolution-title').textContent=provider?'The task is waiting for a working Generator connection':'The audit needs your decision';
  document.getElementById('resolution-summary').textContent=provider
    ?'CrossAudit stopped before an audit began. No result was admitted and the original task is ready to retry.'
    :row.limit_reached
    ?'CrossAudit used all '+used+' of '+maximum+' automatic rounds without a passing result. Nothing will continue or be admitted until you decide.'
    :'CrossAudit stopped safely. Nothing will continue or be admitted until you decide.';
  document.getElementById('resolution-limit-title').textContent=provider?'Generator connection stopped':row.limit_reached
    ?'Automatic rounds used: '+used+' / '+maximum:'The automatic loop could not continue safely';
  document.getElementById('resolution-limit-copy').textContent=String(row.stop_reason||row.why||'The audit controller paused this task.');
  const attemptRows=row.attempts||[];
  document.getElementById('resolution-attempts').innerHTML=attemptRows.map(item=>{
    const word=String(item.verdict||'').toLowerCase();
    return '<div class="decision-attempt"><span class="round-n">round '+esc(item.round)+'</span><span>'
      +esc(item.findings)+' issue'+(item.findings===1?'':'s')+'</span><span class="verdict-word '+esc(word)
      +'">'+esc(item.verdict)+'</span></div>';}).join('');
  document.getElementById('resolution-goal').textContent=(lastState?titleOf(lastState):'')||'The task this conversation asked for.';
  const issues=row.issues||[];
  document.getElementById('resolution-issue-count').textContent=String(issues.length);
  document.getElementById('resolution-issues').innerHTML=issues.length?issues.map((issue,index)=>
    '<article class="decision-issue"><div class="decision-issue-head"><span>'+esc(issue.severity||'BLOCKER')+'</span><b>'
    +esc(issue.rule||'Issue '+(index+1))+'</b></div><p>'+esc(issue.observation||'No explanation was recorded.')+'</p>'
    +(issue.artifact?'<small>Affects '+esc(issue.artifact)+'</small>':'')+'</article>').join('')
    :'<div class="decision-empty">'+(provider
      ?'No audit findings were created because the Generator stopped before producing a reviewable result.'
      :'No structured findings were recorded. Review the stop reason above before continuing.')+'</div>';
  document.getElementById('resolution-request').textContent=provider
    ?'Retry the same task now, review the model connection first, or stop this task.'
    :(row.requested||'Choose whether to revise and continue, or stop this task.');
  document.getElementById('resolution-reopen-title').textContent=provider?'Retry provider':'Revise and continue';
  document.getElementById('resolution-reopen-copy').textContent=provider
    ?'Use the current connection and rerun the original task.'
    :'Give the generator specific correction guidance and unlock one additional audited round.';
  document.getElementById('resolution-open-runtime').hidden=!hasRemediation(row,'select_model');
  document.getElementById('resolution-open-settings').hidden=!hasRemediation(row,'validate_credential');
  resolutionChoice(action||'reopen');
  document.getElementById('resolution-error').className='wizard-error';
  resolutionModal.classList.add('on');document.body.classList.add('deciding');
  if(lastState)renderDecisionBanner(lastState);
  setTimeout(()=>{const target=action?document.getElementById('resolution-reason')
    :resolutionForm.querySelector('input[name="resolution-choice"]');if(target)target.focus();},0);
}
function closeResolution(){resolutionModal.classList.remove('on');document.body.classList.remove('deciding');
  resolutionForm.reset();activeResolution=null;resolutionChoice('');
  if(lastState)renderDecisionBanner(lastState);}
resolutionForm.querySelectorAll('input[name="resolution-choice"]').forEach(input=>input.onchange=()=>resolutionChoice(input.value));
document.getElementById('close-resolution').onclick=closeResolution;
document.getElementById('cancel-resolution').onclick=closeResolution;
document.getElementById('resolution-open-runtime').onclick=()=>{closeResolution();openRuntime();};
document.getElementById('resolution-open-settings').onclick=()=>{closeResolution();openSettings('providers');};
resolutionForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('submit-resolution');
  const cycleId=document.getElementById('resolution-cycle').value;
  const action=document.getElementById('resolution-action').value,reason=document.getElementById('resolution-reason').value.trim();
  const provider=Boolean(activeResolution&&activeResolution.kind==='provider');
  if(!action){showInlineError('resolution-error','Choose whether to revise and continue, or stop this task.');return;}
  if(!reason&&!(provider&&action==='reopen')){showInlineError('resolution-error','Add concrete guidance or a reason so the decision is auditable.');return;}
  button.disabled=true;document.getElementById('resolution-error').className='wizard-error';
  try{await api('/api/escalation',{cycle_id:cycleId,action:provider&&action==='reopen'?'retry_provider':action,reason});
    closeResolution();route.className='route on';
    if(provider&&action==='reopen'){
      pendingContinuation={cycle:'',chat:''};
      route.innerHTML='<b>Provider retry started.</b> The original task is running again; live progress will appear here.';
    }else if(action==='reopen'){
      pendingContinuation={cycle:cycleId,chat:activeChatId};
      say.value=reason;route.innerHTML='<b>Another audited attempt is unlocked.</b> Your guidance is in the composer. Review it, then press Run task.';
      setTimeout(()=>say.focus(),0);
    }else route.innerHTML='<b>Task stopped.</b> The current output remains unadmitted and your reason was recorded.';}
  catch(e){showInlineError('resolution-error',e);}finally{button.disabled=false;}};

let projectState=null;
let projectSource=null;
let activeProjectJob=null;
let createdRoot=null;
let repoNameTouched={science:false,audit:false};
let repositoryCheckNonce=0;
let projectStep=1;
const projectModal=document.getElementById('project-modal');
const projectForm=document.getElementById('project-form');
const recoveryModal=document.getElementById('recovery-modal');
const recoveryForm=document.getElementById('recovery-form');
const deleteProjectModal=document.getElementById('delete-project-modal');
const deleteProjectForm=document.getElementById('delete-project-form');
let deleteProjectPreview=null,deleteNeedsGithubAuthorization=false;
const auditorVendor=document.getElementById('auditor-vendor');
const generatorVendor=document.getElementById('generator-vendor');
const auditorConnection=document.getElementById('auditor-connection');
const generatorConnection=document.getElementById('generator-connection');
const auditorEndpoint=document.getElementById('auditor-endpoint');
const generatorEndpoint=document.getElementById('generator-endpoint');
const auditorModel=document.getElementById('auditor-model');
const generatorModel=document.getElementById('generator-model');
const projectType=document.getElementById('project-type');

function modelOptions(vendor,target){
  const previous=target.value;
  const rows=(projectState&&projectState.models&&projectState.models[vendor])||[];
  target.innerHTML=rows.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.id)+' - '+esc(x.hint)+'</option>').join('')
    +'<option value="__custom__">Enter a custom model ID…</option>';
  if([...target.options].some(o=>o.value===previous))target.value=previous;
  syncCustomModel(target.id.startsWith('auditor')?'auditor':'generator');
}
function connectionOptions(vendor,target){
  const previous=target.value;const state=projectState&&projectState.connections&&projectState.connections[vendor]||{};
  const label=state.label||vendor[0].toUpperCase()+vendor.slice(1);
  const rows=[];
  if(vendor==='openai')rows.push({id:'chatgpt',label:'ChatGPT subscription',ready:Boolean(state.chatgpt&&state.chatgpt.connected)});
  rows.push({id:'api',label:label+' API key',ready:Boolean(state.api_key&&state.api_key.configured)});
  const readyRows=rows.filter(x=>x.ready);
  target.innerHTML=(readyRows.length?'':'<option value="" selected disabled>Connect '+esc(vendor)+' in Settings first</option>')
    +rows.map(x=>'<option value="'+x.id+'"'+(x.ready?'':' disabled')+'>'+esc(x.label)+(x.ready?'':' - connect in Settings')+'</option>').join('');
  if([...target.options].some(o=>o.value===previous&&!o.disabled))target.value=previous;
  else{const ready=[...target.options].find(o=>!o.disabled);if(ready)target.value=ready.value;}
}
function endpointOptions(vendor,target){
  const previous=target.value;const rows=(projectState&&projectState.endpoints&&projectState.endpoints[vendor])||[];
  target.innerHTML=rows.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.label)+'</option>').join('');
  if([...target.options].some(o=>o.value===previous))target.value=previous;
  target.closest('.field').hidden=rows.length<2;
}
function syncCustomModel(role){
  const select=role==='auditor'?auditorModel:generatorModel;
  const custom=select.value==='__custom__';
  document.getElementById(role+'-custom-wrap').className='field custom-model'+(custom?'':' off');
  if(custom)document.getElementById(role+'-details').open=true;
}
function syncRoleChoices(){
  const av=auditorVendor.value;const gv=generatorVendor.value;
  [...generatorVendor.options].forEach(o=>o.disabled=o.value===av);
  [...auditorVendor.options].forEach(o=>o.disabled=o.value===gv);
  if(generatorVendor.selectedOptions[0]&&generatorVendor.selectedOptions[0].disabled){
    generatorVendor.value=[...generatorVendor.options].find(o=>!o.disabled).value;
  }
  connectionOptions(auditorVendor.value,auditorConnection);connectionOptions(generatorVendor.value,generatorConnection);
  endpointOptions(auditorVendor.value,auditorEndpoint);endpointOptions(generatorVendor.value,generatorEndpoint);
  modelOptions(auditorVendor.value,auditorModel);modelOptions(generatorVendor.value,generatorModel);
}
function configureProjectForm(){
  if(!projectState)return;
  const vendors=Object.keys(projectState.models||{});
  if(!auditorVendor.options.length){
    const label=v=>(projectState.connections&&projectState.connections[v]&&projectState.connections[v].label)||v;
    auditorVendor.innerHTML=vendors.map(v=>'<option value="'+esc(v)+'">'+esc(label(v))+'</option>').join('');
    generatorVendor.innerHTML=vendors.map(v=>'<option value="'+esc(v)+'">'+esc(label(v))+'</option>').join('');
    auditorVendor.value=vendors.includes('openai')?'openai':vendors[0];
    generatorVendor.value=vendors.includes('anthropic')?'anthropic':vendors.find(v=>v!==auditorVendor.value);
    syncRoleChoices();
  }
  const gh=projectState.github||{};const auth=projectState.github_auth||{};
  const connection=document.getElementById('github-connection');
  if(gh.connected){connection.textContent=gh.detail||'GitHub connected';connection.className='connection ok';}
  else if(auth.status==='running'){
    connection.className='connection';connection.innerHTML='<div class="github-device"><b>'+esc(auth.detail)+'</b>'
      +(auth.code?'<div class="github-device-actions"><span class="device-code">'+esc(auth.code)+'</span>'
        +'<button type="button" class="secondary" data-copy-github="'+esc(auth.code)+'">Copy code</button>'
        +'<a href="'+esc(auth.url)+'" target="_blank" rel="noopener">Open GitHub ↗</a></div>'
        +'<small>Sign in, enter the code, and approve GitHub CLI. This page updates automatically.</small>':'')+'</div>';
  }else{const help=gh.url?'<a class="secondary" href="'+esc(gh.url)+'" target="_blank" rel="noopener">Install GitHub tool ↗</a>':'';
    connection.className='connection bad';connection.innerHTML='<div class="github-connect"><span>'
    +esc(auth.detail||gh.detail||'GitHub is not connected')+'</span>'+(gh.action==='install_github_cli'?help
      :'<button type="button" class="secondary" data-connect-github>Connect GitHub</button>')+'</div>';}
  document.getElementById('github-toggle').disabled=false;
  updateWorkspaceFields(projectState.workspace);syncGithubFields();renderRecoveryGithub();
}
function renderRecoveryGithub(){
  if(!recoveryModal.classList.contains('on')||!projectState)return;
  const gh=projectState.github||{},auth=projectState.github_auth||{};
  const box=document.getElementById('recovery-connection');
  const connect=document.getElementById('recovery-connect-github');
  if(gh.connected){box.textContent=gh.detail||'GitHub connected';box.className='connection ok';connect.hidden=true;}
  else if(auth.status==='running'){
    box.className='connection';box.innerHTML='<div class="github-device"><b>'+esc(auth.detail||'Authorize CrossAudit in GitHub')+'</b>'
      +(auth.code?'<div class="github-device-actions"><span class="device-code">'+esc(auth.code)+'</span>'
        +'<button type="button" class="secondary" data-copy-recovery-github="'+esc(auth.code)+'">Copy code</button>'
        +'<a href="'+esc(auth.url)+'" target="_blank" rel="noopener">Open GitHub ↗</a></div>'
        +'<small>Enter the code in GitHub. This dialog updates automatically after approval.</small>':'')+'</div>';
    connect.hidden=true;
  }else{box.textContent=auth.detail||gh.detail||'GitHub is not connected';box.className='connection bad';
    connect.hidden=false;connect.disabled=false;connect.textContent='Connect GitHub';}
}
function resetRepositoryCheck(){
  repositoryCheckNonce++;const state=document.getElementById('repo-check');
  state.textContent='Names will be checked again before anything is created.';state.className='repo-check';
}
function syncRepoNames(force=false){
  if(!projectState||!projectState.github||!projectState.github.owner)return;
  const name=document.getElementById('project-name').value.trim();
  if(!name)return;
  const owner=projectState.github.owner;
  if(force||!repoNameTouched.science)document.getElementById('science-repo').value=owner+'/'+name;
  if(force||!repoNameTouched.audit)document.getElementById('audit-repo').value=owner+'/'+name+'-audit';
  updateWorkspaceFields(projectState.workspace);resetRepositoryCheck();
}
function syncGithubFields(){
  const on=document.getElementById('github-toggle').checked;
  document.getElementById('github-fields').className='github-fields'+(on?'':' off');
}
function repositoryPayload(){return {name:document.getElementById('project-name').value.trim(),
  science_repo:document.getElementById('science-repo').value.trim(),
  audit_repo:document.getElementById('audit-repo').value.trim(),
  adopt_existing:document.getElementById('adopt-existing').checked};}
async function checkRepositoryNames(showError=true){
  const status=document.getElementById('repo-check');const nonce=++repositoryCheckNonce;
  status.textContent='Checking GitHub…';status.className='repo-check';
  try{const result=await api('/api/github/check',repositoryPayload());if(nonce!==repositoryCheckNonce)return result;
    const existing=(result.repositories||[]).filter(r=>r.exists).map(r=>r.repo);
    if(existing.length){status.textContent=(result.adopt_existing?'Ready to use: ':'Already exists: ')+existing.join(', ');
      status.className='repo-check '+(result.ready?'ok':'warn');}
    else{status.textContent='Both names are available · one click will create both repositories';status.className='repo-check ok';}
    return result;
  }catch(e){if(nonce===repositoryCheckNonce){status.textContent=e.message;status.className='repo-check warn';}
    if(showError)showInlineError('wizard-error',e);throw e;}
}
function syncProjectType(){
  const science=projectType.value==='science';
  document.getElementById('project-contract-hint').textContent=science
    ?'Scientific projects require the visible metadata.yml/results.json, units, convergence, and provenance contract.'
    :'General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.';
}
function guidanceMarkup(row){
  const issue=row&&row.issue;if(!issue)return '';
  const root=row.root||'';let actions='';
  if(issue.action==='connect_github')actions+='<button type="button" class="secondary" data-job-action="connect_github">Connect GitHub</button>';
  if(issue.action==='edit_repositories')actions+='<button type="button" class="secondary" data-job-action="'+(row.recoverable?'edit_repositories':'edit_new_repositories')+'" data-root="'+esc(root)+'">Edit repository names</button>';
  if(issue.action==='review_workspace')actions+='<button type="button" class="secondary" data-job-action="reveal_folder" data-root="'+esc(root)+'">Open folder</button>';
  if(issue.action==='review_workspace'||issue.action==='choose_workspace')actions+='<button type="button" class="secondary" data-job-action="choose_new_workspace">Choose another folder</button>';
  if(issue.retryable&&!row.recoverable)actions+='<button type="button" class="primary" data-job-action="retry_job">Try again</button>';
  if(issue.action==='retry'&&root)actions+='<button type="button" class="secondary" data-job-action="retry" data-root="'+esc(root)+'">Try again</button>';
  if(issue.url)actions+='<a class="secondary" href="'+esc(issue.url)+'" target="_blank" rel="noopener">Open help ↗</a>';
  if(row.status==='failed')actions+='<button type="button" class="secondary" data-job-action="dismiss_job">Dismiss</button>';
  return '<b>'+esc(issue.title||'Setup needs attention')+'</b><p>'+esc(row.detail||'Review the settings and retry.')+'</p>'
    +(actions?'<div class="guidance-actions">'+actions+'</div>':'');
}
function renderProjectJob(jobs){
  const rows=jobs||[];let row=rows.find(j=>j.id===activeProjectJob);
  if(!row){row=rows.filter(j=>j.status==='running'||j.status==='failed')
    .sort((a,b)=>Number(b.finished||b.started||0)-Number(a.finished||a.started||0))[0];
    if(row)activeProjectJob=row.id;}
  const panel=document.getElementById('project-job');
  if(!row){activeProjectJob=null;panel.className='job-panel';return;}
  panel.className='job-panel on '+row.status;
  document.getElementById('job-title').textContent=row.status==='complete'?'Project ready'
    :row.status==='failed'?'Project creation stopped':'Creating '+row.project;
  document.getElementById('job-detail').textContent=row.detail;
  document.getElementById('job-steps').innerHTML=(row.steps||[]).slice(-8).map(s=>
    '<li>'+esc(s.stage)+' - '+esc(s.detail)+'</li>').join('');
  const guidance=document.getElementById('job-guidance');guidance.innerHTML=guidanceMarkup(row);
  guidance.className='job-guidance'+(guidance.innerHTML?' on':'');
  createdRoot=row.result&&row.result.root||null;
  document.getElementById('open-created').hidden=row.status!=='complete';
}
function renderProjects(d){
  projectState=d;const cap=d.capacity||{active:0,limit:'?'};
  document.getElementById('workspace-label').textContent=d.items.length+' project'
    +(d.items.length===1?'':'s')+', '+cap.active+'/'+cap.limit+' active · '+d.workspace;
  const q=document.getElementById('project-search').value.trim().toLowerCase();
  const rows=d.items.filter(p=>!q||(p.name+' '+p.label+' '+p.auditor+' '+p.generator).toLowerCase().includes(q));
  document.getElementById('project-list').innerHTML=rows.length?rows.map(p=>
    '<div class="project-row" role="button" tabindex="0" data-root="'+esc(p.root)+'" data-current="'+(p.current?'1':'0')+'">'
    +'<span><span class="project-name">'+esc(p.name)+(p.current?' · current':'')+'</span>'
    +(p.label!==p.name?'<span class="project-path">'+esc(p.label)+'</span>':'')
    +(p.progress?'<span class="project-live"><span class="project-progress" role="progressbar" aria-label="Live project activity"><i></i></span>'
      +'<span class="project-live-copy">'+esc(p.progress.actor)+' · '+esc(p.progress.step)+'</span>'
      +'<span class="project-live-time">'+p.progress.elapsed+'s</span></span>':'')
    +(p.setup&&p.setup.recoverable?'<span class="project-recovery"><span>'+esc((p.setup.issue&&p.setup.issue.title)||p.setup.detail||'GitHub setup stopped')+'</span>'
      +'<span class="retry-setup" role="button" tabindex="0" data-resume-root="'+esc(p.root)+'">Fix & retry</span></span>':'')
    +(p.interrupted?'<span class="project-interrupted">Interrupted · open to review and run again</span>':'')+'</span>'
    +'<span class="project-models">'+esc(p.generator)+' → '+esc(p.auditor)+'</span>'
    +'<span class="project-stat">'+p.chats+' chats · '+p.cycles+' cycles</span><span class="status '+esc(p.status)+'">'+esc(p.status)+'</span>'
    +(p.paired?'<span class="paired-mark project-tier">GitHub paired</span>':'<span class="project-stat project-tier">Local</span>')
    +'<button type="button" class="project-pin'+(p.pinned?' pinned':'')+'" data-pin-project="'+esc(p.root)+'" '
      +'aria-label="'+(p.pinned?'Unpin':'Pin')+' project" title="'+(p.pinned?'Unpin':'Pin')+' project">'+(p.pinned?'★':'☆')+'</button>'
    +'<button type="button" class="project-delete" data-delete-project="'+esc(p.root)+'" '
      +(p.current?'disabled ':'')+'aria-label="Delete project from CrossAudit" title="'
      +(p.current?'Return to the main Projects window to delete this open project':'Delete project from CrossAudit')+'">⌫</button>'
    +'<span class="project-arrow">›</span></div>').join(''):'<div class="hub-empty">No matching projects.</div>';
  renderProjectJob(d.jobs);configureProjectForm();renderDeleteGithubAuthorization();
}
async function refreshProjects(){try{renderProjects(await api('/api/projects'));}catch(e){
  document.getElementById('project-list').innerHTML='<div class="hub-empty">'+esc(e.message)+'</div>';}}
function startProjectStream(){if(projectSource)return;try{
  projectSource=new EventSource('/api/projects/stream?t='+encodeURIComponent(T));
  projectSource.onmessage=ev=>{try{renderProjects(JSON.parse(ev.data));}catch(e){}};
  projectSource.onerror=()=>{};
}catch(e){}}
function showProjects(){document.body.classList.add('hub-mode');closePanels();refreshProjects();startProjectStream();
  history.replaceState(null,'',location.pathname+'?t='+encodeURIComponent(T)+'#projects');}
function returnToProjects(){try{const target=new URL(window.name);if(target.protocol==='http:'&&target.hostname==='127.0.0.1'
    &&target.hash==='#projects'&&target.origin!==location.origin){window.name='';location.href=target.href;return;}}catch(e){}
  showProjects();}
function hideProjects(){document.body.classList.remove('hub-mode');projectModal.className='project-modal';
  history.replaceState(null,'',location.pathname+'?t='+encodeURIComponent(T));}
async function openProject(root,current){
  if(current){hideProjects();return;}
  try{const r=await api('/api/projects/open',{root});window.name=location.href;location.href=r.url;}catch(e){
    const panel=document.getElementById('project-job');panel.className='job-panel on failed';
    document.getElementById('job-title').textContent='Could not open project';document.getElementById('job-detail').textContent=e.message;}
}
function closeDeleteProject(){deleteProjectModal.className='project-modal';deleteProjectForm.reset();
  deleteProjectPreview=null;deleteNeedsGithubAuthorization=false;
  document.getElementById('delete-project-error').className='wizard-error';}
function renderDeleteGithubAuthorization(){
  const box=document.getElementById('delete-github-authorization');
  const button=document.getElementById('authorize-delete-repositories');
  if(!deleteProjectModal.classList.contains('on')||!deleteNeedsGithubAuthorization){box.textContent='';button.hidden=true;return;}
  const auth=projectState&&projectState.github_auth||{},scopes=auth.scopes||[];
  if(scopes.includes('delete_repo')&&auth.status==='running'){
    button.hidden=true;box.className='connection';box.innerHTML='<div class="github-device"><b>'+esc(auth.detail||'Authorize permanent repository deletion')+'</b>'
      +(auth.code?'<div class="github-device-actions"><span class="device-code">'+esc(auth.code)+'</span>'
      +'<button type="button" class="secondary" data-copy-delete-github="'+esc(auth.code)+'">Copy code</button>'
      +(auth.url?'<a href="'+esc(auth.url)+'" target="_blank" rel="noopener">Open GitHub ↗</a>':'')+'</div>':'')+'</div>';return;
  }
  if(scopes.includes('delete_repo')&&auth.status==='complete'){
    deleteNeedsGithubAuthorization=false;button.hidden=true;box.className='connection ok';
    box.textContent='GitHub deletion authorized. Submit again to delete the selected repositories.';return;
  }
  box.className='connection bad';box.textContent='GitHub requires the delete_repo permission before it can delete a repository.';
  button.hidden=false;button.disabled=false;button.textContent='Authorize GitHub deletion';
}
function syncDeleteProject(){const working=document.getElementById('delete-working-repository').checked;
  const audit=document.getElementById('delete-audit-repository').checked,github=working||audit;
  document.getElementById('delete-github-confirm-wrap').className='field conditional-field'+(github?'':' off');
  const button=document.getElementById('confirm-delete-project');
  button.disabled=!(deleteProjectPreview&&deleteProjectPreview.can_delete);
  button.textContent=github?(currentLocale==='zh'?'移到废纸篓并删除所选 GitHub 仓库':'Move to Trash & delete selected GitHub repositories')
    :(currentLocale==='zh'?'将项目移到废纸篓':'Move project to Trash');}
async function openDeleteProject(root){deleteProjectForm.reset();deleteProjectPreview=null;deleteNeedsGithubAuthorization=false;
  document.getElementById('delete-project-root').value=root;document.getElementById('delete-project-name').textContent='Project';
  document.getElementById('delete-project-path').textContent=root;document.getElementById('delete-project-impact').textContent='Checking project state…';
  document.getElementById('delete-project-error').className='wizard-error';document.getElementById('confirm-delete-project').disabled=true;
  deleteProjectModal.className='project-modal on';
  try{const preview=await api('/api/projects/delete',{action:'preview',root});deleteProjectPreview=preview;
    document.getElementById('delete-project-name').textContent=preview.name;
    document.getElementById('delete-project-path').textContent=preview.root;
    const impact=[];
    impact.push(currentLocale==='zh'?'恢复位置：'+preview.trash:'Recovery location: '+preview.trash);
    if(preview.dirty_count)impact.push(currentLocale==='zh'?preview.dirty_count+' 个未提交改动会一同归档':preview.dirty_count+' uncommitted changes will be archived');
    if(preview.unpushed_commits)impact.push(currentLocale==='zh'?preview.unpushed_commits+' 个未推送提交会一同归档':preview.unpushed_commits+' unpushed commits will be archived');
    if(preview.activity.length)impact.push((currentLocale==='zh'?'目前不能删除：':'Cannot delete now: ')+preview.activity.join('; '));
    document.getElementById('delete-project-impact').textContent=impact.join(' · ');
    const working=preview.working_repository||'',audit=preview.audit_repository||'';
    const workingBox=document.getElementById('delete-working-repository');workingBox.disabled=!working;
    const auditBox=document.getElementById('delete-audit-repository');auditBox.disabled=!audit;
    document.getElementById('delete-working-repository-name').textContent=working
      ?(currentLocale==='zh'?'保留为默认；选择后永久删除：':'Preserved by default; select to permanently delete: ')+working
      :(currentLocale==='zh'?'未检测到工作仓库。':'No working repository detected.');
    document.getElementById('delete-audit-repository-name').textContent=audit
      ?(currentLocale==='zh'?'选择后永久删除：':'Select to permanently delete: ')+audit
      :(currentLocale==='zh'?'未检测到审计仓库。':'No audit repository detected.');
    document.getElementById('delete-project-confirmation').placeholder=preview.name;syncDeleteProject();
  }catch(e){showInlineError('delete-project-error',e);}}
document.getElementById('delete-project-confirmation').oninput=syncDeleteProject;
document.getElementById('delete-github-confirmation').oninput=syncDeleteProject;
document.getElementById('delete-working-repository').onchange=syncDeleteProject;
document.getElementById('delete-audit-repository').onchange=syncDeleteProject;
document.getElementById('delete-github-authorization').onclick=async ev=>{
  const copy=ev.target.closest('[data-copy-delete-github]');if(!copy)return;
  try{await navigator.clipboard.writeText(copy.getAttribute('data-copy-delete-github'));copy.textContent='Copied';}catch(e){}
};
document.getElementById('authorize-delete-repositories').onclick=async()=>{
  const button=document.getElementById('authorize-delete-repositories');button.disabled=true;button.textContent='Starting…';
  try{const result=await api('/api/github/connect',{scope:'delete_repo'});
    if(result.connected){deleteNeedsGithubAuthorization=false;button.hidden=true;
      const box=document.getElementById('delete-github-authorization');box.className='connection ok';box.textContent='GitHub deletion authorized. Submit again.';}
    else renderDeleteGithubAuthorization();}
  catch(e){showInlineError('delete-project-error',e);button.disabled=false;button.textContent='Authorize GitHub deletion';}
};
document.getElementById('close-delete-project').onclick=closeDeleteProject;
document.getElementById('cancel-delete-project').onclick=closeDeleteProject;
deleteProjectModal.addEventListener('click',ev=>{if(ev.target===deleteProjectModal)closeDeleteProject();});
deleteProjectForm.onsubmit=async ev=>{ev.preventDefault();if(!deleteProjectPreview)return;
  const button=document.getElementById('confirm-delete-project');button.disabled=true;button.textContent=currentLocale==='zh'?'正在删除…':'Deleting…';
  try{const result=await api('/api/projects/delete',{action:'delete',root:deleteProjectPreview.root,
      confirmation:document.getElementById('delete-project-confirmation').value,
      delete_working_repo:document.getElementById('delete-working-repository').checked,
      delete_audit_repo:document.getElementById('delete-audit-repository').checked,
      github_confirmation:document.getElementById('delete-github-confirmation').value});
    closeDeleteProject();await refreshProjects();const panel=document.getElementById('project-job');panel.className='job-panel on complete';
    document.getElementById('open-created').hidden=true;
    document.getElementById('job-title').textContent=currentLocale==='zh'?'项目已移到废纸篓':'Project moved to Trash';
    const failed=(result.github||[]).filter(row=>row.status==='failed');
    document.getElementById('job-detail').textContent=(currentLocale==='zh'?'可从以下位置恢复：':'Recover from: ')+result.archive
      +(failed.length?(currentLocale==='zh'?' · GitHub 删除未完全成功：':' · GitHub deletion incomplete: ')+failed.map(row=>row.repo).join(', '):'');
    document.getElementById('job-steps').innerHTML='';document.getElementById('job-guidance').className='job-guidance';
  }catch(e){if(e.action==='authorize_delete'){deleteNeedsGithubAuthorization=true;renderDeleteGithubAuthorization();}
    showInlineError('delete-project-error',e);syncDeleteProject();}};
function projectModelLabel(role){const select=role==='generator'?generatorModel:auditorModel;
  const vendor=role==='generator'?generatorVendor:auditorVendor;const custom=document.getElementById(role+'-custom');
  return (vendor.value||'-')+' · '+(select.value==='__custom__'?(custom.value.trim()||'custom model'):(select.value||'not connected'));}
function syncProjectReview(){const host=document.getElementById('project-review');if(!host)return;
  const github=document.getElementById('github-toggle').checked;
  const labels=currentLocale==='zh'
    ?[['项目',document.getElementById('project-name').value.trim()||'未命名'],['本地文件夹',selectedProjectFolder||'未选择'],
      ['生成者',projectModelLabel('generator')],['审计者',projectModelLabel('auditor')],['GitHub',github?'创建两个仓库':'仅本地']]
    :[['Project',document.getElementById('project-name').value.trim()||'Untitled'],['Local folder',selectedProjectFolder||'Not selected'],
      ['Generator',projectModelLabel('generator')],['Auditor',projectModelLabel('auditor')],['GitHub',github?'Create two repositories':'Local only']];
  host.innerHTML=labels.map(row=>'<div class="project-review-item"><span>'+esc(row[0])+'</span><b title="'+esc(row[1])+'">'+esc(row[1])+'</b></div>').join('');}
function setProjectStep(step,focus=true){projectStep=Math.max(1,Math.min(3,Number(step)||1));
  document.querySelectorAll('[data-project-step]').forEach(section=>section.hidden=Number(section.dataset.projectStep)!==projectStep);
  document.querySelectorAll('[data-project-indicator]').forEach(item=>{const n=Number(item.dataset.projectIndicator);
    item.classList.toggle('active',n===projectStep);item.classList.toggle('complete',n<projectStep);
    if(n===projectStep)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');});
  document.getElementById('project-back').hidden=projectStep===1;document.getElementById('project-next').hidden=projectStep===3;
  document.getElementById('submit-project').hidden=projectStep!==3;
  document.getElementById('project-foot-note').textContent=currentLocale==='zh'
    ?(projectStep===3?'检查确认后才会创建文件夹和仓库。':'完成当前步骤后继续；现在不会创建任何内容。')
    :(projectStep===3?'Nothing is created until you confirm this review.':'Continue after this step; nothing is created yet.');
  if(projectStep===3)syncProjectReview();
  if(focus)requestAnimationFrame(()=>{const pane=document.querySelector('[data-project-step="'+projectStep+'"]');
    (pane.querySelector('input:not([disabled]),select:not([disabled]),textarea:not([disabled]),button:not([disabled])')||pane).focus();});}
function validateProjectStep(step){document.getElementById('wizard-error').className='wizard-error';
  if(step===1&&!selectedProjectFolder){showInlineError('wizard-error',currentLocale==='zh'?'请选择本地项目文件夹。':'Choose a local project folder.');
    document.getElementById('choose-project-workspace').focus();return false;}
  const pane=document.querySelector('[data-project-step="'+step+'"]');const controls=[...pane.querySelectorAll('input,select,textarea')]
    .filter(control=>!control.disabled&&control.type!=='hidden');
  for(const control of controls){if(!control.checkValidity()){control.reportValidity();control.focus();return false;}}
  if(step===2){for(const role of ['generator','auditor']){const select=role==='generator'?generatorModel:auditorModel;
    if(select.value==='__custom__'&&!document.getElementById(role+'-custom').value.trim()){
      showInlineError('wizard-error',currentLocale==='zh'?(role==='generator'?'请输入生成者模型 ID。':'请输入审计者模型 ID。')
        :('Enter the '+role+' model ID.'));document.getElementById(role+'-custom').focus();return false;}}}
  return true;}
function openProjectModal(){projectForm.reset();document.getElementById('wizard-error').className='wizard-error';
  if(settingsState&&settingsState.doctor&&settingsState.doctor.status==='blocked'){
    openSettings('general');doctorMessage('Fix the required Environment Doctor items before creating a project.',true);return;}
  repoNameTouched={science:false,audit:false};selectedProjectFolder='';resetRepositoryCheck();
  configureProjectForm();const vendors=Object.keys((projectState&&projectState.models)||{});
  auditorVendor.value=vendors.includes('openai')?'openai':vendors[0];
  generatorVendor.value=vendors.includes('anthropic')?'anthropic':vendors.find(v=>v!==auditorVendor.value);
  syncRoleChoices();syncProjectType();syncRepoNames(true);updateWorkspaceFields(projectState&&projectState.workspace);
  projectModal.className='project-modal on';setProjectStep(1,false);
  setTimeout(()=>document.getElementById('project-name').focus(),0);}
function closeProjectModal(){projectModal.className='project-modal';setProjectStep(1,false);}

auditorVendor.onchange=()=>{syncRoleChoices();syncProjectReview();};generatorVendor.onchange=()=>{syncRoleChoices();syncProjectReview();};
auditorConnection.onchange=()=>{modelOptions(auditorVendor.value,auditorModel);syncProjectReview();};
generatorConnection.onchange=()=>{modelOptions(generatorVendor.value,generatorModel);syncProjectReview();};
auditorEndpoint.onchange=()=>{modelOptions(auditorVendor.value,auditorModel);syncProjectReview();};
generatorEndpoint.onchange=()=>{modelOptions(generatorVendor.value,generatorModel);syncProjectReview();};
auditorModel.onchange=()=>{syncCustomModel('auditor');syncProjectReview();};generatorModel.onchange=()=>{syncCustomModel('generator');syncProjectReview();};
document.getElementById('auditor-custom').oninput=syncProjectReview;document.getElementById('generator-custom').oninput=syncProjectReview;
document.querySelectorAll('[data-refresh-models]').forEach(button=>button.onclick=async()=>{
  const role=button.getAttribute('data-refresh-models');const vendor=role==='auditor'?auditorVendor.value:generatorVendor.value;
  const method=role==='auditor'?auditorConnection.value:generatorConnection.value;
  const endpoint=role==='auditor'?auditorEndpoint.value:generatorEndpoint.value;
  button.disabled=true;button.textContent='Refreshing…';
  try{const result=await api('/api/models/refresh',{role,vendor,method,endpoint});
    projectState.models[vendor]=result.models.map(id=>({id,hint:'visible to this account'}));
    modelOptions(vendor,role==='auditor'?auditorModel:generatorModel);
    button.textContent='Updated '+new Date(result.refreshed*1000).toLocaleTimeString();}
  catch(e){button.textContent='Refresh failed';const error=document.getElementById('wizard-error');
    error.textContent=e.message;error.className='wizard-error on';}
  finally{button.disabled=false;setTimeout(()=>button.textContent='Refresh from provider',3500);}
});
document.getElementById('project-name').addEventListener('input',()=>{syncRepoNames(false);syncProjectReview();});
document.getElementById('science-repo').addEventListener('input',()=>{repoNameTouched.science=true;resetRepositoryCheck();});
document.getElementById('audit-repo').addEventListener('input',()=>{repoNameTouched.audit=true;resetRepositoryCheck();});
document.getElementById('adopt-existing').onchange=resetRepositoryCheck;
document.getElementById('check-repositories').onclick=()=>checkRepositoryNames(true).catch(()=>{});
document.getElementById('choose-project-workspace').onclick=()=>chooseWorkspace('project');
document.getElementById('max-rounds-choice').onchange=ev=>{
  const n=Number(ev.target.value);document.getElementById('round-limit-help').textContent='Up to '+n
    +' generator → auditor round'+(n===1?'':'s')+', then the task pauses for you. It never auto-passes.';};
projectType.onchange=syncProjectType;
document.getElementById('github-toggle').onchange=()=>{syncGithubFields();syncProjectReview();};
document.getElementById('project-next').onclick=()=>{if(validateProjectStep(projectStep))setProjectStep(projectStep+1);};
document.getElementById('project-back').onclick=()=>setProjectStep(projectStep-1);
document.getElementById('github-connection').onclick=async ev=>{
  const connect=ev.target.closest('[data-connect-github]');const copy=ev.target.closest('[data-copy-github]');
  if(copy){try{await navigator.clipboard.writeText(copy.getAttribute('data-copy-github'));copy.textContent='Copied';}catch(e){}
    return;}
  if(connect){connect.disabled=true;connect.textContent='Connecting…';try{await api('/api/github/connect',{});}
    catch(e){connect.disabled=false;connect.textContent='Connect GitHub';showInlineError('wizard-error',e);}}
};
document.getElementById('create-project').onclick=openProjectModal;
document.getElementById('close-project-modal').onclick=closeProjectModal;
document.getElementById('cancel-project').onclick=closeProjectModal;
document.getElementById('projects-home').onclick=showProjects;
document.getElementById('back-projects').onclick=returnToProjects;
document.getElementById('project-switcher').onclick=showProjects;
document.getElementById('hub-brand').onclick=hideProjects;
document.getElementById('project-search').oninput=()=>projectState&&renderProjects(projectState);
document.getElementById('project-list').onclick=async ev=>{const row=ev.target.closest('[data-root]');
  const pin=ev.target.closest('[data-pin-project]');
  const remove=ev.target.closest('[data-delete-project]');
  const retry=ev.target.closest('[data-resume-root]');
  if(pin){ev.preventDefault();ev.stopPropagation();const root=pin.getAttribute('data-pin-project');
    const project=projectState&&projectState.items.find(p=>p.root===root);if(!project)return;
    pin.disabled=true;try{await api('/api/projects/pin',{root,pinned:!project.pinned});project.pinned=!project.pinned;
      renderProjects(projectState);}catch(e){pin.disabled=false;}return;}
  if(remove){ev.preventDefault();ev.stopPropagation();if(!remove.disabled)openDeleteProject(remove.getAttribute('data-delete-project'));return;}
  if(retry){ev.preventDefault();ev.stopPropagation();openRecovery(retry.getAttribute('data-resume-root'));return;}
  if(row)openProject(row.getAttribute('data-root'),row.getAttribute('data-current')==='1');};
document.getElementById('project-list').onkeydown=ev=>{
  if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-root]')){ev.preventDefault();ev.target.click();}
  if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-resume-root]')){ev.preventDefault();ev.target.click();}}
function openRecovery(root){
  const row=projectState&&projectState.items.find(p=>p.root===root);if(!row||!row.setup)return;
  const issue=row.setup.issue||{};document.getElementById('recovery-root').value=root;
  document.getElementById('recovery-science').value=row.setup.science||row.label||'';
  document.getElementById('recovery-audit').value=row.setup.audit||'';
  const note=document.getElementById('recovery-note');note.innerHTML='<b>'+esc(issue.title||'GitHub setup stopped')+'</b>'
    +esc(row.setup.detail||'Review the repository settings and retry.');
  const help=document.getElementById('recovery-help');help.hidden=!issue.url;if(issue.url)help.href=issue.url;
  document.getElementById('recovery-error').className='wizard-error';recoveryModal.className='project-modal on';
  renderRecoveryGithub();
  setTimeout(()=>document.getElementById('recovery-science').focus(),0);
}
function closeRecovery(){recoveryModal.className='project-modal';recoveryForm.reset();}
async function resumeProject(root,science,audit){
  try{const r=await api('/api/projects/resume',{root,science_repo:science,audit_repo:audit});activeProjectJob=r.job;createdRoot=null;
    closeRecovery();
    renderProjectJob([{id:r.job,status:'running',project:root.split('/').pop(),detail:'Resuming GitHub setup',steps:[]}]);}
  catch(e){const panel=document.getElementById('project-job');panel.className='job-panel on failed';
    document.getElementById('job-title').textContent='Could not resume setup';
    document.getElementById('job-detail').textContent=e.message;document.getElementById('job-steps').innerHTML='';}}
document.getElementById('close-recovery').onclick=closeRecovery;
document.getElementById('cancel-recovery').onclick=closeRecovery;
recoveryModal.addEventListener('click',ev=>{if(ev.target===recoveryModal)closeRecovery();});
document.getElementById('recovery-connect-github').onclick=async()=>{
  const button=document.getElementById('recovery-connect-github');button.disabled=true;button.textContent='Connecting…';
  try{await api('/api/github/connect',{});renderRecoveryGithub();}
  catch(e){button.disabled=false;button.textContent='Connect GitHub';showInlineError('recovery-error',e);}};
document.getElementById('recovery-connection').onclick=async ev=>{
  const copy=ev.target.closest('[data-copy-recovery-github]');if(!copy)return;
  try{await navigator.clipboard.writeText(copy.getAttribute('data-copy-recovery-github'));copy.textContent='Copied';}catch(e){}
};
recoveryForm.onsubmit=ev=>{ev.preventDefault();resumeProject(document.getElementById('recovery-root').value,
  document.getElementById('recovery-science').value.trim(),document.getElementById('recovery-audit').value.trim());};
function restoreProjectDraft(row){
  const draft=row&&row.draft||{};openProjectModal();if(!projectModal.classList.contains('on'))return false;
  const set=(selector,value)=>{const el=document.querySelector(selector);if(el&&value!==undefined&&value!==null)el.value=String(value);};
  set('#project-name',draft.name||row.project);set('[name="description"]',draft.description);
  set('#project-type',draft.project_type);set('#max-rounds-choice',draft.max_rounds);
  if([...auditorVendor.options].some(o=>o.value===draft.auditor_vendor))auditorVendor.value=draft.auditor_vendor;
  if([...generatorVendor.options].some(o=>o.value===draft.generator_vendor))generatorVendor.value=draft.generator_vendor;
  syncRoleChoices();
  const setRole=(role,connection,endpoint,model)=>{const connectionEl=role==='auditor'?auditorConnection:generatorConnection;
    const endpointEl=role==='auditor'?auditorEndpoint:generatorEndpoint,modelEl=role==='auditor'?auditorModel:generatorModel;
    if([...connectionEl.options].some(o=>o.value===connection&&!o.disabled))connectionEl.value=connection;
    if([...endpointEl.options].some(o=>o.value===endpoint))endpointEl.value=endpoint;
    modelOptions(role==='auditor'?auditorVendor.value:generatorVendor.value,modelEl);
    if([...modelEl.options].some(o=>o.value===model))modelEl.value=model;
    else if(model){modelEl.value='__custom__';document.getElementById(role+'-custom').value=model;}
    syncCustomModel(role);};
  setRole('auditor',draft.auditor_connection,draft.auditor_endpoint,draft.auditor_model);
  setRole('generator',draft.generator_connection,draft.generator_endpoint,draft.generator_model);
  document.getElementById('github-toggle').checked=draft.github!==false;
  document.getElementById('adopt-existing').checked=draft.adopt_existing===true;
  document.querySelector('[name="public"]').checked=draft.public===true;
  set('#science-repo',draft.science_repo||row.science);set('#audit-repo',draft.audit_repo||row.audit);
  repoNameTouched={science:Boolean(draft.science_repo),audit:Boolean(draft.audit_repo)};
  selectedProjectFolder=String(draft.workspace||row.workspace||row.root||'');
  updateWorkspaceFields(selectedProjectFolder);syncProjectType();syncGithubFields();syncProjectReview();resetRepositoryCheck();
  return true;
}
document.getElementById('project-job').onclick=async ev=>{const action=ev.target.closest('[data-job-action]');if(!action)return;
  const kind=action.getAttribute('data-job-action'),root=action.getAttribute('data-root');
  const row=(projectState&&projectState.jobs||[]).find(j=>j.id===activeProjectJob);
  if(kind==='connect_github')document.querySelector('[data-connect-github]')?.click();
  else if(kind==='edit_repositories'&&root)openRecovery(root);
  else if(kind==='edit_new_repositories'&&row){restoreProjectDraft(row);setProjectStep(3);}
  else if(kind==='choose_new_workspace'&&row){if(restoreProjectDraft(row))chooseWorkspace('project');}
  else if(kind==='reveal_folder'&&root){if(!revealProjectFolder(root))document.getElementById('job-detail').textContent='Open this folder in Finder, commit or stash its local changes, then choose Try again.';}
  else if(kind==='retry'&&root)openRecovery(root);
  else if(kind==='retry_job'&&row){action.disabled=true;
    try{const result=await api('/api/projects/job',{action:'retry',job_id:row.id});activeProjectJob=result.job;
      renderProjectJob([{id:result.job,status:'running',project:row.project,detail:'Checking the project again',steps:[]}]);}
    catch(e){action.disabled=false;document.getElementById('job-detail').textContent=e.message;}}
  else if(kind==='dismiss_job'&&row){action.disabled=true;
    try{await api('/api/projects/job',{action:'dismiss',job_id:row.id});activeProjectJob=null;renderProjectJob([]);await refreshProjects();}
    catch(e){action.disabled=false;document.getElementById('job-detail').textContent=e.message;}}};
document.getElementById('open-created').onclick=()=>createdRoot&&openProject(createdRoot,false);
projectModal.addEventListener('click',ev=>{if(ev.target===projectModal)closeProjectModal();});
projectForm.onsubmit=async ev=>{ev.preventDefault();if(projectStep<3){if(validateProjectStep(projectStep))setProjectStep(projectStep+1);return;}
  const submit=document.getElementById('submit-project');
  const error=document.getElementById('wizard-error');error.className='wizard-error';submit.disabled=true;
  const fd=new FormData(projectForm);const payload=Object.fromEntries(fd.entries());
  payload.auditor_model=auditorModel.value==='__custom__'?document.getElementById('auditor-custom').value.trim():auditorModel.value;
  payload.generator_model=generatorModel.value==='__custom__'?document.getElementById('generator-custom').value.trim():generatorModel.value;
  payload.github=document.getElementById('github-toggle').checked;payload.public=fd.has('public');
  payload.adopt_existing=document.getElementById('adopt-existing').checked;
  payload.use_selected_folder=true;
  payload.workspace=selectedProjectFolder;
  payload.max_rounds=Number(payload.max_rounds);
  try{if(payload.github){const checked=await checkRepositoryNames(false);if(!checked.ready){
      throw new Error('Choose unused names, or explicitly allow CrossAudit to use the accessible repositories.');}}
    const r=await api('/api/projects/create',payload);activeProjectJob=r.job;createdRoot=null;
    closeProjectModal();renderProjectJob([{id:r.job,status:'running',project:payload.name,
      detail:'Starting local project setup'}]);}
  catch(e){showInlineError('wizard-error',e);}
  submit.disabled=false;};

function activeChat(d){return d&&d.chats&&(d.chats.items||[]).find(row=>row.id===activeChatId)||null;}
function chatCycles(d){return (d.cycles||[]).filter(row=>(row.chat_id||'history')===activeChatId);}
function chatProgress(d){const p=d.progress;return p&&(p.chat_id||'history')===activeChatId?p:null;}
function statusOf(d){
  const p=chatProgress(d),cycles=chatCycles(d);
  if(p && !p.finished) return 'running';
  if(p && p.finished) return p.outcome || 'ready';
  if(cycles.length) return cycles[cycles.length-1].status;
  return 'ready';
}
function titleOf(d){
  const chat=activeChat(d);if(chat)return chat.title;
  const users = [...d.generator_stream,...d.auditor_stream].filter(x => x.kind === 'you'&&(x.chat_id||'history')===activeChatId);
  if(users.length) return users.sort((a,b) => b.t-a.t)[0].utterance.replace(/\s+/g,' ').slice(0,88);
  const p=chatProgress(d);if(p&&p.task)return p.task.replace(/\s+/g,' ').slice(0,88);
  return 'New chat';
}
function fileUrl(path,view=false){return '/api/file?t=' + encodeURIComponent(T) + '&path=' + encodeURIComponent(path)
  +(view?'&view=1':'');}
async function previewData(path){
  const response=await fetch('/api/preview?t='+encodeURIComponent(T)+'&path='+encodeURIComponent(path));
  const raw=await response.text();let data={};try{data=raw?JSON.parse(raw):{};}catch(e){}
  if(!response.ok)throw new Error(data.reason||raw||('Preview failed ('+response.status+')'));
  return data;
}
function formatBytes(value){
  if(value===null||value===undefined) return '';
  const units=['B','KB','MB','GB','TB','PB'];let size=Number(value),unit=0;
  while(size>=1000&&unit<units.length-1){size/=1000;unit++;}
  return (unit===0?String(size):size.toFixed(size<10?1:0))+' '+units[unit];
}
function artifactRecord(item){
  if(typeof item==='string'){
    const name=item.split('/').pop();const extension=(name.includes('.')?name.split('.').pop():'FILE').toUpperCase();
    return {path:item,name,extension,kind:'File',bytes:null,available:true};
  }
  return item;
}
function auditStatus(d,sha){
  if(!d||!sha) return 'generated';
  const cycle=d.cycles.find(c=>c.sha===sha);
  return cycle ? cycle.status.toLowerCase() : 'generated';
}
function outputFile(item,status,context){
  const f=artifactRecord(item);const bits=[context||f.kind,formatBytes(f.bytes)].filter(Boolean);
  const core='<span class="artifact-icon">'+esc((f.extension||'FILE').slice(0,4))+'</span>'
    +'<span class="artifact-copy"><span class="artifact-name">'+esc(f.path)+'</span>'
    +'<span class="artifact-context">'+esc(bits.join(' · '))+'</span></span>';
  if(f.available===false) return '<div class="output-file unavailable"><span class="artifact-main">'+core+'</span>'
    +'<span class="artifact-action" aria-hidden="true">-</span></div>';
  const name=esc(f.name||f.path),path=esc(f.path);
  const primary='<button type="button" class="artifact-main" data-preview="'+path+'" aria-label="Preview '+name+'">'+core+'</button>';
  return '<div class="artifact output-file '+esc(String(status||'').toLowerCase())+'">'+primary+'<span class="artifact-actions">'
    +'<button type="button" class="artifact-action" data-preview="'+path+'" aria-label="Preview '+name+'" title="File preview">⌕</button>'
    +'<a class="artifact-action" href="'+fileUrl(f.path)+'" download aria-label="Download '+name+'" title="Download">↓</a>'
    +'</span></div>';
}

const filePreviewModal=document.getElementById('file-preview-modal');
const filePreviewBody=document.getElementById('file-preview-body');
const filePreviewNote=document.getElementById('file-preview-note');
let filePreviewTrigger=null;
function inlineMarkdown(value){return esc(value).replace(/`([^`]+)`/g,'<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/_([^_]+)_/g,'<em>$1</em>');}
function markdownPreview(value){
  const lines=String(value||'').replace(/\r\n?/g,'\n').split('\n');let html='',code=false,list='';
  const closeList=()=>{if(list){html+='</'+list+'>';list='';}};
  for(const line of lines){
    if(line.startsWith('```')){closeList();html+=code?'</code></pre>':'<pre><code>';code=!code;continue;}
    if(code){html+=esc(line)+'\n';continue;}
    let match=line.match(/^(#{1,4})\s+(.+)$/);if(match){closeList();const level=match[1].length;html+='<h'+level+'>'+inlineMarkdown(match[2])+'</h'+level+'>';continue;}
    match=line.match(/^\s*[-*+]\s+(.+)$/);if(match){if(list!=='ul'){closeList();list='ul';html+='<ul>';}html+='<li>'+inlineMarkdown(match[1])+'</li>';continue;}
    match=line.match(/^\s*\d+[.)]\s+(.+)$/);if(match){if(list!=='ol'){closeList();list='ol';html+='<ol>';}html+='<li>'+inlineMarkdown(match[1])+'</li>';continue;}
    if(line.startsWith('> ')){closeList();html+='<blockquote>'+inlineMarkdown(line.slice(2))+'</blockquote>';continue;}
    closeList();if(/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line))html+='<hr>';
    else if(line.trim())html+='<p>'+inlineMarkdown(line)+'</p>';
  }
  closeList();if(code)html+='</code></pre>';return html;
}
function closeFilePreview(){filePreviewModal.className='project-modal';filePreviewBody.replaceChildren();
  if(filePreviewTrigger){filePreviewTrigger.focus();filePreviewTrigger=null;}}
async function openFilePreview(path,trigger){
  filePreviewTrigger=trigger||document.activeElement;filePreviewModal.className='project-modal on';
  document.getElementById('file-preview-title').textContent=path.split('/').pop()||'File preview';
  document.getElementById('file-preview-meta').textContent='Preparing preview…';
  const download=document.getElementById('file-preview-download');download.href=fileUrl(path);download.setAttribute('download','');
  filePreviewBody.innerHTML='<div class="preview-loading">Loading audited deliverable…</div>';
  filePreviewNote.textContent='The complete file remains available to download.';
  try{
    const data=await previewData(path);document.getElementById('file-preview-meta').textContent=(data.mime||data.kind)+' · '+formatBytes(data.bytes);
    filePreviewBody.replaceChildren();let node;
    if(data.kind==='pdf'){node=document.createElement('iframe');node.className='preview-frame';node.title=data.name;node.src=fileUrl(path,true);}
    else if(data.kind==='image'){node=document.createElement('img');node.className='preview-image';node.alt=data.name;node.src=fileUrl(path,true);}
    else if(data.kind==='html'){node=document.createElement('iframe');node.className='preview-frame';node.title=data.name;
      node.setAttribute('sandbox','');node.srcdoc='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:"><style>body{font:15px/1.6 system-ui,sans-serif;margin:32px;color:#202124}img{max-width:100%}pre{white-space:pre-wrap}</style>'+data.text;
      filePreviewNote.textContent='HTML preview is isolated from the app and cannot access the network.';}
    else if(data.kind==='markdown'){node=document.createElement('article');node.className='preview-markdown';node.innerHTML=markdownPreview(data.text);}
    else if(data.kind==='document'){node=document.createElement('article');node.className='preview-document';node.textContent=data.text;
      filePreviewNote.textContent='Preview is reconstructed from the final audited DOCX binary.';}
    else if(data.kind==='text'){node=document.createElement('pre');node.className='preview-code';node.textContent=data.text;}
    else{node=document.createElement('div');node.className='preview-unavailable';node.textContent='Preview unavailable for this file type. Download the complete file to open it in a compatible app.';}
    filePreviewBody.appendChild(node);if(data.truncated)filePreviewNote.textContent='The reading preview is shortened for responsiveness; the download is complete.';
  }catch(error){filePreviewBody.innerHTML='<div class="preview-unavailable">'+esc(error.message)+'</div>';}
}
document.getElementById('close-file-preview').onclick=closeFilePreview;
filePreviewModal.addEventListener('click',event=>{if(event.target===filePreviewModal)closeFilePreview();});
document.addEventListener('click',event=>{const button=event.target.closest('[data-preview]');if(button){event.preventDefault();openFilePreview(button.getAttribute('data-preview'),button);}});
function artifactList(items,status,sha){
  if(!items||!items.length) return '';
  const rows=items.map(f=>outputFile(f,status,'')).join('');
  const head='<div class="output-head">Files produced<span class="output-count">'+items.length+'</span></div>';
  if(items.length<=2) return '<section class="output-files" aria-label="Generated files">'+head
    +'<div class="artifact-list">'+rows+'</div></section>';
  const key=esc(String(sha||'')+':'+items.length);
  const open=expandedGroups.has(String(sha||'')+':'+items.length);
  const first=artifactRecord(items[0]);
  return '<section class="output-files" aria-label="Generated files">'+head
    +'<div class="deliverable-group'+(open?' open':'')+'"><button type="button" class="group-head" data-group-toggle="'+key+'" aria-expanded="'+(open?'true':'false')+'">'
    +'<span class="deliverable-icon" aria-hidden="true"></span><span class="group-title"><b>'+items.length+' files</b>'
    +'<span>'+esc(first.name||first.path)+' +'+(items.length-1)+'</span></span>'
    +'<span class="group-chevron" aria-hidden="true"></span></button>'
    +'<div class="group-detail"><div class="group-detail-inner">'+rows
    +'<button type="button" class="output-more" data-open-artifacts>Open Files panel</button>'
    +'</div></div></div></section>';
}
function turn(m,d){
  if(m.kind === 'you'){
    const explicit=m.routing_mode==='explicit';const recipient=m.addressed_to||m.lane;
    const delivery=explicit?'@ '+recipient:recipient==='auditor'?'To Auditor':'To Generator';
    return '<article class="turn user"><div class="turn-main">'
    + '<div class="turn-meta"><b>You</b><span class="direct-mark">' + esc(delivery) + '</span>'
    + '<span class="turn-time">' + at(m.t) + '</span></div>'
    + '<div class="turn-body">' + esc(m.utterance) + '</div></div></article>';
  }
  if(m.kind === 'auditor_chat') return '<article class="turn audit"><div class="turn-main">'
    +'<div class="turn-meta"><span class="role-mark auditor" aria-hidden="true">A</span><b>Auditor</b><span>direct reply · no project files shared</span>'
    +'<span class="turn-time">'+at(m.t)+'</span></div><div class="turn-body">'+esc(m.response)+'</div></div></article>';
  if(m.kind === 'auditor'){
    const fs = (m.findings||[]).map(f => '<div class="finding"><div class="finding-head">'
      + '<span class="severity">' + esc(f.severity) + '</span><span>' + esc(f.rule) + '</span>'
      + '<span class="spacer"></span><span>' + esc(f.artifact) + '</span></div><p>'
      + esc(f.observation) + '</p></div>').join('');
    return '<article class="turn audit"><div class="turn-main">'
      + '<div class="turn-meta"><span class="role-mark auditor" aria-hidden="true">A</span><b>Auditor</b><span class="status ' + esc(m.verdict) + '">'
      + esc(m.verdict) + '</span><span class="turn-time">' + at(m.t) + '</span></div>'
      + (fs || '<div class="turn-body">No findings. The audited increment passed.</div>')
      + '</div></article>';
  }
  return '<article class="turn"><div class="turn-main">'
    + '<div class="turn-meta"><span class="role-mark generator" aria-hidden="true">G</span><b>Generator</b>' + (m.round ? '<span>round ' + m.round + '</span>' : '')
    + '<span class="turn-time">' + at(m.t) + '</span></div><div class="turn-body">'
    + esc(m.summary) + '</div>' + artifactList(m.artifacts||m.files,auditStatus(d,m.sha),m.sha) + '</div></article>';
}
function modelTag(value){const raw=String(value||'');if(!raw)return '';
  const tail=raw.split(':').pop()||raw;
  return (tail.split(' · ')[0]||'').trim()||raw;}
function userState(d){
  const p=chatProgress(d);
  if(p&&p.state==='PROVIDER_UNAVAILABLE'){
    // The run-side signal itself carries the ask: a parked run with a
    // waiting reason needs a person even when no cycle escalation could be
    // recorded (fail-closed verdict protection can refuse the decision
    // object). Rulings settle the run (waiting run is cancelled on close),
    // so a stale "decide" cannot outlive its decision.
    if(currentEscalations(d).length||p.waiting_reason)return {key:'decide',label:STATE_LABELS.decide,live:false};
    // Nothing pending and no waiting reason: fall through to the ledger
    // status instead of demanding a decision with no decision object.
  }
  if(p&&!p.finished){
    if(p.state==='CANCELLING')return {key:'work',label:'Stopping',live:true};
    const key=USER_STATES[p.state]||'work';
    return {key,label:STATE_LABELS[key],live:!['done','decide'].includes(key)};
  }
  const status=String(statusOf(d)).toLowerCase();
  if(status==='passed'||status==='consumed')return {key:'done',label:STATE_LABELS.done,live:false};
  if(status==='escalated')return {key:'decide',label:STATE_LABELS.decide,live:false};
  return null;
}
function setStatePill(d){
  const pill=document.getElementById('thread-status');
  const glyph=pill.querySelector('.pill-glyph'),label=pill.querySelector('.pill-label');
  const detail=pill.querySelector('.pill-detail');
  const s=newTaskMode?null:userState(d);
  const key=s?s.key:'';
  pill.className='state-pill'+(key?' pill-'+key:'')+(s&&s.live?' pill-live':'');
  glyph.hidden=!key;
  label.textContent=s?s.label:'Ready';
  const p=chatProgress(d);
  const rounds=p&&p.steps?p.steps.filter(step=>step.kind==='round_started'):[];
  const roundEvent=rounds.length?rounds[rounds.length-1]:null;
  const heartbeatAge=p&&p.heartbeat_at?Math.max(0,Math.floor(Date.now()/1000-p.heartbeat_at)):null;
  const lastStep=p&&p.steps&&p.steps.length?p.steps[p.steps.length-1]:null;
  if(p&&p.state==='PROVIDER_UNAVAILABLE'){detail.hidden=false;
    detail.textContent='Waiting for provider'+(heartbeatAge===null?'':' · heartbeat '+heartbeatAge+'s ago');}
  else if(lastStep&&lastStep.kind==='run_stalled'&&heartbeatAge!==null&&s&&s.live){
    detail.hidden=false;detail.textContent='last heartbeat '+heartbeatAge+'s ago';}
  else if(roundEvent&&s&&s.live){detail.hidden=false;
    detail.textContent='round '+roundEvent.round_no+'/'+roundEvent.round_limit;}
  else{detail.hidden=true;detail.textContent='';}
  if(key!==lastPillKey){
    if(lastPillKey==='work'&&key==='check'){handoffDirection='check';handoffAt=Date.now();}
    else if(lastPillKey==='check'&&key==='revise'){handoffDirection='revise';handoffAt=Date.now();}
    lastPillKey=key;
    glyph.classList.remove('pill-swap');label.classList.remove('pill-swap');
    void pill.offsetWidth;
    glyph.classList.add('pill-swap');label.classList.add('pill-swap');
  }
}
function reviewCard(d){
  const cycles=chatCycles(d);if(!cycles.length)return '';
  const cycle=cycles[cycles.length-1];
  const status=String(cycle.status||'').toLowerCase();
  if(!['passed','consumed','blocked','escalated'].includes(status))return '';
  const p=chatProgress(d);if(p&&!p.finished)return '';
  const reports=d.auditor_stream.filter(m=>m.kind==='auditor'&&(m.chat_id||'history')===activeChatId);
  const related=reports.filter(m=>m.sha&&cycle.sha&&(String(cycle.sha).startsWith(String(m.sha))||String(m.sha).startsWith(String(cycle.sha))));
  const rows=(related.length?related:reports.slice(-Number(cycle.round||1))).slice(-8);
  const passed=status==='passed'||status==='consumed';
  const open=expandedReviews.has(cycle.id);
  const checks=Object.keys(d.check_contracts||{});
  const roundLines=(rows.length?rows.map(m=>{
    const count=(m.findings||[]).length;
    return '<div class="review-round-row"><span class="round-n">Round '+esc(m.round)+'/'+esc(d.max_rounds)
      +'</span> · <span>'+(count?count+' finding'+(count===1?'':'s'):esc(m.verdict||'PASS'))
      +'</span></div>';}):['<div class="review-round-row"><span class="round-n">Round '
      +esc(cycle.round)+'/'+esc(d.max_rounds)+'</span></div>']).join('');
  const checkLines=passed
    ?'<ul class="review-checks"><li>Independent auditor approved the result</li>'
      +(checks.length?'<li>'+checks.length+' deterministic check'+(checks.length===1?'':'s')+' passed</li>':'<li>No blocking findings</li>')
      +'<li>Recorded in the audit ledger</li></ul>'
    :'';
  const findingRows=rows.filter(m=>(m.findings||[]).length).map(m=>
    '<div class="review-round-row"><span class="round-n">round '+esc(m.round)+'</span></div>'
    +(m.findings||[]).map(f=>'<div class="finding"><div class="finding-head">'
      +'<span class="severity">'+esc(f.severity)+'</span><span>'+esc(f.rule)+'</span>'
      +'<span class="spacer"></span><span>'+esc(f.artifact)+'</span></div><p>'
      +esc(f.observation)+'</p></div>').join('')).join('');
  const detail='<div class="review-detail"><div class="review-detail-inner">'
    +'<div class="review-section"><div class="review-section-title">Deterministic checks</div>'
    +(checks.length?checks.map(name=>'<div class="contract">✓ '+esc(name)+'</div>').join(''):'<div class="empty">No checks configured</div>')
    +'<div class="review-rounds">'+esc(d.rules)+' blocker rules</div></div>'
    +(findingRows?'<div class="review-section"><div class="review-section-title">Findings</div>'+findingRows+'</div>':'')
    +'<div class="review-section"><div class="review-section-title">Record</div><div class="review-record">'
    +'<div class="review-record-row"><span>Commit</span><code>'+esc(String(cycle.sha||'').slice(0,12))+'</code></div>'
    +'<div class="review-record-row"><span>Cycle</span><code>'+esc(cycle.id)+'</code></div>'
    +'<div class="review-record-row"><span>Generator</span><code>'+esc(d.generator)+'</code></div>'
    +'<div class="review-record-row"><span>Auditor</span><code>'+esc(d.auditor)+'</code></div>'
    +'</div></div></div></div>';
  const actionRow=status==='passed'
    ?'<button type="button" class="review-action" data-admit data-admit-cycle="'+esc(cycle.id)+'">Admit result</button>'
    :status==='escalated'
    ?'<button type="button" class="review-action" data-open-decisions>Review issues & decide</button>'
    :'<button type="button" class="review-action" data-open-audits>View audit details</button>';
  return '<section class="review-card'+(open?' open':'')+'" aria-label="Independent review">'
    +'<button type="button" class="review-summary" data-review-toggle="'+esc(cycle.id)+'" aria-expanded="'+(open?'true':'false')+'">'
    +'<div class="review-top"><span class="review-mark" aria-hidden="true"></span><b>Independent review</b>'
    +'<span class="status '+esc(cycle.status)+'">'+esc(cycle.status)+'</span><span class="review-chevron" aria-hidden="true"></span></div>'
    +checkLines
    +'<div class="review-rounds">'+roundLines+'</div>'
    +'</button>'+detail
    +'<div class="review-actions">'+actionRow+'</div></section>';
}
function runCard(d){
  const p = chatProgress(d),cycles=chatCycles(d);
  const latestCycle=cycles.length?cycles[cycles.length-1]:null;
  const ownsPipeline=p||(latestCycle&&d.cycles.length&&latestCycle.sha===d.cycles[d.cycles.length-1].sha);
  const pipeline=ownsPipeline?d.pipeline:[];
  const show = p || pipeline.some(s => s.state !== 'pending');
  if(!show) return '';
  const rawOutcome = p ? (p.finished ? p.outcome : 'running') : statusOf(d);
  const outcome = rawOutcome==='provider_unavailable' ? 'escalated' : rawOutcome;
  const tone = String(outcome||'ready').toLowerCase();
  const handoff = (Date.now()-handoffAt<700&&handoffDirection)?' data-handoff="'+esc(handoffDirection)+'"':'';
  const reached = pipeline.filter(s => s.state !== 'pending').length;
  const meter = pipeline.length ? Math.round(reached / pipeline.length * 100) : 0;
  const roundEvents = p && p.steps ? p.steps.filter(s => s.kind === 'round_started') : [];
  const roundEvent = roundEvents.length ? roundEvents[roundEvents.length-1] : null;
  const round = roundEvent ? roundEvent.round_no : latestCycle ? latestCycle.round : '-';
  const roundLimit = roundEvent&&roundEvent.round_limit ? roundEvent.round_limit : d.max_rounds;
  const focus = pipeline.find(s => s.state === 'current') || pipeline.find(s => s.state === 'failed')
    || pipeline.find(s => s.state === 'pending') || pipeline[pipeline.length-1];
  const focusLabel = focus.state === 'current' ? 'Current gate' : focus.state === 'failed' ? 'Stopped at'
    : focus.state === 'pending' ? 'Next gate' : 'Completed gate';
  const stateNames = {done:'Complete',failed:'Blocked',current:'Active',pending:'Pending'};
  const actorNames = {generator:'Generator',auditor:'Auditor',compute:'Remote compute',tool:'MCP tool',loop:'Controller',done:'Result'};
  const actorMarks = {generator:'G',auditor:'A',compute:'H',tool:'M',loop:'↻',done:'✓'};
  const eventRows = p && p.steps ? p.steps.slice(-12).map(s => '<div class="audit-event">'
    + '<span class="event-mark ' + esc(s.actor) + '">' + esc(actorMarks[s.actor]||'·') + '</span>'
    + '<div class="event-main"><div class="event-line"><b>' + esc(actorNames[s.actor]||s.actor)
    + '</b><span>' + esc(s.text) + '</span></div>'
    + (s.detail ? '<div class="event-detail">' + esc(s.detail) + '</div>' : '') + '</div>'
    + '<time class="event-time">' + at(s.t) + '</time></div>').join('') : '';
  const activityTitle = p && !p.finished ? 'Live activity' : 'Run activity';
  const activity = eventRows || '<div class="activity-empty">Live generator and auditor events appear here while '
    + 'a task runs. The gate states above are reconstructed from the Git ledger.</div>';
  const task = p && p.task ? p.task : titleOf(d);
  return '<section class="run-card ' + esc(tone) + '"' + handoff + ' aria-label="Audit loop">'
    + '<div class="run-overview"><div class="run-top">'
    + '<span class="run-eyebrow">Audit loop</span><span class="status ' + esc(outcome) + '">'
    + esc(outcome) + '</span></div><div class="run-task">' + esc(task) + '</div><div class="run-meta">'
    + '<span>Round <strong>' + esc(round) + '</strong> of ' + esc(roundLimit) + '</span>'
    + '<span><strong>' + reached + '</strong> of ' + pipeline.length + ' gates reached</span>'
    + '<span>' + (p ? p.elapsed + 's elapsed' : 'Ledger snapshot') + '</span></div>'
    + '<div class="run-handoff" aria-hidden="true"><i></i></div>'
    + '<div class="run-meter" role="progressbar" aria-label="Audit gates reached" aria-valuemin="0" '
    + 'aria-valuemax="100" aria-valuenow="' + meter + '"><i style="width:' + meter + '%"></i></div></div>'
    + '<div class="loop">' + pipeline.map((s,i) => '<div class="loop-step ' + esc(s.state) + '" '
      + 'aria-label="' + esc(s.title + ': ' + stateNames[s.state]) + '"><div class="loop-track">'
      + '<div class="loop-mark">' + esc(MARK[s.state] || String(i+1)) + '</div></div>'
      + '<div class="loop-name">' + esc(s.title) + '</div>'
      + '<div class="loop-detail" title="' + esc(s.detail) + '">' + esc(s.detail) + '</div>'
      + '<div class="loop-state">' + esc(stateNames[s.state]) + '</div></div>').join('') + '</div>'
    + '<div class="loop-focus ' + esc(focus.state) + '"><div class="loop-focus-label">' + focusLabel + '</div>'
    + '<div class="loop-focus-copy"><b>' + esc(focus.title) + '</b><p>' + esc(focus.detail) + '</p></div></div>'
    + '<div class="activity"><div class="activity-head">' + activityTitle + '<span>'
    + (p && p.steps ? p.steps.length + ' event' + (p.steps.length===1?'':'s') : 'Ledger-backed state')
    + '</span></div><div class="activity-list">' + activity + '</div></div></section>';
}
function welcome(){
  return '<div class="welcome"><div class="welcome-mark">◇</div><h2>What should CrossAudit work on?</h2>'
    + '<p>Describe what you need or add files. CrossAudit will do the work and independently check the result before showing it here.</p></div>';
}
function allMessages(d){
  // Tasks is direct user input/output, never a raw audit log. Draft generator
  // rounds remain ledger evidence but do not become downloadable deliverables.
  const rows = [...d.generator_stream,...d.auditor_stream].filter(m=>{
    if((m.chat_id||'history')!==activeChatId)return false;
    if(m.kind==='auditor') return false;
    if(m.kind!=='generator') return true;
    return ['passed','consumed'].includes(auditStatus(d,m.sha));
  });
  const seen = new Set();
  return rows.filter(m => {const key = [m.kind,m.t,m.utterance||m.summary||m.verdict].join('|');
    if(seen.has(key)) return false;seen.add(key);return true;}).sort((a,b) => a.t-b.t);
}
function deliveryStatus(d){
  const p=chatProgress(d),cycles=chatCycles(d),cycle=cycles.length?cycles[cycles.length-1]:null;
  const raw=p&&!p.finished?'running':p&&p.finished?p.outcome:cycle?cycle.status.toLowerCase():'';
  if(!raw)return'';const status=String(raw).toLowerCase();
  const escalation=status==='escalated'?currentEscalations(d).slice(-1)[0]:null;
  const copy=status==='running'?['Working','The result will appear here when it is ready.']
    :status==='passed'||status==='consumed'?['Ready','The delivered files passed the independent review.']
    :status==='blocked'?['Needs revision','The result did not pass review yet.']
    :status==='open'?['Ready for your correction','Send the approved guidance to start the human-authorized audited attempt.']
    :status==='escalated'&&escalation&&escalation.limit_reached?['Automatic audit limit reached',
      'CrossAudit paused after '+escalation.round+' of '+escalation.max_rounds+' rounds with '+(escalation.issues||[]).length+' issue'+((escalation.issues||[]).length===1?'':'s')+' remaining.']
    :status==='escalated'||status==='provider_unavailable'?['Needs your input','CrossAudit needs a decision before it can continue.']
    :['Stopped','The task did not complete.'];
  const action=status==='passed'?'<button type="button" data-admit data-admit-cycle="'+esc(cycle.id)+'">Admit result</button>'
    :status==='escalated'||status==='provider_unavailable'?'<button type="button" data-open-decisions>Review issues & decide</button>'
    :status==='open'?''
    :'<button type="button" data-open-audits>View audit details</button>';
  return '<div class="delivery-status '+esc(status)+'"><span class="delivery-dot"></span><span><b>'
    +copy[0]+'</b></span><span>'+copy[1]+'</span>'+action+'</div>';
}
function artifactRows(d){
  const files = new Map();
  d.generator_stream.filter(m => m.kind === 'generator'&&(m.chat_id||'history')===activeChatId).forEach(m => (m.artifacts||m.files||[]).forEach(item => {
    const status=auditStatus(d,m.sha);if(!['passed','consumed'].includes(status))return;
    const artifact=artifactRecord(item);files.set(artifact.path,{artifact,t:m.t,round:m.round,summary:m.summary,status});
  }));
  return [...files.values()].sort((a,b) => b.t-a.t);
}
function artifactsView(d){
  const files = artifactRows(d);
  const cards = files.map(f => outputFile(f.artifact,f.status,f.round?'round '+f.round:f.artifact.kind)).join('');
  return '<div class="view-heading"><h2>Delivered files</h2><p>Only final files that passed independent review.</p></div>'
    + (cards ? '<div class="artifact-grid">' + cards + '</div>'
      : '<div class="empty">No audited deliverables yet.</div>');
}
function auditsView(d){
  const audits = d.auditor_stream.filter(m => m.kind === 'auditor'&&(m.chat_id||'history')===activeChatId);
  return '<div class="view-heading"><h2>Audits</h2><p>Independent verdicts and findings reconstructed from the ledger.</p></div>'
    + runCard(d) + (audits.length ? '<div class="audit-evidence-head"><h3>Audit evidence</h3><span>'
      + audits.length + ' report' + (audits.length===1?'':'s') + '</span></div>'
      + audits.map(m=>turn(m,d)).join('') : '<div class="empty">No audit evidence yet.</div>');
}
function formatTokens(value){
  const n=Number(value||0);if(n>=1000000)return (n/1000000).toFixed(n>=10000000?0:1)+'M';
  if(n>=1000)return (n/1000).toFixed(n>=10000?0:1)+'K';return Math.round(n).toLocaleString();
}
function formatUsd(value){
  if(value===null||value===undefined)return '-';const n=Number(value||0);
  if(n===0)return '$0.00';if(n<0.01)return '$'+n.toFixed(4);return '$'+n.toFixed(2);
}
function usageQuality(row){
  if(row.unpriced_calls)return ['Unpriced','unpriced'];
  if(row.estimated_calls)return ['Estimated','estimated'];return ['Reported',''];
}
function usageView(d){
  const u=d.usage||{};const today=u.today||{};const month=u.month||{},guard=u.budget||{};
  const days=u.days||[];const peak=Math.max(1,...days.map(day=>Number(day.tokens||0)));
  const dayBars=days.map(day=>{const date=new Date(day.date+'T00:00:00');
    return '<div class="usage-day"><span class="usage-day-value">'+formatTokens(day.tokens)+'</span>'
      +'<span class="usage-bar-track"><i class="usage-bar" style="height:'
      +Math.max(day.tokens?4:0,Math.round(Number(day.tokens||0)*100*Math.pow(peak,-1)))+'%"></i></span>'
      +'<span class="usage-day-label">'+esc(date.toLocaleDateString([],{weekday:'short'}))+'</span></div>';}).join('');
  const roles=u.roles||[];const roleMax=Math.max(1,...roles.map(row=>Number(row.tokens||0)));
  const roleRows=roles.map(row=>'<div class="usage-role '+esc(row.role)+'"><div class="usage-role-top"><b>'
    +esc(row.role)+'</b><span>'+formatTokens(row.tokens)+' tokens</span></div><div class="usage-role-meter"><i style="width:'
    +Math.round(Number(row.tokens||0)*100*Math.pow(roleMax,-1))+'%"></i></div><small>'+row.calls+' call'+(row.calls===1?'':'s')
    +' · '+formatUsd(row.api_value_usd)+' API value</small></div>').join('');
  const models=(u.models||[]).map(row=>{const q=usageQuality(row);return '<div class="usage-row"><div class="usage-model"><b>'
    +esc(row.model)+'</b><small>'+esc(row.role)+' · '+esc(row.provider)+'</small></div><span>'+formatTokens(row.tokens)
    +'</span><span>'+formatTokens(Number(row.cache_read||0)+Number(row.cache_write||0))+'</span><span>'
    +formatUsd(row.api_value_usd)+'</span><span class="usage-quality '+q[1]+'">'+q[0]+'</span></div>';}).join('');
  const recent=(u.recent||[]).map(row=>'<div class="usage-call"><span class="usage-call-mark '+esc(row.role)+'">'
    +(row.role==='auditor'?'A':'G')+'</span><div class="usage-call-main"><b>'+esc(row.model)+'</b><span>'
    +esc(row.role)+' · '+esc(row.phase)+', '+formatTokens(row.input)+' in / '+formatTokens(row.output)+' out</span></div>'
    +'<div class="usage-call-value"><b>'+formatTokens(row.tokens)+'</b><span>'
    +(row.api_value_usd===null?'unpriced':formatUsd(row.api_value_usd))+' · '
    +esc(new Date(row.t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))+'</span></div></div>').join('');
  const guardrail=guard.state&&guard.state!=='unconfigured'?'<div class="usage-note"><span>'+(guard.blocked?'!':'◉')+'</span><div><b>Usage guardrail · '+esc(guard.state)+'</b><br>'
    +esc([...(guard.reasons||[]),...(guard.warnings||[])].join(' ')||'Usage is below the configured thresholds.')+'</div></div>':'';
  return '<div class="view-heading"><h2>Token usage</h2><p>Project-level model consumption, updated with every completion.</p></div>'
    +'<div class="usage-note"><span>ⓘ</span><div><b>Local metering · '+esc(u.cost_label||'API-value estimate')+'</b><br>'
    +'Token counts come from the provider runtime when available. Costs use the '+esc(u.price_snapshot||'current')
    +' public API price snapshot and are not a provider invoice or subscription charge.</div></div>'+guardrail
    +'<div class="usage-cards"><div class="usage-card"><div class="usage-card-label">Today</div><div class="usage-card-value">'
    +formatTokens(today.tokens)+'</div><div class="usage-card-detail">'+formatUsd(today.api_value_usd)+' API value</div></div>'
    +'<div class="usage-card"><div class="usage-card-label">This month</div><div class="usage-card-value">'
    +formatTokens(month.tokens)+'</div><div class="usage-card-detail">'+formatUsd(month.api_value_usd)+' API value</div></div>'
    +'<div class="usage-card"><div class="usage-card-label">Model calls</div><div class="usage-card-value">'
    +(month.calls||0)+'</div><div class="usage-card-detail">'+(month.reported_calls||0)+' provider-reported</div></div>'
    +'<div class="usage-card"><div class="usage-card-label">Cached tokens</div><div class="usage-card-value">'
    +formatTokens(Number(month.cache_read||0)+Number(month.cache_write||0))+'</div><div class="usage-card-detail">read + write this month</div></div></div>'
    +'<section class="usage-section"><div class="usage-section-head"><h3>Last 7 days</h3><span>all roles</span></div><div class="usage-bars">'
    +dayBars+'</div></section><section class="usage-section"><div class="usage-section-head"><h3>By role</h3><span>this month</span></div>'
    +(roleRows?'<div class="usage-roles">'+roleRows+'</div>':'<div class="empty">No model calls this month.</div>')+'</section>'
    +'<section class="usage-section"><div class="usage-section-head"><h3>Models</h3><span>this month</span></div>'
    +(models?'<div class="usage-table"><div class="usage-row head"><span>Model</span><span>Tokens</span><span>Cached</span><span>≈ value</span><span>Source</span></div>'
      +models+'</div>':'<div class="empty">Usage will appear after the first model completion.</div>')+'</section>'
    +'<section class="usage-section"><div class="usage-section-head"><h3>Recent calls</h3><span>counts only · no prompt content</span></div>'
    +(recent?'<div class="usage-recent">'+recent+'</div>':'<div class="empty">No calls recorded yet.</div>')+'</section>';
}
const computePanels=new Map();
function computeFileUrl(job,path){return '/api/hpc/file?t='+encodeURIComponent(T)+'&job='
  +encodeURIComponent(job)+'&path='+encodeURIComponent(path);}
function computeView(d){
  const c=d.compute||{hosts:[],jobs:[],aliases:[],active:0,ssh_available:false};
  const hosts=(c.hosts||[]).map(host=>{const probe=host.probe||{};const resources=[];
    if(probe.cpus)resources.push(probe.cpus+' CPU');if(probe.memory_kb)resources.push(formatBytes(probe.memory_kb*1000));
    if((probe.gpus||[]).length)resources.push(probe.gpus.length+' GPU');if((probe.partitions||[]).length)resources.push(probe.partitions.join(', '));
    const agent=host.agent_policy||{};if(agent.enabled)resources.push('Generator tool · '+agent.max_jobs_per_task+' jobs/task · '+agent.max_cpus+' CPU · '+agent.max_gpus+' GPU');
    return '<div class="host-row"><div class="host-top"><b>'+esc(host.alias)+'</b>'
      +'<span class="host-kind">'+esc(probe.scheduler||'workstation')+'</span></div><div class="host-detail">'
      +esc((host.user?host.user+'@':'')+host.hostname+':'+host.port+(host.proxy_jump?' · ProxyJump':'')+' · '+host.scratch)
      +'</div><div class="host-resources">'+resources.map(v=>'<span class="host-resource">'+esc(v)+'</span>').join('')
      +'</div><div class="host-actions"><button type="button" class="secondary" data-hpc-probe="'+esc(host.id)+'">Probe</button>'
      +'<button type="button" class="secondary" data-hpc-run="'+esc(host.id)+'">Run job</button>'
      +'<button type="button" class="secondary" data-hpc-remove="'+esc(host.id)+'">Remove</button></div></div>';}).join('');
  const jobs=(c.jobs||[]).map(job=>{const cache=computePanels.get(job.id)||{};const open=Boolean(cache.open);
    const outputs=(cache.outputs||[]).map(file=>'<a class="hpc-output" href="'+computeFileUrl(job.id,file.path)+'" download>'
      +'<span>↓</span><b>'+esc(file.path)+'</b><span>'+formatBytes(file.bytes)+'</span></a>').join('');
    const consoleBody=cache.mode==='outputs'
      ?'<div class="hpc-output-list">'+(outputs||'<div class="compute-empty">No remote output files found.</div>')+'</div>'
      :'<pre>'+esc(((cache.logs||{}).stdout||'')+(((cache.logs||{}).stderr)?'\n[stderr]\n'+cache.logs.stderr:''))+'</pre>';
    const terminal=['completed','failed','cancelled','timeout','out_of_memory'].includes(job.status);
    return '<div class="hpc-job"><div class="hpc-job-top"><b>'+esc(job.name)+'</b>'+(job.origin==='generator'?'<span class="host-kind">Generator</span>':'')+'<span class="status '+esc(job.status)+'">'
      +esc(job.status)+'</span></div><div class="hpc-job-meta"><span>'+esc(job.host)+'</span><span>'+esc(job.scheduler)+' #'
      +esc(job.remote_id)+'</span><span>'+esc(job.elapsed||'')+'</span><span>'+new Date(job.submitted*1000).toLocaleString()+'</span></div>'
      +'<div class="hpc-job-detail">'+esc(job.detail||'')+'</div>'+(job.connection_error?'<div class="hpc-connection-error">Offline view · '
      +esc(job.connection_error)+' · the remote job continues independently</div>':'')+'<div class="hpc-job-actions">'
      +'<button type="button" class="secondary" data-hpc-logs="'+esc(job.id)+'">Live logs</button>'
      +'<button type="button" class="secondary" data-hpc-outputs="'+esc(job.id)+'">Outputs</button>'
      +(!terminal?'<button type="button" class="secondary" data-hpc-cancel="'+esc(job.id)+'">Cancel job</button>':'')
      +'</div><div class="hpc-console'+(open?' on':'')+'"><div class="hpc-console-tabs">'
      +(cache.mode==='outputs'?'Remote outputs':'Last 64 KB · stdout + stderr')+'<span class="spacer"></span>'
      +(cache.loading?'Updating…':cache.error?'<span style="color:var(--red)">'+esc(cache.error)+'</span>':'')
      +'</div>'+consoleBody+'</div></div>';}).join('');
  return '<div class="view-heading"><h2>Remote compute</h2><p>SSH workstations and Slurm clusters for manual jobs or Generator calculations.</p></div>'
    +'<div class="compute-note"><span>ⓘ</span><div><b>Remote-owned execution.</b> CrossAudit stores only host aliases and job identifiers. '
    +'Keys remain with OpenSSH; remote work continues if the app closes, the Mac sleeps, or the network drops. A host marked as a Generator tool can receive model-authored jobs automatically within its saved policy.</div></div>'
    +'<div class="compute-message" id="compute-message" role="alert"></div>'
    +'<div class="compute-toolbar"><button type="button" class="primary" data-hpc-add>＋ Add SSH host</button>'
    +'<button type="button" class="secondary" data-hpc-run="">Submit job</button><span class="spacer"></span>'
    +'<button type="button" class="secondary" data-hpc-refresh>Refresh now</button></div>'
    +'<div class="compute-grid"><section class="compute-section"><div class="compute-section-head"><b>Compute hosts</b><span>'
    +(c.hosts||[]).length+' connected</span></div>'+(hosts||'<div class="compute-empty">No SSH compute hosts yet.</div>')+'</section>'
    +'<section class="compute-section"><div class="compute-section-head"><b>Remote jobs</b><span>'+c.active+' active</span></div>'
    +(jobs||'<div class="compute-empty">No jobs submitted from this project.</div>')+'</section></div>';
}
function toolsView(d){
  const state=d.mcp||{servers:[],calls:[]},skills=((d.runtime_config||{}).skills||[]);
  const servers=(state.servers||[]).map(server=>{const approved=new Set(server.allowed_tools||[]);
    const tools=(server.tools||[]).map(tool=>{const note=tool.annotations||{},risk=note.destructiveHint?' ⚠':note.readOnlyHint?' ◉':'';
      return '<span class="mcp-tool'+(approved.has(tool.name)?' approved':'')+'" title="'+esc((tool.description||'')
        +' · server annotations are untrusted')+'">'+(approved.has(tool.name)?'✓ ':'')+esc(tool.name+risk)+'</span>';}).join('');
    const endpoint=server.transport==='stdio'?[server.command,...(server.args||[])].join(' '):server.url;
    return '<div class="host-row"><div class="host-top"><b>'+esc(server.name)+'</b>'
      +'<span class="host-kind">'+esc(server.transport)+'</span></div><div class="host-detail">'+esc(endpoint||'')+'</div>'
      +'<div class="host-resources"><span class="host-resource">MCP '+esc(server.protocol_version||'')+'</span><span class="host-resource">'
      +(server.enabled?'Generator enabled':'Manual only')+'</span><span class="host-resource">'+esc(server.max_calls_per_task)+' calls/task</span></div>'
      +'<div class="mcp-tool-list">'+(tools||'<span class="field-help">No tools advertised.</span>')+'</div><div class="host-actions">'
      +'<button type="button" class="secondary" data-mcp-configure="'+esc(server.id)+'">Configure</button>'
      +'<button type="button" class="secondary" data-mcp-probe="'+esc(server.id)+'">Refresh tools</button>'
      +'<button type="button" class="secondary" data-mcp-remove="'+esc(server.id)+'">Remove</button></div></div>';}).join('');
  const calls=(state.calls||[]).map(call=>'<div class="mcp-call"><b>'+esc(call.tool)+' · '+esc(call.server)+'</b><span class="status '
    +esc(call.status)+'">'+esc(call.status)+'</span><small>'+new Date(call.started*1000).toLocaleString()+'</small><small>'
    +Math.round(Number(call.duration_ms||0))+' ms</small></div>').join('');
  const skillRows=skills.map(skill=>'<div class="skill-row"><b>'+esc(skill.name)+'</b><p>'
    +esc((skill.applies_to||[]).length?'Applies to '+skill.applies_to.join(', '):'Applies to every task')+'</p></div>').join('');
  return '<div class="view-heading"><h2>Tools & Skills</h2><p>Project-scoped MCP capabilities and committed Generator guidance.</p></div>'
    +'<div class="compute-note"><span>ⓘ</span><div><b>Explicit capability boundaries.</b> MCP servers and Skills are invisible until you configure them. Approved MCP output remains untrusted data; Skills guide only the Generator and never change the Constitution.</div></div>'
    +'<div class="compute-message" id="mcp-message" role="alert"></div><div class="compute-toolbar">'
    +'<button type="button" class="primary" data-mcp-add>＋ Add MCP server</button><button type="button" class="secondary" data-manage-skills>Manage Skills</button></div>'
    +'<div class="compute-grid tools-grid"><section class="compute-section"><div class="compute-section-head"><b>MCP servers</b><span>'
    +(state.servers||[]).length+' connected</span></div>'+(servers||'<div class="compute-empty">No MCP servers connected to this project.</div>')+'</section>'
    +'<section class="compute-section"><div class="compute-section-head"><b>Recent tool calls</b><span>'+(state.calls||[]).length+' recorded</span></div>'
    +(calls||'<div class="compute-empty">No MCP tools called in this project.</div>')+'</section>'
    +'<section class="compute-section"><div class="compute-section-head"><b>Skills</b><span>'+skills.length+' committed</span></div>'
    +(skillRows||'<div class="compute-empty">No project Skills yet.</div>')+'</section></div>';
}
function renderConversation(d){
  const thread = document.getElementById('thread');
  const previousTop = thread.scrollTop;
  const distanceFromBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight;
  const followLive = distanceFromBottom < 80;
  let html;
  if(newTaskMode) html = welcome();
  else{
    const messages = allMessages(d);
    const p = chatProgress(d);
    const live = p && !p.finished ? runCard(d) : '';
    const review = reviewCard(d);
    // One protagonist per screen: the welcome empty state renders only when
    // the timeline holds nothing at all, and the delivery band only when no
    // review card already states the outcome of the same cycle.
    const body = messages.map(m=>turn(m,d)).join('') + live + review
      + (review ? '' : deliveryStatus(d));
    html = body || welcome();
  }
  document.getElementById('conversation').innerHTML = html;
  if(followLive && !newTaskMode) thread.scrollTop = thread.scrollHeight;
  else thread.scrollTop = Math.min(previousTop,Math.max(0,thread.scrollHeight-thread.clientHeight));
}
const PANEL_TITLES={artifacts:'Files',audits:'Audit history',models:'Models',usage:'Usage',
  compute:'Compute',tools:'Tools & Skills'};
function renderPanelTabs(){
  document.querySelectorAll('.panel-tabs .nav-item').forEach(button=>{
    const selected=button.getAttribute('data-view')===activeView;
    button.classList.toggle('active',selected);
    button.setAttribute('aria-pressed',selected?'true':'false');
  });
}
function renderPanel(d){
  if(!d)return;
  document.getElementById('panel-title').textContent=PANEL_TITLES[activeView]||'Context panel';
  const staticPane=document.getElementById('panel-models');
  const dynamic=document.getElementById('panel-dynamic');
  staticPane.hidden=activeView!=='models';
  if(activeView==='models')dynamic.innerHTML='';
  else if(activeView==='artifacts')dynamic.innerHTML=artifactsView(d);
  else if(activeView==='audits')dynamic.innerHTML=auditsView(d);
  else if(activeView==='usage')dynamic.innerHTML=usageView(d);
  else if(activeView==='compute')dynamic.innerHTML=computeView(d);
  else if(activeView==='tools')dynamic.innerHTML=toolsView(d);
  renderPanelTabs();
}
function openPanelTab(view){
  const allowed=['artifacts','audits','models','usage','compute','tools'];
  activeView=allowed.includes(view)?view:'artifacts';
  if(activeView!=='compute')stopComputeTimers();
  closeRail();
  inspector.classList.add('open');
  document.getElementById('inspect-toggle').setAttribute('aria-expanded','true');
  syncScrim();
  if(lastState)renderPanel(lastState);
}
function renderTasks(d){
  const query=String(document.getElementById('rail-search').value||'').trim().toLowerCase();
  const rows=((d.chats&&d.chats.items)||[]).filter(c=>!query||String(c.title).toLowerCase().includes(query));
  const chatRow=c=>{
    const status=String(c.status||'').toLowerCase();
    const dot=(!status||status==='ready')?'':'<span class="state-dot '+esc(status)+'" title="'+esc(status)+'"></span>';
    return '<div class="task'+(c.id===activeChatId?' active':'')+'" role="button" tabindex="0" data-chat-id="'+esc(c.id)+'">'
    +'<div class="task-copy">'+dot+'<span class="task-title">'+esc(c.title)+'</span>'
    +'<span class="task-meta"><span>'+esc(ago(c.updated))+'</span></span></div>'
    +'<button type="button" class="pin-button'+(c.pinned?' pinned':'')+'" data-pin-chat="'+esc(c.id)+'" '
    +'aria-label="'+(c.pinned?'Unpin':'Pin')+' chat" title="'+(c.pinned?'Unpin':'Pin')+' chat">'+(c.pinned?'★':'☆')+'</button>'
    +'<button type="button" class="task-delete" data-delete-chat="'+esc(c.id)+'" '
    +'aria-label="Delete chat from project" title="Delete chat from project">⌫</button></div>';};
  const pinned=rows.filter(c=>c.pinned),recent=rows.filter(c=>!c.pinned);
  let html='';if(pinned.length)html+='<div class="side-label">Pinned</div>'+pinned.map(chatRow).join('');
  if(recent.length)html+='<div class="side-label">Recent</div>'+recent.map(chatRow).join('');
  document.getElementById('task-list').innerHTML=html||'<div class="empty">No chats yet</div>';
}
function renderDecisionBanner(d){
  const banner=document.getElementById('decision-banner');
  const rows=(d&&d.escalations)||[];
  // A parked run whose decision object could not be recorded (fail-closed
  // verdict protection) still needs a person: its own waiting reason keeps
  // it in the needs-attention count instead of vanishing.
  const p=d&&d.progress;
  const parkedAlone=(p&&p.state==='PROVIDER_UNAVAILABLE'&&p.waiting_reason&&!rows.length)?1:0;
  const count=rows.length+parkedAlone;
  const show=count>0&&!resolutionModal.classList.contains('on')
    &&!document.body.classList.contains('hub-mode');
  banner.hidden=!show;
  if(show)document.getElementById('decision-banner-text').textContent=
    count+' task'+(count===1?'':'s')+' need'+(count===1?'s':'')+' your decision';
}
function renderInspector(d){
  document.getElementById('runtime-generator').textContent = d.generator;
  document.getElementById('runtime-auditor').textContent = d.auditor;
  document.getElementById('max-rounds').textContent = d.max_rounds;
  const progress=chatProgress(d),cycles=chatCycles(d);
  const current = progress && progress.steps ? progress.steps.filter(s =>
    s.kind === 'round_started').slice(-1)[0] : null;
  document.getElementById('current-round').textContent = current
    ? current.round_no + ' / ' + current.round_limit
    : cycles.length ? cycles[cycles.length-1].round + ' / ' + d.max_rounds : '-';
  document.getElementById('rules-count').textContent = d.rules + ' blocker rules';
  document.getElementById('tier-value').textContent = d.tier.tier;
  const contracts = d.check_contracts || {};
  document.getElementById('runtime-checks').innerHTML = Object.keys(contracts).length
    ? Object.entries(contracts).map(([k,v]) => '<div class="contract" title="' + esc(v) + '">✓ '
      + esc(k) + '</div>').join('') : '<div class="empty">No checks configured</div>';
  document.getElementById('mini-metrics').innerHTML = d.metrics.map(m => '<div class="mini-metric">'
    + '<div class="mini-value">' + esc(m.value ?? '-') + '</div><div class="mini-label">'
    + esc(m.label) + '</div></div>').join('');
  const escalations=currentEscalations(d);
  document.getElementById('escalations').innerHTML = escalations.length ? escalations.map(e =>
    '<div class="escalation"><b>' +(e.limit_reached?'Automatic limit reached · ':'')+esc(e.round)+' / '+esc(e.max_rounds)+' rounds</b><p>'
    + esc(e.why) + '</p><small>'+(e.issues||[]).length+' remaining issue'+((e.issues||[]).length===1?'':'s')+'</small>'
    +'<p>'+esc(e.requested||'A human decision is required.')+'</p><div class="escalation-actions"><button type="button" class="secondary" data-resolve="reopen" data-cycle="'
    +esc(e.cycle_id)+'" data-sha="'+esc(e.short_sha||String(e.sha).slice(0,12))+'">Allow another round</button><button type="button" class="secondary" data-resolve="close" data-cycle="'
    +esc(e.cycle_id)+'" data-sha="'+esc(e.short_sha||String(e.sha).slice(0,12))+'">Stop task</button></div></div>').join('') : '<div class="empty">Nothing needs attention.</div>';
}
function maybePromptForHuman(d){
  if(document.body.classList.contains('hub-mode')||resolutionModal.classList.contains('on')||newTaskMode)return;
  const row=currentEscalations(d).slice(-1)[0];
  if(row&&!promptedEscalations.has(row.cycle_id))setTimeout(()=>{
    if(lastState===d&&!resolutionModal.classList.contains('on'))openResolution(row);
  },0);
}
function render(d){
  lastState = d;
  const chatRows=(d.chats&&d.chats.items)||[];
  if(activeChatId&&!chatRows.some(row=>row.id===activeChatId))activeChatId='';
  if(!activeChatId&&chatRows.length&&!newTaskMode)activeChatId=chatRows[0].id;
  if(runtimeModal.classList.contains('on'))syncRuntimeBusy(d);
  const preview=document.getElementById('contract-preview');preview.className='contract-preview';preview.innerHTML='';
  document.getElementById('version-badge').textContent = 'V' + d.version;
  document.getElementById('hub-version').textContent = 'V' + d.version;
  document.getElementById('proj').textContent = d.project;
  document.getElementById('side-project').textContent = d.project;
  document.getElementById('tier-label').textContent = d.tier.tier + ' · local controller';
  document.getElementById('thread-title').textContent = newTaskMode ? 'New chat' : titleOf(d);
  setStatePill(d);
  renderDecisionBanner(d);
  document.getElementById('model-summary').textContent = modelTag(d.generator) + ' → ' + modelTag(d.auditor);
  const activeRun=chatProgress(d),canCancel=Boolean(activeRun&&!activeRun.finished);
  stopRun.hidden=!canCancel;send.hidden=canCancel;
  stopRun.disabled=Boolean(activeRun&&activeRun.state==='CANCELLING');
  stopRun.setAttribute('aria-label',currentLocale==='zh'?'停止正在运行的任务':'Cancel running task');
  stopRun.title=stopRun.getAttribute('aria-label');
  const projectPin=document.getElementById('current-project-pin'),projectPinned=Boolean(d.chats&&d.chats.project_pinned);
  projectPin.textContent=projectPinned?'★':'☆';projectPin.classList.toggle('pinned',projectPinned);
  projectPin.title=projectPinned?'Unpin project':'Pin project';projectPin.setAttribute('aria-label',projectPin.title);
  renderTasks(d);renderInspector(d);renderConversation(d);renderPanel(d);
  const iv = document.getElementById('interrupted');
  const interruptedChat=d.interrupted&&(d.interrupted.chat_id||'history');
  const interruptedChatExists=Boolean(interruptedChat&&(d.chats&&d.chats.items||[]).some(item=>item.id===interruptedChat));
  if(d.interrupted&&(interruptedChat===activeChatId||!interruptedChatExists) && !(chatProgress(d) && !chatProgress(d).finished)){
    const interruptedTask=esc(d.interrupted.task.replace(/\s+/g,' ').slice(0,72));
    const phaseNames=currentLocale==='zh'?{generator:'生成者',auditor:'审计者',input:'输入',loop:'审计循环',tool:'工具',compute:'远程计算'}:{};
    const interruptedPhase=esc(phaseNames[d.interrupted.phase]||d.interrupted.phase||'unknown');
    const interruptedDetail=d.interrupted.detail?'<span class="interrupted-detail">'+esc(d.interrupted.detail)+'</span>':'';
    iv.className = 'interrupted on';iv.innerHTML = currentLocale==='zh'
      ?'<b>任务已安全中断</b><br>“'+interruptedTask+'”。最后可见阶段：'+interruptedPhase+'。'+interruptedDetail+'已提交轮次均已保留；重试会从最近的持久 Git 提交继续，忽略提示也不会改动文件。<div class="interrupted-actions"><button type="button" data-interrupted="retry">重试任务</button><button type="button" data-interrupted="dismiss">忽略提示</button></div>'
      :'<b>Task interrupted safely</b><br>"'+interruptedTask+'". Last visible phase: '+interruptedPhase+'. '+interruptedDetail+'Committed rounds are preserved. Retry resumes from the last durable commit; dismiss keeps files unchanged.<div class="interrupted-actions"><button type="button" data-interrupted="retry">Retry task</button><button type="button" data-interrupted="dismiss">Dismiss notice</button></div>';
  }else iv.className = 'interrupted';
  maybePromptForHuman(d);
}
document.getElementById('interrupted').onclick=async ev=>{const button=ev.target.closest('[data-interrupted]');if(!button)return;
  button.disabled=true;const action=button.getAttribute('data-interrupted');
  try{await api('/api/interrupted',{action});route.className='route on';route.innerHTML=currentLocale==='zh'
    ?(action==='retry'?'<b>任务已重启</b> — 正从最近的持久 Git 提交继续。':'<b>提示已忽略</b> — 文件和已提交证据均已保留。')
    :(action==='retry'?'<b>Task restarted.</b> Continuing from the last durable Git commit.':'<b>Notice dismissed.</b> Files and committed evidence were preserved.');}
  catch(e){route.className='route on error';route.textContent=e.message;button.disabled=false;}};
function connected(on,why){
  document.getElementById('livedot').className='live-dot'+(on?' on':'');
  document.getElementById('conn-text').textContent=why;
  document.querySelector('.live-pill').title = on
    ? why + ' · updated ' + new Date().toLocaleTimeString() : why;
}
let poller=null;
function startPolling(why){connected(false,why);if(poller)return;poller=setInterval(async()=>{
  try{render(await api('/api/state'));connected(true,'polling');}catch(e){connected(false,'offline');}},2000);}
function startStream(){let source;try{source=new EventSource('/api/stream?t='+encodeURIComponent(T));}
  catch(e){startPolling('polling');return;}source.onopen=()=>{connected(true,'live');
  if(poller){clearInterval(poller);poller=null;}};source.onmessage=ev=>{try{render(JSON.parse(ev.data));
  connected(true,'live');}catch(e){}};source.onerror=()=>startPolling('reconnecting');}

const form=document.getElementById('f');const say=document.getElementById('say');
const send=document.getElementById('send');const stopRun=document.getElementById('stop-run');
const route=document.getElementById('route');
const filesBox=document.getElementById('attachments');const fileInput=document.getElementById('file-input');
const sidebar=document.querySelector('.sidebar');const inspector=document.getElementById('inspector');
const scrim=document.getElementById('scrim');
function syncScrim(){
  const sideOpen=sidebar.classList.contains('open');const inspectOpen=inspector.classList.contains('open');
  scrim.className='scrim'+(sideOpen||inspectOpen?' on':'')+(sideOpen?' sidebar-open':'')
    +(inspectOpen?' inspector-open':'');
}
function closeRail(){sidebar.classList.remove('open');
  document.getElementById('sidebar-toggle').setAttribute('aria-expanded','false');syncScrim();}
function closePanels(){sidebar.classList.remove('open');inspector.classList.remove('open');
  document.getElementById('sidebar-toggle').setAttribute('aria-expanded','false');
  document.getElementById('inspect-toggle').setAttribute('aria-expanded','false');syncScrim();}
function toggleSidebar(){const opening=!sidebar.classList.contains('open');closePanels();
  if(opening){sidebar.classList.add('open');document.getElementById('sidebar-toggle').setAttribute('aria-expanded','true');}
  syncScrim();}
function toggleInspector(){
  if(inspector.classList.contains('open')){inspector.classList.remove('open');
    document.getElementById('inspect-toggle').setAttribute('aria-expanded','false');syncScrim();}
  else openPanelTab(activeView);}
function openInspector(){openPanelTab('models');}
function drawFiles(){filesBox.className='attachments'+(pendingFiles.length?' on':'');
  const visible=pendingFiles.slice(0,100);const total=pendingFiles.reduce((sum,e)=>sum+e.file.size,0);
  filesBox.innerHTML=visible.map((entry,i)=>{const f=entry.file;const progress=uploadProgress.get(entry);
    const failed=progress==='failed';const done=progress===100;const ext=(entry.name.includes('.')?entry.name.split('.').pop():'FILE').slice(0,4).toUpperCase();
    const state=failed?'Upload failed':done?'Uploaded':typeof progress==='number'?'Uploading · '+progress+'%':formatBytes(f.size);
    return '<div class="attachment'+(failed?' failed':'')+'"><span class="attachment-type">'+esc(ext)+'</span>'
      +'<span class="attachment-copy"><span class="attachment-name" title="'+esc(entry.name)+'">'+esc(entry.name)+'</span>'
      +'<span class="attachment-state">'+esc(state)+'</span></span><button type="button" data-remove="'+i+'" aria-label="Remove '+esc(entry.name)+'">×</button>'
      +(typeof progress==='number'&&progress<100?'<span class="attachment-progress"><i style="width:'+progress+'%"></i></span>':'')+'</div>';}).join('')
    +(pendingFiles.length?'<div class="attachment-note"><b>'+pendingFiles.length+' file'+(pendingFiles.length===1?'':'s')+' · '+formatBytes(total)+'</b>'
      +(pendingFiles.length>visible.length?'<span class="attachment-more">+'+(pendingFiles.length-visible.length)+' more selected</span>':'')
      +'<span>Stored in chunks without an app quota. Model inspection depends on file support and context.</span></div>':'');}
function uniqueFileName(original){let name=original||'untitled';const used=new Set(pendingFiles.map(e=>e.name.toLowerCase()));
  if(!used.has(name.toLowerCase()))return name;const dot=name.lastIndexOf('.');const base=dot>0?name.slice(0,dot):name;
  const ext=dot>0?name.slice(dot):'';let n=2;while(used.has((base+' ('+n+')'+ext).toLowerCase()))n++;
  return base+' ('+n+')'+ext;}
function addFiles(list){for(const file of Array.from(list||[])){
  if(transferBusy)return;
  pendingFiles.push({file,name:uniqueFileName(file.name)});
}drawFiles();}
function uploadId(){const bytes=crypto.getRandomValues(new Uint8Array(16));return [...bytes].map(v=>v.toString(16).padStart(2,'0')).join('');}
async function uploadFile(entry,batch,ordinal,count){const file=entry.file;const id=uploadId();const chunkSize=384000;let offset=0;
  do{const blob=file.slice(offset,Math.min(file.size,offset+chunkSize));
    const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    await api('/api/upload',{id,batch,ordinal,batch_count:count,name:entry.name,
      type:file.type||'application/octet-stream',offset,total:file.size,data:btoa(binary)});offset+=bytes.length;
    uploadProgress.set(entry,file.size?Math.round(offset/file.size*100):100);drawFiles();
  }while(offset<file.size);return id;}
async function uploadFiles(files){const batch=uploadId();let next=0;const workers=[];
  for(let worker=0;worker<Math.min(3,files.length);worker++)workers.push((async()=>{while(next<files.length){
    const ordinal=next++;const entry=files[ordinal];try{await uploadFile(entry,batch,ordinal,files.length);}
    catch(error){uploadProgress.set(entry,'failed');drawFiles();throw error;}}})());
  const settled=await Promise.allSettled(workers);const failed=settled.find(result=>result.status==='rejected');
  if(failed)throw failed.reason;return batch;
}
const mentionPrefix=/^\s*@(generator|executor|auditor|audit|生成端|执行端|审计端|审计)(?=\s|[,:：-]|$)[\s,:：-]*/i;
function audienceOf(){const m=say.value.match(mentionPrefix);if(!m)return'auto';
  return ['generator','executor','生成端','执行端'].includes(m[1].toLowerCase())?'generator':'auditor';}
function syncAudience(){const audience=audienceOf();document.querySelectorAll('.audience-chip').forEach(button=>
  button.classList.toggle('active',button.getAttribute('data-audience')===audience));}
function setAudience(audience){const body=say.value.replace(mentionPrefix,'').trimStart();
  say.value=(audience==='auto'?'':audience==='generator'?'@Generator ':'@Auditor ')+body;
  say.dispatchEvent(new Event('input'));say.focus();}
document.getElementById('attach').onclick=()=>fileInput.click();fileInput.onchange=()=>{addFiles(fileInput.files);fileInput.value='';};
filesBox.onclick=ev=>{const button=ev.target.closest('[data-remove]');if(button){const i=Number(button.getAttribute('data-remove'));
  if(transferBusy)return;
  uploadProgress.delete(pendingFiles[i]);pendingFiles.splice(i,1);drawFiles();}};
const dropOverlay=document.getElementById('drop-overlay');let dragDepth=0;
function fileDrag(ev){return Array.from((ev.dataTransfer&&ev.dataTransfer.types)||[]).includes('Files');}
window.addEventListener('dragenter',ev=>{if(!fileDrag(ev))return;ev.preventDefault();dragDepth++;
  dropOverlay.className='drop-overlay on';dropOverlay.setAttribute('aria-hidden','false');form.classList.add('drag');});
window.addEventListener('dragover',ev=>{if(fileDrag(ev))ev.preventDefault();});
window.addEventListener('dragleave',ev=>{if(!fileDrag(ev))return;ev.preventDefault();dragDepth=Math.max(0,dragDepth-1);
  if(!dragDepth){dropOverlay.className='drop-overlay';dropOverlay.setAttribute('aria-hidden','true');form.classList.remove('drag');}});
window.addEventListener('drop',ev=>{if(!fileDrag(ev))return;ev.preventDefault();dragDepth=0;
  dropOverlay.className='drop-overlay';dropOverlay.setAttribute('aria-hidden','true');form.classList.remove('drag');
  addFiles(ev.dataTransfer.files);say.focus();});
say.addEventListener('input',()=>{say.style.height='auto';say.style.height=Math.min(say.scrollHeight,150)+'px';syncAudience();});
say.addEventListener('keydown',ev=>{if(ev.key==='Enter'&&!ev.shiftKey&&!ev.isComposing){ev.preventDefault();form.requestSubmit();}});
document.querySelectorAll('.audience-chip').forEach(button=>button.onclick=()=>setAudience(button.getAttribute('data-audience')));
const computeHostModal=document.getElementById('compute-host-modal');
const computeHostForm=document.getElementById('compute-host-form');
const computeJobModal=document.getElementById('compute-job-modal');
const computeJobForm=document.getElementById('compute-job-form');
const mcpModal=document.getElementById('mcp-modal');
const mcpForm=document.getElementById('mcp-form');
const computeLogTimers=new Map();
let computeInputFiles=[];
function computeError(id,error){showInlineError(id,error);}
function computeSurfaceError(error){const box=document.getElementById(activeView==='tools'?'mcp-message':'compute-message');if(!box)return;
  box.textContent=error&&error.message?error.message:String(error);box.className='compute-message on';}
function closeComputeHost(){computeHostModal.className='project-modal';computeHostForm.reset();}
function openComputeHost(){computeHostForm.reset();document.getElementById('compute-host-error').className='wizard-error';
  const aliases=(lastState&&lastState.compute&&lastState.compute.aliases)||[];
  document.getElementById('compute-aliases').innerHTML=aliases.map(value=>'<option value="'+esc(value)+'"></option>').join('');
  document.getElementById('hpc-agent-policy').className='hpc-policy off';
  computeHostModal.className='project-modal on';setTimeout(()=>document.getElementById('compute-alias').focus(),0);}
document.getElementById('hpc-agent-enabled').onchange=event=>{
  document.getElementById('hpc-agent-policy').className='hpc-policy'+(event.target.checked?'':' off');};
function closeComputeJob(){computeJobModal.className='project-modal';computeJobForm.reset();}
function openComputeJob(hostId){const hosts=(lastState&&lastState.compute&&lastState.compute.hosts)||[];
  if(!hosts.length){openComputeHost();return;}computeJobForm.reset();computeInputFiles=[];renderComputeInputs();document.getElementById('compute-job-error').className='wizard-error';
  const select=document.getElementById('compute-job-host');select.innerHTML=hosts.map(host=>'<option value="'+esc(host.id)+'">'
    +esc(host.alias+' · '+((host.probe||{}).scheduler||'workstation'))+'</option>').join('');
  if(hostId&&hosts.some(host=>host.id===hostId))select.value=hostId;
  computeJobModal.className='project-modal on';}
function renderComputeInputs(){const total=computeInputFiles.reduce((sum,row)=>sum+row.file.size,0);
  document.getElementById('compute-input-summary').textContent=computeInputFiles.length
    ?computeInputFiles.length+' file'+(computeInputFiles.length===1?'':'s')+' · '+formatBytes(total)+' · copied to remote inputs/'
    :'Optional. Files are streamed to inputs/ on the remote host with no CrossAudit size or count quota.';
  document.getElementById('compute-input-list').innerHTML=computeInputFiles.map((row,index)=>'<span class="hpc-input"><b>'
    +esc(row.name)+'</b><span>'+formatBytes(row.file.size)+'</span><button type="button" data-compute-input="'+index+'" aria-label="Remove '
    +esc(row.name)+'">×</button></span>').join('');}
document.getElementById('add-compute-inputs').onclick=()=>document.getElementById('compute-input-files').click();
document.getElementById('compute-input-list').onclick=ev=>{const button=ev.target.closest('[data-compute-input]');if(!button)return;
  computeInputFiles.splice(Number(button.getAttribute('data-compute-input')),1);renderComputeInputs();};
document.getElementById('compute-input-files').onchange=ev=>{for(const file of Array.from(ev.target.files||[])){
  const used=new Set(computeInputFiles.map(row=>row.name.toLowerCase()));let name=file.name||'untitled';
  if(used.has(name.toLowerCase())){const dot=name.lastIndexOf('.'),base=dot>0?name.slice(0,dot):name,ext=dot>0?name.slice(dot):'';
    let n=2;while(used.has((base+' ('+n+')'+ext).toLowerCase()))n++;name=base+' ('+n+')'+ext;}
  computeInputFiles.push({file,name});}ev.target.value='';renderComputeInputs();};
document.getElementById('close-compute-host').onclick=closeComputeHost;
document.getElementById('cancel-compute-host').onclick=closeComputeHost;
document.getElementById('close-compute-job').onclick=closeComputeJob;
document.getElementById('cancel-compute-job').onclick=closeComputeJob;
computeHostModal.addEventListener('click',ev=>{if(ev.target===computeHostModal)closeComputeHost();});
computeJobModal.addEventListener('click',ev=>{if(ev.target===computeJobModal)closeComputeJob();});
computeHostForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('save-compute-host');
  button.disabled=true;button.textContent='Connecting…';document.getElementById('compute-host-error').className='wizard-error';
  const fd=new FormData(computeHostForm);const payload=Object.fromEntries(fd.entries());payload.action='register';
  for(const key of ['concurrency','agent_max_jobs','agent_max_nodes','agent_max_cpus','agent_max_gpus'])payload[key]=Number(payload[key]);
  payload.trust_first_key=fd.has('trust_first_key');payload.agent_enabled=fd.has('agent_enabled');
  try{await api('/api/hpc',payload);closeComputeHost();if(lastState)lastState.compute=await api('/api/state').then(s=>s.compute);render(lastState);}
  catch(e){computeError('compute-host-error',e);}finally{button.disabled=false;button.textContent='Probe & add';}};
computeJobForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('submit-compute-job');
  button.disabled=true;button.textContent='Submitting…';document.getElementById('compute-job-error').className='wizard-error';
  const fd=new FormData(computeJobForm);const payload=Object.fromEntries(fd.entries());payload.action='submit';
  for(const key of ['nodes','cpus','gpus'])payload[key]=Number(payload[key]);
  try{if(computeInputFiles.length){button.textContent='Uploading inputs…';payload.upload_batch=await uploadFiles(computeInputFiles);button.textContent='Submitting…';}
    await api('/api/hpc',payload);closeComputeJob();}
  catch(e){computeError('compute-job-error',e);}finally{button.disabled=false;button.textContent='Submit job';}};
function syncMcpTransport(){const stdio=document.getElementById('mcp-transport').value==='stdio';
  document.getElementById('mcp-stdio-fields').classList.toggle('off',!stdio);
  document.getElementById('mcp-http-fields').classList.toggle('off',stdio);
  document.getElementById('mcp-command').required=stdio;document.getElementById('mcp-url').required=!stdio;}
function renderMcpPreview(server){const approved=new Set((server&&server.allowed_tools)||[]),tools=(server&&server.tools)||[];
  document.getElementById('mcp-tool-preview').innerHTML=tools.length?tools.map(tool=>{const note=tool.annotations||{},risk=note.destructiveHint?' ⚠':note.readOnlyHint?' ◉':'';
    return '<span class="mcp-tool'+(approved.has(tool.name)?' approved':'')+'" title="'+esc((tool.description||'')
      +' · server annotations are untrusted')+'">'+(approved.has(tool.name)?'✓ ':'')+esc(tool.name+risk)+'</span>';}).join(''):'<span class="field-help">Connect the server to discover tools.</span>';}
function openMcp(serverId=''){mcpForm.reset();document.getElementById('mcp-error').className='wizard-error';
  const server=((lastState&&lastState.mcp&&lastState.mcp.servers)||[]).find(row=>row.id===serverId);
  document.getElementById('mcp-title').textContent=server?'Configure MCP server':'Add MCP server';
  document.getElementById('mcp-server-id').value=server?server.id:'';
  if(server){document.getElementById('mcp-name').value=server.name||'';document.getElementById('mcp-transport').value=server.transport||'stdio';
    document.getElementById('mcp-command').value=server.command||'';document.getElementById('mcp-args').value=(server.args||[]).join('\n');
    document.getElementById('mcp-url').value=server.url||'';mcpForm.elements.timeout.value=server.timeout||30;
    mcpForm.elements.max_calls_per_task.value=server.max_calls_per_task||5;mcpForm.elements.allowed_tools_text.value=(server.allowed_tools||[]).join(', ');
    mcpForm.elements.enabled.checked=Boolean(server.enabled);mcpForm.elements.allow_private_network.checked=Boolean(server.allow_private_network);}
  syncMcpTransport();renderMcpPreview(server);mcpModal.className='project-modal on';setTimeout(()=>document.getElementById('mcp-name').focus(),0);}
function closeMcp(){mcpModal.className='project-modal';mcpForm.reset();}
document.getElementById('mcp-transport').onchange=syncMcpTransport;
document.getElementById('close-mcp').onclick=closeMcp;document.getElementById('cancel-mcp').onclick=closeMcp;
mcpModal.addEventListener('click',ev=>{if(ev.target===mcpModal)closeMcp();});
mcpForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('save-mcp');button.disabled=true;
  button.textContent='Connecting…';document.getElementById('mcp-error').className='wizard-error';const fd=new FormData(mcpForm);
  const payload=Object.fromEntries(fd.entries());payload.action='register';payload.args=document.getElementById('mcp-args').value.split('\n').map(value=>value.trim()).filter(Boolean);
  payload.allowed_tools=document.getElementById('mcp-allowed-tools').value.split(',').map(value=>value.trim()).filter(Boolean);
  payload.timeout=Number(payload.timeout);payload.max_calls_per_task=Number(payload.max_calls_per_task);
  for(const name of ['approve_local_code','allow_private_network','allow_all_tools','enabled'])payload[name]=fd.has(name);
  delete payload.args_text;delete payload.allowed_tools_text;
  try{await api('/api/mcp',payload);closeMcp();if(lastState){lastState.mcp=await api('/api/state').then(state=>state.mcp);render(lastState);}}
  catch(e){computeError('mcp-error',e);}finally{button.disabled=false;button.textContent='Connect & save';}};
function stopComputeTimers(except=''){for(const [id,timer] of computeLogTimers){if(id!==except){clearInterval(timer);computeLogTimers.delete(id);}}}
async function loadComputePanel(jobId,mode){const current=computePanels.get(jobId)||{};computePanels.set(jobId,{...current,open:true,mode,loading:true,error:''});
  if(lastState)render(lastState);try{const result=await api('/api/hpc',{action:mode==='outputs'?'outputs':'logs',job_id:jobId});
    const row=computePanels.get(jobId)||{};computePanels.set(jobId,{...row,open:true,mode,loading:false,
      ...(mode==='outputs'?{outputs:result.outputs||[]}:{logs:result})});}
  catch(e){const row=computePanels.get(jobId)||{};computePanels.set(jobId,{...row,open:true,mode,loading:false,error:e.message});}
  if(lastState)render(lastState);}
function followComputeLogs(jobId){stopComputeTimers(jobId);if(!computeLogTimers.has(jobId))computeLogTimers.set(jobId,setInterval(()=>{
  if(activeView==='compute'&&(computePanels.get(jobId)||{}).open)loadComputePanel(jobId,'logs');},2000));}
document.getElementById('inspector').addEventListener('click',ev=>{
  const tab=ev.target.closest('[data-view]');
  if(tab)openPanelTab(tab.getAttribute('data-view'));
});
document.getElementById('panel-open-runtime').onclick=openRuntime;
document.getElementById('model-summary').onclick=()=>openPanelTab('models');
document.getElementById('rail-search').addEventListener('input',()=>{if(lastState)renderTasks(lastState);});
function handleActionClick(ev){
  const groupToggle=ev.target.closest('[data-group-toggle]');
  if(groupToggle){const key=groupToggle.getAttribute('data-group-toggle');
    const card=groupToggle.closest('.deliverable-group');
    const open=!expandedGroups.has(key);
    if(open)expandedGroups.add(key);else expandedGroups.delete(key);
    if(card){card.classList.toggle('open',open);groupToggle.setAttribute('aria-expanded',String(open));}
    return;}
  const reviewToggle=ev.target.closest('[data-review-toggle]');
  if(reviewToggle){const key=reviewToggle.getAttribute('data-review-toggle');
    const card=reviewToggle.closest('.review-card');
    const open=!expandedReviews.has(key);
    if(open)expandedReviews.add(key);else expandedReviews.delete(key);
    if(card){card.classList.toggle('open',open);reviewToggle.setAttribute('aria-expanded',String(open));}
    return;}
  if(ev.target.closest('[data-open-artifacts]'))openPanelTab('artifacts');
  if(ev.target.closest('[data-open-audits]'))openPanelTab('audits');
  if(ev.target.closest('[data-open-decisions]')){
    const row=lastState&&currentEscalations(lastState).slice(-1)[0];if(row)openResolution(row);else openInspector();
  }
  if(ev.target.closest('[data-hpc-add]'))openComputeHost();
  if(ev.target.closest('[data-mcp-add]'))openMcp();
  if(ev.target.closest('[data-manage-skills]'))openRuntime();
  const configureMcp=ev.target.closest('[data-mcp-configure]');if(configureMcp)openMcp(configureMcp.getAttribute('data-mcp-configure'));
  const probeMcp=ev.target.closest('[data-mcp-probe]');if(probeMcp){probeMcp.disabled=true;probeMcp.textContent='Refreshing…';
    api('/api/mcp',{action:'probe',server_id:probeMcp.getAttribute('data-mcp-probe')}).catch(computeSurfaceError)
      .finally(()=>{probeMcp.disabled=false;probeMcp.textContent='Refresh tools';});}
  const removeMcp=ev.target.closest('[data-mcp-remove]');if(removeMcp&&confirm(currentLocale==='zh'?'从此项目移除这个 MCP 服务器？':'Remove this MCP server from this project?')){
    removeMcp.disabled=true;api('/api/mcp',{action:'remove',server_id:removeMcp.getAttribute('data-mcp-remove')})
      .catch(computeSurfaceError).finally(()=>{removeMcp.disabled=false;});}
  const run=ev.target.closest('[data-hpc-run]');if(run)openComputeJob(run.getAttribute('data-hpc-run'));
  const probe=ev.target.closest('[data-hpc-probe]');if(probe){probe.disabled=true;probe.textContent='Probing…';
    api('/api/hpc',{action:'probe',host_id:probe.getAttribute('data-hpc-probe')}).catch(computeSurfaceError)
      .finally(()=>{probe.disabled=false;probe.textContent='Probe';});}
  const remove=ev.target.closest('[data-hpc-remove]');if(remove&&confirm('Remove this compute host from this project?')){
    remove.disabled=true;api('/api/hpc',{action:'remove',host_id:remove.getAttribute('data-hpc-remove')})
      .catch(computeSurfaceError).finally(()=>{remove.disabled=false;});}
  const refresh=ev.target.closest('[data-hpc-refresh]');if(refresh){refresh.disabled=true;refresh.textContent='Refreshing…';
    api('/api/hpc',{action:'refresh'}).catch(computeSurfaceError).finally(()=>{refresh.disabled=false;refresh.textContent='Refresh now';});}
  const logs=ev.target.closest('[data-hpc-logs]');if(logs){const id=logs.getAttribute('data-hpc-logs');loadComputePanel(id,'logs');followComputeLogs(id);}
  const outputs=ev.target.closest('[data-hpc-outputs]');if(outputs){const id=outputs.getAttribute('data-hpc-outputs');stopComputeTimers();loadComputePanel(id,'outputs');}
  const cancel=ev.target.closest('[data-hpc-cancel]');if(cancel&&confirm(currentLocale==='zh'?'取消这个远程任务？此操作无法撤销。':'Cancel this remote job? This cannot be undone.')){
    cancel.disabled=true;cancel.textContent='Cancelling…';api('/api/hpc',{action:'cancel',job_id:cancel.getAttribute('data-hpc-cancel')})
      .catch(computeSurfaceError).finally(()=>{cancel.disabled=false;cancel.textContent='Cancel job';});}
  const admit=ev.target.closest('[data-admit]');if(admit){admit.disabled=true;admit.textContent='Verifying…';
    api('/api/admit',{cycle_id:admit.getAttribute('data-admit-cycle')}).catch(e=>{route.className='route on';route.innerHTML='<b>Not admitted.</b> '+esc(e.message);});}
}
document.getElementById('conversation').onclick=handleActionClick;
document.getElementById('panel-dynamic').onclick=handleActionClick;
const deleteChatModal=document.getElementById('delete-chat-modal');
const deleteChatForm=document.getElementById('delete-chat-form');
function closeDeleteChat(){deleteChatModal.className='project-modal';deleteChatForm.reset();
  document.getElementById('delete-chat-error').className='wizard-error';}
function openDeleteChat(id){const chat=lastState&&lastState.chats.items.find(row=>row.id===id);if(!chat)return;
  document.getElementById('delete-chat-id').value=id;document.getElementById('delete-chat-name').textContent=chat.title;
  document.getElementById('delete-chat-impact').textContent=chat.cycles
    ?(currentLocale==='zh'?'此对话有 '+chat.cycles+' 个审计循环；导航会删除，但审计证据会保留。':'This chat has '+chat.cycles+' audit cycle'+(chat.cycles===1?'':'s')+'; navigation is removed while audit evidence remains.')
    :(currentLocale==='zh'?'这是一个空对话，将直接从侧栏移除。':'This is an empty chat and will be removed from the sidebar.');
  document.getElementById('delete-chat-error').className='wizard-error';deleteChatModal.className='project-modal on';}
document.getElementById('close-delete-chat').onclick=closeDeleteChat;
document.getElementById('cancel-delete-chat').onclick=closeDeleteChat;
deleteChatModal.addEventListener('click',ev=>{if(ev.target===deleteChatModal)closeDeleteChat();});
deleteChatForm.onsubmit=async ev=>{ev.preventDefault();const id=document.getElementById('delete-chat-id').value;
  const button=document.getElementById('confirm-delete-chat');button.disabled=true;button.textContent=currentLocale==='zh'?'正在删除…':'Deleting…';
  try{await api('/api/chats/delete',{chat_id:id});closeDeleteChat();
    if(lastState){lastState.chats.items=lastState.chats.items.filter(row=>row.id!==id);
      if(activeChatId===id){activeChatId=lastState.chats.items[0]&&lastState.chats.items[0].id||'';newTaskMode=!activeChatId;}
      render(lastState);}}
  catch(e){showInlineError('delete-chat-error',e);}finally{button.disabled=false;button.textContent=currentLocale==='zh'?'删除对话':'Delete chat';}};
document.getElementById('task-list').onclick=async ev=>{
  const pin=ev.target.closest('[data-pin-chat]'),remove=ev.target.closest('[data-delete-chat]'),row=ev.target.closest('[data-chat-id]');
  if(remove){ev.preventDefault();ev.stopPropagation();openDeleteChat(remove.getAttribute('data-delete-chat'));return;}
  if(pin){ev.preventDefault();ev.stopPropagation();const id=pin.getAttribute('data-pin-chat');
    const chat=lastState&&lastState.chats.items.find(c=>c.id===id);if(!chat)return;
    pin.disabled=true;try{await api('/api/chats/pin',{chat_id:id,pinned:!chat.pinned});chat.pinned=!chat.pinned;
      render(lastState);}catch(e){pin.disabled=false;}return;}
  if(row){activeChatId=row.getAttribute('data-chat-id');newTaskMode=false;
    if(pendingContinuation.chat&&pendingContinuation.chat!==activeChatId)pendingContinuation={cycle:'',chat:''};
    if(resolutionModal.classList.contains('on'))closeResolution();
    render(lastState);document.getElementById('thread').scrollTop=0;closeRail();}
};
document.getElementById('task-list').onkeydown=ev=>{if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-chat-id]')){
  ev.preventDefault();ev.target.click();}};
document.getElementById('current-project-pin').onclick=async()=>{if(!lastState)return;const button=document.getElementById('current-project-pin');
  const pinned=Boolean(lastState.chats&&lastState.chats.project_pinned);button.disabled=true;
  try{await api('/api/projects/pin',{root:lastState.root,pinned:!pinned});lastState.chats.project_pinned=!pinned;render(lastState);}
  catch(e){route.className='route on';route.innerHTML='<b>Could not pin project.</b> '+esc(e.message);}
  finally{button.disabled=false;}};
document.getElementById('new-task').onclick=async()=>{
  newTaskMode=true;say.value='';route.className='route';pendingFiles=[];
  pendingContinuation={cycle:'',chat:''};
  uploadProgress=new Map();
  syncAudience();
  fileInput.value='';drawFiles();
  if(resolutionModal.classList.contains('on'))closeResolution();
  try{const result=await api('/api/chats/new',{title:'New chat'});activeChatId=result.chat.id;
    if(lastState){lastState.chats.items.unshift({...result.chat,cycles:0,status:'ready'});render(lastState);}}
  catch(e){route.className='route on';route.innerHTML='<b>Could not create chat.</b> '+esc(e.message);}
  document.getElementById('thread').scrollTop=0;closeRail();say.focus();
};
document.getElementById('sidebar-toggle').onclick=toggleSidebar;
document.getElementById('inspect-toggle').onclick=toggleInspector;
document.getElementById('inspect-close').onclick=closePanels;
document.getElementById('escalations').onclick=ev=>{const button=ev.target.closest('[data-resolve]');if(!button)return;
  const cycle=button.getAttribute('data-cycle');const row=lastState&&(lastState.escalations||[]).find(item=>item.cycle_id===cycle);
  openResolution(row||cycle,button.getAttribute('data-resolve'),button.getAttribute('data-sha'));};
scrim.onclick=closePanels;
const modalReturnFocus=new WeakMap();
const modalObserver=new MutationObserver(records=>records.forEach(record=>{
  const modal=record.target;const wasOpen=(record.oldValue||'').split(/\s+/).includes('on');
  const isOpen=modal.classList.contains('on');
  if(isOpen&&!wasOpen)modalReturnFocus.set(modal,document.activeElement);
  if(wasOpen&&!isOpen){const trigger=modalReturnFocus.get(modal);modalReturnFocus.delete(modal);
    if(trigger&&trigger.isConnected)setTimeout(()=>trigger.focus(),0);}
}));
document.querySelectorAll('.project-modal').forEach(modal=>modalObserver.observe(modal,{attributes:true,attributeOldValue:true,attributeFilter:['class']}));
function activeModal(){const rows=[...document.querySelectorAll('.project-modal.on')];return rows.at(-1)||null;}
function closeActiveModal(modal){
  if(modal===filePreviewModal)closeFilePreview();
  else if(modal===projectModal)closeProjectModal();else if(modal===recoveryModal)closeRecovery();
  else if(modal===deleteProjectModal)closeDeleteProject();else if(modal===deleteChatModal)closeDeleteChat();
  else if(modal===runtimeModal)closeRuntime();else if(modal===paletteModal)closePalette();
  else if(modal===settingsModal)closeSettings();else if(modal===computeHostModal)closeComputeHost();
  else if(modal===computeJobModal)closeComputeJob();else if(modal===mcpModal)closeMcp();
}
document.addEventListener('keydown',ev=>{const modal=activeModal();
  if(ev.key==='Tab'&&modal){const controls=[...modal.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
      .filter(element=>element.getClientRects().length);if(!controls.length){ev.preventDefault();return;}
    const first=controls[0],last=controls.at(-1);if(ev.shiftKey&&(document.activeElement===first||!modal.contains(document.activeElement))){ev.preventDefault();last.focus();}
    else if(!ev.shiftKey&&(document.activeElement===last||!modal.contains(document.activeElement))){ev.preventDefault();first.focus();}return;}
  if(ev.key==='Escape'){if(modal){ev.preventDefault();closeActiveModal(modal);}
    else if(filePreviewModal.classList.contains('on'))closeFilePreview();
    else if(resolutionModal.classList.contains('on'))closeResolution();
    else closePanels();}
});
document.addEventListener('keydown',ev=>{
  const meta=ev.metaKey||ev.ctrlKey;
  if(meta&&!ev.shiftKey&&!ev.altKey&&String(ev.key).toLowerCase()==='k'){
    ev.preventDefault();
    if(paletteModal.classList.contains('on'))closePalette();else openPalette();
    return;
  }
  if(meta&&ev.key==='.'){if(!stopRun.hidden&&!stopRun.disabled){ev.preventDefault();stopRun.click();}return;}
  if(activeModal()||resolutionModal.classList.contains('on'))return;
  const tag=String((document.activeElement||{}).tagName||'').toLowerCase();
  if(['input','textarea','select'].includes(tag))return;
  if(ev.key==='['){ev.preventDefault();toggleSidebar();}
  else if(ev.key===']'){ev.preventDefault();toggleInspector();}
});
const paletteModal=document.getElementById('palette');
const paletteInput=document.getElementById('palette-input');
const paletteList=document.getElementById('palette-list');
let paletteIndex=0;let paletteItems=[];
function paletteCommands(){
  const inHub=document.body.classList.contains('hub-mode');
  const items=[];
  if(!inHub){
    items.push({title:'New chat',hint:'⌘N',run:()=>document.getElementById('new-task').click()});
    items.push({title:'Files',context:'Context panel',run:()=>openPanelTab('artifacts')});
    items.push({title:'Audit history',context:'Context panel',run:()=>openPanelTab('audits')});
    items.push({title:'Models',context:'Context panel',run:()=>openPanelTab('models')});
    items.push({title:'Usage',context:'Context panel',run:()=>openPanelTab('usage')});
    items.push({title:'Remote compute',context:'Context panel',run:()=>openPanelTab('compute')});
    items.push({title:'Tools & Skills',context:'Context panel',run:()=>openPanelTab('tools')});
    items.push({title:'Project controls',run:openRuntime});
    const running=lastState&&chatProgress(lastState)&&!chatProgress(lastState).finished;
    if(running)items.push({title:'Stop current task',hint:'⌘.',run:()=>stopRun.click()});
  }
  items.push({title:'All projects',run:showProjects});
  items.push({title:'Open settings',run:()=>openSettings('general')});
  items.push({title:'Run Doctor',run:async()=>{await openSettings('general');
    document.getElementById('run-doctor').click();}});
  items.push({title:'Switch theme',run:()=>themeButton.onclick()});
  items.push({title:'Switch language',run:()=>document.getElementById('locale-toggle').onclick()});
  return items;
}
function paletteRow(item,index){
  return '<button type="button" class="palette-row'+(index===paletteIndex?' selected':'')
    +'" data-palette-index="'+index+'"><span>'+esc(item.title)+'</span>'
    +(item.context?'<span class="palette-context">'+esc(item.context)+'</span>':'')
    +(item.hint?'<kbd>'+esc(item.hint)+'</kbd>':'')+'</button>';
}
function renderPalette(){
  const q=String(paletteInput.value||'').trim().toLowerCase();
  const actions=paletteCommands().filter(item=>!q
    ||item.title.toLowerCase().includes(q)||zhValue(item.title).toLowerCase().includes(q));
  const chats=(document.body.classList.contains('hub-mode')||!lastState||!lastState.chats
    ?[]:lastState.chats.items||[])
    .filter(c=>!q||String(c.title).toLowerCase().includes(q)).slice(0,6)
    .map(c=>({title:c.title,context:'Chat',run:()=>{activeChatId=c.id;newTaskMode=false;
      if(resolutionModal.classList.contains('on'))closeResolution();render(lastState);}}));
  paletteItems=[...actions,...chats];
  if(paletteIndex>=paletteItems.length)paletteIndex=0;
  let html='';
  if(actions.length)html+='<div class="palette-section">Actions</div>'
    +actions.map((item,index)=>paletteRow(item,index)).join('');
  if(chats.length)html+='<div class="palette-section">Chats</div>'
    +chats.map((item,index)=>paletteRow(item,actions.length+index)).join('');
  paletteList.innerHTML=html||'<div class="palette-empty">No matching results.</div>';
}
function openPalette(){paletteIndex=0;paletteInput.value='';renderPalette();
  paletteModal.classList.add('on');setTimeout(()=>paletteInput.focus(),0);}
function closePalette(){paletteModal.classList.remove('on');}
function runPaletteItem(index){const item=paletteItems[index];if(!item)return;closePalette();item.run();}
paletteInput.addEventListener('input',()=>{paletteIndex=0;renderPalette();});
paletteInput.addEventListener('keydown',ev=>{
  if(ev.key==='ArrowDown'){ev.preventDefault();
    paletteIndex=Math.min(Math.max(0,paletteItems.length-1),paletteIndex+1);renderPalette();}
  else if(ev.key==='ArrowUp'){ev.preventDefault();paletteIndex=Math.max(0,paletteIndex-1);renderPalette();}
  else if(ev.key==='Enter'){ev.preventDefault();runPaletteItem(paletteIndex);}
});
paletteList.onclick=ev=>{const row=ev.target.closest('[data-palette-index]');
  if(row)runPaletteItem(Number(row.getAttribute('data-palette-index')));};
paletteModal.addEventListener('click',ev=>{if(ev.target===paletteModal)closePalette();});
document.getElementById('palette-open').onclick=openPalette;
document.getElementById('decision-banner-review').onclick=()=>{
  if(!lastState)return;
  const rows=lastState.escalations||[];
  const row=rows[rows.length-1];if(!row)return;
  const exists=(lastState.chats&&lastState.chats.items||[]).some(c=>c.id===row.chat_id);
  if(row.chat_id&&row.chat_id!==activeChatId&&exists){activeChatId=row.chat_id;newTaskMode=false;render(lastState);}
  openResolution(row);
};
window.addEventListener('resize',()=>{if(innerWidth>720)closeRail();});
stopRun.onclick=async()=>{const progress=lastState&&chatProgress(lastState);if(!progress||progress.finished)return;
  stopRun.disabled=true;route.className='route on';route.textContent=currentLocale==='zh'?'正在安全停止…':'Stopping safely…';
  try{await api('/api/run',{action:'cancel',run_id:progress.run_id||''});route.innerHTML=currentLocale==='zh'
    ?'<b>已请求停止。</b> 当前步骤结束后，任务会安全停止。'
    :'<b>Stop requested.</b> The task will stop safely at the next execution boundary.';}
  catch(e){route.className='route on error';route.textContent=e.message;stopRun.disabled=false;}};
form.onsubmit=async ev=>{ev.preventDefault();const rawText=say.value.trim();if(!rawText)return;
  const continuing=pendingContinuation.chat===activeChatId&&Boolean(pendingContinuation.cycle);
  const text=rawText;
  newTaskMode=false;if(lastState)render(lastState);
  send.disabled=true;say.disabled=true;transferBusy=true;document.getElementById('attach').disabled=true;route.className='route on';
  route.textContent=pendingFiles.length?'Sending your files…':'Starting…';
  try{const uploadBatch=pendingFiles.length?await uploadFiles(pendingFiles):null;
    const r=await api('/api/say',{text,chat_id:activeChatId,upload_batch:uploadBatch,attachment_consent:pendingFiles.length>0,
      continuation_cycle:continuing?pendingContinuation.cycle:''});if(r.asked){route.innerHTML='<b class="ask">Needs clarification.</b> '
    + esc(r.clarify);}else{activeChatId=r.chat_id||activeChatId;route.innerHTML=r.lane==='generator'
      ?'<b>Task started.</b> The result will appear in this conversation.'
      :'<b>Message delivered.</b>';
    if(r.lane==='generator')pendingContinuation={cycle:'',chat:''};
    if(!pendingFiles.length||r.attachments_accepted){say.value='';pendingFiles=[];uploadProgress=new Map();fileInput.value='';drawFiles();syncAudience();}}}
  catch(e){route.innerHTML='<b>Refused.</b> '+esc(e.message);}
  transferBusy=false;document.getElementById('attach').disabled=false;send.disabled=false;say.disabled=false;say.focus();};
api('/api/state').then(render).catch(e=>{document.getElementById('thread-title').textContent='Disconnected: '+e.message;});
startStream();
if(location.hash==='#projects')showProjects();
async function initialReadiness(){
  for(let attempt=0;attempt<12;attempt++){
    try{const s=await api('/api/settings');settingsState=s;
      const providers=Object.values(s.providers||{}).filter(p=>p.configured).length;
      const blocked=s.doctor&&s.doctor.status==='blocked';
      if(s.app_mode&&location.hash==='#projects'&&(providers<2||blocked)){
        await openSettings(blocked?'general':'providers');if(blocked)doctorMessage('Required setup needs attention before creating a project.',true);return;}
      if(!s.doctor||s.doctor.status!=='running')return;
    }catch(e){return;}
    await new Promise(resolve=>setTimeout(resolve,500));
  }
}
initialReadiness();
</script></body></html>"""
