# CrossAudit 4.11.1 enterprise release assessment

Date: 2026-08-04

Target: Apple Silicon macOS 13 or later

Release candidate: 4.11.1

## Executive result

CrossAudit 4.11.1 is suitable for local evaluation and controlled pilot use. It
preserves the V3.2 audited protocol while adding a native AppKit/WebKit shell,
Keychain credentials, UI-first project creation, independent background
projects, GitHub connection, chunked file transfer, final-artifact downloads,
live audit progress, and remote-owned SSH/Slurm compute.

The release is not yet suitable for silent enterprise deployment because no
Apple Developer ID certificate is available. The produced application is
ad-hoc signed with hardened runtime and the DMG is checksummed, but it cannot be
notarized or stapled. This limitation is visible in the README and Security
Policy rather than hidden behind an installation workaround.

## Verification matrix

| Area | Release gate | Result |
|---|---|---|
| Python regression | Complete automated suite | Passed: 474, with 2 paid checks skipped |
| Provider compatibility | Protocol mocks plus opt-in live checks | Passed; paid API checks remain opt-in |
| Native packaging | Swift typecheck, PyInstaller analysis, arm64 binaries | Passed |
| App structure | `plutil` and deep strict `codesign` validation | Passed |
| Disk image | Create, verify, mount, inspect, copy, and checksum | Passed |
| Frozen runtime | Isolated first-launch bootstrap and API smoke test | Passed |
| UI security | Missing token, wrong token, foreign Host, path traversal | Automated |
| Credential boundary | Keychain write/read/delete; no secret in argv or response | Automated and local smoke |
| Native editing | Responder-chain Edit menu; copy/paste in secure API-key fields | Automated and installed-app UI smoke |
| Localization | English/Chinese across hub, workspaces, settings, setup, usage and compute; cross-port persistence | Automated, browser, and installed-app restart smoke |
| Subscription boundary | Official ChatGPT browser flow; allowlisted state; text-only fail-closed turns | Automated and live smoke |
| Live state | Same-process event latency below 250 ms; external fallback at 100 ms | Automated |
| Usage metering | Provider/runtime counts, cache normalization, local-only ledger, unknown-price refusal | Automated and local smoke |
| Project isolation | Separate worker, token, lock, ledger, and progress state | Automated |
| Project/Chat hierarchy | Multiple filtered Chats per real folder; persistent pins; Git association and recovery | Automated and browser smoke |
| GitHub setup | Auth states, idempotent adoption, partial-failure retry, origin refusal | Automated |
| Transfers | Arbitrary type/count, chunk offsets, traversal, one-shot staging, zero-byte file | Automated |
| Receipts | Binding verification, recorded cycle state, one-time admission | Automated |
| Runtime models | Atomic model/effort switch, busy refusal, SSE refresh, provider-specific payload | Automated and live |
| Environment Doctor | Missing/outdated tools, startup degradation, safe repair allowlist, update check, responsive UI | Automated and browser smoke |
| Remote compute | SSH-config discovery, strict host keys, read-only probe, Slurm/workstation detach, restart reattachment, 2-second status/logs, cancel, input/output streaming | Automated, real SSH failure smoke, and browser smoke |

The final command outputs and artifact hashes are recorded in the GitHub release
and CI logs. Tests that spend provider credits remain explicitly opt-in and use
repository secrets in CI.

## V4.11.1 release-candidate evidence

- Automated suite: **474 passed, 2 skipped** with warnings treated as errors;
  the final parallel run used independent workers plus a 60-second per-test
  timeout. The skipped cases remain only explicitly opt-in paid-provider checks.
- Native editing was exercised in the installed application, not inferred from
  browser behavior: a harmless 16-character probe was copied from a normal
  field with Command-C, pasted into a masked API-key field with Command-V, and
  then cleared without saving. The AppKit Edit menu exposes Undo, Redo, Cut,
  Copy, Paste, and Select All through the focused WebKit responder.
- English and Simplified Chinese were exercised in the project portfolio,
  provider settings, first-project wizard, and individual workspace. The test
  crossed two independently running loopback ports, then quit and relaunched the
  installed app on another random port; Chinese remained selected. Project
  names, paths, model IDs, rule text, and provider errors remain untranslated
  evidence rather than being rewritten.
