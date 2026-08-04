"""The local CrossAudit workspace.

The console deliberately behaves like an agent workspace rather than an
analytics dashboard: tasks on the left, one chronological run in the centre,
and the audit context on the right.  The ledger remains the source of truth;
the page only reshapes committed evidence and ephemeral in-flight progress.

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
:root{
  color-scheme:light;--bg:#f7f7f5;--panel:#fbfbfa;--surface:#fff;
  --surface-2:#f3f3f1;--hover:#ececea;--text:#20201e;--muted:#73736d;
  --faint:#9b9b94;--line:#e6e5e1;--line-strong:#d8d7d2;
  --green:#16845b;--green-bg:#edf8f3;--red:#c94b43;--red-bg:#fff1ef;
  --amber:#a76c12;--amber-bg:#fff7e7;--violet:#6f56c5;--violet-bg:#f2effb;
  --blue:#3574d4;--blue-bg:#edf4ff;--sidebar:244px;--inspector:0px;
  --radius:12px;--inverse:#20201e;--inverse-text:#fff;--send-hover:#353532;
  --header-bg:rgba(255,255,255,.94);--audit-border:#e3ddf6;
  --shadow:0 8px 24px rgba(32,32,30,.06);
}
:root[data-theme="dark"]{
  color-scheme:dark;--bg:#171716;--panel:#1b1b1a;--surface:#20201f;
  --surface-2:#292927;--hover:#30302e;--text:#efefe9;--muted:#aaa9a2;
  --faint:#7f7e78;--line:#343431;--line-strong:#464641;
  --green:#55c696;--green-bg:#193329;--red:#ff8177;--red-bg:#3a2220;
  --amber:#efb554;--amber-bg:#352b18;--violet:#aa94ed;--violet-bg:#2a2638;
  --blue:#75a7f0;--blue-bg:#202c40;--inverse:#efefe9;--inverse-text:#20201e;
  --send-hover:#d9d9d3;--header-bg:rgba(32,32,31,.94);--audit-border:#40385d;
  --shadow:0 10px 30px rgba(0,0,0,.24);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden}
body{background:var(--surface);color:var(--text);font:13px/1.45 Inter,
  -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}
button,textarea,input{font:inherit;color:inherit}
button{cursor:pointer}
.app{height:100vh;display:grid;grid-template-columns:var(--sidebar) minmax(480px,1fr);
  grid-template-rows:48px minmax(0,1fr);background:var(--surface)}
.topbar{grid-column:1/-1;display:flex;align-items:center;gap:10px;padding:0 14px;
  border-bottom:1px solid var(--line);background:var(--header-bg);z-index:5;min-width:0;overflow:hidden}
.brand{display:flex;align-items:center;gap:9px;font-weight:680;letter-spacing:-.02em}
.brand-mark{width:25px;height:25px;border-radius:8px;background:var(--inverse);color:var(--inverse-text);
  display:grid;place-items:center;font-size:12px}.version{font-size:10px;color:var(--muted);
  padding:2px 6px;border:1px solid var(--line);border-radius:5px;font-weight:650}
.top-project{margin-left:12px;padding-left:16px;border-left:1px solid var(--line);
  color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.top-project b{color:var(--text);font-weight:600}.spacer{margin-left:auto}
.live-pill{height:27px;display:flex;align-items:center;gap:7px;padding:0 9px;
  border:1px solid var(--line);border-radius:7px;color:var(--muted);font-size:11px}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--faint)}
.live-dot.on{background:var(--green);box-shadow:0 0 0 3px var(--green-bg)}
.icon-button{border:0;background:transparent;border-radius:7px;width:30px;height:30px;
  display:grid;place-items:center;color:var(--muted)}.icon-button:hover{background:var(--hover)}
.icon-button.pinned{color:var(--violet)}

.sidebar{grid-row:2;background:var(--panel);border-right:1px solid var(--line);
  min-width:0;display:flex;flex-direction:column;padding:10px 9px 12px;overflow:hidden}
.new-task{height:36px;border:1px solid var(--line-strong);background:var(--surface);
  border-radius:9px;padding:0 11px;display:flex;align-items:center;gap:8px;font-weight:570;
  box-shadow:0 1px 2px rgba(32,32,30,.03)}.new-task:hover{background:var(--surface-2)}
.new-task span:last-child{margin-left:auto;color:var(--faint);font-size:11px}
.nav{padding:10px 1px}.nav-item{width:100%;height:32px;padding:0 9px;border:0;
  border-radius:7px;background:transparent;display:flex;align-items:center;gap:9px;
  color:var(--muted);text-align:left}
.nav-item:hover{background:var(--surface-2);color:var(--text)}
.nav-item.active{background:var(--hover);color:var(--text);font-weight:560}
.nav-icon{width:16px;text-align:center;color:var(--faint)}
.side-label{font-size:10px;text-transform:uppercase;letter-spacing:.09em;color:var(--faint);
  padding:13px 10px 7px;font-weight:650}.task-list{overflow:auto;min-height:0}
.task{padding:8px 7px 8px 10px;border-radius:8px;margin-bottom:2px;display:flex;align-items:center;
  gap:6px;cursor:pointer}.task:hover{background:var(--hover)}
.task.active{background:var(--surface);box-shadow:inset 0 0 0 1px var(--line)}
.task-copy{min-width:0;flex:1}.task-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12.5px}
.task-meta{display:flex;align-items:center;gap:6px;margin-top:3px;color:var(--faint);font-size:10.5px}
.pin-button,.task-delete{width:24px;height:24px;border:0;border-radius:6px;background:transparent;color:var(--faint);
  opacity:0;flex:none}.task:hover .pin-button,.task.active .pin-button,.pin-button.pinned,
  .task:hover .task-delete,.task.active .task-delete{opacity:1}
.pin-button:hover{background:var(--hover);color:var(--text)}.pin-button.pinned{color:var(--violet)}
.task-delete:hover{background:var(--red-bg);color:var(--red)}
.state-dot{width:6px;height:6px;border-radius:50%;background:var(--faint)}
.state-dot.PASSED,.state-dot.CONSUMED,.state-dot.passed,.state-dot.consumed{background:var(--green)}
.state-dot.BLOCKED,.state-dot.blocked{background:var(--red)}
.state-dot.ESCALATED,.state-dot.escalated{background:var(--amber)}
.state-dot.running{background:var(--blue);box-shadow:0 0 0 3px var(--blue-bg)}
.sidebar-foot{margin-top:auto;border-top:1px solid var(--line);padding:10px 9px 0;
  color:var(--muted);font-size:11px}.sidebar-foot b{display:block;color:var(--text);
  font-weight:560;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.workspace{grid-row:2;min-width:0;min-height:0;display:flex;flex-direction:column;background:var(--surface)}
.thread-head{height:60px;flex:none;border-bottom:1px solid var(--line);display:flex;
  align-items:center;padding:0 22px;gap:11px}.thread-title{min-width:0}
.thread-title h1{font-size:14px;line-height:1.2;margin:0;font-weight:650;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.01em}
.thread-title p{margin:3px 0 0;color:var(--muted);font-size:11px}
.status{font-size:10px;line-height:1;padding:5px 7px;border-radius:6px;font-weight:700;
  text-transform:uppercase;letter-spacing:.04em;background:var(--surface-2);color:var(--muted)}
.status.PASS,.status.PASSED,.status.CONSUMED,.status.passed{background:var(--green-bg);color:var(--green)}
.status.BLOCKED,.status.blocked,.status.failed,.status.refused{background:var(--red-bg);color:var(--red)}
.status.ESCALATED,.status.escalated{background:var(--amber-bg);color:var(--amber)}
.status.running{background:var(--blue-bg);color:var(--blue)}
.runtime-button{height:29px;border:1px solid var(--line);border-radius:8px;background:var(--surface);
  color:var(--muted);padding:0 9px;font-size:10.5px;white-space:nowrap}.runtime-button:hover{
  background:var(--hover);color:var(--text)}
.thread{flex:1;overflow:auto;min-height:0;scrollbar-gutter:stable;overscroll-behavior:contain;
  scroll-padding-bottom:var(--composer-clearance,180px);scrollbar-width:thin;scrollbar-color:var(--line-strong) transparent}
.thread::-webkit-scrollbar{width:10px}.thread::-webkit-scrollbar-track{background:transparent}
.thread::-webkit-scrollbar-thumb{background:var(--line-strong);border:3px solid transparent;border-radius:10px;background-clip:padding-box}
.thread-inner{width:min(760px,calc(100% - 48px));margin:0 auto;
  padding:28px 0 calc(var(--composer-clearance,180px) + 28px)}
.welcome{padding:56px 20px 26px;text-align:center}.welcome-mark{width:38px;height:38px;
  margin:0 auto 15px;border-radius:12px;background:var(--inverse);color:var(--inverse-text);display:grid;
  place-items:center;font-size:17px}.welcome h2{font-size:19px;margin:0;letter-spacing:-.025em}
.welcome p{color:var(--muted);max-width:480px;margin:8px auto 0;line-height:1.6}
.turn{display:grid;grid-template-columns:28px minmax(0,1fr);gap:11px;margin-bottom:24px}
.avatar{width:25px;height:25px;border:1px solid var(--line);border-radius:8px;display:grid;
  place-items:center;font-size:10px;font-weight:700;background:var(--panel);color:var(--muted)}
.turn.user .avatar{background:var(--inverse);border-color:var(--inverse);color:var(--inverse-text)}
.turn.audit .avatar{background:var(--violet-bg);border-color:var(--audit-border);color:var(--violet)}
.turn-main{min-width:0}.turn-meta{height:25px;display:flex;align-items:center;gap:7px;
  font-size:11px;color:var(--faint)}.turn-meta b{color:var(--text);font-weight:600}
.turn-time{margin-left:auto}.turn-body{font-size:13.5px;white-space:pre-wrap;
  word-break:break-word;line-height:1.58}.turn-sub{margin-top:7px;color:var(--muted);font-size:11.5px}
.route-note{margin-top:8px;padding:8px 10px;border-left:2px solid var(--line-strong);
  background:var(--panel);color:var(--muted);font-size:11.5px;white-space:pre-wrap;word-break:break-word}
.direct-mark{font-size:9.5px;padding:3px 6px;border-radius:5px;background:var(--blue-bg);color:var(--blue);
  font-weight:650}.participants{display:flex;align-items:center;margin-right:5px}.participant{width:23px;height:23px;
  margin-left:-5px;border:2px solid var(--surface);border-radius:50%;display:grid;place-items:center;
  background:var(--surface-2);font-size:8.5px;font-weight:750;color:var(--muted)}
.participant:first-child{margin-left:0;background:var(--inverse);color:var(--inverse-text)}
.participant.auditor{background:var(--violet-bg);color:var(--violet)}
.finding{margin-top:9px;border:1px solid var(--line);border-radius:9px;padding:10px 11px}
.finding-head{display:flex;align-items:center;gap:7px;font-size:10.5px;color:var(--muted)}
.severity{font-weight:700;color:var(--red)}.finding p{margin:5px 0 0;line-height:1.5}
.output-files{margin-top:11px}.output-head{display:flex;align-items:center;gap:7px;margin-bottom:6px;
  color:var(--muted);font-size:10.5px;font-weight:600}.output-count{font-weight:400;color:var(--faint)}
.artifact-list{display:grid;gap:6px}.output-file{min-width:0;border:1px solid var(--line);
  border-radius:9px;padding:0;display:flex;align-items:stretch;gap:0;background:var(--panel);
  color:inherit;text-decoration:none}.output-file:hover{border-color:var(--line-strong);background:var(--surface-2)}
.output-file.unavailable{opacity:.62}.output-file.unavailable:hover{border-color:var(--line);background:var(--panel)}
.artifact-main{display:flex;align-items:center;gap:9px;min-width:0;flex:1;padding:8px 9px;
  color:inherit;text-decoration:none;border:0;background:transparent;text-align:left;cursor:pointer}
.artifact-main:hover{color:inherit}.artifact-actions{display:flex;align-items:center;padding:5px;border-left:1px solid var(--line)}
.artifact-icon{width:31px;height:31px;flex:none;border-radius:7px;background:var(--blue-bg);color:var(--blue);
  display:grid;place-items:center;font-size:8.5px;font-weight:700;letter-spacing:.02em}
.artifact-copy{min-width:0}.artifact-name{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace}
.artifact-context{display:block;font-size:9.5px;color:var(--faint);margin-top:2px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}.artifact-action{width:28px;height:28px;display:grid;place-items:center;
  flex:none;color:var(--muted);font-size:13px;text-decoration:none;border-radius:6px}.artifact-action:hover{background:var(--hover);color:var(--text)}
.output-more{margin-top:6px;padding:2px 0;border:0;background:transparent;color:var(--blue);
  font:inherit;font-size:10.5px;cursor:pointer}.output-more:hover{text-decoration:underline}
.preview-wizard{width:min(1040px,calc(100% - 32px));height:min(820px,calc(100vh - 40px));
  display:flex;flex-direction:column;overflow:hidden}.preview-wizard .wizard-head{flex:none}
.preview-body{min-height:0;flex:1;overflow:auto;background:var(--surface-2);padding:18px;display:grid;place-items:center}
.preview-loading,.preview-unavailable{color:var(--muted);font-size:12px;text-align:center;max-width:560px;line-height:1.6}
.preview-frame{width:100%;height:100%;min-height:520px;border:1px solid var(--line);border-radius:9px;background:#fff}
.preview-image{display:block;max-width:100%;max-height:100%;object-fit:contain;border-radius:7px;box-shadow:var(--shadow)}
.preview-code,.preview-document,.preview-markdown{width:min(820px,100%);min-height:100%;margin:0;padding:28px 32px;
  border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--text);box-shadow:0 1px 2px rgba(0,0,0,.04)}
.preview-code{white-space:pre-wrap;word-break:break-word;font:11.5px/1.62 ui-monospace,SFMono-Regular,Menlo,monospace}
.preview-document{white-space:pre-wrap;word-break:break-word;font:13.5px/1.7 ui-serif,Georgia,serif}
.preview-markdown{font-size:13.5px;line-height:1.65}.preview-markdown h1,.preview-markdown h2,.preview-markdown h3{line-height:1.25}
.preview-markdown pre{overflow:auto;padding:12px;border-radius:7px;background:var(--surface-2)}
.preview-markdown code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.preview-markdown table{border-collapse:collapse;width:100%}
.preview-markdown th,.preview-markdown td{border:1px solid var(--line);padding:6px 8px;text-align:left}.preview-markdown blockquote{margin-left:0;padding-left:12px;border-left:3px solid var(--line-strong);color:var(--muted)}
.preview-note{min-height:34px;padding:9px 18px;border-top:1px solid var(--line);color:var(--muted);font-size:10.5px;background:var(--panel)}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0,0,0,0);white-space:nowrap;border:0}
.view-heading{padding:4px 0 22px}.view-heading h2{font-size:18px;margin:0;
  letter-spacing:-.025em}.view-heading p{margin:5px 0 0;color:var(--muted)}
.artifact-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.artifact-grid .output-file{margin:0;min-width:0}
.usage-note{display:flex;align-items:flex-start;gap:9px;margin:-10px 0 18px;padding:10px 11px;
  border:1px solid var(--line);border-radius:9px;background:var(--panel);color:var(--muted);font-size:10.5px}
.usage-note b{color:var(--text);font-weight:650}.usage-note span:first-child{color:var(--blue)}
.usage-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:24px}
.usage-card{border:1px solid var(--line);border-radius:11px;padding:13px;background:var(--panel);min-width:0}
.usage-card-label{font-size:9.5px;color:var(--faint);text-transform:uppercase;letter-spacing:.07em;font-weight:680}
.usage-card-value{font-size:21px;font-weight:680;letter-spacing:-.04em;margin-top:6px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}.usage-card-detail{font-size:9.5px;color:var(--muted);margin-top:3px}
.usage-section{margin:0 0 26px}.usage-section-head{display:flex;align-items:baseline;gap:8px;margin-bottom:10px}
.usage-section-head h3{font-size:12.5px;margin:0}.usage-section-head span{color:var(--faint);font-size:9.5px}
.usage-bars{height:122px;display:grid;grid-template-columns:repeat(7,1fr);gap:8px;align-items:end;
  padding:12px 12px 8px;border:1px solid var(--line);border-radius:11px;background:var(--panel)}
.usage-day{height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:5px;min-width:0}
.usage-day-value{font-size:8.5px;color:var(--faint);white-space:nowrap}.usage-bar-track{height:75px;width:100%;
  max-width:28px;display:flex;align-items:flex-end;border-radius:5px;background:var(--surface-2);overflow:hidden}
.usage-bar{width:100%;min-height:2px;border-radius:5px;background:var(--blue)}
.usage-day-label{font-size:8.5px;color:var(--muted)}
.usage-roles{display:grid;grid-template-columns:1fr 1fr;gap:8px}.usage-role{border:1px solid var(--line);
  border-radius:10px;padding:11px 12px;background:var(--panel)}.usage-role-top{display:flex;align-items:center;gap:7px}
.usage-role-top b{font-size:11.5px;text-transform:capitalize}.usage-role-top span{margin-left:auto;color:var(--muted);
  font-size:10.5px}.usage-role-meter{height:4px;background:var(--surface-2);border-radius:9px;overflow:hidden;margin:9px 0 5px}
.usage-role-meter i{height:100%;display:block;background:var(--blue);border-radius:inherit}.usage-role.auditor i{background:var(--violet)}
.usage-role small{color:var(--faint);font-size:9.5px}
.usage-table{border:1px solid var(--line);border-radius:11px;overflow:hidden;background:var(--surface)}
.usage-row{display:grid;grid-template-columns:minmax(160px,1fr) 86px 84px 84px 78px;gap:10px;
  align-items:center;padding:10px 12px;border-bottom:1px solid var(--line);font-size:10.5px}
.usage-row:last-child{border-bottom:0}.usage-row.head{background:var(--panel);color:var(--faint);font-size:9px;
  text-transform:uppercase;letter-spacing:.05em;font-weight:650}.usage-model{min-width:0}.usage-model b{display:block;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font:10.5px ui-monospace,SFMono-Regular,Menlo,monospace}
.usage-model small{color:var(--faint);text-transform:capitalize}.usage-quality{display:inline-flex;width:max-content;
  padding:3px 5px;border-radius:5px;background:var(--green-bg);color:var(--green);font-size:8.5px;font-weight:700}
.usage-quality.estimated{background:var(--amber-bg);color:var(--amber)}.usage-quality.unpriced{background:var(--surface-2);color:var(--muted)}
.usage-recent{display:grid;gap:3px}.usage-call{display:grid;grid-template-columns:24px minmax(0,1fr) auto;
  gap:9px;align-items:center;padding:8px;border-radius:8px}.usage-call:hover{background:var(--panel)}
.usage-call-mark{width:23px;height:23px;border-radius:7px;display:grid;place-items:center;background:var(--blue-bg);
  color:var(--blue);font-size:8px;font-weight:750}.usage-call-mark.auditor{background:var(--violet-bg);color:var(--violet)}
.usage-call-main{min-width:0}.usage-call-main b{display:block;font-size:10.5px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}.usage-call-main span{font-size:9.5px;color:var(--faint)}.usage-call-value{text-align:right}
.usage-call-value b{display:block;font-size:10.5px}.usage-call-value span{display:block;color:var(--faint);font-size:9px}
.delivery-status{margin:2px 0 24px;border:1px solid var(--line);border-radius:10px;padding:10px 12px;
  background:var(--panel);display:flex;align-items:center;gap:9px;color:var(--muted);font-size:11.5px}
.delivery-status .delivery-dot{width:7px;height:7px;border-radius:50%;background:var(--blue);flex:none}
.delivery-status.passed .delivery-dot,.delivery-status.CONSUMED .delivery-dot{background:var(--green)}
.delivery-status.blocked .delivery-dot{background:var(--red)}.delivery-status.escalated .delivery-dot{background:var(--amber)}
.delivery-status b{color:var(--text);font-weight:620}.delivery-status button{margin-left:auto;border:0;
  background:transparent;color:var(--muted);font-size:10.5px}.delivery-status button:hover{color:var(--text)}

.run-card{border:1px solid var(--line-strong);border-radius:14px;margin:4px 0 25px;overflow:hidden;
  background:var(--surface);box-shadow:var(--shadow)}
.run-overview{padding:15px 16px 14px;background:linear-gradient(145deg,var(--panel),var(--surface));
  border-bottom:1px solid var(--line)}
.run-top{display:flex;align-items:center;gap:8px}.run-eyebrow{font-size:10px;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);font-weight:700}.run-top .status{margin-left:auto}
.run-task{font-size:15px;line-height:1.35;font-weight:650;letter-spacing:-.015em;margin:8px 0 7px;
  overflow-wrap:anywhere}.run-meta{display:flex;align-items:center;gap:7px;color:var(--faint);font-size:10.5px}
.run-meta span{display:flex;align-items:center;gap:4px}.run-meta span+span:before{content:'·';margin-right:3px}
.run-meta strong{color:var(--text);font-weight:620}.run-meter{height:3px;border-radius:99px;background:var(--surface-2);
  overflow:hidden;margin-top:11px}.run-meter i{height:100%;display:block;border-radius:inherit;background:var(--blue);
  transition:width .22s ease}.run-card.passed .run-meter i,.run-card.CONSUMED .run-meter i{background:var(--green)}
.run-card.blocked .run-meter i,.run-card.refused .run-meter i{background:var(--red)}
.run-card.escalated .run-meter i{background:var(--amber)}
.pulse{width:7px;height:7px;border-radius:50%;background:var(--blue);
  animation:pulse 1.2s ease-in-out infinite}.pulse.done{animation:none;background:var(--green)}
.pulse.bad{animation:none;background:var(--red)}.pulse.warn{animation:none;background:var(--amber)}
@keyframes pulse{0%,100%{opacity:.25}50%{opacity:1}}
.loop{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));padding:17px 16px 13px;gap:0}
.loop-step{min-width:0;position:relative;padding-right:12px}.loop-step:last-child{padding-right:0}
.loop-track{height:24px;position:relative}.loop-step:not(:last-child) .loop-track:after{content:'';
  position:absolute;top:11px;left:27px;right:4px;height:1px;background:var(--line-strong)}
.loop-step.done:not(:last-child) .loop-track:after{background:var(--green)}
.loop-mark{position:relative;z-index:1;width:23px;height:23px;border-radius:50%;background:var(--surface);
  border:1.5px solid var(--line-strong);display:grid;place-items:center;font-size:9px;color:var(--faint);
  font-weight:750;box-shadow:0 0 0 3px var(--surface)}
.loop-step.done .loop-mark{background:var(--green);border-color:var(--green)}
.loop-step.failed .loop-mark{background:var(--red);border-color:var(--red)}
.loop-step.current .loop-mark{background:var(--blue);border-color:var(--blue);
  box-shadow:0 0 0 3px var(--blue-bg)}
.loop-step.done .loop-mark,.loop-step.failed .loop-mark,.loop-step.current .loop-mark{color:#fff}
.loop-name{font-size:11px;margin-top:7px;font-weight:620;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}.loop-index{color:var(--faint);font-size:8.5px;font-weight:650;margin-right:4px}
.loop-detail{font-size:9.5px;color:var(--faint);margin-top:3px;line-height:1.35;display:-webkit-box;
  -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:26px}
.loop-state{font-size:8.5px;margin-top:5px;color:var(--faint);text-transform:uppercase;letter-spacing:.06em;
  font-weight:700}.loop-step.done .loop-state{color:var(--green)}.loop-step.failed .loop-state{color:var(--red)}
.loop-step.current .loop-state{color:var(--blue)}
.loop-focus{margin:0 16px 15px;padding:10px 11px;border:1px solid var(--line);border-radius:9px;
  background:var(--panel);display:grid;grid-template-columns:88px minmax(0,1fr);gap:8px 12px;align-items:start}
.loop-focus-label{font-size:9px;color:var(--faint);text-transform:uppercase;letter-spacing:.08em;
  font-weight:700;padding-top:2px}.loop-focus-copy b{display:block;font-size:11.5px;font-weight:650}
.loop-focus-copy p{margin:2px 0 0;color:var(--muted);font-size:10.5px;line-height:1.45}
.loop-focus.current{border-color:var(--blue);background:var(--blue-bg)}
.loop-focus.failed{border-color:var(--red);background:var(--red-bg)}
.loop-focus.done{border-color:var(--green);background:var(--green-bg)}
.activity{border-top:1px solid var(--line);padding:12px 16px 14px;background:var(--panel)}
.activity-head{display:flex;align-items:center;margin-bottom:7px;font-size:10px;font-weight:680;
  text-transform:uppercase;letter-spacing:.075em;color:var(--muted)}.activity-head span{margin-left:auto;
  color:var(--faint);font-weight:550;text-transform:none;letter-spacing:0}
.activity-list{display:grid;gap:2px;max-height:190px;overflow:auto}.audit-event{display:grid;
  grid-template-columns:24px minmax(0,1fr) auto;gap:9px;align-items:start;padding:6px 5px;border-radius:7px}
.audit-event:hover{background:var(--hover)}.event-mark{width:22px;height:22px;border-radius:7px;display:grid;
  place-items:center;background:var(--surface-2);color:var(--muted);font-size:8.5px;font-weight:760}
.event-mark.generator{background:var(--blue-bg);color:var(--blue)}.event-mark.auditor{background:var(--violet-bg);
  color:var(--violet)}.event-mark.compute{background:var(--amber-bg);color:var(--amber)}.event-mark.tool{background:var(--green-bg);color:var(--green)}.event-mark.done{background:var(--green-bg);color:var(--green)}
.event-main{min-width:0}.event-line{font-size:10.8px;line-height:1.35}.event-line b{font-weight:650;
  margin-right:6px}.event-detail{color:var(--faint);font-size:9.8px;line-height:1.4;margin-top:2px;
  white-space:pre-wrap;overflow-wrap:anywhere}.event-time{color:var(--faint);font-size:9px;padding-top:2px}
.activity-empty{padding:6px 4px;color:var(--faint);font-size:10.5px;line-height:1.45}
.audit-evidence-head{display:flex;align-items:baseline;gap:8px;margin:24px 0 12px;padding-top:1px}
.audit-evidence-head h3{margin:0;font-size:13px}.audit-evidence-head span{color:var(--faint);font-size:10px}
.interrupted{margin-bottom:20px;padding:10px 12px;background:var(--amber-bg);color:var(--amber);
  border-radius:9px;font-size:12px;display:none}.interrupted.on{display:block}
.interrupted-actions{display:flex;gap:7px;margin-top:9px}.interrupted-actions button{height:29px;border-radius:7px;
  border:1px solid currentColor;background:var(--surface);color:var(--amber);padding:0 10px;cursor:pointer}

.composer-wrap{position:absolute;left:var(--sidebar);right:var(--inspector);bottom:0;
  padding:28px 22px 16px;background:linear-gradient(transparent,var(--surface) 30%);z-index:4}
.composer-wrap.view-hidden{display:none}
.composer{width:min(760px,100%);margin:0 auto;border:1px solid var(--line-strong);
  border-radius:14px;background:var(--surface);box-shadow:0 8px 28px rgba(32,32,30,.10);
  padding:8px}.composer.drag{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-bg),var(--shadow)}
.contract-preview{display:none;margin:1px 3px 7px;padding:7px 9px;border-radius:8px;background:var(--blue-bg);
  color:var(--muted);font-size:10px;line-height:1.4}.contract-preview.on{display:block}.contract-preview b{color:var(--blue)}
.task-choices{display:none;margin:2px 3px 8px;padding:11px;border:1px solid var(--line);border-radius:10px;
  background:var(--panel)}.task-choices.on{display:block}.choice-head{display:flex;gap:10px;align-items:flex-start;
  margin-bottom:9px}.choice-head b{display:block;font-size:11.5px}.choice-head span{display:block;color:var(--muted);
  font-size:10px;margin-top:2px}.choice-close{margin-left:auto;border:0;background:transparent;color:var(--faint);
  font-size:16px}.choice-group{display:grid;grid-template-columns:72px minmax(0,1fr);gap:7px;align-items:start;
  margin-top:7px}.choice-label{font-size:9.5px;color:var(--faint);padding-top:6px;text-transform:uppercase;
  letter-spacing:.06em;font-weight:650}.choice-options{display:flex;gap:5px;flex-wrap:wrap}.choice-option input{position:absolute;
  opacity:0;pointer-events:none}.choice-option span{display:block;border:1px solid var(--line);border-radius:7px;
  background:var(--surface);padding:5px 8px;font-size:9.5px;color:var(--muted);cursor:pointer}
.choice-option input:checked+span{border-color:var(--blue);background:var(--blue-bg);color:var(--blue);
  font-weight:650}.choice-option input:disabled+span{opacity:.42;cursor:not-allowed;text-decoration:line-through}
.choice-note{font-size:9.5px;color:var(--faint);margin:7px 0 0 79px}.choice-actions{display:flex;
  justify-content:flex-end;gap:6px;margin-top:10px}.choice-actions button{height:29px;font-size:10px}
.attachments{display:none;gap:6px;padding:3px 3px 8px;max-height:172px;overflow:auto}
.attachments.on{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr))}
.attachment{position:relative;display:grid;grid-template-columns:28px minmax(0,1fr) 20px;align-items:center;
  gap:7px;background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:7px 7px;
  min-width:0;overflow:hidden}.attachment-type{width:28px;height:28px;border-radius:7px;background:var(--surface);
  border:1px solid var(--line);display:grid;place-items:center;color:var(--blue);font-size:8px;font-weight:750}
.attachment-copy{min-width:0}.attachment-name{display:block;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-size:10.5px;font-weight:590}.attachment-state{display:block;color:var(--faint);
  font-size:9.5px;margin-top:1px}.attachment button{border:0;background:none;color:var(--faint);padding:0;
  width:20px;height:20px;border-radius:5px}.attachment button:hover{background:var(--hover);color:var(--text)}
.attachment-progress{position:absolute;left:0;right:0;bottom:0;height:2px;background:transparent}
.attachment-progress i{display:block;height:100%;background:var(--blue);transition:width .12s ease}
.attachment.failed{border-color:var(--red)}.attachment.failed .attachment-state{color:var(--red)}
.attachment-note{grid-column:1/-1;color:var(--muted);font-size:10.5px;padding:1px 2px;display:flex;gap:7px;
  align-items:center}.attachment-note b{color:var(--text);font-weight:620}.attachment-more{color:var(--blue)}
.transfer-consent{display:none;margin:6px 3px 1px;padding:9px 10px;border-radius:9px;
  background:var(--amber-bg);color:var(--muted);font-size:11px;align-items:center;gap:10px}
.transfer-consent.on{display:flex}.transfer-consent b{display:block;color:var(--amber);font-weight:650}
.transfer-consent button{margin-left:auto;flex:none;border:0;border-radius:7px;padding:7px 9px;
  background:var(--inverse);color:var(--inverse-text);font-weight:600}
.audience-bar{display:flex;align-items:center;gap:5px;padding:1px 3px 5px}.audience-label{font-size:9.5px;
  color:var(--faint);margin-right:2px}.audience-chip{height:23px;border:1px solid var(--line);border-radius:6px;
  background:transparent;color:var(--muted);padding:0 7px;font-size:9.5px}.audience-chip:hover{background:var(--hover)}
.audience-chip.active{background:var(--surface-2);color:var(--text);border-color:var(--line-strong);font-weight:620}
.compose-row{display:flex;align-items:flex-end;gap:7px}textarea{border:0;outline:0;resize:none;
  min-height:42px;max-height:150px;flex:1;padding:10px 7px 8px;background:transparent;line-height:1.45}
textarea::placeholder{color:var(--faint)}.compose-button{border:0;background:transparent;
  width:34px;height:34px;border-radius:9px;display:grid;place-items:center;color:var(--muted);flex:none}
.compose-button:hover{background:var(--hover)}.send{background:var(--inverse);color:var(--inverse-text)}
.send:hover{background:var(--send-hover)}.send:disabled{opacity:.35;cursor:default}
.stop{background:var(--red);color:var(--inverse-text)}
.composer-meta{display:flex;align-items:center;gap:8px;padding:4px 5px 1px;color:var(--faint);font-size:10px}
.route{display:none;margin:7px 3px 0;padding:7px 9px;border-radius:7px;background:var(--surface-2);
  color:var(--muted);font-size:11px;white-space:pre-wrap;word-break:break-word}.route.on{display:block}
.drop-overlay{position:fixed;inset:0;z-index:100;display:none;place-items:center;padding:26px;
  pointer-events:none;background:color-mix(in srgb,var(--surface) 76%,transparent);backdrop-filter:blur(5px)}
.drop-overlay.on{display:grid}.drop-target{width:min(560px,calc(100vw - 52px));min-height:240px;
  border:2px dashed var(--blue);border-radius:20px;background:var(--surface);box-shadow:var(--shadow);
  display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:36px}
.drop-icon{width:48px;height:48px;border-radius:14px;background:var(--blue-bg);color:var(--blue);
  display:grid;place-items:center;font-size:27px;margin-bottom:14px}.drop-target b{font-size:17px}
.drop-target span{color:var(--muted);font-size:12px;margin-top:6px;max-width:380px}
.route b{color:var(--text)}.route .ask{color:var(--amber)}

.inspector{position:fixed;right:0;top:48px;bottom:0;width:min(296px,100vw);z-index:12;
  border-left:1px solid var(--line);background:var(--panel);overflow:auto;padding:15px 14px;
  box-shadow:var(--shadow);transform:translateX(102%);transition:transform .18s ease}
.inspector.open{transform:translateX(0)}.inspect-head{display:flex;align-items:center;height:30px;margin-bottom:8px}
.inspect-head h2{font-size:12.5px;margin:0;font-weight:650}.inspect-section{border-top:1px solid var(--line);
  padding:14px 1px}.inspect-section:first-of-type{border-top:0}.inspect-title{font-size:10px;
  color:var(--faint);text-transform:uppercase;letter-spacing:.08em;font-weight:650;margin-bottom:9px}
.kv{display:flex;gap:10px;padding:4px 0;font-size:11.5px}.kv span:first-child{color:var(--muted)}
.kv span:last-child{margin-left:auto;text-align:right;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;max-width:175px}.model{padding:8px 9px;border:1px solid var(--line);border-radius:8px;
  background:var(--surface);margin-bottom:6px}.model-role{font-size:9.5px;color:var(--faint);text-transform:uppercase;
  letter-spacing:.06em}.model-name{font-size:11px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.contract{font:10.5px ui-monospace,SFMono-Regular,Menlo,monospace;padding:4px 0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mini-metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.mini-metric{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:8px}
.mini-value{font-size:17px;font-weight:650;letter-spacing:-.03em}.mini-label{font-size:9.5px;color:var(--faint)}
.escalation{padding:8px 9px;background:var(--amber-bg);border-radius:8px;margin-bottom:6px}
.escalation b{font-size:11px;color:var(--amber)}.escalation p{font-size:10.5px;color:var(--muted);margin:3px 0 0}
.escalation-actions{display:flex;gap:5px;margin-top:8px}.escalation-actions button{height:25px;font-size:9px}
.decision-wizard{width:min(760px,100%)}.decision-flag{display:inline-flex;align-items:center;gap:6px;
  color:var(--amber);font-size:9px;font-weight:750;letter-spacing:.08em;text-transform:uppercase;margin-bottom:7px}
.decision-flag:before{content:'!';display:grid;place-items:center;width:17px;height:17px;border-radius:50%;
  background:var(--amber-bg);font-size:10px}.decision-limit{display:flex;gap:12px;align-items:flex-start;padding:13px 14px;
  border:1px solid color-mix(in srgb,var(--amber) 42%,var(--line));background:var(--amber-bg);border-radius:10px}
.decision-limit-mark{display:grid;place-items:center;flex:none;width:29px;height:29px;border-radius:9px;
  background:var(--surface);color:var(--amber);font-weight:750}.decision-limit b{display:block;font-size:12px}
.decision-limit p{margin:3px 0 0;color:var(--muted);font-size:10.5px;line-height:1.45}
.decision-section{margin-top:20px}.decision-title{display:flex;align-items:center;gap:8px;font-size:11px;
  font-weight:700;margin-bottom:9px}.decision-count{border-radius:9px;background:var(--red-bg);color:var(--red);
  padding:2px 6px;font-size:9px}.decision-issues{display:grid;gap:7px}.decision-issue{border:1px solid var(--line);
  border-radius:9px;padding:10px 11px;background:var(--panel)}.decision-issue-head{display:flex;gap:7px;
  align-items:center;font-size:9.5px;color:var(--faint)}.decision-issue-head b{color:var(--red);font-size:9.5px}
.decision-issue p{margin:5px 0 0;font-size:11px;line-height:1.5;color:var(--text)}
.decision-empty{border:1px solid var(--line);border-radius:9px;padding:11px;color:var(--muted);
  font-size:10.5px;line-height:1.5}.decision-request{color:var(--muted);font-size:10.5px;line-height:1.5;margin:0 0 10px}
.decision-options{display:grid;grid-template-columns:1fr 1fr;gap:9px}.decision-option{position:relative;
  display:flex;gap:10px;padding:12px;border:1px solid var(--line-strong);border-radius:10px;background:var(--surface);
  cursor:pointer}.decision-option:hover{background:var(--hover)}.decision-option:has(input:checked){border-color:var(--blue);
  box-shadow:0 0 0 2px var(--blue-bg)}.decision-option input{margin-top:2px}.decision-option b{display:block;font-size:11.5px}
.decision-option small{display:block;margin-top:3px;color:var(--muted);font-size:10px;line-height:1.45}
.decision-guidance{margin-top:13px}.decision-guidance textarea{min-height:86px}.decision-ledger-note{display:flex;
  gap:6px;align-items:center;color:var(--muted);font-size:10px;margin-top:8px}.decision-ledger-note b{color:var(--text)}
.empty{color:var(--faint);font-style:italic;font-size:11.5px;padding:5px 0}
.files{white-space:pre-wrap;word-break:break-word}.mobile-sidebar{display:none}.mobile-inspector{display:grid}
#inspect-close{display:grid}.scrim{display:none;position:fixed;inset:48px 0 0;
  z-index:9;border:0;background:rgba(0,0,0,.34);padding:0}.scrim.on{display:block}
.scrim.inspector-open{right:min(296px,100vw)}

@media(max-width:1120px){
  :root{--inspector:0px}.app{grid-template-columns:var(--sidebar) minmax(0,1fr)}
  .inspector{position:fixed;right:0;top:48px;bottom:0;width:min(296px,100vw);z-index:12;box-shadow:var(--shadow);
    transform:translateX(102%);transition:transform .18s ease}.inspector.open{transform:translateX(0)}
  .mobile-inspector,#inspect-close{display:grid}.composer-wrap{right:0}
}
@media(max-width:720px){
  :root{--sidebar:0px}.app{grid-template-columns:1fr}.sidebar{position:fixed;left:0;top:48px;bottom:0;
    width:min(244px,calc(100vw - 44px));z-index:12;box-shadow:var(--shadow);
    transform:translateX(-102%);transition:transform .18s ease}.sidebar.open{transform:translateX(0)}
  .mobile-sidebar{display:grid}
  .scrim.sidebar-open{left:min(244px,calc(100vw - 44px))}
  .top-project{margin-left:2px;padding-left:10px}.thread-inner{width:calc(100% - 28px)}
  .thread-head{padding:0 14px}.composer-wrap{left:0;padding:24px 12px 10px}.loop-detail{display:none}
  .artifact-grid{grid-template-columns:1fr}
  .usage-cards{grid-template-columns:1fr 1fr}.usage-row{grid-template-columns:minmax(120px,1fr) 76px 72px}
  .usage-row>*:nth-child(3),.usage-row>*:nth-child(4){display:none}
}
@media(max-width:560px){
  .topbar{padding:0 8px;gap:6px}.top-project{display:none}.live-pill{width:27px;padding:0;justify-content:center}
  .runtime-button{width:29px;padding:0;font-size:0}.runtime-button:after{content:'⌁';font-size:15px}
  #conn-text{display:none}.thread-head{height:54px}.thread-inner{padding-top:20px}
  .composer-meta #model-summary{display:none}.composer-meta{justify-content:flex-end}
  .turn-meta{height:auto;min-height:25px;flex-wrap:wrap}.finding-head{flex-wrap:wrap}
  .finding-head .spacer{display:none}.finding-head span:last-child{width:100%;overflow-wrap:anywhere}
  .run-overview{padding:13px 12px}.run-task{font-size:13.5px}.run-meta{flex-wrap:wrap}
  .loop{grid-template-columns:1fr;gap:0;padding:14px 12px 7px}
  .loop-step{display:grid;grid-template-columns:31px minmax(0,1fr) auto;grid-template-rows:auto auto;
    padding:0 0 11px;align-items:start}
  .loop-track{grid-row:1/3;height:auto;align-self:stretch}.loop-step:not(:last-child) .loop-track:after{
    top:25px;bottom:-8px;left:11px;right:auto;width:1px;height:auto}
  .loop-name{grid-column:2;grid-row:1;margin:3px 0 0}.loop-state{grid-column:3;grid-row:1;margin:4px 0 0 8px}
  .loop-detail{display:block;grid-column:2/4;grid-row:2;margin:3px 0 0;min-height:0;-webkit-line-clamp:3}
  .loop-focus{margin:0 12px 12px;grid-template-columns:1fr;gap:3px}.activity{padding:11px 12px 13px}
  .audit-event{grid-template-columns:24px minmax(0,1fr)}.event-time{grid-column:2;margin-top:-2px}
  .choice-group{grid-template-columns:1fr}.choice-label{padding-top:0}.choice-note{margin-left:0}
  .decision-options{grid-template-columns:1fr}
  .usage-roles{grid-template-columns:1fr}.usage-cards{grid-template-columns:1fr 1fr}.usage-card-value{font-size:18px}
  .usage-bars{gap:4px;padding-left:6px;padding-right:6px}.usage-day-value{display:none}
  .preview-wizard{width:100%;height:100vh;max-height:none;border-radius:0}.preview-body{padding:8px}
  .preview-code,.preview-document,.preview-markdown{padding:18px 16px;border-radius:7px}.preview-frame{min-height:420px}
  .hpc-connection-grid,.hpc-limit-grid{grid-template-columns:1fr}.hpc-connection-grid .field:nth-child(2){grid-column:auto}
  .hpc-setup-section{padding:12px}.hpc-host-wizard .wizard-head p{max-width:280px}
}
@media(max-width:380px){
  .version{display:none}.brand{gap:7px}.thread-title p{display:none}.status{padding:4px 6px}
  .composer-wrap{padding-left:8px;padding-right:8px}.thread-inner{width:calc(100% - 20px)}
}
@media(prefers-reduced-motion:reduce){.pulse{animation:none}.inspector,.sidebar{transition:none}}

/* The project control plane is deliberately quieter than a dashboard: one
   compact list, one primary action, and the same tokens as the project view. */
.project-hub{display:none;height:100vh;background:var(--bg);overflow:auto}
body.hub-mode .app{display:none}body.hub-mode .project-hub{display:block}
.hub-bar{height:58px;padding:0 28px;display:flex;align-items:center;gap:12px;
  border-bottom:1px solid var(--line);background:var(--header-bg);position:sticky;top:0;z-index:8}
.brand-button{border:0;background:transparent;padding:0;display:flex;align-items:center;
  gap:9px;font-weight:680}.brand-button:hover{opacity:.76}
.primary{height:34px;border:0;border-radius:8px;padding:0 13px;background:var(--inverse);
  color:var(--inverse-text);font-weight:620}.primary:hover{background:var(--send-hover)}
.primary:disabled{opacity:.45;cursor:not-allowed}.secondary{height:34px;border:1px solid var(--line-strong);
  border-radius:8px;padding:0 12px;background:var(--surface);display:inline-flex;align-items:center;
  justify-content:center;text-decoration:none;color:var(--text)}.secondary:hover{background:var(--hover)}
.hub-main{width:min(1100px,calc(100% - 48px));margin:0 auto;padding:44px 0 72px}
.hub-heading{display:flex;gap:18px;align-items:flex-end;margin-bottom:26px}.hub-heading h1{margin:0;
  font-size:26px;letter-spacing:-.035em}.hub-heading p{margin:5px 0 0;color:var(--muted)}
.hub-summary{margin-left:auto;color:var(--muted);font-size:12px}.hub-tools{display:flex;gap:9px;
  margin-bottom:14px}.hub-search{height:36px;min-width:280px;border:1px solid var(--line);
  border-radius:9px;background:var(--surface);padding:0 12px;outline:0}.hub-search:focus{border-color:var(--faint)}
.project-table{border:1px solid var(--line);border-radius:12px;background:var(--surface);overflow:hidden;
  box-shadow:var(--shadow)}.project-row{width:100%;border:0;border-bottom:1px solid var(--line);
  background:transparent;display:grid;grid-template-columns:minmax(220px,1.5fr) minmax(220px,1fr)
  92px 100px 116px 28px 28px 28px;align-items:center;gap:14px;padding:15px 18px;text-align:left;cursor:pointer}
.project-row:last-child{border-bottom:0}.project-row:hover{background:var(--surface-2)}
.project-pin{width:27px;height:27px;border:0;border-radius:7px;background:transparent;color:var(--faint);
  font-size:15px}.project-pin:hover{background:var(--hover);color:var(--text)}.project-pin.pinned{color:var(--violet)}
.project-delete{width:27px;height:27px;border:0;border-radius:7px;background:transparent;color:var(--faint);
  font-size:14px}.project-delete:hover{background:var(--red-bg);color:var(--red)}
.project-name{display:block;font-weight:630;font-size:13.5px}.project-path{display:block;font-size:10.5px;color:var(--faint);
  margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.project-models{font-size:11px;
  color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.project-stat{font-size:11px;
  color:var(--muted)}.project-arrow{color:var(--faint);font-size:16px}.paired-mark{font-size:10px;
  color:var(--violet);background:var(--violet-bg);border-radius:6px;padding:4px 6px;width:max-content}
.project-live{display:flex;align-items:center;gap:7px;margin-top:7px;min-width:0;color:var(--blue);
  font-size:10px}.project-progress{position:relative;display:block;width:76px;height:3px;overflow:hidden;
  border-radius:5px;background:color-mix(in srgb,var(--blue) 16%,transparent);flex:none}
.project-progress i{position:absolute;inset:0 auto 0 -45%;width:45%;border-radius:inherit;background:var(--blue);
  animation:project-progress 1.15s ease-in-out infinite}.project-live-copy{overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}.project-live-time{color:var(--faint);flex:none}@keyframes project-progress{
  0%{transform:translateX(0)}100%{transform:translateX(325%)}}
.project-recovery{display:flex;align-items:center;gap:7px;margin-top:7px;color:var(--red);
  font-size:10px}.retry-setup{border:1px solid var(--red);border-radius:6px;background:var(--surface);
  color:var(--red);padding:3px 7px;font-size:10px;font-weight:650}.retry-setup:hover{background:var(--red-bg)}
.project-interrupted{display:block;margin-top:7px;color:var(--amber);font-size:10px}
.hub-empty{padding:50px 20px;text-align:center;color:var(--muted)}
.job-panel{display:none;margin:0 0 16px;border:1px solid var(--blue);border-radius:11px;
  background:var(--blue-bg);padding:14px 16px}.job-panel.on{display:flex;gap:13px;align-items:flex-start}
.job-spinner{width:14px;height:14px;border:2px solid color-mix(in srgb,var(--blue) 28%,transparent);
  border-top-color:var(--blue);border-radius:50%;animation:spin .8s linear infinite;margin-top:2px}
.job-panel.failed{border-color:var(--red);background:var(--red-bg)}.job-panel.complete{border-color:var(--green);
  background:var(--green-bg)}.job-panel.failed .job-spinner,.job-panel.complete .job-spinner{animation:none;
  border:0;width:16px;height:16px}.job-panel.failed .job-spinner:after{content:'×';color:var(--red);font-weight:800}
.job-panel.complete .job-spinner:after{content:'✓';color:var(--green);font-weight:800}
.job-copy{min-width:0;flex:1}.job-copy b{display:block}.job-copy span{font-size:11px;color:var(--muted)}
.job-steps{margin:8px 0 0;padding:0;list-style:none;display:grid;gap:3px}.job-steps li{font-size:10px;
  color:var(--muted)}.job-steps li:before{content:'✓';color:var(--green);margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}

.project-modal{display:none;position:fixed;inset:0;z-index:30;background:rgba(15,15,14,.42);
  backdrop-filter:blur(2px);padding:28px;align-items:center;justify-content:center}.project-modal.on{display:flex}
.delete-summary{border:1px solid var(--line);border-radius:10px;background:var(--surface-2);
  padding:12px 13px;display:grid;gap:5px;font-size:11px}.delete-summary b{font-size:12px}
.delete-summary code{font-family:ui-monospace,SFMono-Regular,monospace;color:var(--muted);overflow-wrap:anywhere}
.delete-warning{border:1px solid color-mix(in srgb,var(--red) 32%,var(--line));background:var(--red-bg);
  color:var(--red);border-radius:10px;padding:11px 12px;font-size:11px;line-height:1.5}
.delete-detail{color:var(--muted);font-size:10.5px;line-height:1.5}.danger-button{height:34px;border:0;
  border-radius:8px;padding:0 13px;background:var(--red);color:#fff;font-weight:650}
.danger-button:hover{filter:brightness(.94)}.danger-button:disabled{opacity:.4;cursor:not-allowed}
.conditional-field.off{display:none}
.wizard{width:min(720px,100%);max-height:calc(100vh - 40px);overflow:auto;background:var(--surface);
  border:1px solid var(--line);border-radius:15px;box-shadow:0 24px 80px rgba(0,0,0,.22)}
.wizard-head{padding:21px 24px 17px;display:flex;gap:12px;align-items:flex-start;border-bottom:1px solid var(--line)}
.wizard-head h2{font-size:17px;margin:0;letter-spacing:-.02em}.wizard-head p{margin:4px 0 0;color:var(--muted);
  font-size:11.5px}.wizard-body{padding:22px 24px}.form-section{margin-bottom:25px}.form-section:last-child{margin:0}
.form-title{font-size:11px;font-weight:680;margin-bottom:11px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--faint)}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}.field{display:block}
.field.full{grid-column:1/-1}.field span{display:block;font-size:11px;color:var(--muted);margin-bottom:6px}
.field input,.field select,.field textarea{width:100%;border:1px solid var(--line-strong);border-radius:8px;
  background:var(--surface);padding:9px 10px;outline:0}.field textarea{resize:vertical;min-height:74px}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--blue);box-shadow:0 0 0 2px var(--blue-bg)}
.path-picker{display:flex;gap:8px;align-items:center}.path-picker input{min-width:0;flex:1;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px}.path-picker button{white-space:nowrap}
.path-preview{display:block;margin-top:6px;color:var(--faint);font-size:10px;overflow-wrap:anywhere}
.role-card{border:1px solid var(--line);border-radius:10px;padding:13px;background:var(--panel)}
.role-card b{display:block;margin-bottom:9px}.role-card .field+.field{margin-top:10px}
.runtime-role-head{display:flex;align-items:flex-start;gap:9px;margin-bottom:11px}.runtime-role-head b{
  margin:0}.runtime-role-head span{margin-left:auto;color:var(--faint);font-size:10px}.runtime-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:12px}.runtime-note{margin-top:12px;padding:10px 11px;
  border:1px solid var(--line);border-radius:9px;background:var(--surface-2);color:var(--muted);
  font-size:10.5px;line-height:1.5}.runtime-note b{color:var(--text)}.effort-help{display:block;
  color:var(--faint);font-size:10px;margin-top:6px;line-height:1.4}.runtime-saved{color:var(--green)}
.model-actions{display:flex;justify-content:flex-end;margin-top:6px}.model-actions button{height:27px;font-size:10px}
.fallback-list{display:grid;gap:8px}.fallback-row{display:grid;grid-template-columns:130px minmax(0,1fr) 92px 28px;
  gap:7px;align-items:center}.fallback-row select,.fallback-row input{width:100%;border:1px solid var(--line-strong);border-radius:7px;
  background:var(--surface);padding:8px;font-size:10px}.fallback-remove{height:30px;border:1px solid var(--line);
  border-radius:7px;background:var(--surface);color:var(--muted);cursor:pointer}.fallback-empty{color:var(--faint);
  font-size:10px;padding:8px 0}.guardrail-state{font-size:10px;color:var(--muted);margin-top:8px}
.custom-model.off{display:none}
.github-box{border:1px solid var(--line);border-radius:10px;padding:14px;background:var(--panel)}
.toggle-line{display:flex;align-items:flex-start;gap:10px}.toggle-line input{margin-top:3px}.toggle-line b{display:block}
.toggle-line small{display:block;color:var(--muted);margin-top:2px}.github-fields{margin-top:14px}
.github-fields.off{display:none}.connection{font-size:11px;margin:10px 0 0;color:var(--muted)}
.connection.ok{color:var(--green)}.connection.bad{color:var(--red)}
.github-connect{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.github-connect .secondary{height:30px}
.github-device{margin-top:9px;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);
  color:var(--text)}.github-device b{font-size:12px}.device-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:.12em;padding:4px 7px;border-radius:5px;background:var(--surface-2);user-select:all}
.github-device-actions{display:flex;gap:7px;margin-top:8px;align-items:center}.github-device a{color:var(--blue);
  font-weight:620;text-decoration:none}.github-device small{display:block;color:var(--muted);margin-top:5px}
.repo-actions{display:flex;align-items:center;gap:8px;margin-top:11px}.repo-actions .secondary{height:29px}
.repo-check{font-size:10.5px;color:var(--muted)}.repo-check.ok{color:var(--green)}.repo-check.warn{color:var(--amber)}
.job-guidance{display:none;margin-top:10px;padding:10px;border:1px solid color-mix(in srgb,var(--red) 30%,var(--line));
  border-radius:8px;background:var(--surface)}.job-guidance.on{display:block}.job-guidance b{font-size:11px}
.job-guidance p{margin:4px 0 8px;color:var(--muted);font-size:10.5px}.guidance-actions{display:flex;gap:7px;flex-wrap:wrap}
.guidance-actions a,.guidance-actions button{height:28px;font-size:10px}
.recovery-note{padding:11px;border:1px solid var(--amber);background:var(--amber-bg);border-radius:9px;
  color:var(--text);font-size:11px;line-height:1.5;margin-bottom:14px}.recovery-note b{display:block;margin-bottom:3px}
.wizard-error{display:none;color:var(--red);background:var(--red-bg);border-radius:8px;padding:9px 11px;
  margin-top:14px;font-size:11px}.wizard-error.on{display:block}
.wizard-error a{color:inherit;font-weight:700;margin-left:7px}
.wizard-foot{padding:15px 24px;border-top:1px solid var(--line);display:flex;align-items:center;gap:9px}
.wizard-foot span{font-size:10.5px;color:var(--muted);margin-right:auto;max-width:390px}
.credential-card{border:1px solid var(--line);border-radius:10px;padding:14px;background:var(--panel)}
.credential-card+.credential-card{margin-top:10px}.credential-head{display:flex;align-items:center;
  gap:8px;margin-bottom:10px}.credential-head b{font-size:12px}.credential-state{margin-left:auto;font-size:10px;
  color:var(--faint)}.credential-state.ok{color:var(--green)}.secret-row{display:grid;
  grid-template-columns:minmax(0,1fr) auto;gap:9px;align-items:end}.secret-row .toggle-line{padding-bottom:9px}
.connection-method{display:flex;align-items:center;gap:12px;padding:11px;border:1px solid var(--line);
  border-radius:9px;background:var(--surface-2);margin-bottom:11px}.connection-method-copy{min-width:0;flex:1}
.connection-method-copy b{display:block;font-size:11.5px}.connection-method-copy small{display:block;color:var(--muted);
  margin-top:3px;line-height:1.4}.connection-method .secondary{flex:none}.provider-note{padding:9px 10px;
  border-radius:8px;background:var(--amber-bg);color:var(--muted);font-size:10.5px;line-height:1.45;
  margin-bottom:11px}.provider-note b{color:var(--amber)}.login-link{color:var(--blue);font-weight:650;
  text-decoration:none}.field-help{display:block!important;margin-top:5px;color:var(--faint);font-size:10px;
  line-height:1.4}
.settings-readiness{display:grid;grid-template-columns:1fr 1fr;gap:8px}.readiness-item{border:1px solid var(--line);
  border-radius:8px;padding:10px;background:var(--panel);font-size:11px}.readiness-item span{float:right;color:var(--green)}
.readiness-item span.bad{color:var(--red)}
.doctor-panel{margin-top:12px;border:1px solid var(--line);border-radius:11px;background:var(--panel);overflow:hidden}
.doctor-head{display:flex;align-items:center;gap:10px;padding:12px 13px;border-bottom:1px solid var(--line)}
.doctor-head-copy{min-width:0;flex:1}.doctor-head-copy b{display:block;font-size:12px}.doctor-head-copy small{
  display:block;margin-top:2px;color:var(--muted);font-size:10.5px}.doctor-state{width:8px;height:8px;border-radius:50%;
  background:var(--faint);flex:none}.doctor-state.ready{background:var(--green)}.doctor-state.blocked,.doctor-state.failed{
  background:var(--red)}.doctor-state.attention{background:var(--amber)}.doctor-state.running{background:var(--blue);
  animation:pulse 1.2s ease-in-out infinite}.doctor-head .secondary{height:29px;flex:none}
.doctor-list{display:grid}.doctor-empty{padding:18px;color:var(--muted);font-size:11px;text-align:center}
.doctor-check{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:9px;padding:11px 13px;
  border-bottom:1px solid var(--line);align-items:start}.doctor-check:last-child{border-bottom:0}.doctor-mark{width:17px;
  height:17px;border-radius:50%;display:grid;place-items:center;font-size:9px;font-weight:800;background:var(--green-bg);
  color:var(--green);margin-top:1px}.doctor-check.missing .doctor-mark,.doctor-check.outdated .doctor-mark{background:var(--red-bg);
  color:var(--red)}.doctor-check.warning .doctor-mark,.doctor-check.unknown .doctor-mark,.doctor-check.waiting .doctor-mark{background:var(--amber-bg);
  color:var(--amber)}.doctor-copy{min-width:0}.doctor-copy b{display:block;font-size:11px}.doctor-copy small{display:block;
  color:var(--muted);font-size:10px;line-height:1.4;margin-top:2px;overflow-wrap:anywhere}.doctor-version{color:var(--faint);
  font:9.5px ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:2px;white-space:nowrap}.doctor-action{
  grid-column:2/4;display:flex;gap:7px;align-items:center;flex-wrap:wrap}.doctor-action .secondary{height:27px;font-size:10px;
  text-decoration:none}.doctor-identity{display:grid;grid-template-columns:1fr 1fr auto;gap:7px;width:100%}.doctor-identity input{
  min-width:0;border:1px solid var(--line-strong);border-radius:7px;background:var(--surface);padding:7px 8px;font-size:10px}
.doctor-message{display:none;margin:0 13px 12px;padding:9px 10px;border-radius:8px;background:var(--blue-bg);color:var(--blue);
  font-size:10.5px}.doctor-message.on{display:block}.doctor-message.bad{background:var(--red-bg);color:var(--red)}
#provider-credentials{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
#provider-credentials .credential-card{margin:0;min-width:0}
#provider-credentials .provider-note{min-height:58px}
.top-project{cursor:pointer;border-top:0;border-right:0;border-bottom:0;background:transparent;text-align:left}
.compute-toolbar{display:flex;align-items:center;gap:8px;margin-bottom:16px}.compute-toolbar .spacer{flex:1}
.compute-note{display:flex;gap:9px;padding:11px 12px;border:1px solid var(--line);border-radius:10px;
  background:var(--panel);color:var(--muted);font-size:10.5px;line-height:1.5;margin-bottom:16px}
.compute-message{display:none;margin:-8px 0 16px;padding:9px 11px;border-radius:8px;background:var(--red-bg);
  color:var(--red);font-size:10.5px}.compute-message.on{display:block}
.compute-note b{color:var(--text)}.compute-grid{display:grid;grid-template-columns:minmax(230px,.8fr) minmax(0,1.6fr);
  gap:14px;align-items:start}.compute-section{border:1px solid var(--line);border-radius:11px;background:var(--panel);overflow:hidden}
.compute-section-head{display:flex;align-items:center;gap:8px;padding:11px 12px;border-bottom:1px solid var(--line)}
.compute-section-head b{font-size:11.5px}.compute-section-head span{margin-left:auto;color:var(--faint);font-size:10px}
.compute-empty{padding:24px 14px;text-align:center;color:var(--faint);font-size:11px}.host-row{padding:11px 12px;border-bottom:1px solid var(--line)}
.host-row:last-child{border-bottom:0}.host-top{display:flex;align-items:center;gap:7px}.host-top b{font-size:11.5px}
.host-dot{width:7px;height:7px;border-radius:50%;background:var(--green)}.host-kind{margin-left:auto;color:var(--violet);
  background:var(--violet-bg);padding:3px 5px;border-radius:5px;font-size:9px;text-transform:uppercase}
.host-detail{margin-top:5px;color:var(--muted);font-size:9.5px;line-height:1.45;overflow-wrap:anywhere}.host-resources{display:flex;
  flex-wrap:wrap;gap:4px;margin-top:7px}.host-resource{border:1px solid var(--line);border-radius:5px;padding:2px 5px;
  color:var(--faint);font-size:8.5px}.host-actions{display:flex;gap:6px;margin-top:8px}.host-actions button{height:26px;font-size:9px}
.hpc-job{padding:12px;border-bottom:1px solid var(--line)}.hpc-job:last-child{border-bottom:0}.hpc-job-top{display:flex;
  align-items:center;gap:8px}.hpc-job-top b{font-size:11.5px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hpc-job-top .status{margin-left:auto}.hpc-job-meta{display:flex;flex-wrap:wrap;gap:9px;color:var(--faint);font-size:9px;margin-top:5px}
.hpc-job-detail{color:var(--muted);font-size:10px;margin-top:6px}.hpc-connection-error{color:var(--amber);font-size:9.5px;
  margin-top:5px}.hpc-job-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.hpc-job-actions button,.hpc-job-actions a{
  height:26px;font-size:9px}.hpc-console{display:none;margin-top:9px;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.hpc-console.on{display:block}.hpc-console-tabs{display:flex;align-items:center;gap:4px;padding:6px 7px;background:var(--surface-2);
  border-bottom:1px solid var(--line);font-size:9px;color:var(--faint)}.hpc-console pre{margin:0;padding:9px;max-height:240px;
  overflow:auto;background:#111;color:#d8d8d8;font:9.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}
.hpc-output-list{display:grid;gap:5px;padding:8px}.hpc-output{display:flex;align-items:center;gap:8px;border:1px solid var(--line);
  border-radius:7px;padding:7px 8px;color:var(--text);text-decoration:none;font-size:9.5px}.hpc-output span:last-child{margin-left:auto;color:var(--faint)}
.hpc-confirm{display:flex;align-items:flex-start;gap:9px;padding:10px;border:1px solid var(--amber);border-radius:8px;
  background:var(--amber-bg);font-size:10px;color:var(--muted)}.hpc-confirm input{margin-top:2px}.hpc-confirm b{display:block;color:var(--amber)}
.hpc-host-wizard{width:min(820px,100%);overflow:hidden;display:flex;flex-direction:column}
.hpc-host-wizard .wizard-body{overflow:auto}.hpc-host-intro{display:flex;align-items:flex-start;gap:10px;padding:11px 12px;
  margin-bottom:14px;border-radius:10px;background:var(--blue-bg);color:var(--muted);font-size:10.5px;line-height:1.5}
.hpc-host-intro b{display:block;color:var(--text);font-size:11px;margin-bottom:2px}.hpc-host-intro-icon{color:var(--blue);font-size:14px}
.hpc-setup-section{border:1px solid var(--line);border-radius:11px;background:var(--panel);padding:15px;margin-bottom:12px}
.hpc-setup-section:last-child{margin-bottom:0}.hpc-section-head{display:grid;grid-template-columns:25px minmax(0,1fr);gap:9px;
  align-items:start;margin-bottom:13px}.hpc-section-index{width:24px;height:24px;border-radius:7px;background:var(--surface-2);
  color:var(--muted);display:grid;place-items:center;font-size:9.5px;font-weight:750}.hpc-section-head b{display:block;font-size:12px}
.hpc-section-head p{margin:2px 0 0;color:var(--muted);font-size:10px;line-height:1.45}
.hpc-connection-grid{display:grid;grid-template-columns:1fr 1.4fr 110px;gap:11px}.hpc-connection-grid .field.full{grid-column:1/-1}
.hpc-permission{display:flex;align-items:flex-start;gap:10px;padding:11px 12px;border:1px solid var(--line-strong);
  border-radius:9px;background:var(--surface);cursor:pointer}.hpc-permission:has(input:checked){border-color:var(--blue);background:var(--blue-bg)}
.hpc-permission input{margin-top:2px}.hpc-permission b{display:block;font-size:11px;color:var(--text)}.hpc-permission small{display:block;
  margin-top:3px;color:var(--muted);font-size:10px;line-height:1.45}.hpc-policy{margin-top:13px;padding-top:13px;border-top:1px solid var(--line)}
.hpc-policy.off{display:none}.hpc-policy-title{display:flex;align-items:baseline;gap:7px;margin-bottom:9px;font-size:11px;font-weight:650}
.hpc-policy-title span{color:var(--faint);font-size:9.5px;font-weight:400}.hpc-limit-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.hpc-advanced{margin-top:10px;border-top:1px solid var(--line);padding-top:10px}.hpc-advanced summary{cursor:pointer;color:var(--muted);
  font-size:10.5px;user-select:none}.hpc-advanced .hpc-limit-grid{margin-top:10px}.hpc-host-key{display:flex;align-items:flex-start;gap:9px;
  font-size:10px;color:var(--muted)}.hpc-host-key input{margin-top:2px}.hpc-host-key b{display:block;color:var(--text);font-size:10.5px}
.hpc-host-key small{display:block;margin-top:2px;line-height:1.45}.hpc-host-wizard .wizard-foot{flex:none;background:var(--surface)}
.hpc-input-list{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.hpc-input{display:inline-flex;align-items:center;gap:5px;
  max-width:100%;border:1px solid var(--line);border-radius:7px;padding:4px 6px;color:var(--muted);font-size:9.5px}
.hpc-input b{max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)}
.hpc-input button{border:0;background:transparent;color:var(--faint);cursor:pointer;padding:0 2px;font-size:12px}
.hpc-script{min-height:180px!important;font:10.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace!important}
.mcp-transport-fields.off{display:none}.mcp-tool-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
.mcp-tool{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:6px;
  padding:4px 6px;font-size:9px;color:var(--muted)}.mcp-tool.approved{border-color:color-mix(in srgb,var(--green) 45%,var(--line));
  color:var(--green)}.mcp-call{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;padding:10px 12px;
  border-bottom:1px solid var(--line)}.mcp-call:last-child{border-bottom:0}.mcp-call b{font-size:10.5px}
.mcp-call small{color:var(--faint);font-size:9px}.skill-row{padding:11px 12px;border-bottom:1px solid var(--line)}
.skill-row:last-child{border-bottom:0}.skill-row b{font-size:11px}.skill-row p{margin:4px 0 0;color:var(--muted);font-size:9.5px}
.tools-grid .compute-section:last-child{grid-column:1/-1}
@media(max-width:840px){.compute-grid{grid-template-columns:1fr}.compute-toolbar{flex-wrap:wrap}
  .hpc-connection-grid{grid-template-columns:1fr 1fr}.hpc-connection-grid .field:nth-child(2){grid-column:1/-1}.hpc-limit-grid{grid-template-columns:1fr 1fr}}
@media(max-width:760px){.hub-bar{padding:0 14px}.hub-main{width:calc(100% - 24px);padding-top:26px}
  .hub-heading{align-items:flex-start;flex-direction:column}.hub-summary{margin-left:0}.project-row{grid-template-columns:minmax(0,1fr) 58px 62px 28px 28px 16px;gap:8px}
  .project-models,.project-tier{display:none}.form-grid{grid-template-columns:1fr}
  .field.full{grid-column:auto}.project-modal{padding:8px}.wizard{max-height:calc(100vh - 16px)}
  #provider-credentials{grid-template-columns:1fr}
  .doctor-check{grid-template-columns:18px minmax(0,1fr)}.doctor-version{grid-column:2}.doctor-action{grid-column:2}
  .doctor-identity{grid-template-columns:1fr}.doctor-head{align-items:flex-start}
  .runtime-grid{grid-template-columns:1fr}
  .fallback-row{grid-template-columns:minmax(0,1fr) 92px 28px}.fallback-row [data-fallback-model]{grid-column:1/-1;grid-row:2}
  .path-picker{align-items:stretch;flex-direction:column}.path-picker button{width:100%}.repo-actions{align-items:flex-start;
    flex-direction:column}.hub-tools,.hub-search{width:100%;min-width:0}}
</style></head>
<body>
<section class="project-hub" id="project-hub" aria-label="Projects">
  <header class="hub-bar"><button class="brand-button" id="hub-brand"><span class="brand-mark">◇</span>
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
  <form class="wizard" id="project-form"><div class="wizard-head"><div><h2 id="wizard-title">Create a supervised project</h2>
    <p>Configure both roles and, if you choose, create the separated GitHub repositories.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-project-modal" aria-label="Close">×</button></div>
    <div class="wizard-body"><section class="form-section"><div class="form-title">Project</div><div class="form-grid">
      <label class="field"><span>Project name</span><input name="name" id="project-name" maxlength="80" required placeholder="chem-agent"></label>
      <label class="field"><span>Automatic revision limit</span><select name="max_rounds" id="max-rounds-choice"><option value="1">1 — quick stop</option><option value="3" selected>3 — recommended</option><option value="5">5 — persistent</option><option value="10">10 — maximum</option></select><small class="field-help" id="round-limit-help">Up to 3 generator → auditor rounds, then the task pauses for you. It never auto-passes.</small></label>
      <label class="field full"><span>Local workspace folder</span><div class="path-picker"><input id="project-workspace" readonly aria-label="Selected local workspace"><button type="button" class="secondary" id="choose-project-workspace">Choose folder…</button></div><small class="path-preview" id="project-path-preview">Choose where this project's local folder will be created.</small></label>
      <label class="field full"><span>Project type</span><select name="project_type" id="project-type">
        <option value="general" selected>General work — documents, reviews, code</option>
        <option value="science">Scientific / data workflow — structured experiment outputs</option></select></label>
      <label class="field full"><span>What are you building, and what would count as a mistake?</span>
        <textarea name="description" maxlength="4000" required placeholder="A user-facing review that must be accurate, balanced, and delivered as one clear document."></textarea></label>
      <div class="field full"><span id="project-contract-hint">General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.</span></div>
    </div></section>
    <section class="form-section"><div class="form-title">Independent roles</div><div class="form-grid">
      <div class="role-card"><b>Auditor</b><label class="field"><span>Provider</span><select name="auditor_vendor" id="auditor-vendor"></select></label>
        <label class="field"><span>Connection</span><select name="auditor_connection" id="auditor-connection" required></select></label>
        <label class="field"><span>API region</span><select name="auditor_endpoint" id="auditor-endpoint"></select><small class="field-help">The region must match the API key.</small></label>
        <label class="field"><span>Model</span><select name="auditor_model_choice" id="auditor-model"></select></label>
        <label class="field custom-model off" id="auditor-custom-wrap"><span>Custom model ID</span><input id="auditor-custom" maxlength="120" placeholder="Model available to your account"></label>
        <div class="model-actions"><button type="button" class="secondary" data-refresh-models="auditor">Refresh from provider</button></div></div>
      <div class="role-card"><b>Generator</b><label class="field"><span>Provider</span><select name="generator_vendor" id="generator-vendor"></select></label>
        <label class="field"><span>Connection</span><select name="generator_connection" id="generator-connection" required></select></label>
        <label class="field"><span>API region</span><select name="generator_endpoint" id="generator-endpoint"></select><small class="field-help">The region must match the API key.</small></label>
        <label class="field"><span>Model</span><select name="generator_model_choice" id="generator-model"></select></label>
        <label class="field custom-model off" id="generator-custom-wrap"><span>Custom model ID</span><input id="generator-custom" maxlength="120" placeholder="Model available to your account"></label>
        <div class="model-actions"><button type="button" class="secondary" data-refresh-models="generator">Refresh from provider</button></div></div>
    </div></section>
    <section class="form-section"><div class="form-title">GitHub</div><div class="github-box">
      <label class="toggle-line"><input type="checkbox" name="github" id="github-toggle" checked><span><b>Create and connect two repositories</b>
        <small>The work repository holds deliverables. The audit repository holds rules, reports and the auditor secret.</small></span></label>
      <div class="connection" id="github-connection">Checking GitHub connection…</div>
      <div class="github-fields" id="github-fields"><div class="form-grid">
        <label class="field"><span>Work repository name</span><input name="science_repo" id="science-repo" maxlength="161" placeholder="owner/project"></label>
        <label class="field"><span>Audit repository name</span><input name="audit_repo" id="audit-repo" maxlength="161" placeholder="owner/project-audit"></label>
        <label class="toggle-line full"><input type="checkbox" name="adopt_existing" id="adopt-existing"><span><b>Use accessible repositories if these names already exist</b><small>Off by default. Leave it off when you want two new repositories.</small></span></label>
        <label class="toggle-line full"><input type="checkbox" name="public"><span><b>Public repositories</b><small>Off by default. Private is safer for a new project.</small></span></label>
      </div><div class="repo-actions"><button type="button" class="secondary" id="check-repositories">Check names</button><span class="repo-check" id="repo-check">Names will be checked again before anything is created.</span></div></div></div><div class="wizard-error" id="wizard-error"></div></section></div>
    <div class="wizard-foot"><span>Creating may send the description to the auditor model and create repositories in your connected GitHub account.</span>
      <button type="button" class="secondary" id="cancel-project">Cancel</button><button class="primary" id="submit-project">Create project</button></div>
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
      <label class="toggle-line" style="margin-top:14px"><input type="checkbox" id="delete-project-github"><span><b>Also permanently delete the connected GitHub repositories</b>
        <small id="delete-project-repositories">No GitHub repositories detected.</small></span></label>
      <label class="field conditional-field off" id="delete-github-confirm-wrap" style="margin-top:12px"><span>Type DELETE GITHUB</span>
        <input id="delete-github-confirmation" autocomplete="off" placeholder="DELETE GITHUB"></label>
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
  <form class="wizard" id="runtime-form"><div class="wizard-head"><div><h2 id="runtime-title">Models, reasoning & audit loop</h2>
    <p>Change project controls for the next provider call without restarting this workspace.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-runtime" aria-label="Close">×</button></div>
    <div class="wizard-body"><div class="runtime-grid">
      <section class="role-card" id="runtime-generator-card"><div class="runtime-role-head"><b>Generator</b><span id="runtime-generator-vendor">…</span></div>
        <label class="field"><span>Model</span><select id="runtime-generator-model"></select></label>
        <label class="field custom-model off" id="runtime-generator-custom-wrap"><span>Custom model ID</span><input id="runtime-generator-custom" maxlength="120" placeholder="Exact provider model ID"></label>
        <label class="field"><span>Reasoning effort</span><select id="runtime-generator-effort"></select><small class="effort-help" id="runtime-generator-effort-help"></small></label>
        <div class="model-actions"><button type="button" class="secondary" data-runtime-refresh="generator">Refresh models</button></div>
      </section>
      <section class="role-card" id="runtime-auditor-card"><div class="runtime-role-head"><b>Independent auditor</b><span id="runtime-auditor-vendor">…</span></div>
        <label class="field"><span>Model</span><select id="runtime-auditor-model"></select></label>
        <label class="field custom-model off" id="runtime-auditor-custom-wrap"><span>Custom model ID</span><input id="runtime-auditor-custom" maxlength="120" placeholder="Exact provider model ID"></label>
        <label class="field"><span>Reasoning effort</span><select id="runtime-auditor-effort"></select><small class="effort-help" id="runtime-auditor-effort-help"></small></label>
        <div class="model-actions"><button type="button" class="secondary" data-runtime-refresh="auditor">Refresh models</button></div>
      </section>
    </div><section class="form-section" style="margin-top:12px"><div class="form-title">Automatic provider recovery</div>
      <div class="runtime-grid"><div class="role-card"><div class="runtime-role-head"><b>Generator fallback chain</b><span>in order</span></div><div class="fallback-list" id="runtime-generator-fallbacks"></div><div class="model-actions"><button type="button" class="secondary" data-add-fallback="generator">＋ Add fallback</button></div></div>
      <div class="role-card"><div class="runtime-role-head"><b>Auditor fallback chain</b><span>in order</span></div><div class="fallback-list" id="runtime-auditor-fallbacks"></div><div class="model-actions"><button type="button" class="secondary" data-add-fallback="auditor">＋ Add fallback</button></div></div></div>
      <div class="form-grid" style="margin-top:13px"><label class="field"><span>Attempts per route</span><input id="runtime-max-attempts" type="number" min="1" max="10"></label>
        <label class="field"><span>Initial retry delay (seconds)</span><input id="runtime-initial-backoff" type="number" min="0" max="60" step="0.1"></label>
        <label class="field"><span>Maximum retry delay (seconds)</span><input id="runtime-max-backoff" type="number" min="0" max="300" step="0.1"></label>
        <label class="field"><span>Honor Retry-After up to (seconds)</span><input id="runtime-retry-after-cap" type="number" min="0" max="900" step="1"></label>
        <label class="field"><span>Open circuit after failures</span><input id="runtime-circuit-failures" type="number" min="1" max="20"></label>
        <label class="field"><span>Circuit cooldown (seconds)</span><input id="runtime-circuit-cooldown" type="number" min="1" max="3600" step="1"></label></div>
      <small class="field-help">Retries stay inside one provider call and never consume Generator → Auditor revision rounds. A fallback is used only after its earlier route fails.</small>
    </section><section class="form-section" style="margin-top:12px"><div class="form-title">Usage guardrails</div>
      <div class="form-grid"><label class="field"><span>Daily token warning</span><input id="runtime-daily-token-warning" type="number" min="1" placeholder="No warning"></label>
        <label class="field"><span>Daily token hard limit</span><input id="runtime-daily-token-limit" type="number" min="1" placeholder="No limit"></label>
        <label class="field"><span>Monthly API-value warning (USD)</span><input id="runtime-monthly-cost-warning" type="number" min="0.01" step="0.01" placeholder="No warning"></label>
        <label class="field"><span>Monthly API-value hard limit (USD)</span><input id="runtime-monthly-cost-limit" type="number" min="0.01" step="0.01" placeholder="No limit"></label></div>
      <div class="guardrail-state" id="runtime-guardrail-state">Limits are local safeguards; provider billing remains authoritative.</div>
    </section><section class="form-section" style="margin-top:12px"><div class="form-title">Audit loop</div>
      <label class="field"><span>Automatic revision limit</span><select id="runtime-max-rounds"><option value="1">1 — quick stop</option><option value="3">3 — recommended</option><option value="5">5 — persistent</option><option value="10">10 — maximum</option></select><small class="field-help">After this many generator → auditor rounds, the task pauses for your explicit decision. It never auto-passes.</small></label>
    </section><section class="form-section" style="margin-top:12px"><div class="form-title">Generator guidance</div>
      <div class="form-grid"><label class="field"><span>Edit guidance</span><select id="runtime-skill-select"><option value="__new__">Create new guidance…</option></select></label>
        <label class="field"><span>Name</span><input id="runtime-skill-name" maxlength="60" placeholder="house-style"></label>
        <label class="field full"><span>Applies to paths (optional)</span><input id="runtime-skill-scope" maxlength="500" placeholder="work/reports, work/data"><small class="field-help">Comma-separated project-relative prefixes. Leave blank to apply on every task.</small></label>
        <label class="field full"><span>Instructions for the generator</span><textarea id="runtime-skill-body" maxlength="60000" placeholder="Describe the tone, output shape, conventions or checklist this project should follow."></textarea><small class="field-help">Guidance changes how the generator works. It never changes the Constitution or what the independent auditor enforces.</small></label></div>
      <div class="model-actions"><button type="button" class="secondary" id="save-runtime-skill">Save guidance</button><span class="repo-check" id="runtime-skill-status"></span></div>
    </section><div class="runtime-note" id="runtime-note"><b>Committed project controls.</b> Models and loop limits update crossaudit.yml; generator guidance is versioned in the project. A running audit keeps the controls it started with.</div>
      <div class="wizard-error" id="runtime-error"></div></div>
    <div class="wizard-foot"><span id="runtime-foot">Automatic means the provider chooses its documented default.</span>
      <button type="button" class="secondary" id="cancel-runtime">Cancel</button><button class="primary" id="save-runtime">Save for next call</button></div>
  </form>
</div>

<div class="project-modal" id="resolution-modal" role="dialog" aria-modal="true" aria-labelledby="resolution-title">
  <form class="wizard decision-wizard" id="resolution-form"><div class="wizard-head"><div>
    <div class="decision-flag" id="resolution-flag">Automatic loop paused</div>
    <h2 id="resolution-title">The audit needs your decision</h2>
    <p id="resolution-summary">CrossAudit stopped safely. Nothing will continue or be admitted until you decide.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-resolution" aria-label="Review later" title="Review later">×</button></div>
    <div class="wizard-body"><input type="hidden" id="resolution-cycle"><input type="hidden" id="resolution-action">
      <div class="decision-limit"><span class="decision-limit-mark">!</span><div><b id="resolution-limit-title">Automatic audit limit reached</b>
        <p id="resolution-limit-copy">The configured rounds were used without a passing result.</p></div></div>
      <section class="decision-section"><div class="decision-title">What is still blocking the result <span class="decision-count" id="resolution-issue-count">0</span></div>
        <div class="decision-issues" id="resolution-issues"></div></section>
      <section class="decision-section"><div class="decision-title">What CrossAudit needs from you</div>
        <p class="decision-request" id="resolution-request">Choose whether to provide concrete correction guidance for one more round or stop this task.</p>
        <div class="decision-options">
          <label class="decision-option"><input type="radio" name="resolution-choice" value="reopen" required><span><b>Revise and continue</b><small>Give the generator specific correction guidance and unlock one additional audited round.</small></span></label>
          <label class="decision-option"><input type="radio" name="resolution-choice" value="close" required><span><b>Stop this task</b><small>Keep the current output unadmitted and close the audit cycle with your reason.</small></span></label>
        </div>
        <label class="field decision-guidance"><span id="resolution-reason-label">Your guidance or reason</span><textarea id="resolution-reason" maxlength="400" required placeholder="Select an action, then explain what CrossAudit should do."></textarea></label>
        <div class="decision-ledger-note"><b>Human decision required.</b> Your action and explanation become part of the durable audit ledger.</div>
      </section><div class="wizard-error" id="resolution-error"></div></div>
    <div class="wizard-foot"><span>The models cannot approve their own result or bypass this pause.</span>
      <button type="button" class="secondary" id="cancel-resolution">Review later</button><button class="primary" id="submit-resolution">Record human decision</button></div>
  </form>
</div>

<div class="project-modal" id="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
  <form class="wizard" id="settings-form"><div class="wizard-head"><div><h2 id="settings-title">CrossAudit settings</h2>
    <p>Check this Mac, repair setup issues, and connect model providers without using Terminal.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-settings" aria-label="Close settings">×</button></div>
    <div class="wizard-body"><section class="form-section"><div class="form-title">Application readiness</div>
      <div class="settings-readiness"><div class="readiness-item">Git<span id="git-state">…</span></div>
        <div class="readiness-item">GitHub connection tool<span id="ghcli-state">…</span></div>
        <div class="readiness-item">Application build<span id="runtime-state">…</span></div>
        <div class="readiness-item">Code identity<span id="digest-state">…</span></div></div>
      <div class="doctor-panel"><div class="doctor-head"><span class="doctor-state" id="doctor-state"></span>
        <div class="doctor-head-copy"><b>Environment Doctor</b><small id="doctor-summary">Preparing checks…</small></div>
        <button type="button" class="secondary" id="run-doctor">Run check</button></div>
        <div class="doctor-list" id="doctor-checks"><div class="doctor-empty">Checking required software…</div></div>
        <div class="doctor-message" id="doctor-message"></div></div>
      <label class="field" style="margin-top:12px"><span>Project workspace</span><div class="path-picker"><input id="settings-workspace" readonly><button type="button" class="secondary" id="choose-settings-workspace">Choose folder…</button></div></label>
    </section><section class="form-section"><div class="form-title">Provider credentials</div>
      <div class="provider-note"><b>Developer access and consumer subscriptions are different products.</b> CrossAudit only offers web sign-in where the provider publishes a supported third-party inference flow. It never imports browser cookies or CLI session files.</div>
      <div id="provider-credentials"></div>
    </section><div class="wizard-error" id="settings-error"></div></div>
    <div class="wizard-foot"><span>API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.</span>
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

<div class="app">
  <header class="topbar">
    <button class="icon-button mobile-sidebar" id="sidebar-toggle" aria-label="Open navigation"
      aria-controls="sidebar-panel" aria-expanded="false">☰</button>
    <button class="icon-button" id="back-projects" aria-label="Back to projects" title="Back to projects">←</button>
    <button class="brand-button" id="projects-home"><span class="brand-mark">◇</span>CrossAudit
      <span class="version" id="version-badge">V4.14.0</span></button>
    <button class="top-project" id="project-switcher"><b id="proj">…</b> <span id="branch-label">/ project folder</span>⌄</button>
    <button class="icon-button" id="current-project-pin" aria-label="Pin project" title="Pin project">☆</button>
    <span class="spacer"></span>
    <div class="live-pill"><span class="live-dot" id="livedot"></span><span id="conn-text">connecting</span></div>
    <button class="icon-button" id="locale-toggle" aria-label="Switch to Chinese" title="Switch language">中文</button>
    <button class="icon-button" id="settings-open" aria-label="Settings" title="Settings">⚙</button>
    <button class="icon-button" id="theme-toggle" aria-label="Switch to dark theme" title="Toggle theme">◐</button>
    <button class="icon-button mobile-inspector" id="inspect-toggle" aria-label="Toggle audit context"
      aria-controls="inspector" aria-expanded="false">☷</button>
  </header>

  <button class="scrim" id="scrim" aria-label="Close open panel"></button>

  <aside class="sidebar" id="sidebar-panel" aria-label="Tasks">
    <button class="new-task" id="new-task"><span>＋</span>New chat<span>⌘ N</span></button>
    <nav class="nav" aria-label="Workspace views">
      <button type="button" class="nav-item active" data-view="tasks" aria-pressed="true"><span class="nav-icon">◫</span>Chat</button>
      <button type="button" class="nav-item" data-view="artifacts" aria-pressed="false"><span class="nav-icon">▱</span>Artifacts</button>
      <button type="button" class="nav-item" data-view="audits" aria-pressed="false"><span class="nav-icon">◇</span>Audits</button>
      <button type="button" class="nav-item" data-view="usage" aria-pressed="false"><span class="nav-icon">◒</span>Usage</button>
      <button type="button" class="nav-item" data-view="compute" aria-pressed="false"><span class="nav-icon">⌁</span>Compute</button>
      <button type="button" class="nav-item" data-view="tools" aria-pressed="false"><span class="nav-icon">⌘</span>Tools & Skills</button></nav>
    <div class="task-list" id="task-list"></div>
    <div class="sidebar-foot"><b id="side-project">…</b><span id="tier-label">local controller</span></div>
  </aside>

  <main class="workspace">
    <div class="thread-head"><div class="participants" aria-label="Conversation participants">
      <span class="participant" title="You">Y</span><span class="participant" title="Generator">G</span>
      <span class="participant auditor" title="Auditor">A</span></div><div class="thread-title"><h1 id="thread-title">New task</h1>
      <p id="thread-subtitle">Independent generation and audit</p></div><span class="spacer"></span>
      <button type="button" class="runtime-button" id="runtime-open" title="Switch models, reasoning effort and audit loop settings">Project controls</button>
      <span class="status" id="thread-status">ready</span></div>
    <div class="thread" id="thread"><div class="thread-inner">
      <div class="interrupted" id="interrupted"></div><div id="conversation"></div>
    </div></div>
  </main>

  <div class="composer-wrap"><form class="composer" id="f" autocomplete="off">
    <input id="file-input" type="file" multiple hidden>
    <div class="contract-preview" id="contract-preview"></div>
    <section class="task-choices" id="task-choices" aria-label="Task delivery choices">
      <div class="choice-head"><div><b>Before I start</b><span>Confirm the choices that materially change the deliverable.</span></div>
        <button type="button" class="choice-close" id="close-task-choices" aria-label="Close choices">×</button></div>
      <div class="choice-group"><span class="choice-label">Focus</span><div class="choice-options">
        <label class="choice-option"><input type="radio" name="task_focus" value="Balanced coverage" checked><span>Balanced</span></label>
        <label class="choice-option"><input type="radio" name="task_focus" value="Technical depth"><span>Technical depth</span></label>
        <label class="choice-option"><input type="radio" name="task_focus" value="Everyday use and practical experience"><span>Everyday use</span></label>
        <label class="choice-option"><input type="radio" name="task_focus" value="Value and purchase recommendation"><span>Value</span></label>
      </div></div>
      <div class="choice-group"><span class="choice-label">Format</span><div class="choice-options">
        <label class="choice-option"><input type="radio" name="task_format" value="Markdown (.md)" checked><span>Markdown</span></label>
        <label class="choice-option"><input type="radio" name="task_format" value="Plain text (.txt)"><span>Plain text</span></label>
        <label class="choice-option"><input type="radio" name="task_format" value="HTML (.html)"><span>HTML</span></label>
        <label class="choice-option" title="Rendered locally and audited from the final binary"><input type="radio" name="task_format" value="PDF (.pdf)"><span>PDF</span></label>
        <label class="choice-option" title="Rendered locally and audited from the final binary"><input type="radio" name="task_format" value="Word (.docx)"><span>DOCX</span></label>
      </div></div><p class="choice-note">PDF and DOCX are rendered locally; only the final audited file is shown.</p>
      <div class="choice-group"><span class="choice-label">Tone</span><div class="choice-options">
        <label class="choice-option"><input type="radio" name="task_tone" value="Editorial and readable" checked><span>Editorial</span></label>
        <label class="choice-option"><input type="radio" name="task_tone" value="Technical and precise"><span>Technical</span></label>
        <label class="choice-option"><input type="radio" name="task_tone" value="Concise and direct"><span>Concise</span></label>
        <label class="choice-option"><input type="radio" name="task_tone" value="Persuasive but evidence-led"><span>Persuasive</span></label>
      </div></div>
      <div class="choice-actions"><button type="button" class="secondary" id="use-prompt-as-written">Use prompt as written</button>
        <button type="button" class="primary" id="run-with-choices">Run with selections</button></div>
    </section>
    <div class="attachments" id="attachments"></div>
    <div class="transfer-consent" id="transfer-consent"><span><b>Confirm file transfer</b>
      <span id="consent-copy"></span></span><button type="button" id="confirm-transfer">Send files</button></div>
    <div class="audience-bar" aria-label="Message recipient"><span class="audience-label">To</span>
      <button type="button" class="audience-chip active" data-audience="auto">Auto</button>
      <button type="button" class="audience-chip" data-audience="generator">@ Generator</button>
      <button type="button" class="audience-chip" data-audience="auditor">@ Auditor</button></div>
    <div class="compose-row"><button type="button" class="compose-button" id="attach" aria-label="Add files" title="Add files">＋</button>
      <textarea id="say" rows="1" placeholder="Message the group, or @ someone…"></textarea>
      <button id="send" class="compose-button send" aria-label="Run task">↑</button></div>
    <div class="composer-meta"><span id="model-summary">Generator → Auditor</span><span class="spacer"></span>
      <span>Enter to send · Shift+Enter for new line</span></div><div class="route" id="route"></div>
  </form></div>

  <aside class="inspector" id="inspector" aria-label="Audit context">
    <div class="inspect-head"><h2>Audit context</h2><span class="spacer"></span>
      <button class="icon-button" id="inspect-close" aria-label="Close audit context">×</button></div>
    <section class="inspect-section"><div class="inspect-title">Models</div>
      <div class="model"><div class="model-role">Generator</div><div class="model-name" id="runtime-generator">…</div></div>
      <div class="model"><div class="model-role">Independent auditor</div><div class="model-name" id="runtime-auditor">…</div></div></section>
    <section class="inspect-section"><div class="inspect-title">Loop parameters</div>
      <div class="kv"><span>Maximum rounds</span><span id="max-rounds">…</span></div>
      <div class="kv"><span>Current round</span><span id="current-round">—</span></div>
      <div class="kv"><span>Constitution</span><span id="rules-count">…</span></div>
      <div class="kv"><span>Admission tier</span><span id="tier-value">…</span></div></section>
    <section class="inspect-section"><div class="inspect-title">Deterministic checks</div>
      <div id="runtime-checks"></div></section>
    <section class="inspect-section"><div class="inspect-title">Ledger</div>
      <div class="mini-metrics" id="mini-metrics"></div></section>
    <section class="inspect-section"><div class="inspect-title">Needs attention</div>
      <div id="escalations"></div></section>
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
  "Project":"项目","Project name":"项目名称","Project type":"项目类型","General work — documents, reviews, code":"通用工作——文档、评审、代码",
  "Scientific / data workflow — structured experiment outputs":"科学 / 数据工作流——结构化实验输出",
  "General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.":"通用项目检查格式、引用、链接和完整性，不要求科学元数据附属文件。",
  "What are you building, and what would count as a mistake?":"你要构建什么？哪些情况应判定为错误？",
  "A user-facing review that must be accurate, balanced, and delivered as one clear document.":"一份面向用户、准确平衡且以单一清晰文档交付的评审。",
  "Automatic revision limit":"自动修订轮数上限","1 — quick stop":"1 — 快速停止","3 — recommended":"3 — 推荐",
  "5 — persistent":"5 — 持续修订","10 — maximum":"10 — 最大值",
  "Up to 3 generator → auditor rounds, then the task pauses for you. It never auto-passes.":"最多进行 3 轮生成者 → 审计者循环，随后暂停并等待你决定；绝不会自动通过。",
  "Local workspace folder":"本地工作区文件夹","Choose folder…":"选择文件夹…","Selected local workspace":"已选择的本地工作区",
  "Choose where this project's local folder will be created.":"选择创建该项目本地文件夹的位置。",
  "Independent roles":"独立角色","Generator":"生成者","Independent auditor":"独立审计者","Provider":"供应商","Connection":"连接方式",
  "API region":"API 区域","The region must match the API key.":"区域必须与 API key 匹配。","Model":"模型",
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
  "Models, reasoning & audit loop":"模型、推理与审计循环","Change project controls for the next provider call without restarting this workspace.":"无需重启工作区，即可修改下一次供应商调用使用的项目控制。",
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
  "Project controls updated":"项目控制已更新","— recovery routes, usage guardrails, models and loop limits apply to the next provider call.":"— 恢复路由、用量保护线、模型和循环上限将在下一次供应商调用时生效。",
  "The selected effort is sent on the next provider request.":"所选推理强度会用于下一次供应商请求。",
  "After this many generator → auditor rounds, the task pauses for your explicit decision. It never auto-passes.":"达到该生成者 → 审计者轮数后，任务会暂停并等待你的明确决定，绝不会自动通过。",
  "Generator guidance":"生成者指导","Edit guidance":"编辑指导","Create new guidance…":"创建新指导…","Name":"名称",
  "Applies to paths (optional)":"适用路径（可选）","Comma-separated project-relative prefixes. Leave blank to apply on every task.":"以逗号分隔的项目相对路径前缀。留空则适用于所有任务。",
  "Instructions for the generator":"给生成者的说明","Describe the tone, output shape, conventions or checklist this project should follow.":"描述此项目应遵循的语气、输出形式、约定或检查清单。",
  "Guidance changes how the generator works. It never changes the Constitution or what the independent auditor enforces.":"指导只改变生成者的工作方式，不会修改 Constitution 或独立审计者执行的标准。",
  "Save guidance":"保存指导","Committed project controls.":"已提交的项目控制。",
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
  "CrossAudit settings":"CrossAudit 设置","Check this Mac, repair setup issues, and connect model providers without using Terminal.":"检查此 Mac、修复设置问题并连接模型供应商，全程无需终端。",
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
  "Tasks":"任务","New chat":"新对话","＋ New chat":"＋ 新对话","Workspace views":"工作区视图","Chat":"对话","Artifacts":"交付文件","Audits":"审计","Usage":"用量","Compute":"计算","Tools & Skills":"工具与技能",
  "Back to projects":"返回项目列表","Pin project":"置顶项目","Settings":"设置","Switch theme":"切换主题","Toggle audit context":"切换审计上下文","Open navigation":"打开导航","Close open panel":"关闭面板",
  "Conversation participants":"对话参与者","You":"你","Auditor":"审计者","New task":"新任务","Independent generation and audit":"独立生成与审计","Project controls":"项目控制",
  "Message recipient":"消息接收方","To":"发送给","Auto":"自动","@ Generator":"@ 生成者","@ Auditor":"@ 审计者","Add files":"添加文件","＋ Add files":"＋ 添加文件",
  "Message the group, or @ someone…":"给群组发送消息，或 @ 某一方…","Run task":"运行任务","Generator → Auditor":"生成者 → 审计者","Enter to send · Shift+Enter for new line":"Enter 发送 · Shift+Enter 换行",
  "Audit context":"审计上下文","Close audit context":"关闭审计上下文","Models":"模型","Loop parameters":"循环参数","Maximum rounds":"最大轮数","Current round":"当前轮次","Constitution":"审计章程","Admission tier":"准入级别","Deterministic checks":"确定性检查","Ledger":"账本","Needs attention":"需要处理",
  "Task delivery choices":"任务交付选项","Confirm the choices that materially change the deliverable.":"确认会实质影响交付物的选项。","Before I start":"开始之前","Focus":"重点","Balanced":"均衡","Technical depth":"技术深度","Everyday use":"日常使用","Value":"价值","Format":"格式","Markdown":"Markdown","Plain text":"纯文本","HTML":"HTML","PDF":"PDF","DOCX":"DOCX","PDF and DOCX are rendered locally; only the final audited file is shown.":"PDF 和 DOCX 在本地渲染；界面只显示通过审计的最终文件。","Tone":"语气","Editorial":"编辑风格","Technical":"技术风格","Concise":"简洁","Persuasive":"说服性","Close choices":"关闭选项","Use prompt as written":"按原提示执行","Run with selections":"按所选项运行",
  "Confirm file transfer":"确认文件传输","Drop files to add them":"拖放文件以添加","No CrossAudit file-count or file-size quota. Available storage, filesystem limits and provider context still apply.":"CrossAudit 不限制文件数量或大小，但仍受可用存储、文件系统和供应商上下文限制。","Send files":"发送文件",
  "Rendered locally and audited from the final binary":"在本地渲染，并从最终二进制文件回读审计","File preview":"文件预览","Preparing preview…":"正在准备预览…","Loading audited deliverable…":"正在加载已审计的交付文件…","Download":"下载","Close preview":"关闭预览","The complete file remains available to download.":"完整文件始终可供下载。","Preview unavailable for this file type. Download the complete file to open it in a compatible app.":"此文件类型无法安全预览。请下载完整文件并使用兼容应用打开。","The reading preview is shortened for responsiveness; the download is complete.":"为保证界面流畅，阅读预览已截短；下载文件是完整的。","Preview is reconstructed from the final audited DOCX binary.":"预览内容从最终通过审计的 DOCX 二进制文件中重建。","HTML preview is isolated from the app and cannot access the network.":"HTML 预览与应用隔离，且无法访问网络。","ready":"就绪","connecting":"正在连接","Connected":"已连接","Not connected":"未连接","Checking…":"正在检查…","Loading projects…":"正在加载项目…","Something went wrong":"发生了错误","Open help ↗":"打开帮助 ↗",
  "Close":"关闭","Close settings":"关闭设置","No matching projects.":"没有匹配的项目。","Switch to dark theme":"切换到深色主题","Switch to light theme":"切换到浅色主题",
  "Delete project":"删除项目","Review the local and GitHub impact before anything is changed.":"更改任何内容前，请检查本地与 GitHub 影响。",
  "Checking project state…":"正在检查项目状态…","The local folder will move to CrossAudit Trash and can be recovered. GitHub repositories remain untouched unless you explicitly select permanent deletion below.":"本地文件夹会移到 CrossAudit 废纸篓并可恢复。除非你在下方明确选择永久删除，否则 GitHub 仓库保持不变。",
  "Type the project name to confirm":"输入项目名称以确认","Also permanently delete the connected GitHub repositories":"同时永久删除已连接的 GitHub 仓库",
  "No GitHub repositories detected.":"未检测到 GitHub 仓库。","Type DELETE GITHUB":"输入 DELETE GITHUB","Running tasks and remote compute block deletion.":"运行中的任务和远程计算会阻止删除。",
  "Move project to Trash":"将项目移到废纸篓","Delete chat?":"删除对话？","This chat will disappear from the project sidebar.":"此对话将从项目侧栏消失。",
  "Audit reports, receipts, commits and delivered files are preserved in the project ledger. Deleting a chat never rewrites evidence that may already have admitted a result.":"审计报告、收据、提交和交付文件会保留在项目账本中。删除对话绝不会重写可能已经准入结果的证据。",
  "This only removes the individual chat from navigation.":"此操作只会从导航中移除该独立对话。","Delete chat":"删除对话","Delete chat from project":"从项目中删除对话","Delete project from CrossAudit":"从 CrossAudit 删除项目",
  "Return to the main Projects window to delete this open project":"请返回主项目窗口后删除当前打开的项目","Move to Trash & delete GitHub repositories":"移到废纸篓并删除 GitHub 仓库","Deleting…":"正在删除…","Project moved to Trash":"项目已移到废纸篓",
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
  "Switch models, reasoning effort and audit loop settings":"切换模型、推理强度和审计循环设置"
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
  [/^(\d+) projects? · (\d+)\/(\d+) active · (.+)$/i,m=>m[1]+' 个项目 · '+m[2]+'/'+m[3]+' 活跃 · '+m[4]],
  [/^(.+) API key — connect in Settings$/i,m=>m[1]+' API key — 请先在设置中连接'],
  [/^Connect (.+) in Settings first$/i,m=>'请先在设置中连接 '+m[1]],
  [/^(.+) — highest capability$/i,m=>m[1]+' — 最高能力'],
  [/^(.+) — balanced · recommended$/i,m=>m[1]+' — 均衡 · 推荐'],
  [/^(.+) — fastest, lowest cost$/i,m=>m[1]+' — 最快、成本最低'],
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
let attachmentConsent = false;
let taskChoiceMode = '';
let pendingChoiceTask = '';
let activeView = 'tasks';
let newTaskMode = false;
let activeChatId = '';

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

let workspacePickerContext='project';
function updateWorkspaceFields(path){
  const value=path||'Not selected';
  document.getElementById('project-workspace').value=value;
  document.getElementById('settings-workspace').value=value;
  const name=document.getElementById('project-name').value.trim()||'your-project';
  document.getElementById('project-path-preview').textContent=value==='Not selected'
    ?'Choose where this project\'s local folder will be created.'
    :'Local project: '+value.replace(/\/$/,'')+'/'+name;
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
  const current=(projectState&&projectState.workspace)||document.getElementById('settings-workspace').value||'';
  const bridge=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.crossaudit;
  if(!bridge){workspaceError('Use the CrossAudit macOS app to choose a local folder. The browser console cannot read arbitrary folder paths.');return;}
  bridge.postMessage({action:'chooseWorkspace',current});
}
window.crossauditWorkspaceSelected=async choice=>{
  if(!choice||!choice.path)return;
  try{const result=await api('/api/workspace/select',{path:choice.path});
    if(projectState)projectState.workspace=result.workspace;updateWorkspaceFields(result.workspace);
    await refreshProjects();
  }catch(e){showInlineError(workspacePickerContext==='settings'?'settings-error':'wizard-error',e);}
};

const settingsModal=document.getElementById('settings-modal');
const settingsForm=document.getElementById('settings-form');
let settingsSource=null;let settingsState=null;
function renderProviderCards(d){
  const host=document.getElementById('provider-credentials');
  const vendors=Object.keys(d.providers||{});
  if(host.getAttribute('data-vendors')===vendors.join(','))return;
  host.setAttribute('data-vendors',vendors.join(','));
  host.innerHTML=vendors.map(vendor=>{const p=d.providers[vendor]||{};const label=p.label||vendor;
    const subscription=vendor==='openai'
      ?'<div class="connection-method"><div class="connection-method-copy"><b>ChatGPT subscription</b><small id="chatgpt-detail">'+esc((p.subscription||{}).detail||'Official Codex sign-in.')+'</small></div><button type="button" class="secondary" id="connect-chatgpt">Connect</button></div>'
      :'<div class="provider-note"><b>API access.</b> '+esc((p.subscription||{}).detail||'Use an official developer API key.')+'</div>';
    const links=(p.console_url?'<a class="login-link" href="'+esc(p.console_url)+'" target="_blank" rel="noopener">Get key ↗</a> ':'')
      +(p.docs_url?'<a class="login-link" href="'+esc(p.docs_url)+'" target="_blank" rel="noopener">API docs ↗</a>':'');
    return '<div class="credential-card"><div class="credential-head"><b>'+esc(label)+'</b><span class="credential-state" id="'+esc(vendor)+'-state">Checking…</span></div>'
      +subscription+'<div class="secret-row"><label class="field"><span>New API key · '+links+'</span><input type="password" id="'+esc(vendor)+'-key" data-provider-key="'+esc(vendor)+'" autocomplete="new-password" placeholder="Leave blank to keep the saved key"></label>'
      +'<label class="toggle-line"><input type="checkbox" id="remove-'+esc(vendor)+'" data-provider-remove="'+esc(vendor)+'"><span><b>Remove</b><small>Delete saved key</small></span></label></div>'
      +'<div class="secret-row"><label class="field"><span>Backup API key (optional)</span><input type="password" id="'+esc(vendor)+'-backup-key" data-provider-key="'+esc(vendor)+'_backup" autocomplete="new-password" placeholder="Used only by an explicit fallback route"></label>'
      +'<label class="toggle-line"><input type="checkbox" id="remove-'+esc(vendor)+'-backup" data-provider-remove="'+esc(vendor)+'_backup"><span><b>Remove</b><small>Delete backup key</small></span></label></div></div>';
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
  renderDoctor(d.doctor);
}
async function openSettings(){
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
function runtimeEl(role,name){return document.getElementById('runtime-'+role+'-'+name);}
function runtimeModel(role){const select=runtimeEl(role,'model');return select.value==='__custom__'
  ?runtimeEl(role,'custom').value.trim():select.value;}
function renderRuntimeEfforts(role,row){const target=runtimeEl(role,'effort');const previous=target.value;
  target.innerHTML='<option value="">Automatic · provider default</option>'+(row.efforts||[]).map(item=>
    '<option value="'+esc(item.id)+'">'+esc(item.id)+' — '+esc(item.hint||'')+'</option>').join('');
  const wanted=row.reasoning_effort!==undefined?row.reasoning_effort:previous;
  if([...target.options].some(option=>option.value===wanted))target.value=wanted;else target.value='';
  runtimeEl(role,'effort-help').textContent=row.detail||((row.efforts||[]).length
    ?'Applies to the next provider request.':'This model uses its provider-controlled default.');
  target.disabled=!(row.efforts||[]).length;}
function renderRuntimeRole(role,row){runtimeRoles[role]=row;const card=runtimeEl(role,'card');
  const human=row.vendor==='human';card.classList.toggle('human',human);runtimeEl(role,'vendor').textContent=row.label||row.vendor;
  const select=runtimeEl(role,'model');const rows=row.models||[];select.innerHTML=rows.map(item=>
    '<option value="'+esc(item.id)+'">'+esc(item.id)+' — '+esc(item.hint||'available')+'</option>').join('')
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
  syncRuntimeBusy(lastState);runtimeModal.className='project-modal on';}
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
    closeRuntime();route.className='route on';route.innerHTML='<b>Project controls updated</b> — recovery routes, usage guardrails, models and loop limits apply to the next provider call.';}
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
  const submit=document.getElementById('submit-resolution');
  if(action==='reopen'){
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
function openResolution(value,action='',sha=''){
  let row=typeof value==='object'&&value?value:null;
  if(!row&&lastState)row=(lastState.escalations||[]).find(item=>item.cycle_id===value);
  row=row||{cycle_id:value,short_sha:sha,sha,round:1,max_rounds:lastState&&lastState.max_rounds||3,
    limit_reached:false,why:'The automatic audit loop stopped.',issues:[],attempts:[],
    requested:'Review why the loop stopped, then decide whether to revise or stop.'};
  activeResolution=row;promptedEscalations.add(row.cycle_id);
  document.getElementById('resolution-cycle').value=row.cycle_id||'';
  document.getElementById('resolution-reason').value='';resolutionChoice(action);
  const used=Number(row.round||0),maximum=Number(row.max_rounds||(lastState&&lastState.max_rounds)||0);
  document.getElementById('resolution-flag').textContent=row.limit_reached?'Automatic audit limit reached':'Automatic loop paused';
  document.getElementById('resolution-title').textContent='The audit needs your decision';
  document.getElementById('resolution-summary').textContent=row.limit_reached
    ?'CrossAudit used all '+used+' of '+maximum+' automatic rounds without a passing result. Nothing will continue or be admitted until you decide.'
    :'CrossAudit stopped safely. Nothing will continue or be admitted until you decide.';
  document.getElementById('resolution-limit-title').textContent=row.limit_reached
    ?'Automatic rounds used: '+used+' / '+maximum:'The automatic loop could not continue safely';
  const attempts=(row.attempts||[]).map(item=>'Round '+item.round+': '+item.verdict+' · '+item.findings+' issue'+(item.findings===1?'':'s')).join(' → ');
  document.getElementById('resolution-limit-copy').textContent=attempts
    ?'Round history: '+attempts
    :String(row.stop_reason||row.why||'The audit controller paused this task.');
  const issues=row.issues||[];
  document.getElementById('resolution-issue-count').textContent=String(issues.length);
  document.getElementById('resolution-issues').innerHTML=issues.length?issues.map((issue,index)=>
    '<article class="decision-issue"><div class="decision-issue-head"><span>'+esc(issue.severity||'BLOCKER')+'</span><b>'
    +esc(issue.rule||'Issue '+(index+1))+'</b></div><p>'+esc(issue.observation||'No explanation was recorded.')+'</p>'
    +(issue.artifact?'<small>Affects '+esc(issue.artifact)+'</small>':'')+'</article>').join('')
    :'<div class="decision-empty">No structured findings were recorded. Review the stop reason above before continuing.</div>';
  document.getElementById('resolution-request').textContent=row.requested||'Choose whether to revise and continue, or stop this task.';
  document.getElementById('resolution-error').className='wizard-error';
  resolutionModal.className='project-modal on';
  setTimeout(()=>{const target=action?document.getElementById('resolution-reason')
    :resolutionForm.querySelector('input[name="resolution-choice"]');if(target)target.focus();},0);
}
function closeResolution(){resolutionModal.className='project-modal';resolutionForm.reset();activeResolution=null;resolutionChoice('');}
resolutionForm.querySelectorAll('input[name="resolution-choice"]').forEach(input=>input.onchange=()=>resolutionChoice(input.value));
document.getElementById('close-resolution').onclick=closeResolution;
document.getElementById('cancel-resolution').onclick=closeResolution;
resolutionModal.addEventListener('click',ev=>{if(ev.target===resolutionModal)closeResolution();});
resolutionForm.onsubmit=async ev=>{ev.preventDefault();const button=document.getElementById('submit-resolution');
  const cycleId=document.getElementById('resolution-cycle').value;
  const action=document.getElementById('resolution-action').value,reason=document.getElementById('resolution-reason').value.trim();
  if(!action){showInlineError('resolution-error','Choose whether to revise and continue, or stop this task.');return;}
  if(!reason){showInlineError('resolution-error','Add concrete guidance or a reason so the decision is auditable.');return;}
  button.disabled=true;document.getElementById('resolution-error').className='wizard-error';
  try{await api('/api/escalation',{cycle_id:cycleId,action,reason});
    closeResolution();route.className='route on';
    if(action==='reopen'){
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
const projectModal=document.getElementById('project-modal');
const projectForm=document.getElementById('project-form');
const recoveryModal=document.getElementById('recovery-modal');
const recoveryForm=document.getElementById('recovery-form');
const deleteProjectModal=document.getElementById('delete-project-modal');
const deleteProjectForm=document.getElementById('delete-project-form');
let deleteProjectPreview=null;
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
  target.innerHTML=rows.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.id)+' — '+esc(x.hint)+'</option>').join('')
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
    +rows.map(x=>'<option value="'+x.id+'"'+(x.ready?'':' disabled')+'>'+esc(x.label)+(x.ready?'':' — connect in Settings')+'</option>').join('');
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
  document.getElementById(role+'-custom-wrap').className='field custom-model'+(select.value==='__custom__'?'':' off');
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
  if(issue.action==='choose_workspace')actions+='<button type="button" class="secondary" data-job-action="choose_workspace">Choose another folder</button>';
  if(issue.action==='retry'&&root)actions+='<button type="button" class="secondary" data-job-action="retry" data-root="'+esc(root)+'">Try again</button>';
  if(issue.url)actions+='<a class="secondary" href="'+esc(issue.url)+'" target="_blank" rel="noopener">Open help ↗</a>';
  return '<b>'+esc(issue.title||'Setup needs attention')+'</b><p>'+esc(row.detail||'Review the settings and retry.')+'</p>'
    +(actions?'<div class="guidance-actions">'+actions+'</div>':'');
}
function renderProjectJob(jobs){
  const row=(jobs||[]).find(j=>j.id===activeProjectJob);
  const panel=document.getElementById('project-job');
  if(!row){panel.className='job-panel';return;}
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
    +(d.items.length===1?'':'s')+' · '+cap.active+'/'+cap.limit+' active · '+d.workspace;
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
  renderProjectJob(d.jobs);configureProjectForm();
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
  deleteProjectPreview=null;document.getElementById('delete-project-error').className='wizard-error';}
function syncDeleteProject(){const github=document.getElementById('delete-project-github').checked;
  document.getElementById('delete-github-confirm-wrap').className='field conditional-field'+(github?'':' off');
  const localReady=Boolean(deleteProjectPreview)&&document.getElementById('delete-project-confirmation').value===deleteProjectPreview.name;
  const remoteReady=!github||document.getElementById('delete-github-confirmation').value==='DELETE GITHUB';
  const button=document.getElementById('confirm-delete-project');button.disabled=!(localReady&&remoteReady&&deleteProjectPreview.can_delete);
  button.textContent=github?(currentLocale==='zh'?'移到废纸篓并永久删除 GitHub 仓库':'Move to Trash & delete GitHub repositories')
    :(currentLocale==='zh'?'将项目移到废纸篓':'Move project to Trash');}
async function openDeleteProject(root){deleteProjectForm.reset();deleteProjectPreview=null;
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
    const repos=preview.repositories||[],remote=document.getElementById('delete-project-github');remote.disabled=!repos.length;
    document.getElementById('delete-project-repositories').textContent=repos.length
      ?(currentLocale==='zh'?'永久删除：':'Permanently delete: ')+repos.join(', ')
      :(currentLocale==='zh'?'未检测到 GitHub 仓库。':'No GitHub repositories detected.');
    document.getElementById('delete-project-confirmation').placeholder=preview.name;syncDeleteProject();
  }catch(e){showInlineError('delete-project-error',e);}}
document.getElementById('delete-project-confirmation').oninput=syncDeleteProject;
document.getElementById('delete-github-confirmation').oninput=syncDeleteProject;
document.getElementById('delete-project-github').onchange=syncDeleteProject;
document.getElementById('close-delete-project').onclick=closeDeleteProject;
document.getElementById('cancel-delete-project').onclick=closeDeleteProject;
deleteProjectModal.addEventListener('click',ev=>{if(ev.target===deleteProjectModal)closeDeleteProject();});
deleteProjectForm.onsubmit=async ev=>{ev.preventDefault();if(!deleteProjectPreview)return;
  const button=document.getElementById('confirm-delete-project');button.disabled=true;button.textContent=currentLocale==='zh'?'正在删除…':'Deleting…';
  try{const result=await api('/api/projects/delete',{action:'delete',root:deleteProjectPreview.root,
      confirmation:document.getElementById('delete-project-confirmation').value,
      delete_github:document.getElementById('delete-project-github').checked,
      github_confirmation:document.getElementById('delete-github-confirmation').value});
    closeDeleteProject();await refreshProjects();const panel=document.getElementById('project-job');panel.className='job-panel on complete';
    document.getElementById('open-created').hidden=true;
    document.getElementById('job-title').textContent=currentLocale==='zh'?'项目已移到废纸篓':'Project moved to Trash';
    const failed=(result.github||[]).filter(row=>row.status==='failed');
    document.getElementById('job-detail').textContent=(currentLocale==='zh'?'可从以下位置恢复：':'Recover from: ')+result.archive
      +(failed.length?(currentLocale==='zh'?' · GitHub 删除未完全成功：':' · GitHub deletion incomplete: ')+failed.map(row=>row.repo).join(', '):'');
    document.getElementById('job-steps').innerHTML='';document.getElementById('job-guidance').className='job-guidance';
  }catch(e){showInlineError('delete-project-error',e);syncDeleteProject();}};
function openProjectModal(){projectForm.reset();document.getElementById('wizard-error').className='wizard-error';
  if(settingsState&&settingsState.doctor&&settingsState.doctor.status==='blocked'){
    openSettings();doctorMessage('Fix the required Environment Doctor items before creating a project.',true);return;}
  repoNameTouched={science:false,audit:false};resetRepositoryCheck();
  configureProjectForm();const vendors=Object.keys((projectState&&projectState.models)||{});
  auditorVendor.value=vendors.includes('openai')?'openai':vendors[0];
  generatorVendor.value=vendors.includes('anthropic')?'anthropic':vendors.find(v=>v!==auditorVendor.value);
  syncRoleChoices();syncProjectType();syncRepoNames(true);updateWorkspaceFields(projectState&&projectState.workspace);
  projectModal.className='project-modal on';
  setTimeout(()=>document.getElementById('project-name').focus(),0);}
function closeProjectModal(){projectModal.className='project-modal';}

auditorVendor.onchange=syncRoleChoices;generatorVendor.onchange=syncRoleChoices;
auditorConnection.onchange=()=>modelOptions(auditorVendor.value,auditorModel);
generatorConnection.onchange=()=>modelOptions(generatorVendor.value,generatorModel);
auditorEndpoint.onchange=()=>modelOptions(auditorVendor.value,auditorModel);
generatorEndpoint.onchange=()=>modelOptions(generatorVendor.value,generatorModel);
auditorModel.onchange=()=>syncCustomModel('auditor');generatorModel.onchange=()=>syncCustomModel('generator');
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
document.getElementById('project-name').addEventListener('input',()=>syncRepoNames(false));
document.getElementById('science-repo').addEventListener('input',()=>{repoNameTouched.science=true;resetRepositoryCheck();});
document.getElementById('audit-repo').addEventListener('input',()=>{repoNameTouched.audit=true;resetRepositoryCheck();});
document.getElementById('adopt-existing').onchange=resetRepositoryCheck;
document.getElementById('check-repositories').onclick=()=>checkRepositoryNames(true).catch(()=>{});
document.getElementById('choose-project-workspace').onclick=()=>chooseWorkspace('project');
document.getElementById('max-rounds-choice').onchange=ev=>{
  const n=Number(ev.target.value);document.getElementById('round-limit-help').textContent='Up to '+n
    +' generator → auditor round'+(n===1?'':'s')+', then the task pauses for you. It never auto-passes.';};
projectType.onchange=syncProjectType;
document.getElementById('github-toggle').onchange=syncGithubFields;
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
document.getElementById('project-job').onclick=ev=>{const action=ev.target.closest('[data-job-action]');if(!action)return;
  const kind=action.getAttribute('data-job-action'),root=action.getAttribute('data-root');
  if(kind==='connect_github')document.querySelector('[data-connect-github]')?.click();
  else if(kind==='edit_repositories'&&root)openRecovery(root);
  else if(kind==='edit_new_repositories'){const row=(projectState&&projectState.jobs||[]).find(j=>j.id===activeProjectJob);
    openProjectModal();if(row){document.getElementById('project-name').value=row.project||'';
      document.getElementById('science-repo').value=row.science||'';document.getElementById('audit-repo').value=row.audit||'';
      repoNameTouched={science:true,audit:true};resetRepositoryCheck();}}
  else if(kind==='choose_workspace')chooseWorkspace('project');
  else if(kind==='retry'&&root)openRecovery(root);};
document.getElementById('open-created').onclick=()=>createdRoot&&openProject(createdRoot,false);
projectModal.addEventListener('click',ev=>{if(ev.target===projectModal)closeProjectModal();});
projectForm.onsubmit=async ev=>{ev.preventDefault();const submit=document.getElementById('submit-project');
  const error=document.getElementById('wizard-error');error.className='wizard-error';submit.disabled=true;
  const fd=new FormData(projectForm);const payload=Object.fromEntries(fd.entries());
  payload.auditor_model=auditorModel.value==='__custom__'?document.getElementById('auditor-custom').value.trim():auditorModel.value;
  payload.generator_model=generatorModel.value==='__custom__'?document.getElementById('generator-custom').value.trim():generatorModel.value;
  payload.github=document.getElementById('github-toggle').checked;payload.public=fd.has('public');
  payload.adopt_existing=document.getElementById('adopt-existing').checked;
  payload.workspace=projectState&&projectState.workspace||'';
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
  const f=artifactRecord(item);const bits=[context||f.kind,formatBytes(f.bytes),status].filter(Boolean);
  const core='<span class="artifact-icon">'+esc((f.extension||'FILE').slice(0,4))+'</span>'
    +'<span class="artifact-copy"><span class="artifact-name">'+esc(f.path)+'</span>'
    +'<span class="artifact-context">'+esc(bits.join(' · '))+'</span></span>';
  if(f.available===false) return '<div class="output-file unavailable"><span class="artifact-main">'+core+'</span>'
    +'<span class="artifact-action" aria-hidden="true">—</span></div>';
  const name=esc(f.name||f.path),path=esc(f.path);
  const primary='<button type="button" class="artifact-main" data-preview="'+path+'" aria-label="Preview '+name+'">'+core+'</button>';
  return '<div class="artifact output-file">'+primary+'<span class="artifact-actions">'
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
function artifactList(items,status){
  if(!items||!items.length) return '';
  const shown=items.slice(0,6).map(f=>outputFile(f,status,'')).join('');
  const more=items.length>6?'<button type="button" class="output-more" data-open-artifacts>View all '
    +items.length+' files</button>':'';
  return '<section class="output-files" aria-label="Generated files"><div class="output-head">Files produced'
    +'<span class="output-count">'+items.length+'</span></div><div class="artifact-list">'+shown+'</div>'+more+'</section>';
}
function turn(m,d){
  if(m.kind === 'you'){
    const explicit=m.routing_mode==='explicit';const recipient=m.addressed_to||m.lane;
    const delivery=explicit?'@ '+recipient:recipient==='auditor'?'To Auditor':'To Generator';
    return '<article class="turn user"><div class="avatar">Y</div><div class="turn-main">'
    + '<div class="turn-meta"><b>You</b><span class="direct-mark">' + esc(delivery) + '</span>'
    + '<span class="turn-time">' + at(m.t) + '</span></div>'
    + '<div class="turn-body">' + esc(m.utterance) + '</div></div></article>';
  }
  if(m.kind === 'auditor_chat') return '<article class="turn audit"><div class="avatar">A</div><div class="turn-main">'
    +'<div class="turn-meta"><b>Auditor</b><span>direct reply · no project files shared</span>'
    +'<span class="turn-time">'+at(m.t)+'</span></div><div class="turn-body">'+esc(m.response)+'</div></div></article>';
  if(m.kind === 'auditor'){
    const fs = (m.findings||[]).map(f => '<div class="finding"><div class="finding-head">'
      + '<span class="severity">' + esc(f.severity) + '</span><span>' + esc(f.rule) + '</span>'
      + '<span class="spacer"></span><span>' + esc(f.artifact) + '</span></div><p>'
      + esc(f.observation) + '</p></div>').join('');
    return '<article class="turn audit"><div class="avatar">A</div><div class="turn-main">'
      + '<div class="turn-meta"><b>Auditor</b><span class="status ' + esc(m.verdict) + '">'
      + esc(m.verdict) + '</span><span class="turn-time">' + at(m.t) + '</span></div>'
      + (fs || '<div class="turn-body">No findings. The audited increment passed.</div>')
      + '</div></article>';
  }
  return '<article class="turn"><div class="avatar">G</div><div class="turn-main">'
    + '<div class="turn-meta"><b>Generator</b>' + (m.round ? '<span>round ' + m.round + '</span>' : '')
    + '<span class="turn-time">' + at(m.t) + '</span></div><div class="turn-body">'
    + esc(m.summary) + '</div>' + artifactList(m.artifacts||m.files,auditStatus(d,m.sha)) + '</div></article>';
}
function runCard(d){
  const p = chatProgress(d),cycles=chatCycles(d);
  const latestCycle=cycles.length?cycles[cycles.length-1]:null;
  const ownsPipeline=p||(latestCycle&&d.cycles.length&&latestCycle.sha===d.cycles[d.cycles.length-1].sha);
  const pipeline=ownsPipeline?d.pipeline:[];
  const show = p || pipeline.some(s => s.state !== 'pending');
  if(!show) return '';
  const outcome = p ? (p.finished ? p.outcome : 'running') : statusOf(d);
  const tone = String(outcome||'ready').toLowerCase();
  const pulse = outcome === 'passed' || outcome === 'PASSED' || outcome === 'CONSUMED' ? ' done'
    : outcome === 'escalated' || outcome === 'ESCALATED' ? ' warn'
    : outcome === 'running' ? '' : ' bad';
  const reached = pipeline.filter(s => s.state !== 'pending').length;
  const meter = pipeline.length ? Math.round(reached / pipeline.length * 100) : 0;
  const roundEvents = p && p.steps ? p.steps.filter(s => s.actor === 'loop' && s.text.startsWith('round ')) : [];
  const roundMatch = roundEvents.length ? roundEvents[roundEvents.length-1].text.match(/\d+/) : null;
  const round = roundMatch ? roundMatch[0] : latestCycle ? latestCycle.round : '—';
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
  return '<section class="run-card ' + esc(tone) + '" aria-label="Audit loop">'
    + '<div class="run-overview"><div class="run-top"><span class="pulse' + pulse + '"></span>'
    + '<span class="run-eyebrow">Audit loop</span><span class="status ' + esc(outcome) + '">'
    + esc(outcome) + '</span></div><div class="run-task">' + esc(task) + '</div><div class="run-meta">'
    + '<span>Round <strong>' + esc(round) + '</strong> of ' + esc(d.max_rounds) + '</span>'
    + '<span><strong>' + reached + '</strong> of ' + pipeline.length + ' gates reached</span>'
    + '<span>' + (p ? p.elapsed + 's elapsed' : 'Ledger snapshot') + '</span></div>'
    + '<div class="run-meter" role="progressbar" aria-label="Audit gates reached" aria-valuemin="0" '
    + 'aria-valuemax="100" aria-valuenow="' + meter + '"><i style="width:' + meter + '%"></i></div></div>'
    + '<div class="loop">' + pipeline.map((s,i) => '<div class="loop-step ' + esc(s.state) + '" '
      + 'aria-label="' + esc(s.title + ': ' + stateNames[s.state]) + '"><div class="loop-track">'
      + '<div class="loop-mark">' + esc(MARK[s.state] || String(i+1)) + '</div></div>'
      + '<div class="loop-name"><span class="loop-index">0' + (i+1) + '</span>' + esc(s.title) + '</div>'
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
    + '<p>Describe a task in plain language. A generator will make the change, deterministic checks will run, '
    + 'and an independent model will audit every round before admission.</p></div>';
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
    :status==='escalated'?['Needs your input','CrossAudit needs a decision before it can continue.']
    :['Stopped','The task did not complete.'];
  const action=status==='passed'?'<button type="button" data-admit data-admit-cycle="'+esc(cycle.id)+'">Admit result</button>'
    :status==='escalated'?'<button type="button" data-open-decisions>Review issues & decide</button>'
    :status==='open'?''
    :'<button type="button" data-open-audits>View audit details</button>';
  return '<div class="delivery-status '+esc(status)+'"><span class="delivery-dot"></span><span><b>'
    +copy[0]+'</b> · '+copy[1]+'</span>'+action+'</div>';
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
  if(value===null||value===undefined)return '—';const n=Number(value||0);
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
    +esc(row.role)+' · '+esc(row.phase)+' · '+formatTokens(row.input)+' in / '+formatTokens(row.output)+' out</span></div>'
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
    return '<div class="host-row"><div class="host-top"><span class="host-dot"></span><b>'+esc(host.alias)+'</b>'
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
    return '<div class="host-row"><div class="host-top"><span class="host-dot"></span><b>'+esc(server.name)+'</b>'
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
  else if(activeView === 'artifacts') html = artifactsView(d);
  else if(activeView === 'audits') html = auditsView(d);
  else if(activeView === 'usage') html = usageView(d);
  else if(activeView === 'compute') html = computeView(d);
  else if(activeView === 'tools') html = toolsView(d);
  else{
    const messages = allMessages(d);
    html = (messages.length ? messages.map(m=>turn(m,d)).join('') : welcome()) + deliveryStatus(d);
  }
  document.getElementById('conversation').innerHTML = html;
  if(followLive && !newTaskMode) thread.scrollTop = thread.scrollHeight;
  else thread.scrollTop = Math.min(previousTop,Math.max(0,thread.scrollHeight-thread.clientHeight));
}
function renderTasks(d){
  const rows=(d.chats&&d.chats.items)||[];
  const chatRow=c=>'<div class="task'+(c.id===activeChatId?' active':'')+'" role="button" tabindex="0" data-chat-id="'+esc(c.id)+'">'
    +'<div class="task-copy"><div class="task-title">'+esc(c.title)+'</div><div class="task-meta"><span class="state-dot '
    +esc(c.status)+'"></span><span>'+esc(c.status)+'</span><span>· '+c.cycles+' cycle'+(c.cycles===1?'':'s')+'</span></div></div>'
    +'<button type="button" class="pin-button'+(c.pinned?' pinned':'')+'" data-pin-chat="'+esc(c.id)+'" '
    +'aria-label="'+(c.pinned?'Unpin':'Pin')+' chat" title="'+(c.pinned?'Unpin':'Pin')+' chat">'+(c.pinned?'★':'☆')+'</button>'
    +'<button type="button" class="task-delete" data-delete-chat="'+esc(c.id)+'" '
    +'aria-label="Delete chat from project" title="Delete chat from project">⌫</button></div>';
  const pinned=rows.filter(c=>c.pinned),recent=rows.filter(c=>!c.pinned);
  let html='';if(pinned.length)html+='<div class="side-label">Pinned</div>'+pinned.map(chatRow).join('');
  if(recent.length)html+='<div class="side-label">Recent</div>'+recent.map(chatRow).join('');
  document.getElementById('task-list').innerHTML=html||'<div class="empty" style="padding:9px">No chats yet</div>';
}
function renderInspector(d){
  document.getElementById('runtime-generator').textContent = d.generator;
  document.getElementById('runtime-auditor').textContent = d.auditor;
  document.getElementById('max-rounds').textContent = d.max_rounds;
  const progress=chatProgress(d),cycles=chatCycles(d);
  const current = progress && progress.steps ? progress.steps.filter(s =>
    s.actor === 'loop' && s.text.startsWith('round ')).slice(-1)[0] : null;
  document.getElementById('current-round').textContent = current ? current.text.replace('round ','')
    : cycles.length ? cycles[cycles.length-1].round + ' / ' + d.max_rounds : '—';
  document.getElementById('rules-count').textContent = d.rules + ' blocker rules';
  document.getElementById('tier-value').textContent = d.tier.tier;
  const contracts = d.check_contracts || {};
  document.getElementById('runtime-checks').innerHTML = Object.keys(contracts).length
    ? Object.entries(contracts).map(([k,v]) => '<div class="contract" title="' + esc(v) + '">✓ '
      + esc(k) + '</div>').join('') : '<div class="empty">No checks configured</div>';
  document.getElementById('mini-metrics').innerHTML = d.metrics.map(m => '<div class="mini-metric">'
    + '<div class="mini-value">' + esc(m.value ?? '—') + '</div><div class="mini-label">'
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
  document.querySelector('.composer-wrap').classList.toggle('view-hidden',['usage','compute','tools'].includes(activeView));
  const preview=document.getElementById('contract-preview');preview.className='contract-preview';preview.innerHTML='';
  document.getElementById('version-badge').textContent = 'V' + d.version;
  document.getElementById('hub-version').textContent = 'V' + d.version;
  document.getElementById('proj').textContent = d.project;
  document.getElementById('side-project').textContent = d.project;
  document.getElementById('tier-label').textContent = d.tier.tier + ' · local controller';
  const files = artifactRows(d);
  const auditRows = d.auditor_stream.filter(m => m.kind === 'auditor'&&(m.chat_id||'history')===activeChatId);
  const heading = newTaskMode ? 'New chat' : activeView === 'artifacts' ? 'Artifacts'
    : activeView === 'audits' ? 'Audits' : activeView === 'usage' ? 'Usage' : activeView === 'compute' ? 'Compute' : activeView === 'tools' ? 'Tools & Skills' : titleOf(d);
  const subtitle = newTaskMode ? 'Independent generation and audit'
    : activeView === 'artifacts' ? files.length + ' audited deliverables'
    : activeView === 'audits' ? auditRows.length + ' independent audit reports'
    : activeView === 'usage' ? formatTokens((d.usage&&d.usage.month&&d.usage.month.tokens)||0) + ' tokens this month'
    : activeView === 'compute' ? ((d.compute&&d.compute.active)||0)+' remote jobs active'
    : activeView === 'tools' ? ((d.mcp&&d.mcp.servers)||[]).length+' MCP servers · '+((d.runtime_config&&d.runtime_config.skills)||[]).length+' Skills'
    : d.generator + ' → ' + d.auditor;
  document.getElementById('thread-title').textContent = heading;
  document.getElementById('thread-subtitle').textContent = subtitle;
  const state = activeView === 'audits' && auditRows.length ? auditRows[auditRows.length-1].verdict
    : activeView === 'artifacts' ? 'ledger' : activeView === 'usage' ? 'local' : activeView === 'compute' ? 'remote' : activeView === 'tools' ? 'policy' : newTaskMode ? 'ready' : statusOf(d);
  const badge = document.getElementById('thread-status');
  badge.textContent = state;badge.className = 'status ' + state;
  document.getElementById('model-summary').textContent = d.generator + ' → ' + d.auditor;
  const projectPin=document.getElementById('current-project-pin'),projectPinned=Boolean(d.chats&&d.chats.project_pinned);
  projectPin.textContent=projectPinned?'★':'☆';projectPin.classList.toggle('pinned',projectPinned);
  projectPin.title=projectPinned?'Unpin project':'Pin project';projectPin.setAttribute('aria-label',projectPin.title);
  renderTasks(d);renderInspector(d);renderConversation(d);
  const iv = document.getElementById('interrupted');
  const interruptedChat=d.interrupted&&(d.interrupted.chat_id||'history');
  const interruptedChatExists=Boolean(interruptedChat&&(d.chats&&d.chats.items||[]).some(item=>item.id===interruptedChat));
  if(d.interrupted&&(interruptedChat===activeChatId||!interruptedChatExists) && !(chatProgress(d) && !chatProgress(d).finished)){
    const interruptedTask=esc(d.interrupted.task.replace(/\s+/g,' ').slice(0,72)),interruptedPhase=esc(d.interrupted.phase||'unknown');
    iv.className = 'interrupted on';iv.innerHTML = currentLocale==='zh'
      ?'<b>任务已安全中断</b><br>“'+interruptedTask+'”。最后可见阶段：'+interruptedPhase+'。已提交轮次均已保留；重试会从最近的持久 Git 提交继续，忽略提示也不会改动文件。<div class="interrupted-actions"><button type="button" data-interrupted="retry">重试任务</button><button type="button" data-interrupted="dismiss">忽略提示</button></div>'
      :'<b>Task interrupted safely</b><br>"'+interruptedTask+'". Last visible phase: '+interruptedPhase+'. Committed rounds are preserved. Retry resumes from the last durable commit; dismiss keeps files unchanged.<div class="interrupted-actions"><button type="button" data-interrupted="retry">Retry task</button><button type="button" data-interrupted="dismiss">Dismiss notice</button></div>';
  }else iv.className = 'interrupted';
  maybePromptForHuman(d);
}
document.getElementById('interrupted').onclick=async ev=>{const button=ev.target.closest('[data-interrupted]');if(!button)return;
  button.disabled=true;const action=button.getAttribute('data-interrupted');
  try{await api('/api/interrupted',{action});route.className='route on';route.innerHTML=currentLocale==='zh'
    ?(action==='retry'?'<b>任务已重启</b> — 正从最近的持久 Git 提交继续。':'<b>提示已忽略</b> — 文件和已提交证据均已保留。')
    :(action==='retry'?'<b>Task restarted</b> — continuing from the last durable Git commit.':'<b>Notice dismissed</b> — files and committed evidence were preserved.');}
  catch(e){route.className='route on error';route.textContent=e.message;button.disabled=false;}};
function selectView(view){
  activeView = ['tasks','artifacts','audits','usage','compute','tools'].includes(view) ? view : 'tasks';
  if(activeView!=='compute')stopComputeTimers();
  newTaskMode = false;
  document.querySelectorAll('.nav-item').forEach(button => {
    const selected = button.getAttribute('data-view') === activeView;
    button.classList.toggle('active',selected);button.setAttribute('aria-pressed',selected ? 'true' : 'false');
  });
  if(lastState) render(lastState);
  document.getElementById('thread').scrollTop = 0;
  closePanels();
}
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
const send=document.getElementById('send');const route=document.getElementById('route');
const filesBox=document.getElementById('attachments');const fileInput=document.getElementById('file-input');
const consentBox=document.getElementById('transfer-consent');
const sidebar=document.querySelector('.sidebar');const inspector=document.getElementById('inspector');
const scrim=document.getElementById('scrim');
function syncScrim(){
  const sideOpen=sidebar.classList.contains('open');const inspectOpen=inspector.classList.contains('open');
  scrim.className='scrim'+(sideOpen||inspectOpen?' on':'')+(sideOpen?' sidebar-open':'')
    +(inspectOpen?' inspector-open':'');
}
function closePanels(){sidebar.classList.remove('open');inspector.classList.remove('open');
  document.getElementById('sidebar-toggle').setAttribute('aria-expanded','false');
  document.getElementById('inspect-toggle').setAttribute('aria-expanded','false');syncScrim();}
function toggleSidebar(){const opening=!sidebar.classList.contains('open');closePanels();
  if(opening){sidebar.classList.add('open');document.getElementById('sidebar-toggle').setAttribute('aria-expanded','true');}
  syncScrim();}
function toggleInspector(){const opening=!inspector.classList.contains('open');closePanels();
  if(opening){inspector.classList.add('open');document.getElementById('inspect-toggle').setAttribute('aria-expanded','true');}
  syncScrim();}
function openInspector(){closePanels();inspector.classList.add('open');
  document.getElementById('inspect-toggle').setAttribute('aria-expanded','true');syncScrim();}
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
function resetConsent(){attachmentConsent=false;consentBox.className='transfer-consent';}
function uniqueFileName(original){let name=original||'untitled';const used=new Set(pendingFiles.map(e=>e.name.toLowerCase()));
  if(!used.has(name.toLowerCase()))return name;const dot=name.lastIndexOf('.');const base=dot>0?name.slice(0,dot):name;
  const ext=dot>0?name.slice(dot):'';let n=2;while(used.has((base+' ('+n+')'+ext).toLowerCase()))n++;
  return base+' ('+n+')'+ext;}
function addFiles(list){resetConsent();for(const file of Array.from(list||[])){
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
function showTransferConsent(){
  const target=lastState?lastState.generator:'the configured generator';
  document.getElementById('consent-copy').textContent=pendingFiles.length+' file(s) will be stored in this project. Supported text content will be sent to '+target+'.';
  document.getElementById('confirm-transfer').textContent='Upload and send';
  consentBox.className='transfer-consent on';
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
  uploadProgress.delete(pendingFiles[i]);pendingFiles.splice(i,1);resetConsent();drawFiles();}};
document.getElementById('confirm-transfer').onclick=()=>{attachmentConsent=true;consentBox.className='transfer-consent';form.requestSubmit();};
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
const taskChoices=document.getElementById('task-choices');
function resetTaskChoices(){taskChoiceMode='';pendingChoiceTask='';taskChoices.className='task-choices';}
function likelyContentTask(text){return /(?:\b(?:write|draft|review|report|article|essay|brief|summary|copy|document)\b|写|撰写|评测|评论|报告|文章|总结)/i.test(text);}
function needsTaskChoices(text){return audienceOf()!=='auditor'&&likelyContentTask(text);}
function selectedChoice(name){const item=document.querySelector('input[name="'+name+'"]:checked');return item?item.value:'';}
function taskChoicePayload(){return taskChoiceMode==='prompt'?{mode:'prompt'}:{mode:'selected',
  focus:selectedChoice('task_focus'),format:selectedChoice('task_format'),tone:selectedChoice('task_tone')};}
document.getElementById('close-task-choices').onclick=()=>{taskChoices.className='task-choices';say.focus();};
document.getElementById('use-prompt-as-written').onclick=()=>{taskChoiceMode='prompt';taskChoices.className='task-choices';form.requestSubmit();};
document.getElementById('run-with-choices').onclick=()=>{taskChoiceMode='selected';taskChoices.className='task-choices';form.requestSubmit();};
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
document.querySelectorAll('.nav-item').forEach(button => button.onclick=()=>selectView(button.getAttribute('data-view')));
document.getElementById('conversation').onclick=ev=>{
  if(ev.target.closest('[data-open-artifacts]'))selectView('artifacts');
  if(ev.target.closest('[data-open-audits]'))selectView('audits');
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
    api('/api/admit',{cycle_id:admit.getAttribute('data-admit-cycle')}).catch(e=>{route.className='route on';route.innerHTML='<b>Not admitted</b> — '+esc(e.message);});}
};
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
  if(row){activeChatId=row.getAttribute('data-chat-id');newTaskMode=false;activeView='tasks';
    if(pendingContinuation.chat&&pendingContinuation.chat!==activeChatId)pendingContinuation={cycle:'',chat:''};
    document.querySelectorAll('.nav-item').forEach(button=>button.classList.toggle('active',button.getAttribute('data-view')==='tasks'));
    render(lastState);document.getElementById('thread').scrollTop=0;closePanels();}
};
document.getElementById('task-list').onkeydown=ev=>{if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-chat-id]')){
  ev.preventDefault();ev.target.click();}};
document.getElementById('current-project-pin').onclick=async()=>{if(!lastState)return;const button=document.getElementById('current-project-pin');
  const pinned=Boolean(lastState.chats&&lastState.chats.project_pinned);button.disabled=true;
  try{await api('/api/projects/pin',{root:lastState.root,pinned:!pinned});lastState.chats.project_pinned=!pinned;render(lastState);}
  catch(e){route.className='route on';route.innerHTML='<b>Could not pin project</b> — '+esc(e.message);}
  finally{button.disabled=false;}};
document.getElementById('new-task').onclick=async()=>{
  activeView='tasks';newTaskMode=true;say.value='';route.className='route';pendingFiles=[];
  pendingContinuation={cycle:'',chat:''};
  uploadProgress=new Map();
  resetTaskChoices();
  syncAudience();
  fileInput.value='';resetConsent();drawFiles();
  document.querySelectorAll('.nav-item').forEach(button => {
    const selected=button.getAttribute('data-view')==='tasks';button.classList.toggle('active',selected);
    button.setAttribute('aria-pressed',selected?'true':'false');
  });
  try{const result=await api('/api/chats/new',{title:'New chat'});activeChatId=result.chat.id;
    if(lastState){lastState.chats.items.unshift({...result.chat,cycles:0,status:'ready'});render(lastState);}}
  catch(e){route.className='route on';route.innerHTML='<b>Could not create chat</b> — '+esc(e.message);}
  document.getElementById('thread').scrollTop=0;closePanels();say.focus();
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
  else if(modal===runtimeModal)closeRuntime();else if(modal===resolutionModal)closeResolution();
  else if(modal===settingsModal)closeSettings();else if(modal===computeHostModal)closeComputeHost();
  else if(modal===computeJobModal)closeComputeJob();else if(modal===mcpModal)closeMcp();
}
document.addEventListener('keydown',ev=>{const modal=activeModal();
  if(ev.key==='Tab'&&modal){const controls=[...modal.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
      .filter(element=>element.getClientRects().length);if(!controls.length){ev.preventDefault();return;}
    const first=controls[0],last=controls.at(-1);if(ev.shiftKey&&(document.activeElement===first||!modal.contains(document.activeElement))){ev.preventDefault();last.focus();}
    else if(!ev.shiftKey&&(document.activeElement===last||!modal.contains(document.activeElement))){ev.preventDefault();first.focus();}return;}
  if(ev.key==='Escape'){if(modal){ev.preventDefault();closeActiveModal(modal);}
    else if(filePreviewModal.classList.contains('on'))closeFilePreview();else closePanels();}
});
window.addEventListener('resize',()=>{if(innerWidth>1120)closePanels();});
form.onsubmit=async ev=>{ev.preventDefault();const rawText=say.value.trim();if(!rawText)return;
  const continuing=pendingContinuation.chat===activeChatId&&Boolean(pendingContinuation.cycle);
  if(needsTaskChoices(rawText)&&!taskChoiceMode&&!continuing){pendingChoiceTask=rawText;taskChoices.className='task-choices on';return;}
  const text=rawText;const deliveryChoices=taskChoiceMode&&pendingChoiceTask===rawText?taskChoicePayload():null;
  if(pendingFiles.length&&!attachmentConsent){showTransferConsent();return;}
  newTaskMode=false;activeView='tasks';if(lastState)render(lastState);
  send.disabled=true;say.disabled=true;transferBusy=true;document.getElementById('attach').disabled=true;route.className='route on';
  route.textContent=pendingFiles.length?'Sending your files…':'Starting…';
  try{const uploadBatch=pendingFiles.length?await uploadFiles(pendingFiles):null;
    const r=await api('/api/say',{text,chat_id:activeChatId,upload_batch:uploadBatch,attachment_consent:attachmentConsent,
      delivery_choices:continuing?null:deliveryChoices,continuation_cycle:continuing?pendingContinuation.cycle:''});if(r.asked){route.innerHTML='<b class="ask">Needs clarification</b> — '
    + esc(r.clarify);resetConsent();resetTaskChoices();}else{activeChatId=r.chat_id||activeChatId;route.innerHTML=r.lane==='generator'
      ?'<b>Task started.</b> The result will appear in this conversation.'
      :'<b>Message delivered.</b>';
    if(r.lane==='generator')pendingContinuation={cycle:'',chat:''};
    if(!pendingFiles.length||r.attachments_accepted){say.value='';pendingFiles=[];uploadProgress=new Map();fileInput.value='';drawFiles();syncAudience();resetTaskChoices();}
    resetConsent();}}
  catch(e){resetConsent();route.innerHTML='<b>Refused</b> — '+esc(e.message);}
  transferBusy=false;document.getElementById('attach').disabled=false;send.disabled=false;say.disabled=false;say.focus();};
api('/api/state').then(render).catch(e=>{document.getElementById('thread-title').textContent='Disconnected — '+e.message;});
startStream();
if(location.hash==='#projects')showProjects();
async function initialReadiness(){
  for(let attempt=0;attempt<12;attempt++){
    try{const s=await api('/api/settings');settingsState=s;
      const providers=Object.values(s.providers||{}).filter(p=>p.configured).length;
      const blocked=s.doctor&&s.doctor.status==='blocked';
      if(s.app_mode&&location.hash==='#projects'&&(providers<2||blocked)){
        await openSettings();if(blocked)doctorMessage('Required setup needs attention before creating a project.',true);return;}
      if(!s.doctor||s.doctor.status!=='running')return;
    }catch(e){return;}
    await new Promise(resolve=>setTimeout(resolve,500));
  }
}
initialReadiness();
</script></body></html>"""
