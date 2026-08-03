# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability, leaked credential, or
exploit. Use GitHub's private vulnerability reporting for this repository. If
that channel is unavailable, contact the maintainers listed in `pyproject.toml`
and include the affected version, reproduction steps, impact, and any proposed
mitigation. Do not include real API keys or user data.

## Supported version

Security fixes are made against the latest `main` release. CrossAudit 4.4.0 is
the current native-app release.

## Desktop trust boundary

The native shell embeds a loopback-only Python core. Every HTTP request must
carry an unguessable process token and an allowed localhost `Host` header. The
browser layer cannot retrieve stored credentials. Provider keys are kept in the
macOS login Keychain and injected only into the local core process.

OpenAI subscription authentication is delegated to the pinned official Codex
runtime through its documented App Server protocol. CrossAudit never receives,
parses, logs, or serves OAuth tokens. Only allowlisted non-secret account state
is exposed to the UI. Subscription completions run in ephemeral, read-only,
network-disabled threads, and any command, file-change, web, or tool event makes
the provider round fail closed. Anthropic consumer credentials are never
captured or reused; Claude access remains API/approved-enterprise only.

Project workers are independent processes with separate repositories, tokens,
locks, ledgers, and scoped write directories. Provider output is data, not a
shell program: CrossAudit does not execute generated commands automatically.

## Distribution status

The 4.4.0 community DMG is ad-hoc signed and is not Apple-notarized. Verify the
published SHA-256 checksum before first launch. Organization-wide distribution
should wait for a Developer ID signed, notarized, and stapled artifact.