- Critical Ruff checks passed; Bandit reported **0 high and 0 medium** findings;
  dependency audit found no known vulnerability. Swift compiled with warnings
  treated as errors, the generated JavaScript passed `node --check`, and the
  source tree compiled to Python bytecode.
- Wheel and source distributions were built from the final source. The wheel
  installed in a fresh environment, reported V4.11.1, and contained the global
  cross-workspace locale persistence layer.
- The final DMG passed repeat checksum verification, read-only mount/copy,
  `plutil`, deep strict code-sign verification, arm64 inspection, and a frozen
  controller/API smoke. `/Applications/CrossAudit.app` was replaced from that
  verified copy and launched as one native shell plus one frozen core. Previous
  app bundles were moved to the Trash and remain recoverable.
- Distribution SHA-256:
  `ed3aaaea15c40ca4d8a13cf9966ec47ec0918453d4867488eff3c19f9544c732`.

## V4.11.0 release-candidate evidence

- Automated suite: **472 passed, 2 skipped** under both normal and strict-warning
  runs. A four-process run passed before the final UI guidance additions, and the
  final coverage run reports **81%** statement coverage. The two skipped cases are
  only explicitly opt-in paid-provider checks.
- Static and dependency gates: critical Ruff rules passed; Bandit reported
  **0 high and 0 medium** findings; `pip-audit` found no known dependency
  vulnerability. Python bytecode compilation and the generated page's JavaScript
  syntax check passed.
- Failure and longevity testing found and fixed two release-blocking defects: a
  provider HTTP-error socket leak and an idle-watcher thread retained after every
  console shutdown. A 100-start/stop stress run ended with one thread, matching
  its starting count.
- A generator refusal before its first commit now creates a durable, Chat-bound
  escalation. Non-retryable authentication and request errors stop after one
  provider attempt. The live UI presents **Review decision**, records the human
  reason, and offers another round or a final stop without exposing a cycle ID.
- Project controls now cover models, provider-supported reasoning effort, the
  automatic revision limit, and committed generator guidance. Browser acceptance
  created guidance with a path scope, saved it through the token-protected UI,
  and observed the committed value immediately through SSE.
- Browser acceptance also covered project creation, provider selection, local
  workspace creation, project navigation, file add/remove, every workspace view,
  light/dark mode, escalation resolution, and a 390 x 844 responsive layout with
  no horizontal overflow. The browser console contained no warning or error.
- Frozen runtime testing used isolated support and workspace folders, reported
  V4.11.0, exposed the Project guidance UI state, and returned HTTP 403 for a
  missing token, wrong token, and foreign Host. Wheel and source distributions
  were built; the wheel installed into a fresh environment, passed `pip check`,
  and reported V4.11.0.
- Installed upgrade: the running V4.10.0 app quit cleanly, was retained in the
  Trash, and V4.11.0 was copied from the verified DMG to `/Applications`.
  Launch produced exactly one native shell and one frozen core, which remained
  stable during the post-install observation. The macOS UI session was locked,
  so an accessibility-driven click-through of the installed native window could
  not be repeated; equivalent WebView flows were exercised in the real browser,
  while lifecycle behavior remains covered by automated native tests.
- Distribution: the APFS DMG passed repeat verification, mount/copy inspection,
  deep strict code-sign verification, arm64 and macOS 13 Info.plist checks. Its
  SHA-256 is
  `e83a4a678f43094865f2edfec0b1ac1093d836de5a032f56eda0f72b80a514d5`.

## V4.10.0 release-candidate evidence

- Automated suite: **461 passed, 2 skipped** in 46.00 seconds. The skipped
  cases remain only explicitly opt-in paid-provider checks. Python bytecode
  compilation and the native arm64 macOS 13 Swift typecheck also passed.
- Remote-control tests cover safe alias/path/resource validation, OpenSSH-config
  includes, no private-key persistence, first-key trust, changed-key refusal,
  binary input streaming, Slurm `sbatch/squeue/sacct/scancel`, detached
  workstation `setsid`, concurrency, connection loss, controller restart,
  logs, portable output discovery/download, and process-group cancellation.
- Real-machine SSH smoke used the system OpenSSH 10.2 client and an existing SSH
  alias. The strict, non-interactive read-only probe reached the genuine network
  failure path without trusting a key, creating a remote directory, or starting
  a job. Successful Slurm and workstation paths were exercised through a
  deterministic transport simulator; no successful real-cluster run is claimed.
