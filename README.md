# CrossAudit 4.14.0

[![Version 4.14.0](https://img.shields.io/badge/version-4.14.0-6d5dfc)](https://github.com/dongzhaohe321418-lab/crossaudit_v4/releases/tag/v4.14.0)
[![macOS 13+](https://img.shields.io/badge/macOS-13%2B-111111)](https://github.com/dongzhaohe321418-lab/crossaudit_v4#install)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://github.com/dongzhaohe321418-lab/crossaudit_v4#command-line-installation)

**Latest release: CrossAudit 4.14.0.** The source on `main` is authoritative
until the matching DMG is attached to a GitHub release.

CrossAudit is a local, cross-vendor AI work loop. One model creates files, a
model from a different provider audits the committed result, and every task,
revision, finding, verdict, and receipt is recorded in Git.

You describe the work once. CrossAudit runs the loop:

```text
your task
   |
   v
generator model --> committed files --> deterministic checks --> auditor proposal
                                            |                         |
                                            +------ evidence gate ----+
                                                       |
                                   +-------------------+-------------------+
                                   |                   |                   |
                              verified BLOCK       clean PASS       uncertain claim
                                   |                   |                   |
                           guarded minimal fix       receipt         Git governance
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
- A reproduced deterministic failure can go back to the generator for a bounded
  number of guarded repair rounds.
- A model-only blocker is a proposal, not authority: it enters bounded dispute
  and human governance instead of silently becoming a patch instruction.
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
- An Apple-style spatial interface with translucent navigation and transient
  controls, calm opaque work and evidence surfaces, native system typography,
  light/dark themes, and explicit reduced-transparency, reduced-motion,
  high-contrast, and narrow-window fallbacks.
- Standard macOS editing commands—including Undo, Cut, Copy, Paste, and Select
  All—work in task, configuration, and write-only API-key fields.
- The complete app interface switches between English and Simplified Chinese;
  the choice persists across workspaces and launches without rewriting project
  data, file names, model IDs, or audit evidence.
- Real background operation: closing the main window keeps the local core and
  Project workers alive, with a menu-bar entry to restore or explicitly quit.
- An in-app Environment Doctor that checks required software, versions, TLS,
  workspace access, the Git ledger, build identity, and available updates. Safe
  repairs and official installation guidance stay inside Settings.
- A complete Projects screen, guided project creation, provider settings,
  GitHub connection, task conversation, file transfer, audit-loop progress,
  human escalation, and result download in one UI.
- Codex-style organization: each Project is a real local folder containing
  multiple independent Chats, and both Projects and Chats can be pinned.
- API credentials stored in the macOS login Keychain and never returned to the
  web view.
- OpenAI access through either a write-only API key or official **Sign in with
  ChatGPT** subscription authentication. The bundled OpenAI Codex runtime owns
  the browser flow and tokens; CrossAudit receives only account status and
  model output.
- Independent background workers per project and immediate event-driven UI
  updates through Server-Sent Events.
- Safe autonomy by default: one plain-language request is enough. The Generator
  infers reversible choices such as focus, tone, structure, filename, and the
  simplest useful output format. Low-confidence ordinary work continues through
  the supervised loop; rule changes, audit rulings, destructive actions, and new
  capabilities still require an explicit human decision.
- Claude Science-style remote compute: register existing OpenSSH hosts, probe
  workstations or Slurm login nodes, submit detached jobs, follow scheduler
  state and logs in real time, cancel explicitly, and stream remote outputs
  back without making the Mac the job owner. An explicitly enabled host can
  also act as the Generator's policy-bounded external calculator: the Generator
  submits work, waits in the background, reads declared result data, and then
  continues the same audited task automatically.
- Project-scoped MCP tools over local stdio or Streamable HTTP, with exact
  executable consent, HTTPS/private-network controls, write-only Keychain
  bearer tokens, per-tool allowlists, call budgets, live progress, bounded
  results, and content-free hashed call records.
- Local token metering for every Generator and Auditor call, with a live Usage
  view, cache-aware counts, role/model breakdowns, and clearly labelled public
  API-value estimates.
- A command-line interface for automation and development.
- First-party OpenAI, Anthropic, Google Gemini, DeepSeek, Zhipu GLM, Moonshot
  Kimi, MiniMax, Alibaba Qwen, xAI, and Mistral connections, plus an explicitly
  trusted custom OpenAI-compatible endpoint for CLI deployments.
- Live model discovery using the exact credential selected for each role, plus
  manual model IDs for staged, regional, or account-specific releases.
- Live Generator and Auditor model switching, with model-specific reasoning
  effort controls. A saved change is committed atomically and applies to the
  next provider call without restarting the project.
- UI-managed generator guidance for house style, output shape, path-specific
  conventions, and reusable checklists. Guidance is committed with the Project,
  remains invisible to the independent auditor, and cannot relax the Constitution.
- Explicit escalation decisions in the conversation: when the automatic round
  limit is reached, the workspace opens a human handoff that summarizes the
  rounds attempted and remaining blockers, then asks the user to **Revise and
  continue** or **Stop this task**. The decision and explanation are durable;
  receipt IDs and Terminal commands stay out of the user flow.
- Correct OpenAI `max_completion_tokens` handling.
- Deterministic schema, units, convergence, and provenance checks.
- Evidence-before-authority routing: model confidence and vendor identity never
  grant blocking power by themselves; every receipt binds the normalized
  evidence set, policy version, authority decision, and governance route.
- A repair guard that refuses out-of-scope or oversized revisions and flags
  broad exception handling, silent fallbacks/retries, suppressions, skipped
  tests, and relaxed assertions before an automatic repair can be committed.
- Git-backed reports and receipt verification.
- Stable exit codes and JSON output for automation.
- Local and two-repository deployment modes.

## Requirements

- An Apple Silicon Mac running macOS 13 or later for the desktop application
- Git (the application reports clearly when the Xcode Command Line Tools are
  missing)
- Two independent model-provider connections. OpenAI can use a ChatGPT plan or
  an API key. Every other built-in provider currently uses its official
  developer API credential in CrossAudit.
- A GitHub account only when you choose the optional two-repository workflow
- OpenSSH 8.1 or later only when you use the optional remote Compute workspace

Python 3.10 or newer is required only for the optional command-line/source
installation. The `.dmg` bundles its own Python core, GitHub CLI, and the pinned
official OpenAI Codex runtime.

## Install

### macOS application

1. Download `CrossAudit-4.14.0-arm64.dmg` and its checksum from the
   [V4.14.0 release](https://github.com/dongzhaohe321418-lab/crossaudit_v4/releases/tag/v4.14.0).
2. Optionally verify it in Terminal:

   ```bash
   shasum -a 256 -c CrossAudit-4.14.0-arm64.dmg.sha256
   ```

3. Open the DMG and drag **CrossAudit** to **Applications**.
4. Open CrossAudit, then open **Settings**. For OpenAI, choose **Connect** to
   complete the official ChatGPT browser login or enter an API key. Connect any
   second first-party provider from the same screen. API keys go to the macOS
   login Keychain; ChatGPT credentials remain owned by the official Codex runtime.

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
crossaudit 4.14.0 (receipt schema 2)
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
4. Open the new workspace, type the request, attach any inputs, and select
   **Run task**. State a format only when it matters; otherwise the Generator
   chooses the simplest useful one automatically.
5. Watch the generator, deterministic checks, auditor, and correction rounds
   update live. Download only the final
   user-facing artifacts from their conversation cards. After PASS, select
   **Admit result** to re-verify and consume the receipt once; a second attempt
   is refused.

The Projects button returns to the portfolio view. Every project has its own
background process and live progress bar, so switching workspaces does not stop
other loops.

Each Project is the real local folder selected during setup—not a cosmetic
label or hidden cloud container. Inside it, **New chat** starts an independent
task thread that shares the Project's files, configuration, Git repository, and
auditor Constitution. The sidebar separates pinned and recent Chats; the star
in the top bar pins the whole Project in the Projects list. Chat message,
deliverable, audit, and live-loop views are filtered to the selected Chat.
Existing pre-4.7 evidence appears automatically as **Project history**.

The delete controls keep those boundaries explicit. Deleting one Chat removes
it from Project navigation but never rewrites shared Git commits, audit reports,
receipts, or admitted files; a private tombstone prevents old ledger IDs from
silently recreating the Chat. Deleting a whole Project is available from the
main Projects view only when setup, audited work, and remote compute are idle.
By default CrossAudit atomically moves the complete local folder—including
uncommitted and unpushed work—into that workspace's hidden
`.crossaudit-trash/` recovery directory and shows the exact recovery path.
Connected GitHub repositories remain untouched. The working and audit
repositories have separate permanent-delete choices, both off by default, so a
user can remove only the audit ledger while preserving the delivered working
repository. Either irreversible choice requires both the exact Project name and
the phrase `DELETE GITHUB`. GitHub additionally requires its `delete_repo`
scope; CrossAudit exposes the official device flow when that permission is
missing. Partial remote failures never remove the recoverable local archive.

Closing the main CrossAudit window does **not** stop the application or an
active loop. CrossAudit remains visible as a diamond in the macOS menu bar;
choose **Open CrossAudit**, click its Dock icon, or open the application again
to restore the same live workspace. Choose **Quit CrossAudit** from the app or
menu-bar menu only when you intend to stop the local controller. Project work
already committed to Git remains durable across a later restart.

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

The native app exposes the desktop equivalent at **Settings → Environment
Doctor**. It runs asynchronously and updates in real time. It distinguishes a
missing tool from an outdated one, shows the installed and minimum versions,
and blocks project creation only for required failures. On macOS it can open
Apple's Command Line Tools installer, initialize a missing local Git ledger,
save a project-local Git identity, choose a writable workspace, or take the
user to the verified CrossAudit update. It never runs arbitrary commands from
the web view.

#### Connect an SSH workstation or HPC cluster

Select **Compute** inside a Project, then choose **Add SSH host**. CrossAudit
follows the same public remote-compute model documented for
[Claude Science](https://claude.com/docs/claude-science/remote-compute-clusters):

1. Enter a host alias from your existing `~/.ssh/config`. OpenSSH resolves its
   user, port, key, `ProxyJump`, `ProxyCommand`, agent, VPN, and corporate
   network behavior. CrossAudit never reads or copies the private key.
2. Choose an absolute scratch directory. On Slurm, it must be shared between
   the login and compute nodes.
3. Optionally record the account code, module loads, approved partitions, and
   other cluster policy in Host instructions.
4. Run the read-only probe. It checks CPU, memory, GPU, Slurm, partitions,
   modules, conda, and Apptainer and installs nothing remotely.

To make a host available to the Generator, enable **Allow Generator to use this
host automatically** and set the hard per-task policy: job count, nodes, CPUs,
GPUs, memory, wall time, and fixed scheduler partition/account/QoS. Disabled
hosts are not included in the Generator prompt at all.

During a normal task, the Generator can then request a remote calculation. The
controller—not the model—validates the host ID and policy, stages only declared
regular files from the Project's configured work directories, submits the job,
tracks it in the existing Compute view, and returns bounded stdout, stderr, and
declared text results to the Generator. The Generator uses that data to produce
the normal project files; those files still go through deterministic checks and
the independent Auditor before admission. Compute calls do not consume audit
rounds, but the saved jobs-per-task policy and an application-wide safety cap
prevent unbounded tool loops.

Automatic input staging uses the same streaming rule as manual transfer: there
is no CrossAudit file-count or file-size quota. Available storage, filesystem
limits, SSH/scheduler policy, and provider context still apply. Returned files
remain downloadable in full; only the text copied back into the model context is
bounded so one remote result cannot exhaust the conversation.

New host keys are refused by default. If the cluster administrator confirms a
new hostname, **Trust a new host key once** asks OpenSSH to use standard
trust-on-first-use. A changed saved key is always refused and cannot be replaced
from the CrossAudit UI.

**Submit job** shows explicit fields for partition, account, QoS, nodes, CPUs,
GPUs, memory, wall time, input files, and the complete shell script. Submission
requires a separate remote-execution confirmation. Selected input files are
uploaded to the local private inbox in bounded chunks and then streamed to the
job's remote `inputs/` directory; CrossAudit does not impose a file-count or
file-size quota.

When the probe finds `sbatch`, CrossAudit submits to Slurm and monitors `squeue`
and `sacct`. Otherwise it starts a detached `nohup` workstation process. Both
forms are owned by the remote scheduler or operating system, not by the local
app. Closing CrossAudit, sleeping the Mac, losing Wi-Fi, or disconnecting the
VPN therefore does not terminate the job. The private local job ledger retains
the host alias, scheduler ID, resource request, input digests, and remote job
directory so the next app process can reattach.

Job cards update through the existing authenticated SSE stream and provide:

- queued/running/final scheduler state and elapsed time;
- a reconnect-safe warning when only monitoring is offline;
- rolling stdout and stderr tails while the job runs;
- explicit cancellation through `scancel` or the detached process ID;
- a validated remote output list and constant-memory download streaming.

Remote scripts run outside the CrossAudit local sandbox as the configured SSH
user. They can access everything that account can access. This is especially
important for automatic Generator jobs, whose scripts are model-authored and do
not receive per-job confirmation after the host policy is enabled. Use a
dedicated HPC account, least-privilege filesystem permissions, scheduler limits,
and the cluster's normal review policy. CrossAudit never gives the model SSH
credentials, never opens an interactive shell to the WebView, and never lets a
model widen the saved host policy.

#### Connect MCP tools and Project Skills

Open **Tools & Skills** inside a Project. CrossAudit implements the official
[MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
and tool protocol with both standard transports:

- **Local stdio** starts one exact executable and argument vector without a
  shell. The complete command is visible and requires explicit approval.
- **Streamable HTTP** uses the single MCP endpoint, JSON-RPC POST requests,
  JSON or SSE responses, negotiated protocol-version headers, and session IDs
  described by the official
  [transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
  Public endpoints require HTTPS; loopback HTTP is allowed for local testing.

Registration performs `initialize`, sends `notifications/initialized`, and
reads the complete paginated `tools/list`. Connect a new server with Generator
access disabled, inspect its tool names, descriptions, input schemas and
untrusted annotations, then approve exact tool names and a calls-per-task cap.
New tools advertised later remain blocked until reviewed. A server and all its
tools are invisible to the Generator while disabled.

During a task the Generator may emit one `tools/call` request at a time. The
controller validates the server, exact tool name, JSON argument size and saved
call budget. Progress appears immediately in the audit loop. Bounded text and
structured results return to the same Generator turn as **untrusted external
data**; they never become instructions to the Auditor or amendments to the
Constitution. The private local call ledger retains only server/tool identity,
timing, status, and hashes of arguments/results—not their contents.

Remote bearer tokens are write-only macOS Keychain items and are never returned
to the WebView. Servers requiring interactive OAuth report a clear authorization
error; this build accepts a server-issued bearer token rather than implementing
an unsafe partial OAuth flow. Local MCP processes receive a small sanitized
environment, but they still run with the macOS user's filesystem permissions.
Review the publisher and use least privilege, as recommended by the official
[MCP security guidance](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices).

**Skills** are committed, project-level Markdown guidance for the Generator.
Create and edit them entirely in **Tools & Skills → Manage Skills**, optionally
scoped to project-relative paths. Skill hashes are recorded in receipts; Skills
cannot widen writable directories, override the Constitution, call the Auditor,
or silently turn guidance into an admission rule.

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

#### Understand token usage and API-value estimates

Select **Usage** inside a project to see token consumption as soon as each
model completion finishes. The view includes today and month totals, a seven-day
trend, Generator/Auditor allocation, model-level input/output/cache counts, and
recent calls. It records setup drafting, task generation, conversation control,
and formal audits, so the total reflects the whole supervised workflow rather
than only the final answer.

The provider response is the primary source. OpenAI API and Anthropic API usage,
and token-usage notifications emitted by the official Codex subscription
runtime, are marked **Reported**. Any completion that does not expose usage is
marked **Estimated**; an unknown or custom model is marked **Unpriced** instead
of borrowing another model's price. CrossAudit normalizes usage into four
mutually exclusive buckets: non-cached input, output, cache write, and cache
read.

Dollar figures are always labelled **API-value estimate**. They use a dated
snapshot of public [OpenAI API pricing](https://openai.com/api/pricing/) and
[Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing).
They are not an invoice, do not include negotiated discounts or tax, and do not
claim to measure what a ChatGPT subscription costs. Subscription calls can have
exact runtime token counts while their displayed dollar value remains only the
equivalent public API value.

Usage data stays in the project's gitignored `.crossaudit/usage.jsonl` file. It
uses mode 600 on macOS/Linux and the project directory's inherited user ACL on
Windows. Each line contains counts, time, role, phase, provider, and model only;
prompts, generated text, provider request IDs, API keys, and OAuth material are
never written. The aggregation and charts run locally and send no telemetry.
The local-first event normalization and explicit `≈ API value` presentation are
informed by the MIT-licensed [Agent Island](https://github.com/tristan666666/agent-island)
project; CrossAudit maintains its own provider adapters and price snapshot.

Open **Project controls → Usage guardrails** to set a daily token warning or
hard limit and a monthly API-value warning or hard limit. Warnings appear live
in Usage without interrupting work. A hard limit is checked before every model
request and pauses the task before more tokens are sent. A dollar limit is
fail-closed when an unpriced model has been used: CrossAudit will not pretend it
can prove a cost ceiling from incomplete prices. These are local safeguards;
the provider account remains the authority for quota and billing.

#### Create and switch projects in the browser

Click the CrossAudit name or the project switcher in the top bar to open the
local Projects view. For each new project, **Choose folder** opens the native
macOS directory picker. CrossAudit remembers only folders you explicitly
approved and discovers projects across all of them; it never scans the rest of
your home directory. Selecting a project starts or reattaches to that project's
own token-protected console.

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

**New project** opens the complete setup flow in the app: project name and
description, local parent folder, round budget, independent generator and
auditor vendors, and the model for each role. The selected folder is tested with
a real create/remove probe before it is saved. Unwritable, missing, or stale
folders stay in the form with a direct **Choose another folder** recovery action.
The form will not permit both roles to use the same vendor.
Every model menu includes a custom-ID escape hatch and **Refresh from provider**,
which asks the selected vendor which models the exact role credential can use;
this avoids freezing the UI at the model list current when CrossAudit shipped.
Inside an existing workspace, **Models & effort** changes either role's model
and, where the provider publishes a supported request control, its reasoning
effort. Changes are serialized between calls: controls lock while a loop is
running, the active call keeps the settings it started with, and the next call
uses the newly committed settings. The project view and Projects screen update
immediately over SSE; no daemon or app restart is needed. **Automatic** omits
the parameter and lets the provider use its documented default. CrossAudit does
not send guessed effort fields to an unknown model or provider.
For region-bound services, the same role card also exposes **API region**.
CrossAudit sends the key only to that allowlisted regional host, and stores the
chosen base URL in the project so later background runs use the same region.
It can also use the account already authenticated with `gh` to create a private
work repository and a separate audit repository. Both names are independently
editable. **Check names** verifies the exact connected account and both names
before any local or remote mutation. If an accessible repository exists,
CrossAudit requires the user to explicitly choose adoption; it never silently
reuses it. The folder selected in the Project form is always the exact local
project root; the Project name never creates another nested directory. An
unbound empty folder receives a clone before CrossAudit adds its owned setup
files, while a matching bound clone is fetched before those files are written.
Existing remote `main` history is never force-pushed. Before
reporting success,
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
a local-only project. Turning it on and submitting the final form creates both
named repositories in one guided action. Existing repositories are adopted
idempotently only after explicit consent, and an unrelated local `origin` is
never replaced. Merge conflicts abort safely and leave both histories intact.
Setup steps are persisted locally. If authentication, SSO,
permissions, rate limits, push, seeding, or secret upload fails after one
repository has already been created, the project row shows the exact failed
step and a **Fix & retry** action. The recovery dialog preserves both names,
offers the relevant GitHub or connection action, and resumes from durable state;
CrossAudit never silently deletes a repository during recovery.

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

Selecting a file does not transmit it. Pressing **Run task** is the single,
explicit authorization to send the written instruction and the files visibly
attached to that instruction to the configured Generator. The server
independently requires that send authorization, validates names and chunk offsets,
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

Click an output card to open CrossAudit's built-in file preview. PDF pages and
images render directly; DOCX content is reconstructed from the final Word
binary; Markdown, source code, JSON, YAML, CSV, logs and other text formats use
the reading view; and HTML runs in a sandbox with no script, application, or
network permission. Unknown binaries are never executed and show a download
action instead. Text previews are bounded for interface responsiveness, but the
download always contains the complete file and has no CrossAudit size quota.

PDF and Word are complete delivery formats, not browser placeholders. When the
user explicitly asks for PDF or DOCX in the instruction, CrossAudit binds the
request to one temporary Markdown source and the local controller converts it with a
deterministic renderer. CrossAudit validates the final PDF/OOXML container,
recovers its text from the exact final bytes, removes the temporary source, and
commits only the requested document. The independent Auditor therefore reviews
the same binary the user previews and downloads. Encrypted PDFs, unreadable or
empty documents, corrupt ZIP members, and macro-enabled OOXML fail closed at a
mandatory deterministic boundary. English and CJK text, headings, paragraphs,
lists, block quotes, fenced code and pipe tables are supported.

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

A cycle can end in four workflow states. The receipt additionally records the
authority status (`PASS`, `ADVISORY`, `BLOCK`, or `ESCALATE`) and its route:

| State | Meaning |
|---|---|
| `PASS` | Deterministic checks passed and the independent auditor found no blocker. |
| `BLOCKED` | Reproduced machine evidence prevents acceptance and may enter a guarded repair round. |
| `ESCALATED` | Evidence is insufficient for automatic authority, or the loop needs a person. |
| `DCL_ONLY` | Deterministic checks ran without a model audit; this can never count as PASS. |

The generator cannot edit the rule file, configuration, state, or audit ledger.
It may write only inside the configured scope, which defaults to `experiments/`.
The auditor receives the committed files and rules, not the generator's hidden
chain of thought or narrative.

Only verified machine blockers are returned to the Generator automatically.
The repair candidate is checked against the affected files and a change-size
budget before commit. A semantic model blocker instead pauses at the Git-backed
governance lane, where the principal may dispute the finding once, reopen the
cycle with a recorded reason, or close it without admission. See
[`docs/EVIDENCE_GOVERNANCE_FUSION.md`](docs/EVIDENCE_GOVERNANCE_FUSION.md).

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
the models cannot safely resolve a conflict. In the app, an explicit decision
screen opens in the affected conversation. It shows the configured round limit,
the verdict history, remaining audit findings, affected files, and concrete
next-step guidance. Closing it with **Review later** does not clear the warning:
the project remains visibly paused and no output can be admitted.

Choose **Revise and continue** to record correction guidance and unlock another
audited attempt, or **Stop this task** to retain the current output as unadmitted.
Both actions require a written explanation and enter the durable ledger.

The equivalent CLI flow is available for automation and advanced users. View
pending work with `crossaudit status`, then record a decision:

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
  reasoning_effort: high
  key_env: CROSSAUDIT_AUDITOR_KEY

generator:
  vendor: anthropic
  provider: anthropic
  model: claude-sonnet-4-6
  reasoning_effort: medium
  key_env: CROSSAUDIT_GENERATOR_KEY
  fallbacks:
    - vendor: google
      provider: google
      model: gemini-3.5-pro
      key_env: CROSSAUDIT_GOOGLE_KEY

resilience:
  max_attempts: 3
  initial_backoff_seconds: 1
  max_backoff_seconds: 20
  retry_after_cap_seconds: 120
  circuit_breaker_failures: 3
  circuit_breaker_cooldown_seconds: 60

budgets:
  daily_token_warning: 500000
  daily_token_limit: 1000000
  monthly_cost_warning_usd: 50
  monthly_cost_limit_usd: 100

repair:
  enabled: true
  max_changed_lines: 200

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

All of these controls are available in **Project controls**; editing YAML is
optional. Provider retries stay inside a single model turn and never consume an
audit revision round. HTTP `Retry-After` is honored up to the configured cap,
then exponential backoff is used. Repeated failures open a durable local
circuit; the next configured fallback route is tried immediately. The actual
vendor, provider, model, effort, and whether a fallback was used are recorded in
usage and audit evidence.

Fallback pools must preserve independence. No vendor may appear anywhere in
both the Generator pool and the Auditor pool. CrossAudit validates the complete
pair before committing UI changes and again before every build; an overlapping
configuration is refused rather than silently weakening the audit boundary.

The default local setup provides a replayable self-audit trail. It does not
prevent the owner of the repository from rewriting Git history. For stronger
organizational separation, use the two-repository deployment described below.

## Credentials and environment variables

The macOS app exposes provider connection settings in the UI. API keys are
stored in the current user's login Keychain. The UI can add, replace, or remove
them, but it can query only whether a credential exists; it never reads a secret
back into JavaScript.

Each provider has independent **primary** and optional **backup** Keychain
slots. A fallback route must explicitly select the backup slot before it can be
used; merely saving a second key never causes silent rotation. Keys remain
write-only, paste works in both fields, and route/circuit state stores only the
environment-variable name—not the credential value.

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
| `CROSSAUDIT_GOOGLE_KEY` | Google AI Studio Gemini API/auth key. |
| `CROSSAUDIT_DEEPSEEK_KEY` | DeepSeek Platform API key. |
| `CROSSAUDIT_ZHIPU_KEY` | Zhipu BigModel GLM API key. |
| `CROSSAUDIT_MOONSHOT_KEY` | Moonshot/Kimi Platform API key. |
| `CROSSAUDIT_MINIMAX_KEY` | MiniMax Open Platform API key. |
| `CROSSAUDIT_QWEN_KEY` | Alibaba Cloud Model Studio/DashScope API key. |
| `CROSSAUDIT_XAI_KEY` | xAI Console inference API key. |
| `CROSSAUDIT_MISTRAL_KEY` | Mistral La Plateforme API key. |
| `CROSSAUDIT_GENERATOR_MODEL` | Override the configured generator model. |
| `CROSSAUDIT_GENERATOR_PROVIDER` | Override the configured generator provider. |
| `CROSSAUDIT_GENERATOR_BASE_URL` | Override the generator's provider endpoint. |
| `CROSSAUDIT_KEYS_FILE` | Use a different credential-file location. |
| `CROSSAUDIT_SHOW_KEYS` | Show key input during setup when explicitly set to `1`; hidden is the secure default. |
| `CROSSAUDIT_CA_BUNDLE` | Trust a specific CA bundle without disabling TLS verification. |
| `CROSSAUDIT_GIT_TIMEOUT` | Seconds a single git operation may run before it is abandoned (default `240`). Raise it only for unusually large repositories. |
| `CROSSAUDIT_MAX_DOC_BYTES` | Byte ceiling for a single PDF/DOCX blob before it is refused as too large to audit rather than read into memory (default `67108864`, i.e. 64 MiB). Must match between the audit host and the verify host, exactly as the blob read caps must. |
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
| Anthropic | `anthropic` | `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` |
| Google Gemini | `google` | Models returned by the Gemini `models.list` endpoint; curated fallback includes Gemini 3.x |
| DeepSeek | `deepseek` | `deepseek-v4-pro`, `deepseek-v4-flash` |
| Zhipu GLM | `zhipu` | `glm-5.2`, `glm-5`, `glm-4.7` |
| Moonshot Kimi | `moonshot` | `kimi-k2.6`, `kimi-k2.5`, `kimi-k2-thinking-turbo` |
| MiniMax | `minimax` | `MiniMax-M2.7`, `MiniMax-M2.7-highspeed`, `MiniMax-M2.5` |
| Alibaba Qwen | `qwen` | `qwen3.7-max`, `qwen3.7-plus`, `qwen3-coder-plus`, `qwen-plus` |
| xAI | `xai` | `grok-4.5`, `grok-4.3`, `grok-code-fast-1` |
| Mistral AI | `mistral` | `mistral-medium-3-5`, `mistral-medium-latest`, `devstral-latest` |
| Other | `openai_compat` | exact model ID entered by the user |

The curated rows are resilient fallbacks, not a guarantee that every region or
account can access every model. In the app, click **Refresh from provider** to
replace them with the exact IDs visible to the selected credential. This avoids
freezing a fast-moving model catalogue into an application release.
Zhipu, Moonshot, MiniMax, and Qwen expose their supported China/international
API regions directly in the project form. Their regional keys are not assumed
to be interchangeable. See [provider support and authentication boundaries](docs/PROVIDER_SUPPORT.md)
for the researched endpoint and subscription-login policy.

Built-in OpenAI requests use `max_completion_tokens`. Custom OpenAI-compatible
providers retain family-based compatibility with endpoints that still expect
`max_tokens`.

Reasoning effort is request-level, not a permanent account setting. V4.9 exposes
only values that the selected model/provider combination documents or, for a
ChatGPT connection, values advertised live by the bundled official runtime.
Current built-in mappings cover OpenAI GPT-5 reasoning families, supported
Anthropic Claude models, Gemini thinking models, and reasoning-capable xAI
models. Other providers remain on **Automatic** until their public API contract
offers a compatible request control. Unsupported custom IDs are also kept on
Automatic so a model switch cannot introduce an avoidable HTTP 400.

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
`crossaudit --version` reports 4.14.0 and reinstall if an older package is still
on your PATH. Restart a background console after upgrading because an existing
daemon keeps the Python code that was loaded when it started.

### The macOS app is blocked on first launch

V4.14.0 is structurally signed with the hardened runtime but is not notarized.
Control-click **CrossAudit.app**, choose **Open**, and confirm only after you
have verified the published SHA-256 checksum. An Apple Developer ID signed and
notarized build is required before broad organizational deployment.

### Settings says Git is unavailable

Open **Settings → Environment Doctor** and choose **Install Git tools**. macOS
opens Apple's Command Line Tools installer; finish the system dialog and choose
**Run check**. The app bundles GitHub CLI and Codex but uses the system Git for
project history and commits. If Git is installed but too old, Doctor shows the
installed/minimum versions and opens the official update guidance.

### A project does not appear to update

The UI reconnects its event stream automatically. Use **View > Reload** if the
web view was suspended for a long time. Project activity and cycle state are
durable, so reloading or returning from Projects does not restart the work.

If the background process itself is killed during a task, the workspace shows
**Task interrupted safely**, including the last visible phase. **Retry task**
starts from the last durable Git commit and preserves the original chat and any
human-authorized continuation cycle. **Dismiss notice** leaves every file and
ledger record untouched. CrossAudit cannot prove whether a remote provider
finished a request after the local connection died, so it never claims an
exactly-once API call; recovery is explicitly anchored to local durable state.

### The model menu looks old or does not contain my model

Use the menu's manual-entry option or pass `--auditor-model` and
`--generator-model` to setup. Model availability belongs to the provider
account, not the API key format.

### Reasoning effort cannot be selected

This means the selected model/provider combination has no verified effort
contract in CrossAudit. Leave it on **Automatic**. For ChatGPT connections,
use **Refresh models** after signing in so the choices come from the live
workspace catalogue. If a loop is already running, wait for that loop to finish;
the controls deliberately lock rather than changing a request mid-flight.

### A provider returns HTTP 400 mentioning the model

The configured model ID is unavailable, misspelled, retired, or not enabled for
the account. Edit `model:` in `crossaudit.yml` or rerun setup with
`crossaudit init --force`.

### A provider returns HTTP 401

The key was rejected. Run `crossaudit doctor`; it reports only whether the key
is present, so copied diagnostic output does not reveal credential metadata
without printing the secret.

### A provider returns HTTP 429

The provider rate limit, quota, or balance was reached. This is not a
CrossAudit loop limit. CrossAudit honors `Retry-After`, retries with bounded
backoff without spending audit rounds, opens the route circuit after repeated
failures, and then tries the next user-configured fallback. If every route is
unavailable, the cycle escalates and no output is admitted. It never buys
credit, rotates an undeclared credential, or substitutes the other audit role.

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
- Remote Compute runs only scripts the user explicitly reviews and approves.
  Jobs execute with the user's remote account permissions, outside the local
  sandbox, and remain subject to cluster policy and scheduler limits.
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
python -m pip install ".[dev]"
python -m pytest -q --timeout=30
```

This installs the same wheel layout that users receive. Re-run the install
after changing package code, or set `PYTHONPATH=src` only for a deliberate
source-tree test. The release CI tests real installed wheels on Python
3.10–3.13 across Linux, macOS, and Windows, enforces branch-coverage and static
correctness gates, audits the installed dependency graph, and executes the
credential-free packaged-runtime self-test.

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
