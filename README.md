# CrossAudit 4.2.0

[![Version 4.2.0](https://img.shields.io/badge/version-4.2.0-6d5dfc)](https://github.com/dongzhaohe321418-lab/crossaudit_v4/releases/tag/v4.2.0)
[![macOS 13+](https://img.shields.io/badge/macOS-13%2B-111111)](https://github.com/dongzhaohe321418-lab/crossaudit_v4#install)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/dongzhaohe321418-lab/crossaudit_v4#command-line-installation)

**Latest release: [CrossAudit 4.2.0](https://github.com/dongzhaohe321418-lab/crossaudit_v4/releases/tag/v4.2.0).**

CrossAudit is a local, cross-vendor AI work loop. One model creates files, a
model from a different provider audits the committed result, and every task,
revision, finding, verdict, and receipt is recorded in Git.

You describe the work once. CrossAudit runs the loop:

```text
your task
   |
   v
generator model --> committed files --> deterministic checks
                                            |
                                            v
                                      auditor model
                                       /         \
                                  BLOCKED        PASS
                                     |             |
                                     +--> fix      +--> receipt
```

The browser console shows this process live. It uses event-driven updates, so a
new task, commit, finding, or verdict appears as soon as the state changes.

## Why CrossAudit exists

AI-generated work is easy to produce and difficult to trust. A second prompt in
the same model is useful feedback, but it is not independent supervision. It
shares the same provider, model family, context, and often the same blind spots.

CrossAudit makes the separation explicit:

- The generator and auditor must use different vendors.
- The auditor reads committed files, not the generator's private reasoning.
- Objective checks run before the model review.
- A BLOCKED result goes back to the generator for a bounded number of rounds.
- Every round is committed, so the final result has a replayable history.
- PASS creates a cryptographically bound receipt that can be verified later.
- Ambiguous or unresolved cases escalate to a human instead of looping forever.

CrossAudit works best when the requested output can be saved as files and the
acceptance criteria can be stated as rules. Examples include code, reports,
research artefacts, data pipelines, contract reviews, financial models, and
structured content.

## What V4 includes

- A native Apple Silicon macOS application: no terminal or separate browser is
  required for normal use.
- A complete Projects screen, guided project creation, provider settings,
  GitHub connection, task conversation, file transfer, audit-loop progress,
  human escalation, and result download in one UI.
- API credentials stored in the macOS login Keychain and never returned to the
  web view.
- OpenAI access through either a write-only API key or official **Sign in with
  ChatGPT** subscription authentication. The bundled OpenAI Codex runtime owns
  the browser flow and tokens; CrossAudit receives only account status and
  model output.
- Independent background workers per project and immediate event-driven UI
  updates through Server-Sent Events.
- A command-line interface for automation and development.
- OpenAI, Anthropic, Google, DeepSeek, and custom OpenAI-compatible endpoints.
- Current OpenAI GPT-5.6 and Anthropic Claude model choices, plus manual model
  IDs for future or account-specific releases.
- Correct OpenAI `max_completion_tokens` handling.
- Deterministic schema, units, convergence, and provenance checks.
- Git-backed reports and receipt verification.
- Stable exit codes and JSON output for automation.
- Local and two-repository deployment modes.

## Requirements

- An Apple Silicon Mac running macOS 13 or later for the desktop application
- Git (the application reports clearly when the Xcode Command Line Tools are
  missing)
- Two independent model-provider connections. OpenAI can use a ChatGPT plan or
  an API key. Anthropic currently requires an API/enterprise-cloud credential.
- A GitHub account only when you choose the optional two-repository workflow

Python 3.10 or newer is required only for the optional command-line/source
installation. The `.dmg` bundles its own Python core, GitHub CLI, and the pinned
official OpenAI Codex runtime.

## Install

### macOS application

1. Download `CrossAudit-4.2.0-arm64.dmg` and its checksum from the
   [V4.2.0 release](https://github.com/dongzhaohe321418-lab/crossaudit_v4/releases/tag/v4.2.0).
2. Optionally verify it in Terminal:

   ```bash
   shasum -a 256 -c CrossAudit-4.2.0-arm64.dmg.sha256
   ```

3. Open the DMG and drag **CrossAudit** to **Applications**.
4. Open CrossAudit, then open **Settings**. For OpenAI, choose **Connect** to
   complete the official ChatGPT browser login or enter an API key. Enter the
   independent Anthropic API key and save. API keys go to the macOS login
   Keychain; ChatGPT credentials remain owned by the official Codex runtime.

This initial community build is ad-hoc signed but not Apple-notarized because
the project does not yet have an Apple Developer ID certificate. macOS may
therefore require Control-clicking the app, choosing **Open**, and confirming
the first launch. The checksum verifies the downloaded bytes; it is not a
substitute for notarization. A production distribution should use Developer ID
Application signing, hardened runtime, notarization, and stapling.

### Command-line installation

For users who want shell automation, [`pipx`](https://pipx.pypa.io/stable/installation/)
keeps CrossAudit and its Python dependencies isolated while making the
`crossaudit` command available from any directory:

```bash
pipx install "git+https://github.com/dongzhaohe321418-lab/crossaudit_v4@main"
crossaudit --version
```

Expected version output:

```text
crossaudit 4.2.0 (receipt schema 2)
```

Use a virtual environment instead when developing CrossAudit, testing source
changes, or intentionally keeping the command inside one project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "crossaudit @ git+https://github.com/dongzhaohe321418-lab/crossaudit_v4@main"
```

Installing the package does not ask for credentials, open a browser, create a
project, or contact a model provider. Setup begins only when you run
`crossaudit init`.

## Five-minute quick start

### Desktop application

1. Open CrossAudit and connect both providers in **Settings**. Every normal
   application setting—including write-only API-key entry—is available in the
   UI; no YAML or environment-variable editing is required.
2. Select **New project**, describe the intended output and choose different
   vendors for Generator and Auditor.
3. Leave GitHub off for a local project, or select the two-repository option and
   use **Connect GitHub**. CrossAudit shows GitHub's official device code and
   resumes automatically after authorization.
4. Open the new workspace, type the request, attach any inputs, choose the
   desired output format, and select **Run task**.
5. Confirm the named provider destination. Watch the generator, deterministic
   checks, auditor, and correction rounds update live. Download only the final
   user-facing artifacts from their conversation cards. After PASS, select
   **Admit result** to re-verify and consume the receipt once; a second attempt
   is refused.

The Projects button returns to the portfolio view. Every project has its own
background process and live progress bar, so switching workspaces does not stop
other loops.

The **Automatic revision limit** in New Project is a cost and termination
guardrail, not an audit score. It controls how many generator → auditor
correction rounds may run automatically. If the result still has blockers at
the limit, CrossAudit pauses and escalates to the user; it never converts a
failure into PASS. The default is three and the UI offers 1, 3, 5, or 10.

### Command-line workflow

#### 1. Create a supervised project

```bash
crossaudit init my-project
```

The wizard will:

1. Create `my-project` and initialize Git.
2. Ask which vendor and model should audit the work.
3. Ask which different vendor and model should generate the work.
4. Store credentials outside the repository in a mode-600 file.
5. Turn your plain-language quality requirements into versioned audit rules.
6. Commit the initial configuration and project structure.
7. Start the browser console unless `--no-console` was supplied.

If your terminal does not support interactive selection, specify the models:

```bash
crossaudit init my-project --no-console \
  --auditor-vendor openai \
  --auditor-model gpt-5.6-terra \
  --generator-vendor anthropic \
  --generator-model claude-sonnet-4-6
```

The exact model must be available to your provider account. Interactive model
menus always include a manual-entry option, so CrossAudit does not prevent you
from using a model released after this package.

#### 2. Check the installation

```bash
cd my-project
crossaudit doctor
```

`doctor` checks Python, Git, package identity, TLS certificates, configuration,
credentials, vendor separation, the rule file, state storage, and the current
admission tier. It is read-only unless you explicitly run `doctor --fix` in an
interactive terminal.

#### 3. Give CrossAudit a real task

```bash
crossaudit build "Create a small reproducible benchmark and summarize its result"
```

CrossAudit commits the task, asks the generator to create or revise files,
commits that round, runs deterministic checks, asks the independent auditor to
review the committed tree, and records the verdict. If the auditor reports a
BLOCKER, the findings are returned to the generator for another round. The
default maximum is three rounds.

#### 4. Watch the loop live

```bash
crossaudit console
```

The command starts a local background server, opens the dashboard, and prints a
tokenized localhost URL. The console shows:

- current generator, check, and auditor activity;
- the latest task and cycle state;
- recent PASS, BLOCKED, and ESCALATED cycles;
- audit findings and reports;
- receipt and admission status;
- pending human decisions;
- the command conversation and routing history.

The conversation behaves like a supervised three-person group: you, the
Generator, and the Auditor. Speak normally and the auditor-side router assigns
the message to the correct lane. Use **@ Generator** or type `@Generator` to
send an explicit work instruction through the normal generate-check-audit loop.
Use **@ Auditor** or type `@Auditor` for an explicit auditor-side message.
Auditor-addressed amendments, disputes, and escalation rulings retain their
normal governed actions; other direct messages are read-only replies.

The group appearance does not merge the agents' contexts. A direct Auditor chat
sends only the message you addressed to it—not project files, the Constitution,
controller state, or old reports. Formal audits receive evidence through the
audited protocol instead. Every message records whether delivery was automatic
or explicitly addressed, so an `@` mention cannot become an invisible bypass.

Updates are pushed through Server-Sent Events. There is no fixed polling delay.
If the connection drops, the browser reconnects and refreshes from the durable
state.

#### Create and switch projects in the browser

Click the CrossAudit name or the project switcher in the top bar to open the
local Projects view. It discovers CrossAudit projects in the current workspace;
it does not scan the rest of your home directory. Selecting a project starts or
reattaches to that project's own token-protected console.

Each project runs in its own detached local process, with its own working tree,
one-build lock, progress tracker, session token, and ledger. Work in one project
cannot occupy or overwrite another project's loop. The Projects view relays the
independent Server-Sent Event streams: a running row shows a compact live
activity bar, current actor and step, and elapsed time. Opening that row
reattaches to the same process, so the full loop is visible immediately rather
than restarted or reconstructed from guesses.

The workspace also enforces a cross-process build capacity (four active
projects by default) so independent daemons cannot accidentally exhaust the
machine or provider quota together. The Projects header shows active/available
capacity live; `CROSSAUDIT_MAX_ACTIVE_PROJECTS` changes the limit. Stale slots
left by a crashed process are reclaimed automatically.

**New project** opens the complete setup flow in the browser: project name and
description, round budget, independent generator and auditor vendors, and the
model for each role. The form will not permit both roles to use the same vendor.
Every model menu includes a custom-ID escape hatch and **Refresh from provider**,
which asks the selected vendor which models the exact role credential can use;
this avoids freezing the UI at the model list current when CrossAudit shipped.
It can also use the account already authenticated with `gh` to create a private
science repository and a separate audit repository. Before reporting success,
CrossAudit verifies every step: repository creation or adoption, the science
`origin` and initial push, the audit Constitution and ledger push, and auditor
secret upload. Creation progress is sent live to the Projects view.

If GitHub CLI is installed but no account is authenticated, the wizard shows
**Connect GitHub**. That explicit action starts GitHub CLI's official web/device
authorization flow—CrossAudit never implements a second OAuth client and never
receives or prints the resulting token. The UI displays the one-time device
code, a copy button, and an **Open GitHub** link, then switches automatically to
the connected account when authorization completes. Authentication is not
started merely by opening the page or enabling repository creation.

GitHub setup is explicit: leave **Create and connect two repositories** off for
a local-only project. Turning it on and submitting the final form creates the
named repositories in the connected account. Existing repositories are adopted
idempotently, but an unrelated local `origin` is never replaced. Setup steps
are persisted locally. If authorization, push, seeding, or secret upload fails
after one repository has already been created, the project row shows the failed
step and a **Retry setup** action. Retry adopts completed resources and
continues; CrossAudit never silently deletes a repository during recovery.

#### Attach inputs and download outputs

Drag files anywhere over the workspace or use the **+** button to select several
files. The composer shows each attachment, aggregate count and size, upload
progress, failures, and a remove action before anything is sent. CrossAudit
accepts any number of files and does not impose a per-file or per-project size
quota. Files are uploaded concurrently in bounded chunks and the final task
request carries one fixed-size batch reference rather than an ever-growing list
of file IDs. A large upload does not have to fit in browser or server memory;
practical capacity is governed by the user's available disk and filesystem.

All file types can be stored, including binary files, images, PDFs, archives,
and datasets. UTF-8 text that fits the configured model request is included in
the generator context. Other files remain available in the project with their
name, size, media type, and SHA-256 digest, but CrossAudit explicitly tells the
text model that it has not read their contents. This is intentionally honest:
upload capacity is not the same thing as a model's context-window or modality
support.

Selecting a file does not transmit it. The first **Run task** click shows the
exact configured generator vendor and model that would receive the contents.
Only the separate provider-specific confirmation sends the files. The server
independently requires the same consent, validates names and chunk offsets,
rejects path traversal, and stores the accepted batch under the gitignored
controller inbox with restrictive permissions and SHA-256 digests. File contents are clearly
delimited as untrusted task data in the generator prompt.

Generated files appear inline in the conversation as compact output cards with
their file type, size, audit state, and a direct download action. A long output
set stays compact and links to the complete Artifacts view. The download
endpoint is token-protected and will serve only regular files that
the generator history recorded inside a configured `scope.dirs` directory. It
cannot be used to read arbitrary project files, configuration, credentials, or
paths outside the project. Downloads are streamed from disk without an
application-level output-size cap instead of being buffered into server memory.

Manage the background console with:

```bash
crossaudit console --status
crossaudit console --stop
crossaudit console --foreground
```

#### 5. Inspect or verify the result

```bash
crossaudit status
crossaudit routing
crossaudit verify cycles/<cycle>/receipt.json
```

To consume a passing receipt as a one-time admission decision:

```bash
crossaudit verify cycles/<cycle>/receipt.json --admit
```

Admission is intentionally one-time. Reusing the same receipt is refused.

Dry-run verification reports three distinct claims: `BINDINGS VERIFIED` means
the receipt still matches its commit, Constitution, report, and report verdict;
`RECORDED` means the controller observed that exact receipt; `ADMISSION READY`
means it is also the latest unconsumed PASS. Only `--admit` consumes it.

## How the build loop behaves

Each task produces a sequence of Git commits rather than silently replacing the
previous attempt:

```text
task commit
generator round 1 commit
audit report commit
receipt commit
generator round 2 commit, if blocked
audit report commit
receipt commit
```

A cycle can end in four meaningful states:

| State | Meaning |
|---|---|
| `PASS` | Deterministic checks passed and the independent auditor found no blocker. |
| `BLOCKED` | At least one objective check or auditor finding prevents acceptance. |
| `ESCALATED` | The loop cannot make a safe decision and needs a person. |
| `DCL_ONLY` | Deterministic checks ran without a model audit; this can never count as PASS. |

The generator cannot edit the rule file, configuration, state, or audit ledger.
It may write only inside the configured scope, which defaults to `experiments/`.
The auditor receives the committed files and rules, not the generator's hidden
chain of thought or narrative.

## Rules and amendments

The project's acceptance rules live in `AUDIT_RULES.md`. Each rule has a stable
ID and one of two severities:

- `BLOCKER`: an objective failure that prevents PASS.
- `ADVISORY`: useful judgement that is recorded but does not block.

During setup, you describe the project and its failure conditions in ordinary
language. CrossAudit drafts the rules, shows them for approval, and commits the
accepted version.

Change the rules between cycles with:

```bash
crossaudit amend "Every benchmark must include the exact command and random seed"
```

An audit always cites the committed rule version it used. Rules never change in
the middle of a cycle.

## Human escalation

CrossAudit stops and asks for a human decision when the round budget is spent or
the models cannot safely resolve a conflict. View pending work with
`crossaudit status`, then record a decision:

```bash
crossaudit resolve <cycle-id> --reopen --because "The source file is now available"
crossaudit resolve <cycle-id> --close --because "The task is no longer required"
```

The reason is committed to the ledger. Resolution requires an interactive
human terminal and cannot be produced by either model.

## Configuration

`crossaudit.yml` is the project configuration. Credentials are referenced by
environment-variable name and are never stored in this file.

```yaml
version: 1
science_repo: my-project
constitution: AUDIT_RULES.md
max_rounds: 3

auditor:
  vendor: openai
  provider: openai_compat
  model: gpt-5.6-terra
  key_env: CROSSAUDIT_AUDITOR_KEY

generator:
  vendor: anthropic
  provider: anthropic
  model: claude-sonnet-4-6
  key_env: CROSSAUDIT_GENERATOR_KEY

isolation:
  minimum:
    parametric: true
    contextual: true
    permissive: false

state:
  dir: .crossaudit

ledger:
  dir: cycles

scope:
  dirs: [experiments]

checks: [schema, units, convergence, provenance]
```

The default local setup provides a replayable self-audit trail. It does not
prevent the owner of the repository from rewriting Git history. For stronger
organizational separation, use the two-repository deployment described below.

## Credentials and environment variables

The macOS app exposes provider connection settings in the UI. API keys are
stored in the current user's login Keychain. The UI can add, replace, or remove
them, but it can query only whether a credential exists; it never reads a secret
back into JavaScript.

For OpenAI, **Connect ChatGPT** uses the documented Codex App Server browser
flow. OpenAI documents both ChatGPT subscription and API-key sign-in for Codex,
and specifically describes App Server as the product-integration surface for
authentication and streamed events. CrossAudit invokes that official runtime,
never parses its credential store, and constrains each provider turn to an
ephemeral read-only, text-only thread. See the official
[OpenAI authentication](https://learn.chatgpt.com/docs/auth) and
[Codex App Server](https://learn.chatgpt.com/docs/app-server) documentation.

Claude.ai subscriptions and Anthropic API billing are separate products, and
Anthropic's consumer terms prohibit sharing account login information or
credentials. CrossAudit therefore does not offer a Claude subscription bridge,
browser-cookie import, or token scraping. Use an Anthropic API key or an
organization-approved enterprise-cloud connection. See Anthropic's
[subscription/API explanation](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console)
and [consumer terms](https://www.anthropic.com/legal/consumer-terms).

The CLI setup wizard writes role credentials to `~/.crossaudit-keys.env` with
file mode 600. The file is parsed as data; CrossAudit does not execute arbitrary
content from it. An already-exported environment variable takes precedence.

| Variable | Purpose |
|---|---|
| `CROSSAUDIT_AUDITOR_KEY` | Credential used only by the auditor. |
| `CROSSAUDIT_GENERATOR_KEY` | Separate credential used only by the generator. |
| `CROSSAUDIT_OPENAI_KEY` | OpenAI vendor credential used by desktop-created projects. |
| `CROSSAUDIT_ANTHROPIC_KEY` | Anthropic vendor credential used by desktop-created projects. |
| `CROSSAUDIT_GENERATOR_MODEL` | Override the configured generator model. |
| `CROSSAUDIT_GENERATOR_PROVIDER` | Override the configured generator provider. |
| `CROSSAUDIT_GENERATOR_BASE_URL` | Override the generator's provider endpoint. |
| `CROSSAUDIT_KEYS_FILE` | Use a different credential-file location. |
| `CROSSAUDIT_SHOW_KEYS` | Show key input during setup when explicitly set to `1`; hidden is the secure default. |
| `CROSSAUDIT_CA_BUNDLE` | Trust a specific CA bundle without disabling TLS verification. |
| `CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT` | Explicitly allow sending a configured key to a non-built-in endpoint. |
| `CROSSAUDIT_MAX_ACTIVE_PROJECTS` | Maximum simultaneous project builds in one workspace (default `4`, range `1`–`32`). |
| `CROSSAUDIT_WORKSPACE_ROOT` | Advanced override for the app project directory; primarily useful in controlled tests. |
| `CROSSAUDIT_APP_SUPPORT` | Advanced override for the app support directory; primarily useful in controlled tests. |
| `CROSSAUDIT_APP_MODE` | Internal flag marking a native-app controller process. Do not set it for CLI use. |
| `CROSSAUDIT_APP_URL` | Internal startup-message prefix used by the native shell. |
| `CROSSAUDIT_BUNDLED_GH` | Internal path to the GitHub CLI bundled inside the app. |
| `CROSSAUDIT_BUNDLED_CODEX` | Internal path to the pinned official OpenAI Codex runtime bundled inside the app. |
| `CROSSAUDIT_CODEX_CWD` | Advanced test-only override for the empty read-only subscription-provider working directory. |

Never commit API keys. If a key is pasted into a public issue, log, screenshot,
or chat, revoke it and create a replacement.

## Provider and model support

The setup wizard includes these provider families:

| Vendor | Provider adapter | Example model choices |
|---|---|---|
| OpenAI API | `openai_compat` | `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` |
| ChatGPT subscription | `openai_codex` | Models returned live by the connected ChatGPT workspace |
| Anthropic | `anthropic` | `claude-fable-5`, `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` |
| Google | `openai_compat` | `gemini-2.5-pro`, `gemini-2.5-flash` |
| DeepSeek | `openai_compat` | `deepseek-reasoner`, `deepseek-chat` |
| Other | `openai_compat` | exact model ID entered by the user |

The menu is a convenience, not a guarantee that every account can access every
model. Use the exact ID returned by your provider account.

Built-in OpenAI requests use `max_completion_tokens`. Custom OpenAI-compatible
providers retain family-based compatibility with endpoints that still expect
`max_tokens`.

Custom origins are denied by default because a base URL controls where the key
is sent. Opt in only after checking the endpoint:

```bash
export CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT=1
```

## Deterministic checks

The default project enables four objective checks before the model review:

| Check | What it validates |
|---|---|
| `schema` | Required YAML/JSON files parse and contain expected fields. |
| `units` | Every result quantity declares both a unit and source. |
| `convergence` | Final results do not claim failed or over-threshold convergence. |
| `provenance` | Result sources agree with declared inputs and code versions. |

`crossaudit init` writes `DETERMINISTIC_CHECKS.md` from the live check
implementations. The same exact contract is included in the generator prompt,
`doctor` output, Console, and `checks.json`. These checks are configured by the
`checks:` list in `crossaudit.yml`; `crossaudit amend` changes the model-audited
Constitution, not this machine contract.

Run checks without a model call:

```bash
crossaudit check
crossaudit check --sha HEAD
crossaudit audit --offline
```

An offline audit returns `DCL_ONLY`, never PASS, because no independent model
review occurred.

## Two-repository deployment

Local mode keeps the work and audit ledger in one repository. For stronger
privilege separation, CrossAudit can plan or create a work repository and a
separate audit repository:

```bash
crossaudit init my-project --github
crossaudit pair --science owner/work --audit owner/work-audit
crossaudit pair --science owner/work --audit owner/work-audit --apply
```

Without `--apply`, `pair` prints the intended GitHub operations and changes
nothing remotely. Review the plan before creating repositories or secrets.

## Command reference

| Command | Purpose |
|---|---|
| `crossaudit init [path]` | Create and configure a supervised project. |
| `crossaudit doctor` | Validate the installation and project setup. |
| `crossaudit build "task"` | Run the generator-auditor correction loop. |
| `crossaudit talk "request"` | Route a natural-language request to the correct workflow. |
| `crossaudit run` | Audit the latest committed increment. |
| `crossaudit check` | Run deterministic checks only. |
| `crossaudit audit` | Run one explicit audit cycle. |
| `crossaudit verify <receipt>` | Recompute and verify receipt bindings. |
| `crossaudit status` | List cycle states. |
| `crossaudit watch` | Show live terminal progress. |
| `crossaudit console` | Start or manage the browser dashboard. |
| `crossaudit routing` | Show recorded conversation-routing decisions. |
| `crossaudit amend "change"` | Propose and version a rule change. |
| `crossaudit resolve <cycle>` | Record a human escalation decision. |
| `crossaudit skills` | Inspect or create generator-only house guidance. |
| `crossaudit pair` | Plan or create the two-repository deployment. |

Run `crossaudit --help` or `crossaudit <command> --help` for all options.

Every command supports human-readable output. Commands that emit structured
results also support the global `--json` flag before the command name:

```bash
crossaudit --json status
```

## Exit codes

Exit codes are stable so scripts do not need to parse prose:

| Code | Meaning |
|---:|---|
| `0` | The command's successful outcome. |
| `10` | BLOCKED by a deterministic failure or auditor blocker. |
| `11` | ESCALATED or DCL_ONLY; a person or later round owns the next action. |
| `20` | Configuration or environment refused the operation. |
| `21` | Receipt, ledger, manifest, or verifier integrity failure. |
| `22` | Provider, network, or model request failure. |

## Troubleshooting

### The OpenAI request says `max_tokens` is unsupported

V4 sends `max_completion_tokens` to the built-in OpenAI endpoint and retries
once when a compatible endpoint explicitly asks for that field. Confirm that
`crossaudit --version` reports 4.2.0 and reinstall if an older package is still
on your PATH. Restart a background console after upgrading because an existing
daemon keeps the Python code that was loaded when it started.

### The macOS app is blocked on first launch

V4.2.0 is structurally signed with the hardened runtime but is not notarized.
Control-click **CrossAudit.app**, choose **Open**, and confirm only after you
have verified the published SHA-256 checksum. An Apple Developer ID signed and
notarized build is required before broad organizational deployment.

### Settings says Git is unavailable

Install Apple's command-line developer tools with `xcode-select --install`,
then reopen CrossAudit. The app bundles GitHub CLI but uses the system Git for
project history and commits.

### A project does not appear to update

The UI reconnects its event stream automatically. Use **View > Reload** if the
web view was suspended for a long time. Project activity and cycle state are
durable, so reloading or returning from Projects does not restart the work.

### The model menu looks old or does not contain my model

Use the menu's manual-entry option or pass `--auditor-model` and
`--generator-model` to setup. Model availability belongs to the provider
account, not the API key format.

### A provider returns HTTP 400 mentioning the model

The configured model ID is unavailable, misspelled, retired, or not enabled for
the account. Edit `model:` in `crossaudit.yml` or rerun setup with
`crossaudit init --force`.

### A provider returns HTTP 401

The key was rejected. Run `crossaudit doctor`; it shows only the key length and
last four characters so you can identify a truncated or swapped credential
without printing the secret.

### A provider returns HTTP 429

The provider rate limit, quota, or balance was reached. This is not a
CrossAudit loop limit.

### `certificate verify failed`

Install your Python distribution's certificates or set `CROSSAUDIT_CA_BUNDLE`
to the required trusted CA file. CrossAudit never disables TLS verification.

### The key file exists but the process says the key is missing

The process may have started before the key was written. Restart the console:

```bash
crossaudit console --stop
crossaudit console
```

Or load the file into the current shell:

```bash
source ~/.crossaudit-keys.env
```

### The browser console returns 403

Use the complete tokenized URL printed by `crossaudit console --status`. The
server accepts localhost hosts only and rejects requests without its token.

### The verdict is DCL_ONLY

The deterministic layer ran, but no model audit occurred. Add the auditor key
and rerun. DCL_ONLY intentionally cannot be promoted to PASS.

### A build keeps returning BLOCKED

Read the newest `cycles/*/report.md`. If the finding is objective, fix the
artefact or let the next generator round do so. If the rule or finding requires
human judgement, let the cycle escalate and use `crossaudit resolve`.

## Security model and limitations

CrossAudit improves traceability and separation; it does not turn model output
into a mathematical proof.

- A model audit can miss defects.
- Local Git history can be rewritten by the repository owner.
- Provider accounts and infrastructure remain external trust dependencies.
- The macOS application listens only on loopback and every UI/API request uses
  an unguessable per-process token; forged hosts and missing or incorrect tokens
  are rejected.
- Desktop provider credentials live in the macOS login Keychain. They are
  injected only into the local core process and are never written to a project.
- The generator writes files but does not execute arbitrary generated commands.
- The default checks assume structured result artefacts; other domains should
  add appropriate rules and check packs.
- A receipt proves what CrossAudit processed and which verifier created it. It
  does not prove that a real-world claim is true beyond the available evidence.

CrossAudit fails closed: malformed model replies, unknown receipt schemas,
weakened isolation evidence, altered commits, and custom endpoints without
explicit authorization are refused rather than guessed.

File upload has no artificial count, per-file, or per-project quota. It is not
physically unlimited: the available disk, filesystem, browser, operating-system,
provider request, and model context limits still apply. Uploads are streamed in
bounded chunks, validated, staged with restrictive permissions, consumed once,
and never treated as executable instructions. Binary storage support does not
imply that a text-only model can understand every format.

## Development

Clone the repository and install the development dependency:

```bash
git clone https://github.com/dongzhaohe321418-lab/crossaudit_v4.git
cd crossaudit_v4
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

Build the native application and DMG on an Apple Silicon Mac:

```bash
./packaging/macos/build_dmg.sh
```

The V4 baseline includes automated tests covering the CLI, wizard, providers,
deterministic checks, correction loop, receipts, admission, Keychain boundary,
real-time console, independent daemon lifecycle, chunked transfers, frozen-app
identity, GitHub setup recovery, and documentation contracts. The release
process additionally verifies the app signature structure, plist, executable
architectures, mounted DMG contents, first-launch bootstrap, token security,
and an opt-in real-provider workflow.

## License

CrossAudit is released under the [MIT License](LICENSE).
