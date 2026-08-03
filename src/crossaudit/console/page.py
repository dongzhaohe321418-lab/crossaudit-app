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
  border-bottom:1px solid var(--line);background:var(--header-bg);z-index:5}
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
.task{padding:9px 10px;border-radius:8px;margin-bottom:2px}.task:hover{background:var(--hover)}
.task.active{background:var(--surface);box-shadow:inset 0 0 0 1px var(--line)}
.task-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12.5px}
.task-meta{display:flex;align-items:center;gap:6px;margin-top:3px;color:var(--faint);font-size:10.5px}
.state-dot{width:6px;height:6px;border-radius:50%;background:var(--faint)}
.state-dot.PASSED,.state-dot.CONSUMED{background:var(--green)}
.state-dot.BLOCKED{background:var(--red)}.state-dot.ESCALATED{background:var(--amber)}
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
.thread{flex:1;overflow:auto;min-height:0;scrollbar-gutter:stable}
.thread-inner{width:min(760px,calc(100% - 48px));margin:0 auto;padding:28px 0 120px}
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
  border-radius:9px;padding:8px 9px;display:flex;align-items:center;gap:9px;background:var(--panel);
  color:inherit;text-decoration:none}.output-file:hover{border-color:var(--line-strong);background:var(--surface-2)}
.output-file.unavailable{opacity:.62}.output-file.unavailable:hover{border-color:var(--line);background:var(--panel)}
.artifact-icon{width:31px;height:31px;flex:none;border-radius:7px;background:var(--blue-bg);color:var(--blue);
  display:grid;place-items:center;font-size:8.5px;font-weight:700;letter-spacing:.02em}
.artifact-copy{min-width:0}.artifact-name{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace}
.artifact-context{display:block;font-size:9.5px;color:var(--faint);margin-top:2px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}.artifact-action{margin-left:auto;flex:none;color:var(--muted);
  font-size:14px}.output-more{margin-top:6px;padding:2px 0;border:0;background:transparent;color:var(--blue);
  font:inherit;font-size:10.5px;cursor:pointer}.output-more:hover{text-decoration:underline}
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
  color:var(--violet)}.event-mark.done{background:var(--green-bg);color:var(--green)}
.event-main{min-width:0}.event-line{font-size:10.8px;line-height:1.35}.event-line b{font-weight:650;
  margin-right:6px}.event-detail{color:var(--faint);font-size:9.8px;line-height:1.4;margin-top:2px;
  white-space:pre-wrap;overflow-wrap:anywhere}.event-time{color:var(--faint);font-size:9px;padding-top:2px}
.activity-empty{padding:6px 4px;color:var(--faint);font-size:10.5px;line-height:1.45}
.audit-evidence-head{display:flex;align-items:baseline;gap:8px;margin:24px 0 12px;padding-top:1px}
.audit-evidence-head h3{margin:0;font-size:13px}.audit-evidence-head span{color:var(--faint);font-size:10px}
.interrupted{margin-bottom:20px;padding:10px 12px;background:var(--amber-bg);color:var(--amber);
  border-radius:9px;font-size:12px;display:none}.interrupted.on{display:block}

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
  .usage-roles{grid-template-columns:1fr}.usage-cards{grid-template-columns:1fr 1fr}.usage-card-value{font-size:18px}
  .usage-bars{gap:4px;padding-left:6px;padding-right:6px}.usage-day-value{display:none}
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
  border-radius:8px;padding:0 12px;background:var(--surface)}.secondary:hover{background:var(--hover)}
.hub-main{width:min(1100px,calc(100% - 48px));margin:0 auto;padding:44px 0 72px}
.hub-heading{display:flex;gap:18px;align-items:flex-end;margin-bottom:26px}.hub-heading h1{margin:0;
  font-size:26px;letter-spacing:-.035em}.hub-heading p{margin:5px 0 0;color:var(--muted)}
.hub-summary{margin-left:auto;color:var(--muted);font-size:12px}.hub-tools{display:flex;gap:9px;
  margin-bottom:14px}.hub-search{height:36px;min-width:280px;border:1px solid var(--line);
  border-radius:9px;background:var(--surface);padding:0 12px;outline:0}.hub-search:focus{border-color:var(--faint)}
.project-table{border:1px solid var(--line);border-radius:12px;background:var(--surface);overflow:hidden;
  box-shadow:var(--shadow)}.project-row{width:100%;border:0;border-bottom:1px solid var(--line);
  background:transparent;display:grid;grid-template-columns:minmax(220px,1.5fr) minmax(220px,1fr)
  92px 100px 116px 28px;align-items:center;gap:14px;padding:15px 18px;text-align:left;cursor:pointer}