- Browser acceptance rendered V4.10.0 and the Compute workspace at 1280 px with
  no horizontal overflow or console errors. It exercised the add-host dialog,
  inline validation, resource/script approval, live-state schema, input list,
  logs, outputs, cancel controls, and 2-second monitoring behavior.
- Frozen runtime: a copy mounted from the final DMG started against isolated
  support/workspace folders, reported V4.10.0 with the complete compute schema,
  and returned HTTP 403 for a missing token, wrong token, and foreign Host.
- Installed upgrade: the running 4.9.0 app quit cleanly, its bundle was retained
  in the Trash, and the verified DMG installed 4.10.0 in `/Applications`. Launch
  produced exactly one native shell and one local core; transient GitHub checks
  exited normally and the persistent official Codex runtime remained a child of
  that core.
- Package smoke built both wheel and source distribution, installed the wheel in
  a fresh virtual environment, reported 4.10.0, and passed `pip check`.
- Distribution: the arm64 DMG passed APFS verification, deep strict code-sign
  verification, architecture and 4.10.0 Info.plist checks. Its SHA-256 is
  `4d07ca43d357d0b68f39eb9b30b0f04b4535de68d66aa8f7db3a0cdab7b06eb4`.

## V4.8.0 release-candidate evidence

- Automated suite: **438 passed, 2 skipped** in 45.47 seconds; the skipped
  cases remain only explicitly opt-in paid-provider checks. The native Swift
  shell also passed an arm64 macOS 13 typecheck.
- Native background lifecycle: closing the main window orders it out without
  terminating the application, local core, or detached Project workers. The
  Dock icon and permanent menu-bar diamond restore the same WebView; only the
  explicit Quit command tears down the local controller.
- Health visibility: the menu bar reports the background state. An unexpected
  core exit changes that state, restores the main window, shows the failure,
  and requests user attention instead of failing silently while hidden.
- Installed-app lifecycle: the 4.8.0 shell, core, and bundled Codex child all
  stopped after an explicit native termination signal. Relaunch produced one
  shell and one core, with no duplicate controller or orphaned child process.
- Distribution: the arm64 DMG passed its published SHA-256 check
  (`38326f7001e0534be4d5f7fb2280d6b4d4fe9b92a742163642344a0bc5aff09a`),
  the installed app reported 4.8.0, and deep strict code-sign verification
  passed for the installed bundle.

## V4.7.0 release-candidate evidence

- Automated suite: **437 passed, 2 skipped** in 45.30 seconds. The skipped
  cases are only explicitly opt-in paid-provider checks.
- Project hierarchy: a Project remains the user-selected local folder and Git
  repository, while any number of lightweight Chats can own independent task,
  output, audit, and progress views inside it. Project and Chat pins persist in
  a mode-600 gitignored file; no conversation content is duplicated there.
- Evidence association: each generated round carries a validated
  `CrossAudit-Chat` Git trailer. Deleting local navigation metadata does not
  orphan a Chat because immutable committed evidence can reconstruct it.
- Backward compatibility: pre-4.7 routing and audit evidence appears as
  **Project history** without rewriting commits, reports, receipts, or routing
  records.
- Browser acceptance: two Chats were created and switched in one real Project,
  one Chat and its Project were pinned, both groupings survived a daemon
  restart, light/dark themes rendered correctly, and no console warning or
  error was emitted. A 390 x 844 check found and fixed a 42 px top-bar overflow;
  the retest reported viewport width = body width = workspace width = 390 px.
- Distribution: valid APFS DMG CRC, valid 4.7.0 Info.plist, arm64 shell and
  frozen core, and strict deep code-sign verification. An isolated frozen first
  launch served V4.7.0 and refused missing token, wrong token, and foreign Host
  with HTTP 403. SHA-256:
  `83239f7565d1be7384eef62ed1d1c3164c16ef6319a799c3518c6ab1bf56888a`.

## V4.6.0 release-candidate evidence

- Automated suite: **429 passed, 2 skipped** in 43.86 seconds. The skipped cases
  are only explicitly opt-in provider tests; live calls were run separately.
