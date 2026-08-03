# CrossAudit 4.3.0 enterprise release assessment

Date: 2026-08-03

Target: Apple Silicon macOS 13 or later

Release candidate: 4.3.0

## Executive result

CrossAudit 4.3.0 is suitable for local evaluation and controlled pilot use. It
preserves the V3.2 audited protocol while adding a native AppKit/WebKit shell,
Keychain credentials, UI-first project creation, independent background
projects, GitHub connection, chunked file transfer, final-artifact downloads,
and live audit progress.

The release is not yet suitable for silent enterprise deployment because no
Apple Developer ID certificate is available. The produced application is
ad-hoc signed with hardened runtime and the DMG is checksummed, but it cannot be
notarized or stapled. This limitation is visible in the README and Security
Policy rather than hidden behind an installation workaround.

## Verification matrix

| Area | Release gate | Result |
|---|---|---|
| Python regression | Complete automated suite | Required before tag |
| Provider compatibility | Real OpenAI and Anthropic calls, opt-in | Required before tag |
| Native packaging | Swift typecheck, PyInstaller analysis, arm64 binaries | Required before tag |
| App structure | `plutil` and deep strict `codesign` validation | Required before tag |
| Disk image | Create, verify, mount, inspect, copy, and checksum | Required before tag |
| Frozen runtime | Isolated first-launch bootstrap and API smoke test | Required before tag |
| UI security | Missing token, wrong token, foreign Host, path traversal | Automated |
| Credential boundary | Keychain write/read/delete; no secret in argv or response | Automated and local smoke |
| Subscription boundary | Official ChatGPT browser flow; allowlisted state; text-only fail-closed turns | Automated and live smoke |
| Live state | Same-process event latency below 250 ms; external fallback at 100 ms | Automated |
| Usage metering | Provider/runtime counts, cache normalization, local-only ledger, unknown-price refusal | Automated and local smoke |
| Project isolation | Separate worker, token, lock, ledger, and progress state | Automated |
| GitHub setup | Auth states, idempotent adoption, partial-failure retry, origin refusal | Automated |
| Transfers | Arbitrary type/count, chunk offsets, traversal, one-shot staging, zero-byte file | Automated |
| Receipts | Binding verification, recorded cycle state, one-time admission | Automated |

The final command outputs and artifact hashes are recorded in the GitHub release
and CI logs. Tests that spend provider credits remain explicitly opt-in and use
repository secrets in CI.

## V4.3.0 release-candidate evidence

- Automated suite: **390 passed, 2 skipped**. The skipped cases are the
  intentionally opt-in paid-provider tests.
- Paid-provider smoke: **2 passed**, covering real OpenAI and Anthropic API
  completions and requiring provider-reported token usage for both vendors.
- Local browser smoke: the Usage view rendered at 1280 x 720 and 390 x 844 in
  both themes without horizontal overflow or console errors. Provider-reported,
  estimated, and unpriced states were distinct; an externally appended usage
  event appeared over the live stream within 250 ms without a refresh.
- Installed frozen core: reported 4.3.0 through its authenticated state API,
  exposed the complete usage schema, used `frozen-app` identity, listened only on
  loopback, and returned 403 for both missing-token and foreign-Host requests.
- Distribution: arm64 shell and Codex runtime, strict deep codesign validation,
  valid Info.plist, valid DMG CRC, and a separately published SHA-256 checksum.
- Transfer stress: a 257-file batch resolved through one fixed-size reference,
  a 900 KB generated file passed without a CrossAudit output quota, a 2 MB
  artifact streamed through the HTTP endpoint, and incomplete batches failed
  closed.

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

## Residual risks and recommendations

- Obtain an Apple Developer Program identity, sign nested code explicitly,
  notarize, staple, and validate with Gatekeeper before a broad public launch.
- Add update signing and an authenticated update feed before supporting automatic
  upgrades.
- Run the live-provider workflow on every provider/model change and weekly
  thereafter because provider contracts change independently of this codebase.
- Treat GitHub repository creation as an external transaction: retain the
  existing resumable setup journal and never auto-delete partially created
  repositories.
- Monitor disk capacity for very large projects. CrossAudit intentionally has no
  arbitrary upload quota, but no operating system or provider is physically
  unlimited.
- For regulated deployments, use separate provider and GitHub organizations,
  configure repository protections, and retain external immutable logs.