.project-row:last-child{border-bottom:0}.project-row:hover{background:var(--surface-2)}
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
.role-card{border:1px solid var(--line);border-radius:10px;padding:13px;background:var(--panel)}
.role-card b{display:block;margin-bottom:9px}.role-card .field+.field{margin-top:10px}
.model-actions{display:flex;justify-content:flex-end;margin-top:6px}.model-actions button{height:27px;font-size:10px}
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
.wizard-error{display:none;color:var(--red);background:var(--red-bg);border-radius:8px;padding:9px 11px;
  margin-top:14px;font-size:11px}.wizard-error.on{display:block}
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
.top-project{cursor:pointer;border-top:0;border-right:0;border-bottom:0;background:transparent;text-align:left}
@media(max-width:760px){.hub-bar{padding:0 14px}.hub-main{width:calc(100% - 24px);padding-top:26px}
  .hub-heading{align-items:flex-start;flex-direction:column}.hub-summary{margin-left:0}.project-row{grid-template-columns:minmax(0,1fr) 60px 62px 16px;gap:8px}
  .project-models,.project-tier{display:none}.form-grid{grid-template-columns:1fr}
  .field.full{grid-column:auto}.project-modal{padding:8px}.wizard{max-height:calc(100vh - 16px)}}
</style></head>
<body>
<section class="project-hub" id="project-hub" aria-label="Projects">
  <header class="hub-bar"><button class="brand-button" id="hub-brand"><span class="brand-mark">◇</span>
    CrossAudit <span class="version" id="hub-version">V4.3.0</span></button><span class="spacer"></span>
    <button class="icon-button" id="hub-settings" aria-label="Settings" title="Settings">⚙</button>
    <button class="icon-button" id="hub-theme" aria-label="Switch theme">◐</button>
    <button class="primary" id="create-project">＋ New project</button></header>
  <main class="hub-main"><div class="hub-heading"><div><h1>Projects</h1>
    <p>Supervised workspaces on this computer.</p></div><div class="hub-summary" id="workspace-label">Discovering workspace…</div></div>
    <div class="job-panel" id="project-job"><span class="job-spinner"></span><div class="job-copy">
      <b id="job-title">Creating project</b><span id="job-detail">Validating settings…</span>
      <ul class="job-steps" id="job-steps"></ul></div>
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
        <label class="field"><span>Model</span><select name="auditor_model_choice" id="auditor-model"></select></label>
        <label class="field custom-model off" id="auditor-custom-wrap"><span>Custom model ID</span><input id="auditor-custom" maxlength="120" placeholder="Model available to your account"></label>
        <div class="model-actions"><button type="button" class="secondary" data-refresh-models="auditor">Refresh from provider</button></div></div>
      <div class="role-card"><b>Generator</b><label class="field"><span>Provider</span><select name="generator_vendor" id="generator-vendor"></select></label>
        <label class="field"><span>Connection</span><select name="generator_connection" id="generator-connection" required></select></label>
        <label class="field"><span>Model</span><select name="generator_model_choice" id="generator-model"></select></label>
        <label class="field custom-model off" id="generator-custom-wrap"><span>Custom model ID</span><input id="generator-custom" maxlength="120" placeholder="Model available to your account"></label>
        <div class="model-actions"><button type="button" class="secondary" data-refresh-models="generator">Refresh from provider</button></div></div>
    </div></section>
    <section class="form-section"><div class="form-title">GitHub</div><div class="github-box">
      <label class="toggle-line"><input type="checkbox" name="github" id="github-toggle" checked><span><b>Create and connect two repositories</b>
        <small>The work repository holds deliverables. The audit repository holds rules, reports and the auditor secret.</small></span></label>
      <div class="connection" id="github-connection">Checking GitHub connection…</div>
      <div class="github-fields" id="github-fields"><div class="form-grid">
        <label class="field"><span>Work repository</span><input name="science_repo" id="science-repo" placeholder="owner/project"></label>
        <label class="field"><span>Audit repository</span><input name="audit_repo" id="audit-repo" placeholder="owner/project-audit"></label>
        <label class="toggle-line full"><input type="checkbox" name="public"><span><b>Public repositories</b><small>Off by default. Private is safer for a new project.</small></span></label>
      </div></div></div><div class="wizard-error" id="wizard-error"></div></section></div>
    <div class="wizard-foot"><span>Creating may send the description to the auditor model and create repositories in your connected GitHub account.</span>
      <button type="button" class="secondary" id="cancel-project">Cancel</button><button class="primary" id="submit-project">Create project</button></div>
  </form>
</div>