- Live request controls: OpenAI `gpt-5.6-luna` accepted `low`, Anthropic
  `claude-sonnet-4-6` accepted `medium`, and the official signed-in Codex runtime
  accepted a turn-level `low` override. All returned provider/runtime usage.
- Frozen end-to-end: the signed 4.6.0 core atomically switched Generator to
  Sonnet 4.6 / medium and Auditor to GPT-5.6 Luna / low, completed a real
  cross-vendor loop with PASS, admitted the exact receipt to CONSUMED, and
  refused the replay. The receipt records the auditor effort in both its audit
  and exchange evidence.
- Runtime safety: model/effort controls are refused immediately while a loop is
  running, changes commit only `crossaudit.yml`, dirty configuration is never
  overwritten, unsupported model/provider combinations stay on Automatic, and
  the active workspace updates over SSE without restart.
- Browser acceptance: desktop dark, responsive 390 x 844, and light-theme views
  rendered the two-role model/effort dialog with zero horizontal overflow and no
  console warnings or errors. A saved switch appeared in the workspace within
  the next event frame without reloading.
- Distribution: valid APFS DMG CRC, valid Info.plist, arm64 shell/core/`gh`/Codex
  executables, and strict deep code-sign verification. Frozen first launch
  reported 4.6.0 and refused missing token, wrong token, and foreign Host with
  HTTP 403. SHA-256:
  `9352ad0aa1a3e5c64d1020066d6bb8478f62d62c3fbf107e8899acc747c56f69`.

## V4.5.0 release-candidate evidence

- Automated suite: **422 passed, 2 skipped** in 38.99 seconds. The skipped cases
  are only the explicitly opt-in paid-provider tests.
- Paid-provider smoke: **2 passed**, using real OpenAI and Anthropic completions
  and provider-reported usage. No credential value was printed or persisted in
  the repository.
- First-party provider matrix: OpenAI, Anthropic, Google Gemini, DeepSeek,
  Zhipu GLM, Moonshot Kimi, MiniMax, Alibaba Qwen, xAI, and Mistral each have a
  tested credential name, model catalogue, exact completion adapter, and
  allowlisted first-party origin. Live model discovery remains authoritative;
  curated model IDs are fallbacks.
- Regional routing: Zhipu, Moonshot, MiniMax, and Qwen expose explicit API-region
  choices. Unit and project-creation tests prove that the selected regional base
  is persisted independently for Auditor and Generator and that an unknown
  region is refused before a network request.
- Compatibility regression: built-in OpenAI uses
  `max_completion_tokens`; OpenAI-compatible providers retry only a named token
  parameter mismatch; MiniMax uses its documented non-zero temperature; and
  single-origin providers cannot acquire a duplicated `/v1` path from the UI.
- Live update stress: the 250 ms same-process SSE gate passed 20 consecutive
  repetitions after the progress fast path was introduced; the 100 ms fallback
  continues to re-derive durable Git/controller changes.
- Browser acceptance: the installed frozen UI rendered V4.5.0, ten provider
  cards and ten write-only key fields with no horizontal overflow or console
  error. Project setup displayed the regional choices and continued to disable
  the Generator's copy of the selected Auditor vendor.
- Frozen runtime: authenticated state reported version 4.5.0 and
  `frozen-app`, listened on loopback, and returned HTTP 403 for missing token,
  wrong token, and forged Host requests. Native shell launch created exactly one
  child core; normal AppKit Quit stopped both.
- Distribution: valid APFS DMG CRC, valid Info.plist, arm64 shell/core/`gh`/Codex
  executables, and strict deep code-sign verification. SHA-256:
  `8d0cbeef86788c1a2b817b545b1c6ead53f65a116fd4b94c91719d031ef0ba83`.

## V4.4.0 release-candidate evidence

- Automated suite: **397 passed, 2 skipped**. The skipped cases are the
  intentionally opt-in paid-provider tests.
- Paid-provider smoke: **2 passed**, covering real OpenAI and Anthropic API
  completions and requiring provider-reported token usage for both vendors.
- Local browser smoke: the Usage view rendered at 1280 x 720 and 390 x 844 in
  both themes without horizontal overflow or console errors. Provider-reported,
  estimated, and unpriced states were distinct; an externally appended usage
  event appeared over the live stream within 250 ms without a refresh.
