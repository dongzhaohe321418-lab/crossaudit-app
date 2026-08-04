"""`crossaudit pair` — creating the two repositories, and saying honestly what
that buys (DESIGN.md §6.2).

Two repositories are not about research. They are about privilege separation:
the generator cannot reach the rules it is judged by or the reports written
about it, and the auditor cannot reach the work's history. That separation is
what lets the ledger hold the two agents to account against *each other*, which
a single repository can never do.

This verb plans before it acts, always. `--plan` (the default) prints exactly
what would be created and changed; `--apply` does it. Nothing here writes to
anyone's account without that second word.

It also refuses to overstate what it achieved. Creating repositories and
uploading secrets produces the `paired` tier — privilege separation, history
out of unilateral control. It does not produce `enforced`: that needs an
independent, persistent controller consuming receipts atomically and an
admission check bound to a verified App, and until `doctor` can see both, the
honest word is "verified notification", not "enforced".
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from ..config import load
from ..errors import EXIT_CONFIG, EXIT_OK, ConfigDenial

TIERS = {
    "local": "one history, yours to rewrite: self-review, not accountability",
    "remote": "history out of unilateral control: you can be held to your own record",
    "paired": "privilege separation: the two agents can be held to account "
              "against each other",
    "enforced": "admission actually refused on a failed audit",
}

# External tools must never be allowed to freeze the desktop control plane.
# Authentication and identity checks run while rendering the Projects page, so
# keep those especially short.  Mutating network operations get a larger but
# still finite budget and run in a background job in the app.
GH_AUTH_TIMEOUT = 5
GH_IDENTITY_TIMEOUT = 10
GH_COMMAND_TIMEOUT = 120
GIT_COMMAND_TIMEOUT = 120


def _timed_out(tool: str, seconds: int) -> ConfigDenial:
    return ConfigDenial(
        f"{tool} did not respond within {seconds} seconds. Check the network or "
        "close any hidden sign-in prompt, then retry.",
        issue="command_timeout", action="retry",
        url="https://www.githubstatus.com" if tool == "GitHub" else "")


def gh() -> str:
    bundled = os.environ.get("CROSSAUDIT_BUNDLED_GH", "").strip()
    path = bundled if bundled and Path(bundled).is_file() else shutil.which("gh")
    if not path:
        raise ConfigDenial(
            "pairing needs the GitHub CLI: install it from https://cli.github.com "
            "and run `gh auth login`. CrossAudit deliberately does not implement "
            "its own OAuth flow or handle your token",
            issue="github_cli", action="install_github_cli",
            url="https://cli.github.com")
    try:
        proc = subprocess.run([path, "auth", "status"], capture_output=True,
                              text=True, timeout=GH_AUTH_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", GH_AUTH_TIMEOUT) from exc
    if proc.returncode != 0:
        raise ConfigDenial(
            "GitHub is not connected. Connect the account in CrossAudit and retry.",
            issue="github_auth", action="connect_github",
            url="https://github.com/login/device")
    return path


def _gh(*args: str, check: bool = True,
        timeout: int = GH_COMMAND_TIMEOUT) -> str:
    try:
        proc = subprocess.run([gh(), *args], capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", timeout) from exc
    if check and proc.returncode != 0:
        said = proc.stderr.strip()[:300]
        low = said.lower()
        hint = ""
        if "saml" in low or "sso" in low:
            hint = " Authorize GitHub CLI for the organisation's SSO, then retry."
            issue, action, url = ("github_sso", "open_github",
                                  "https://github.com/settings/applications")
        elif "rate limit" in low:
            hint = " GitHub rate-limited this account; wait for the reset, then retry."
            issue, action, url = ("github_rate_limit", "retry",
                                  "https://www.githubstatus.com")
        elif "resource not accessible" in low or "forbidden" in low or "403" in low:
            hint = " The connected account lacks repository or organisation permission."
            issue, action, url = ("github_permission", "open_github",
                                  "https://github.com/settings/repositories")
        elif "already exists" in low:
            hint = " The name exists but may not be visible to this account; verify ownership."
            issue, action, url = ("repo_exists", "edit_repositories", "")
        else:
            issue, action, url = ("github_error", "retry", "")
        raise ConfigDenial(f"gh {' '.join(args[:2])} failed: {said}.{hint}".rstrip(),
                           issue=issue, action=action, url=url)
    return proc.stdout.strip()


def _owner() -> str:
    return json.loads(_gh("api", "user", timeout=GH_IDENTITY_TIMEOUT))["login"]


def github_scopes() -> set[str]:
    """Read OAuth scope names from GitHub response headers without exposing the token."""
    try:
        proc = subprocess.run([gh(), "api", "-i", "user"], capture_output=True,
                              text=True, timeout=GH_IDENTITY_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", GH_IDENTITY_TIMEOUT) from exc
    if proc.returncode != 0:
        raise ConfigDenial(
            "GitHub could not verify authorization scopes: "
            f"{(proc.stderr or proc.stdout).strip()[:240]}",
            issue="github_auth", action="connect_github",
            url="https://github.com/login/device")
    match = re.search(r"(?im)^x-oauth-scopes:\s*(.*)$", proc.stdout)
    return ({scope.strip() for scope in match.group(1).split(",") if scope.strip()}
            if match else set())


def _exists(repo: str) -> bool:
    try:
        proc = subprocess.run([gh(), "repo", "view", repo], capture_output=True,
                              text=True, timeout=GH_IDENTITY_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", GH_IDENTITY_TIMEOUT) from exc
    if proc.returncode == 0:
        return True
    said = f"{proc.stdout}\n{proc.stderr}".casefold()
    if ("not found" in said or "could not resolve to a repository" in said or
            "could not resolve to a repo" in said):
        return False
    raise ConfigDenial(
        f"GitHub could not check {repo}: {(proc.stderr or proc.stdout).strip()[:240]}",
        issue="github_check", action="retry")


def _git(root: Path, *args: str, check: bool = True) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                              text=True, timeout=GIT_COMMAND_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
    if check and proc.returncode != 0:
        raise ConfigDenial(f"git {' '.join(args[:2])} failed: "
                           f"{proc.stderr.strip()[:240]}")
    return proc.stdout.strip()


def _github_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _normalise_remote(value: str) -> str:
    value = value.strip().removesuffix(".git")
    value = re.sub(r"^git@github\.com:", "https://github.com/", value)
    return value.rstrip("/").lower()


def _record_local_state_ignores(root: Path) -> None:
    path = root / ".gitignore"
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    entries = (".crossaudit/", ".crossaudit-home/", ".crossaudit-trash/")
    missing = [entry for entry in entries if entry not in current]
    if not missing:
        return
    with open(path, "a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n# CrossAudit's local state. The ledger is committed; this is not.\n"
                     + "\n".join(missing) + "\n")
    _git(root, "add", "--", ".gitignore")
    parents = _git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    if len(parents) >= 3:
        _git(root, "commit", "-q", "--amend", "--no-edit")
    else:
        _git(root, "-c", "user.name=CrossAudit", "-c",
             "user.email=crossaudit@local.invalid", "commit", "-q", "-m",
             "crossaudit: ignore local state", "--", ".gitignore")


def _sync_existing_main(root: Path) -> None:
    """Bring an adopted remote main into the local history without discarding either side."""
    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", "main"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT)
    if remote.returncode == 2:
        return  # An accessible but empty repository has no main branch yet.
    if remote.returncode != 0:
        raise ConfigDenial(
            "could not inspect the existing working repository main branch: "
            f"{(remote.stderr or remote.stdout).strip()[:240]}",
            issue="github_check", action="retry")
    local_state = (".crossaudit/", ".crossaudit-home/", ".crossaudit-trash/")
    dirty = []
    for line in _git(root, "status", "--porcelain", check=False).splitlines():
        path = line[3:].split(" -> ")[-1]
        if any(path == prefix.rstrip("/") or path.startswith(prefix)
               for prefix in local_state):
            continue
        dirty.append(line)
    if dirty:
        raise ConfigDenial(
            "the local working repository has uncommitted changes; commit or stash "
            "them before adopting its remote history",
            issue="remote_history", action="retry")
    _git(root, "fetch", "-q", "origin", "main")
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=str(root),
        capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT)
    if head.returncode != 0:
        _git(root, "checkout", "-q", "-B", "main", "origin/main")
        return
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT)
    if ancestor.returncode == 0:
        return
    merged = subprocess.run(
        ["git", "merge", "--no-edit", "--allow-unrelated-histories",
         "-X", "theirs", "origin/main"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT)
    if merged.returncode == 0:
        _record_local_state_ignores(root)
        return
    subprocess.run(["git", "merge", "--abort"], cwd=str(root),
                   capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT)
    raise ConfigDenial(
        "the local and remote working repository histories conflict; the merge was "
        "aborted without changing either history. Resolve the local files or choose "
        "a clean matching clone, then retry",
        issue="remote_history", action="retry")


def _write_pair_config(cfg, science: str, audit: str) -> None:
    """Persist the exact adopted repositories without flattening user comments."""
    body = cfg.path.read_text(encoding="utf-8")
    body, science_count = re.subn(r"(?m)^science_repo:\s*.*$",
                                  f"science_repo: {science}", body, count=1)
    body, audit_count = re.subn(r"(?m)^(?:#\s*)?audit_repo:\s*.*$",
                                f"audit_repo: {audit}", body, count=1)
    if not science_count:
        raise ConfigDenial("crossaudit.yml has no science_repo line to update")
    if not audit_count:
        body = body.replace(f"science_repo: {science}\n",
                            f"science_repo: {science}\naudit_repo: {audit}\n", 1)
    tmp = cfg.path.with_suffix(".yml.tmp")
    tmp.write_text(body, encoding="utf-8", newline="\n")
    tmp.replace(cfg.path)


def apply_pair(cfg, science: str, audit: str, *, private: bool,
               progress=None, allow_existing: bool = True) -> dict:
    """Create, connect and seed the two repositories, checking every mutation.

    This is shared by the CLI and the browser project wizard.  It is idempotent:
    an existing repository is adopted, but an unrelated local ``origin`` is
    never overwritten.
    """
    tell = progress or (lambda _stage, _detail: None)
    if science == audit:
        raise ConfigDenial("science and audit repositories must be different")
    for label, repo in (("science", science), ("audit", audit)):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ConfigDenial(f"{label} repository must be owner/name, got {repo!r}")

    const = cfg.root / cfg.constitution
    if not const.is_file():
        raise ConfigDenial(f"no Constitution at {const}; run `crossaudit init` first")

    expected = _github_url(science)
    current = _git(cfg.root, "remote", "get-url", "origin", check=False)
    if current and _normalise_remote(current) != _normalise_remote(expected):
        raise ConfigDenial(
            f"local origin is {current}, not {expected}; refusing to replace it",
            issue="origin_conflict", action="edit_repositories")
    config_rel = cfg.path.relative_to(cfg.root).as_posix()
    for staged in (False, True):
        args = ["git", "diff"]
        if staged:
            args.append("--cached")
        args.extend(["--quiet", "--", config_rel])
        try:
            clean = subprocess.run(args, cwd=str(cfg.root),
                                   timeout=GIT_COMMAND_TIMEOUT).returncode
        except subprocess.TimeoutExpired as exc:
            raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
        if clean != 0:
            where = "staged " if staged else ""
            raise ConfigDenial(
                f"{config_rel} has {where}changes; commit or restore them before pairing")

    gh()  # all local preflights passed; remote mutations may now begin
    tell("github", "GitHub authentication verified")
    created = []
    adopted = set()
    for repo in (science, audit):
        if _exists(repo):
            if not allow_existing:
                raise ConfigDenial(
                    f"repository {repo} already exists; edit the name or explicitly "
                    "allow CrossAudit to use repositories you can access",
                    issue="repo_exists", action="edit_repositories",
                    repositories=[repo])
            adopted.add(repo)
            tell("github", f"Adopting existing {repo}")
        else:
            _gh("repo", "create", repo, "--private" if private else "--public")
            created.append(repo)
            tell("github", f"Created {repo}")

    # The repository identities are part of the governed project, so publish
    # them in the science history rather than leaving a local-only config edit.
    _write_pair_config(cfg, science, audit)
    _git(cfg.root, "add", "--", config_rel)
    try:
        pending_config = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", config_rel],
            cwd=str(cfg.root), timeout=GIT_COMMAND_TIMEOUT).returncode
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
    if pending_config == 1:
        _git(cfg.root, "commit", "-q", "-m", "crossaudit: record repository pair",
             "--", config_rel)
    elif pending_config != 0:
        raise ConfigDenial("could not inspect the repository configuration change")

    if not current:
        _git(cfg.root, "remote", "add", "origin", expected)
    if science in adopted:
        tell("github", f"Synchronizing existing history from {science}")
        _sync_existing_main(cfg.root)
    _git(cfg.root, "push", "-u", "origin", "HEAD:main")
    tell("science", f"Pushed the local project to {science}")

    staging = cfg.root / cfg.state_dir / "pair-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    try:
        _gh("repo", "clone", audit, str(staging), "--", "-q")
        shutil.copyfile(const, staging / const.name)
        (staging / "cycles").mkdir(exist_ok=True)
        (staging / "cycles" / "README.md").write_text(
            "# Ledger\n\nOne directory per audit cycle: the report, the deterministic\n"
            "check output, and the receipt that binds them to a commit. Append-only:\n"
            "a re-audit adds an attempt, it never rewrites one.\n",
            encoding="utf-8", newline="\n")
        name = _git(staging, "config", "user.name", check=False)
        email = _git(staging, "config", "user.email", check=False)
        if not name:
            _git(staging, "config", "user.name", "CrossAudit")
        if not email:
            _git(staging, "config", "user.email", "crossaudit@local.invalid")
        _git(staging, "add", "-A")
        try:
            pending = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                     cwd=str(staging),
                                     timeout=GIT_COMMAND_TIMEOUT).returncode
        except subprocess.TimeoutExpired as exc:
            raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
        if pending == 1:
            _git(staging, "commit", "-q", "-m", "seed: constitution and ledger")
            _git(staging, "push", "-q", "origin", "HEAD:main")
        elif pending != 0:
            raise ConfigDenial("could not inspect the audit repository staging area")
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    tell("audit", f"Seeded {audit} with the Constitution and ledger")

    secret_uploaded = False
    key = os.environ.get(cfg.auditor.key_env, "").strip()
    if key:
        try:
            proc = subprocess.run([gh(), "secret", "set", cfg.auditor.key_env,
                                  "--repo", audit], input=key, text=True,
                                  capture_output=True, timeout=GH_COMMAND_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise _timed_out("GitHub", GH_COMMAND_TIMEOUT) from exc
        if proc.returncode != 0:
            raise ConfigDenial(f"could not upload {cfg.auditor.key_env}: "
                               f"{proc.stderr.strip()[:240]}",
                               issue="github_secret_permission",
                               action="open_github",
                               url=f"https://github.com/{audit}/settings/secrets/actions")
        secret_uploaded = True
        tell("secret", f"Uploaded {cfg.auditor.key_env} to the audit repository")
    else:
        tell("secret", f"{cfg.auditor.key_env} is not loaded; secret upload skipped")

    tell("config", "Saved the exact repository pair in crossaudit.yml")
    return {"science": science, "audit": audit, "created": created,
            "secret_uploaded": secret_uploaded,
            "tier": "paired", "branch_protection": "manual"}


def plan(science: str, audit: str, *, private: bool) -> list[tuple[str, str]]:
    """(action, why) pairs, in the order they would run."""
    vis = "--private" if private else "--public"
    return [
        (f"gh repo create {science} {vis}",
         "the work and its history"),
        (f"gh repo create {audit} {vis}",
         "the rules and every report: the generator has no write path here"),
        (f"push AUDIT_RULES.md to {audit}",
         "the Constitution lives where the audited party cannot edit it"),
        (f"gh secret set CROSSAUDIT_AUDITOR_KEY --repo {audit}",
         "the auditor's key, readable only by the audit side"),
        (f"gh api repos/{science}/branches/main/protection",
         "admission as a required check — a deployer toggle, and paid on private "
         "repositories under some plans"),
    ]


def cmd_pair(args) -> int:
    cfg = load()
    owner = _owner()
    science = args.science or f"{owner}/{cfg.root.name}"
    audit = args.audit or f"{science}-audit"
    private = not args.public

    print("\nCrossAudit — pairing the repositories")
    print("=" * 66)
    print(f"  science  {science}")
    print(f"  audit    {audit}")
    print(f"  buys     {TIERS['paired']}")
    print(f"  not      {TIERS['enforced']} — that needs a controller and an App")
    print()

    for i, (action, why) in enumerate(plan(science, audit, private=private), 1):
        print(f"  {i}. {action}")
        print(f"     {why}")

    if not args.apply:
        print("\n  This was a plan; nothing was created. Run again with --apply.")
        return EXIT_OK

    print("\n  Applying…")
    result = apply_pair(
        cfg, science, audit, private=private,
        progress=lambda _stage, detail: print(f"  · {detail}"))

    if not result["secret_uploaded"]:
        print(f"\n  ${cfg.auditor.key_env} is not loaded; upload it with "
              f"`gh secret set {cfg.auditor.key_env} --repo {audit}`")
    print("\n  Branch protection is the one step left, and it is yours: it needs")
    print("  admin rights and, on private repositories, a paid plan on some tiers.")
    print(f"    gh api repos/{science}/branches/main/protection -X PUT \\")
    print("      -f 'required_status_checks[strict]=true' \\")
    print("      -f 'required_status_checks[contexts][]=crossaudit/admission'")
    print("\n  Then `crossaudit doctor --online` reads the rules that actually")
    print("  exist and tells you which tier you are really at — plan text is not")
    print("  evidence.")
    return EXIT_OK