<div class="project-modal" id="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
  <form class="wizard" id="settings-form"><div class="wizard-head"><div><h2 id="settings-title">CrossAudit settings</h2>
    <p>Connect subscriptions or enter API keys without editing files or environment variables.</p></div>
    <span class="spacer"></span><button type="button" class="icon-button" id="close-settings" aria-label="Close settings">×</button></div>
    <div class="wizard-body"><section class="form-section"><div class="form-title">Provider credentials</div>
      <div class="credential-card"><div class="credential-head"><b>OpenAI</b><span class="credential-state" id="openai-state">Checking…</span></div>
        <div class="connection-method"><div class="connection-method-copy"><b>ChatGPT subscription</b><small id="chatgpt-detail">Use the official Codex login and an eligible ChatGPT plan. CrossAudit never receives the OAuth token.</small></div><button type="button" class="secondary" id="connect-chatgpt">Connect</button></div>
        <div class="secret-row"><label class="field"><span>New API key</span><input type="password" id="openai-key" autocomplete="new-password" placeholder="Leave blank to keep the saved key"></label>
          <label class="toggle-line"><input type="checkbox" id="remove-openai"><span><b>Remove</b><small>Delete saved key</small></span></label></div></div>
      <div class="credential-card"><div class="credential-head"><b>Anthropic</b><span class="credential-state" id="anthropic-state">Checking…</span></div>
        <div class="provider-note"><b>Subscription login unavailable.</b> Anthropic currently requires third-party applications to use API or approved enterprise-cloud credentials; CrossAudit will not capture Claude.ai cookies or subscription tokens.</div>
        <div class="secret-row"><label class="field"><span>New API key</span><input type="password" id="anthropic-key" autocomplete="new-password" placeholder="Leave blank to keep the saved key"></label>
          <label class="toggle-line"><input type="checkbox" id="remove-anthropic"><span><b>Remove</b><small>Delete saved key</small></span></label></div></div>
    </section><section class="form-section"><div class="form-title">Application readiness</div>
      <div class="settings-readiness"><div class="readiness-item">Git<span id="git-state">…</span></div>
        <div class="readiness-item">GitHub connection tool<span id="ghcli-state">…</span></div>
        <div class="readiness-item">Application build<span id="runtime-state">…</span></div>
        <div class="readiness-item">Code identity<span id="digest-state">…</span></div></div>
      <label class="field" style="margin-top:12px"><span>Project workspace</span><input id="settings-workspace" readonly></label>
    </section><div class="wizard-error" id="settings-error"></div></div>
    <div class="wizard-foot"><span>API keys are write-only macOS Keychain items. Subscription credentials stay with the official provider runtime.</span>
      <button type="button" class="secondary" id="cancel-settings">Cancel</button><button class="primary" id="save-settings">Save settings</button></div>
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
      <span class="version" id="version-badge">V4.3.0</span></button>
    <button class="top-project" id="project-switcher"><b id="proj">…</b> <span id="branch-label">/ supervised workspace</span>⌄</button>
    <span class="spacer"></span>
    <div class="live-pill"><span class="live-dot" id="livedot"></span><span id="conn-text">connecting</span></div>
    <button class="icon-button" id="settings-open" aria-label="Settings" title="Settings">⚙</button>
    <button class="icon-button" id="theme-toggle" aria-label="Switch to dark theme" title="Toggle theme">◐</button>
    <button class="icon-button mobile-inspector" id="inspect-toggle" aria-label="Toggle audit context"
      aria-controls="inspector" aria-expanded="false">☷</button>
  </header>

  <button class="scrim" id="scrim" aria-label="Close open panel"></button>

  <aside class="sidebar" id="sidebar-panel" aria-label="Tasks">
    <button class="new-task" id="new-task"><span>＋</span>New task<span>⌘ N</span></button>
    <nav class="nav" aria-label="Workspace views">
      <button type="button" class="nav-item active" data-view="tasks" aria-pressed="true"><span class="nav-icon">◫</span>Tasks</button>
      <button type="button" class="nav-item" data-view="artifacts" aria-pressed="false"><span class="nav-icon">▱</span>Artifacts</button>
      <button type="button" class="nav-item" data-view="audits" aria-pressed="false"><span class="nav-icon">◇</span>Audits</button>
      <button type="button" class="nav-item" data-view="usage" aria-pressed="false"><span class="nav-icon">◒</span>Usage</button></nav>
    <div class="side-label">Recent</div><div class="task-list" id="task-list"></div>
    <div class="sidebar-foot"><b id="side-project">…</b><span id="tier-label">local controller</span></div>
  </aside>

  <main class="workspace">
    <div class="thread-head"><div class="participants" aria-label="Conversation participants">
      <span class="participant" title="You">Y</span><span class="participant" title="Generator">G</span>
      <span class="participant auditor" title="Auditor">A</span></div><div class="thread-title"><h1 id="thread-title">New task</h1>
      <p id="thread-subtitle">Independent generation and audit</p></div><span class="spacer"></span>
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
        <label class="choice-option" title="Binary export is not yet receipt-auditable"><input type="radio" name="task_format" value="PDF" disabled><span>PDF</span></label>
        <label class="choice-option" title="Binary export is not yet receipt-auditable"><input type="radio" name="task_format" value="DOCX" disabled><span>DOCX</span></label>
      </div></div><p class="choice-note">PDF and DOCX are not available yet.</p>
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
const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const at = t => t ? new Date(t*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '';
const MARK = {done:'✓',failed:'×',current:'·',pending:''};
let lastState = null;
let pendingFiles = [];
let uploadProgress = new Map();
let transferBusy = false;
let attachmentConsent = false;
let taskChoiceMode = '';
let pendingChoiceTask = '';
let activeView = 'tasks';
let newTaskMode = false;

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

async function api(path, body){
  const opt = body ? {method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify(body)} : {};
  const r = await fetch(path + '?t=' + encodeURIComponent(T), opt);
  if(!r.ok) throw new Error(r.status + ' ' + await r.text());
  return r.json();
}

const settingsModal=document.getElementById('settings-modal');
const settingsForm=document.getElementById('settings-form');
let settingsSource=null;
function renderSettings(d){
  for(const vendor of ['openai','anthropic']){
    const provider=d.providers&&d.providers[vendor]||{};
    const apiConfigured=Boolean(provider.api_key&&provider.api_key.configured);
    const configured=Boolean(provider.configured);
    const state=document.getElementById(vendor+'-state');state.textContent=configured?'Connected':'Not connected';
    state.className='credential-state'+(configured?' ok':'');
    document.getElementById('remove-'+vendor).disabled=!apiConfigured;
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
  const deps=d.dependencies||{};
  for(const [id,value] of [['git-state',deps.git],['ghcli-state',deps.github_cli]]){
    const el=document.getElementById(id);el.textContent=value?'Ready':'Missing';el.className=value?'':'bad';
  }
  document.getElementById('settings-workspace').value=d.workspace||'Not selected';
  const runtime=d.runtime||{};document.getElementById('runtime-state').textContent=runtime.install_mode||'unknown';
  document.getElementById('digest-state').textContent=runtime.code_digest||'unavailable';
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
settingsModal.addEventListener('click',ev=>{if(ev.target===settingsModal)closeSettings();});
document.getElementById('connect-chatgpt').onclick=async()=>{
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
  const payload={openai_key:document.getElementById('openai-key').value,
    anthropic_key:document.getElementById('anthropic-key').value,
    remove_openai:document.getElementById('remove-openai').checked,
    remove_anthropic:document.getElementById('remove-anthropic').checked};
  try{const state=await api('/api/settings',payload);settingsForm.reset();renderSettings(state);
    if(projectState)configureProjectForm();}
  catch(e){error.textContent=e.message;error.className='wizard-error on';}
  save.disabled=false;};

let projectState=null;
let projectSource=null;
let activeProjectJob=null;
let createdRoot=null;
const projectModal=document.getElementById('project-modal');
const projectForm=document.getElementById('project-form');
const auditorVendor=document.getElementById('auditor-vendor');
const generatorVendor=document.getElementById('generator-vendor');
const auditorConnection=document.getElementById('auditor-connection');
const generatorConnection=document.getElementById('generator-connection');
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
  const rows=[];
  if(vendor==='openai')rows.push({id:'chatgpt',label:'ChatGPT subscription',ready:Boolean(state.chatgpt&&state.chatgpt.connected)});
  rows.push({id:'api',label:vendor[0].toUpperCase()+vendor.slice(1)+' API key',ready:Boolean(state.api_key&&state.api_key.configured)});
  const readyRows=rows.filter(x=>x.ready);
  target.innerHTML=(readyRows.length?'':'<option value="" selected disabled>Connect '+esc(vendor)+' in Settings first</option>')
    +rows.map(x=>'<option value="'+x.id+'"'+(x.ready?'':' disabled')+'>'+esc(x.label)+(x.ready?'':' — connect in Settings')+'</option>').join('');
  if([...target.options].some(o=>o.value===previous&&!o.disabled))target.value=previous;
  else{const ready=[...target.options].find(o=>!o.disabled);if(ready)target.value=ready.value;}
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
  modelOptions(auditorVendor.value,auditorModel);modelOptions(generatorVendor.value,generatorModel);
}
function configureProjectForm(){
  if(!projectState)return;
  const vendors=Object.keys(projectState.models||{});
  if(!auditorVendor.options.length){
    auditorVendor.innerHTML=vendors.map(v=>'<option value="'+esc(v)+'">'+esc(v)+'</option>').join('');
    generatorVendor.innerHTML=vendors.map(v=>'<option value="'+esc(v)+'">'+esc(v)+'</option>').join('');
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
  }else{connection.className='connection bad';connection.innerHTML='<div class="github-connect"><span>'
    +esc(auth.detail||gh.detail||'GitHub is not connected')+'</span><button type="button" class="secondary" data-connect-github>Connect GitHub</button></div>';}
  document.getElementById('github-toggle').disabled=!gh.connected;
  if(!gh.connected)document.getElementById('github-toggle').checked=false;
  syncGithubFields();
}
function syncRepoNames(){
  if(!projectState||!projectState.github||!projectState.github.owner)return;
  const name=document.getElementById('project-name').value.trim();
  if(!name)return;
  const owner=projectState.github.owner;
  document.getElementById('science-repo').value=owner+'/'+name;
  document.getElementById('audit-repo').value=owner+'/'+name+'-audit';
}
function syncGithubFields(){
  const on=document.getElementById('github-toggle').checked;
  document.getElementById('github-fields').className='github-fields'+(on?'':' off');
}
function syncProjectType(){
  const science=projectType.value==='science';
  document.getElementById('project-contract-hint').textContent=science
    ?'Scientific projects require the visible metadata.yml/results.json, units, convergence, and provenance contract.'
    :'General projects use format, reference, link, and completeness checks. They do not require scientific metadata sidecars.';
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
    +(p.setup&&p.setup.recoverable?'<span class="project-recovery"><span>'+esc(p.setup.detail||'GitHub setup stopped')+'</span>'
      +'<span class="retry-setup" role="button" tabindex="0" data-resume-root="'+esc(p.root)+'">Retry setup</span></span>':'')
    +(p.interrupted?'<span class="project-interrupted">Interrupted · open to review and run again</span>':'')+'</span>'
    +'<span class="project-models">'+esc(p.generator)+' → '+esc(p.auditor)+'</span>'
    +'<span class="project-stat">'+p.cycles+' cycles</span><span class="status '+esc(p.status)+'">'+esc(p.status)+'</span>'
    +(p.paired?'<span class="paired-mark project-tier">GitHub paired</span>':'<span class="project-stat project-tier">Local</span>')
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
function hideProjects(){document.body.classList.remove('hub-mode');projectModal.className='project-modal';
  history.replaceState(null,'',location.pathname+'?t='+encodeURIComponent(T));}
async function openProject(root,current){
  if(current){hideProjects();return;}
  try{const r=await api('/api/projects/open',{root});location.href=r.url;}catch(e){
    const panel=document.getElementById('project-job');panel.className='job-panel on failed';
    document.getElementById('job-title').textContent='Could not open project';document.getElementById('job-detail').textContent=e.message;}
}
function openProjectModal(){projectForm.reset();document.getElementById('wizard-error').className='wizard-error';
  configureProjectForm();const vendors=Object.keys((projectState&&projectState.models)||{});
  auditorVendor.value=vendors.includes('openai')?'openai':vendors[0];
  generatorVendor.value=vendors.includes('anthropic')?'anthropic':vendors.find(v=>v!==auditorVendor.value);
  syncRoleChoices();syncProjectType();projectModal.className='project-modal on';
  setTimeout(()=>document.getElementById('project-name').focus(),0);}
function closeProjectModal(){projectModal.className='project-modal';}

auditorVendor.onchange=syncRoleChoices;generatorVendor.onchange=syncRoleChoices;
auditorConnection.onchange=()=>modelOptions(auditorVendor.value,auditorModel);
generatorConnection.onchange=()=>modelOptions(generatorVendor.value,generatorModel);
auditorModel.onchange=()=>syncCustomModel('auditor');generatorModel.onchange=()=>syncCustomModel('generator');
document.querySelectorAll('[data-refresh-models]').forEach(button=>button.onclick=async()=>{
  const role=button.getAttribute('data-refresh-models');const vendor=role==='auditor'?auditorVendor.value:generatorVendor.value;
  const method=role==='auditor'?auditorConnection.value:generatorConnection.value;
  button.disabled=true;button.textContent='Refreshing…';
  try{const result=await api('/api/models/refresh',{role,vendor,method});
    projectState.models[vendor]=result.models.map(id=>({id,hint:'visible to this account'}));
    modelOptions(vendor,role==='auditor'?auditorModel:generatorModel);
    button.textContent='Updated '+new Date(result.refreshed*1000).toLocaleTimeString();}
  catch(e){button.textContent='Refresh failed';const error=document.getElementById('wizard-error');
    error.textContent=e.message;error.className='wizard-error on';}
  finally{button.disabled=false;setTimeout(()=>button.textContent='Refresh from provider',3500);}
});
document.getElementById('project-name').addEventListener('input',syncRepoNames);
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
    catch(e){connect.disabled=false;connect.textContent='Connect GitHub';document.getElementById('wizard-error').textContent=e.message;
      document.getElementById('wizard-error').className='wizard-error on';}}
};
document.getElementById('create-project').onclick=openProjectModal;
document.getElementById('close-project-modal').onclick=closeProjectModal;
document.getElementById('cancel-project').onclick=closeProjectModal;
document.getElementById('projects-home').onclick=showProjects;
document.getElementById('back-projects').onclick=showProjects;
document.getElementById('project-switcher').onclick=showProjects;
document.getElementById('hub-brand').onclick=hideProjects;
document.getElementById('project-search').oninput=()=>projectState&&renderProjects(projectState);
document.getElementById('project-list').onclick=ev=>{const row=ev.target.closest('[data-root]');
  const retry=ev.target.closest('[data-resume-root]');
  if(retry){ev.preventDefault();ev.stopPropagation();resumeProject(retry.getAttribute('data-resume-root'));return;}
  if(row)openProject(row.getAttribute('data-root'),row.getAttribute('data-current')==='1');};
document.getElementById('project-list').onkeydown=ev=>{
  if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-root]')){ev.preventDefault();ev.target.click();}
  if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[data-resume-root]')){ev.preventDefault();ev.target.click();}}
async function resumeProject(root){
  try{const r=await api('/api/projects/resume',{root});activeProjectJob=r.job;createdRoot=null;
    renderProjectJob([{id:r.job,status:'running',project:root.split('/').pop(),detail:'Resuming GitHub setup',steps:[]}]);}
  catch(e){const panel=document.getElementById('project-job');panel.className='job-panel on failed';
    document.getElementById('job-title').textContent='Could not resume setup';
    document.getElementById('job-detail').textContent=e.message;document.getElementById('job-steps').innerHTML='';}}
document.getElementById('open-created').onclick=()=>createdRoot&&openProject(createdRoot,false);
projectModal.addEventListener('click',ev=>{if(ev.target===projectModal)closeProjectModal();});
projectForm.onsubmit=async ev=>{ev.preventDefault();const submit=document.getElementById('submit-project');
  const error=document.getElementById('wizard-error');error.className='wizard-error';submit.disabled=true;
  const fd=new FormData(projectForm);const payload=Object.fromEntries(fd.entries());
  payload.auditor_model=auditorModel.value==='__custom__'?document.getElementById('auditor-custom').value.trim():auditorModel.value;
  payload.generator_model=generatorModel.value==='__custom__'?document.getElementById('generator-custom').value.trim():generatorModel.value;
  payload.github=document.getElementById('github-toggle').checked;payload.public=fd.has('public');
  payload.max_rounds=Number(payload.max_rounds);
  try{const r=await api('/api/projects/create',payload);activeProjectJob=r.job;createdRoot=null;
    closeProjectModal();renderProjectJob([{id:r.job,status:'running',project:payload.name,
      detail:'Starting local project setup'}]);}
  catch(e){error.textContent=e.message;error.className='wizard-error on';}
  submit.disabled=false;};

function statusOf(d){
  if(d.progress && !d.progress.finished) return 'running';
  if(d.progress && d.progress.finished) return d.progress.outcome || 'ready';
  if(d.cycles.length) return d.cycles[d.cycles.length-1].status;
  return 'ready';
}
function titleOf(d){
  const users = [...d.generator_stream,...d.auditor_stream].filter(x => x.kind === 'you');
  if(users.length) return users.sort((a,b) => b.t-a.t)[0].utterance.replace(/\s+/g,' ').slice(0,88);
  if(d.progress && d.progress.task) return d.progress.task.replace(/\s+/g,' ').slice(0,88);
  return 'New task';
}
function fileUrl(path){return '/api/file?t=' + encodeURIComponent(T) + '&path=' + encodeURIComponent(path);}
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
  if(f.available===false) return '<div class="output-file unavailable">'+core
    +'<span class="artifact-action" aria-hidden="true">—</span></div>';
  return '<a class="artifact output-file" href="'+fileUrl(f.path)+'" download aria-label="Download '
    +esc(f.name||f.path)+'">'+core+'<span class="artifact-action" aria-hidden="true">↓</span></a>';
}
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
  const p = d.progress;
  const show = p || d.pipeline.some(s => s.state !== 'pending');
  if(!show) return '';
  const outcome = p ? (p.finished ? p.outcome : 'running') : statusOf(d);
  const tone = String(outcome||'ready').toLowerCase();
  const pulse = outcome === 'passed' || outcome === 'PASSED' || outcome === 'CONSUMED' ? ' done'
    : outcome === 'escalated' || outcome === 'ESCALATED' ? ' warn'
    : outcome === 'running' ? '' : ' bad';
  const reached = d.pipeline.filter(s => s.state !== 'pending').length;
  const meter = d.pipeline.length ? Math.round(reached / d.pipeline.length * 100) : 0;
  const latestCycle = d.cycles.length ? d.cycles[d.cycles.length-1] : null;
  const roundEvents = p && p.steps ? p.steps.filter(s => s.actor === 'loop' && s.text.startsWith('round ')) : [];
  const roundMatch = roundEvents.length ? roundEvents[roundEvents.length-1].text.match(/\d+/) : null;
  const round = roundMatch ? roundMatch[0] : latestCycle ? latestCycle.round : '—';
  const focus = d.pipeline.find(s => s.state === 'current') || d.pipeline.find(s => s.state === 'failed')
    || d.pipeline.find(s => s.state === 'pending') || d.pipeline[d.pipeline.length-1];
  const focusLabel = focus.state === 'current' ? 'Current gate' : focus.state === 'failed' ? 'Stopped at'
    : focus.state === 'pending' ? 'Next gate' : 'Completed gate';
  const stateNames = {done:'Complete',failed:'Blocked',current:'Active',pending:'Pending'};
  const actorNames = {generator:'Generator',auditor:'Auditor',loop:'Controller',done:'Result'};
  const actorMarks = {generator:'G',auditor:'A',loop:'↻',done:'✓'};
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
    + '<span><strong>' + reached + '</strong> of ' + d.pipeline.length + ' gates reached</span>'
    + '<span>' + (p ? p.elapsed + 's elapsed' : 'Ledger snapshot') + '</span></div>'
    + '<div class="run-meter" role="progressbar" aria-label="Audit gates reached" aria-valuemin="0" '
    + 'aria-valuemax="100" aria-valuenow="' + meter + '"><i style="width:' + meter + '%"></i></div></div>'
    + '<div class="loop">' + d.pipeline.map((s,i) => '<div class="loop-step ' + esc(s.state) + '" '
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
    if(m.kind==='auditor') return false;
    if(m.kind!=='generator') return true;
    return ['passed','consumed'].includes(auditStatus(d,m.sha));
  });
  const seen = new Set();
  return rows.filter(m => {const key = [m.kind,m.t,m.utterance||m.summary||m.verdict].join('|');
    if(seen.has(key)) return false;seen.add(key);return true;}).sort((a,b) => a.t-b.t);
}
function deliveryStatus(d){
  const p=d.progress;const cycle=d.cycles.length?d.cycles[d.cycles.length-1]:null;
  const raw=p&&!p.finished?'running':p&&p.finished?p.outcome:cycle?cycle.status.toLowerCase():'';
  if(!raw)return'';const status=String(raw).toLowerCase();
  const copy=status==='running'?['Working','The result will appear here when it is ready.']
    :status==='passed'||status==='consumed'?['Ready','The delivered files passed the independent review.']
    :status==='blocked'?['Needs revision','The result did not pass review yet.']
    :status==='escalated'?['Needs your input','CrossAudit needs a decision before it can continue.']
    :['Stopped','The task did not complete.'];
  const action=status==='passed'?'<button type="button" data-admit>Admit result</button>'
    :'<button type="button" data-open-audits>View audit details</button>';
  return '<div class="delivery-status '+esc(status)+'"><span class="delivery-dot"></span><span><b>'
    +copy[0]+'</b> · '+copy[1]+'</span>'+action+'</div>';
}
function artifactRows(d){
  const files = new Map();
  d.generator_stream.filter(m => m.kind === 'generator').forEach(m => (m.artifacts||m.files||[]).forEach(item => {
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
  const audits = d.auditor_stream.filter(m => m.kind === 'auditor');
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
  const u=d.usage||{};const today=u.today||{};const month=u.month||{};
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
  return '<div class="view-heading"><h2>Token usage</h2><p>Project-level model consumption, updated with every completion.</p></div>'
    +'<div class="usage-note"><span>ⓘ</span><div><b>Local metering · '+esc(u.cost_label||'API-value estimate')+'</b><br>'
    +'Token counts come from the provider runtime when available. Costs use the '+esc(u.price_snapshot||'current')
    +' public API price snapshot and are not a provider invoice or subscription charge.</div></div>'
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
  else{
    const messages = allMessages(d);
    html = (messages.length ? messages.map(m=>turn(m,d)).join('') : welcome()) + deliveryStatus(d);
  }
  document.getElementById('conversation').innerHTML = html;
  if(followLive && !newTaskMode) thread.scrollTop = thread.scrollHeight;
  else thread.scrollTop = Math.min(previousTop,Math.max(0,thread.scrollHeight-thread.clientHeight));
}
function renderTasks(d){
  const rows = [...d.cycles].reverse();
  document.getElementById('task-list').innerHTML = rows.length ? rows.map((c,i) =>
    '<div class="task' + (i === 0 ? ' active' : '') + '"><div class="task-title">'
    + esc(c.sha.slice(0,12)) + '</div><div class="task-meta"><span class="state-dot '
    + esc(c.status) + '"></span><span>' + esc(c.status.toLowerCase()) + '</span><span>· round '
    + c.round + '</span></div></div>').join('') : '<div class="empty" style="padding:9px">No tasks yet</div>';
}
function renderInspector(d){
  document.getElementById('runtime-generator').textContent = d.generator;
  document.getElementById('runtime-auditor').textContent = d.auditor;
  document.getElementById('max-rounds').textContent = d.max_rounds;
  const current = d.progress && d.progress.steps ? d.progress.steps.filter(s =>
    s.actor === 'loop' && s.text.startsWith('round ')).slice(-1)[0] : null;
  document.getElementById('current-round').textContent = current ? current.text.replace('round ','')
    : d.cycles.length ? d.cycles[d.cycles.length-1].round + ' / ' + d.max_rounds : '—';
  document.getElementById('rules-count').textContent = d.rules + ' blocker rules';
  document.getElementById('tier-value').textContent = d.tier.tier;
  const contracts = d.check_contracts || {};
  document.getElementById('runtime-checks').innerHTML = Object.keys(contracts).length
    ? Object.entries(contracts).map(([k,v]) => '<div class="contract" title="' + esc(v) + '">✓ '
      + esc(k) + '</div>').join('') : '<div class="empty">No checks configured</div>';
  document.getElementById('mini-metrics').innerHTML = d.metrics.map(m => '<div class="mini-metric">'
    + '<div class="mini-value">' + esc(m.value ?? '—') + '</div><div class="mini-label">'
    + esc(m.label) + '</div></div>').join('');
  document.getElementById('escalations').innerHTML = d.escalations.length ? d.escalations.map(e =>
    '<div class="escalation"><b>' + esc(e.sha) + ' · round ' + e.round + '</b><p>'
    + esc(e.why) + '</p></div>').join('') : '<div class="empty">Nothing needs attention.</div>';
}
function render(d){
  lastState = d;
  document.querySelector('.composer-wrap').classList.toggle('view-hidden',activeView==='usage');
  const preview=document.getElementById('contract-preview');preview.className='contract-preview';preview.innerHTML='';
  document.getElementById('version-badge').textContent = 'V' + d.version;
  document.getElementById('hub-version').textContent = 'V' + d.version;
  document.getElementById('proj').textContent = d.project;
  document.getElementById('side-project').textContent = d.project;
  document.getElementById('tier-label').textContent = d.tier.tier + ' · local controller';
  const files = artifactRows(d);
  const auditRows = d.auditor_stream.filter(m => m.kind === 'auditor');
  const heading = newTaskMode ? 'New task' : activeView === 'artifacts' ? 'Artifacts'
    : activeView === 'audits' ? 'Audits' : activeView === 'usage' ? 'Usage' : titleOf(d);
  const subtitle = newTaskMode ? 'Independent generation and audit'
    : activeView === 'artifacts' ? files.length + ' audited deliverables'
    : activeView === 'audits' ? auditRows.length + ' independent audit reports'
    : activeView === 'usage' ? formatTokens((d.usage&&d.usage.month&&d.usage.month.tokens)||0) + ' tokens this month'
    : d.generator + ' → ' + d.auditor;
  document.getElementById('thread-title').textContent = heading;
  document.getElementById('thread-subtitle').textContent = subtitle;
  const state = activeView === 'audits' && auditRows.length ? auditRows[auditRows.length-1].verdict
    : activeView === 'artifacts' ? 'ledger' : activeView === 'usage' ? 'local' : newTaskMode ? 'ready' : statusOf(d);
  const badge = document.getElementById('thread-status');
  badge.textContent = state;badge.className = 'status ' + state;
  document.getElementById('model-summary').textContent = d.generator + ' → ' + d.auditor;
  renderTasks(d);renderInspector(d);renderConversation(d);
  const iv = document.getElementById('interrupted');
  if(d.interrupted && !(d.progress && !d.progress.finished)){
    iv.className = 'interrupted on';iv.textContent = 'Interrupted run: "'
      + d.interrupted.task.replace(/\s+/g,' ').slice(0,72) + '". Send it again to continue.';
  }else iv.className = 'interrupted';
}
function selectView(view){
  activeView = ['tasks','artifacts','audits','usage'].includes(view) ? view : 'tasks';
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
document.querySelectorAll('.nav-item').forEach(button => button.onclick=()=>selectView(button.getAttribute('data-view')));
document.getElementById('conversation').onclick=ev=>{
  if(ev.target.closest('[data-open-artifacts]'))selectView('artifacts');
  if(ev.target.closest('[data-open-audits]'))selectView('audits');
  const admit=ev.target.closest('[data-admit]');if(admit){admit.disabled=true;admit.textContent='Verifying…';
    api('/api/admit',{}).catch(e=>{route.className='route on';route.innerHTML='<b>Not admitted</b> — '+esc(e.message);});}
};
document.getElementById('new-task').onclick=()=>{
  activeView='tasks';newTaskMode=true;say.value='';route.className='route';pendingFiles=[];
  uploadProgress=new Map();
  resetTaskChoices();
  syncAudience();
  fileInput.value='';resetConsent();drawFiles();
  document.querySelectorAll('.nav-item').forEach(button => {
    const selected=button.getAttribute('data-view')==='tasks';button.classList.toggle('active',selected);
    button.setAttribute('aria-pressed',selected?'true':'false');
  });
  if(lastState)render(lastState);document.getElementById('thread').scrollTop=0;closePanels();say.focus();
};
document.getElementById('sidebar-toggle').onclick=toggleSidebar;
document.getElementById('inspect-toggle').onclick=toggleInspector;
document.getElementById('inspect-close').onclick=closePanels;
scrim.onclick=closePanels;
document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closePanels();});
window.addEventListener('resize',()=>{if(innerWidth>1120)closePanels();});
form.onsubmit=async ev=>{ev.preventDefault();const rawText=say.value.trim();if(!rawText)return;
  if(needsTaskChoices(rawText)&&!taskChoiceMode){pendingChoiceTask=rawText;taskChoices.className='task-choices on';return;}
  const text=rawText;const deliveryChoices=taskChoiceMode&&pendingChoiceTask===rawText?taskChoicePayload():null;
  if(pendingFiles.length&&!attachmentConsent){showTransferConsent();return;}
  newTaskMode=false;activeView='tasks';if(lastState)render(lastState);
  send.disabled=true;say.disabled=true;transferBusy=true;document.getElementById('attach').disabled=true;route.className='route on';
  route.textContent=pendingFiles.length?'Sending your files…':'Starting…';
  try{const uploadBatch=pendingFiles.length?await uploadFiles(pendingFiles):null;
    const r=await api('/api/say',{text,upload_batch:uploadBatch,attachment_consent:attachmentConsent,
      delivery_choices:deliveryChoices});if(r.asked){route.innerHTML='<b class="ask">Needs clarification</b> — '
    + esc(r.clarify);resetConsent();resetTaskChoices();}else{route.innerHTML=r.lane==='generator'
      ?'<b>Task started.</b> The result will appear in this conversation.'
      :'<b>Message delivered.</b>';
    if(!pendingFiles.length||r.attachments_accepted){say.value='';pendingFiles=[];uploadProgress=new Map();fileInput.value='';drawFiles();syncAudience();resetTaskChoices();}
    resetConsent();}}
  catch(e){resetConsent();route.innerHTML='<b>Refused</b> — '+esc(e.message);}
  transferBusy=false;document.getElementById('attach').disabled=false;send.disabled=false;say.disabled=false;say.focus();};
api('/api/state').then(render).catch(e=>{document.getElementById('thread-title').textContent='Disconnected — '+e.message;});
startStream();
if(location.hash==='#projects')showProjects();
api('/api/settings').then(s=>{if(s.app_mode&&location.hash==='#projects'&&
  (!s.providers.openai.configured||!s.providers.anthropic.configured))openSettings();}).catch(()=>{});
</script></body></html>"""