- Installed frozen core: reports 4.4.0 through its authenticated state API,
  exposed the complete usage schema, used `frozen-app` identity, listened only on
  loopback, and returned 403 for both missing-token and foreign-Host requests.
- Distribution: arm64 shell and Codex runtime, strict deep codesign validation,
  valid Info.plist, valid DMG CRC, and SHA-256
  `826de30cf09dbd73bd0c99b26c96923de8e1ccfadf6cc96a8d906ac0aed63ab5`.
- Transfer stress: a 257-file batch resolved through one fixed-size reference,
  a 900 KB generated file passed without a CrossAudit output quota, a 2 MB
  artifact streamed through the HTTP endpoint, and incomplete batches failed
  closed.
- GitHub first-use E2E: the same project-creation transaction used by the UI
  created private `crossaudit-v44-e2e-20260803` and
  `crossaudit-v44-e2e-20260803-audit` repositories under the connected account,
  pushed both default branches as `main`, persisted the exact names in
  `crossaudit.yml`, and seeded the audit repository with the Constitution and
  ledger. The project row advanced live from setup to `GitHub paired`.

## Failures found and corrected in V4

1. Desktop-created projects originally inherited role-named credentials. They
   now bind credentials by vendor so swapping Generator and Auditor roles cannot
   swap keys accidentally.
2. A frozen PyInstaller build had no trustworthy source-tree digest. V4 embeds a
   build identity manifest and labels the verifier mode `frozen-app`.
3. The hidden project-hub controller could leak into the project list. It is now
   excluded while ordinary selected projects remain visible.
4. Completed transport uploads could be replayed and consumed disk twice. The
   staging files and metadata are removed only after a durable inbox copy.
5. Zero-byte files needed an explicit end-to-end test. They now complete,
   stage, and consume once like every other attachment.
6. Keychain's stdin password mode requires confirmation input. The app supplies
   the same secret twice over stdin while keeping it out of process arguments.
7. Normal app users previously had no credential workflow. A write-only Settings
   UI now reports configured state without returning stored values.
8. App packaging previously depended on the user's Python installation and
   GitHub CLI. V4 bundles the Python core, its runtime, and a licensed `gh`
   binary; only system Git remains a documented prerequisite.
9. Building inside a file-provider-managed Documents directory attached
   `FinderInfo` metadata that strict signing refused. The release bundle is now
   assembled and signed in a fresh `mktemp` staging directory before the DMG is
   copied into `dist`.
10. The first installed native shell relied on an implicit Swift application
    entry and never called its launch delegate. V4 now owns and retains an
    explicit `NSApplication`, delegate, activation policy, and run loop. The
    installed-path test confirmed both shell and core processes start, the core
    listens only on loopback, and a normal Quit stops both.
11. The default conversation exposed BLOCKED intermediate files as downloads.
    Tasks and Delivered Files now show only PASSED or CONSUMED outputs; audit
    rounds and findings remain behind the explicitly selected Audits view.
12. A provider repeated an identical output-file block during a correction
    round. Exact byte-for-byte duplicates now collapse into one deterministic
    write, while conflicting duplicates remain refused.
13. The frozen project-console entry initially relied on its parent process to
    set the project working directory. It now anchors itself to the validated
    project root before any shared CLI operation can load configuration.
14. Receipt admission remained CLI-only. A PASS now exposes an explicit
    **Admit result** UI action that re-verifies all bindings, confirms the exact
    controller-recorded latest receipt and frozen-app identity, then consumes it
    once. No unverified or replayed receipt is promoted.
15. The chunk transport had no whole-file limit, but `/api/say` still carried an
    array containing every upload ID. A sufficiently large selection therefore
    hit the final JSON request bound. V4.2 records batch position with each
    chunk and submits one opaque 32-byte batch reference, independent of count.
16. Artifact download buffered the whole file and refused files over 1 MB. V4.2
    validates the same ledger and scope boundary, then streams the permitted
    regular file from disk in 1 MB blocks with no application-level size cap.
17. File drag-and-drop was confined to the composer and the attachment display
    hid transfer state in text chips. V4.2 accepts file drops across the entire
    workspace and renders file cards with aggregate size, progress, failure,
    removal, and duplicate-name disambiguation. The file picker remains a true
    multiple selector.
18. Generator output validation imposed fixed 40-file and 400 KB limits that
    contradicted the UI's no-quota contract. Those CrossAudit limits are gone;
    provider context, response capacity, disk and filesystem limits remain
    visible as real external constraints.
19. Token consumption was invisible even though Generator, Auditor, routing,
    and Constitution drafting can each spend provider capacity. V4.3 records
    provider/runtime counts in a local append-only ledger, normalizes cache
    reads and writes without double counting, and exposes a live role/model/day
    view. Missing usage is clearly estimated, and unknown models are left
    unpriced instead of receiving an invented cost.
20. Subscription usage could only be approximated from generated text. V4.3
    consumes the official Codex runtime's token-usage notifications, so ChatGPT
    subscription turns show reported counts while still labelling money as
    comparable API value rather than a subscription invoice.
21. New-project setup used one fixed workspace and regenerated repository names
    whenever the project name changed. V4.4 adds a native per-project parent
    folder picker, a persisted set of explicitly approved workspaces, stable
    independently editable work/audit names, preflight availability checks,
    explicit adoption consent, structured GitHub guidance, and resumable UI
    recovery after partial remote setup. Recovery embeds the live GitHub device
    code, copy action, browser link, and automatic connected-state transition.
22. The native shell cleaned up its core during a normal AppKit Quit but did
    not translate terminal or service-manager `SIGINT`/`SIGTERM` into that same
    lifecycle. V4.4 installs main-queue signal sources so managed shutdowns use
    `applicationWillTerminate`, terminate the frozen core, and close its
    provider runtime instead of leaving a local orphan process.
23. Provider names previously existed only as UI/model-catalog entries, so a
    configured Gemini or DeepSeek role could still fall through to OpenAI's
    completion origin. V4.5 generates every settings card, wizard choice,
    catalogue request, credential name, and runtime adapter from one registry.
24. Region-bound API keys could be sent to the wrong first-party regional host.
    V4.5 makes the region explicit and allowlists each supported host; it never
    probes multiple regions with the same secret.
25. OpenAI's token-limit migration and MiniMax's non-zero temperature contract
    produced avoidable provider HTTP 400 failures. Both are now encoded in the
    adapter contract with a narrowly scoped one-retry compatibility path.
26. A loaded Linux runner exposed that a progress event could wait behind a
    complete Git/ledger snapshot before reaching SSE. The stream now reuses its
    last complete durable view for an in-memory progress-only update, then
    performs the usual full derivation on the 100 ms fallback tick.
27. Model selection was fixed for the lifetime of a project daemon and reasoning
    effort could not be expressed. V4.6 adds independent live role controls,
    provider/model capability checks, request-level adapter fields, atomic Git
    persistence, Codex catalogue discovery, and receipt/report evidence.
28. If a correction round reproduced the previous bytes, the controller correctly
    escalated but incorrectly described the cause as spending the full round
    budget. It now records that the Generator produced no new auditable revision
    in the exact round where progress stopped.
29. Remote work had no durable application boundary. V4.10 delegates identity
    and host trust to OpenSSH, persists only safe control-plane identifiers,
    detaches work to Slurm or a remote process group, and reattaches monitoring
    after local shutdown or network loss.
30. Windows can reset a TCP connection when a server closes with unread POST
    bytes, causing a valid token-denial response to disappear. The loopback
    handler now performs a bounded, short-timeout drain for rejected small
    bodies, flushes an explicit no-store 403, and closes deterministically. The
    security test passed 30 consecutive local repetitions before the matrix rerun.

## Residual risks and recommendations

- Obtain an Apple Developer Program identity, sign nested code explicitly,
  notarize, staple, and validate with Gatekeeper before a broad public launch.
- Add update signing and an authenticated update feed before supporting automatic
  upgrades.
- Run the live-provider workflow on every provider/model change and weekly
  thereafter because provider contracts change independently of this codebase.
- Add live credential-backed contract jobs for the eight newly preset providers
  as isolated non-production accounts become available. Static origin and
  payload tests do not prove provider-side entitlement or quota.
- Treat GitHub repository creation as an external transaction: retain the
  existing resumable setup journal and never auto-delete partially created
  repositories.
- Monitor disk capacity for very large projects. CrossAudit intentionally has no
  arbitrary upload quota, but no operating system or provider is physically
  unlimited.
- For regulated deployments, use separate provider and GitHub organizations,
  configure repository protections, and retain external immutable logs.
