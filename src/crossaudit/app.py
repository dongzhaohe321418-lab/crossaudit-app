"""CrossAudit V4 macOS application core.

The Swift shell owns the native window. This process owns the loopback server,
Git ledger, providers, and project workers. It prints exactly one tokenised URL
for the shell, then remains in the foreground until the application exits.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from . import __version__
from .app_keys import load_into_environment
from .config import CONFIG_NAME, load
from .console import serve
from .console import daemon
from .dcl import describe as describe_checks
from .scaffold import CONFIG_TEMPLATE, GENERAL_CHECKS, read
from .workspace import configured_workspace


def app_support() -> Path:
    override = os.environ.get("CROSSAUDIT_APP_SUPPORT", "").strip()
    return (Path(override).expanduser() if override else
            Path.home() / "Library" / "Application Support" / "CrossAudit")


def workspace_root(support: Path | None = None) -> Path:
    return configured_workspace(support or app_support())


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _controller_project(workspace: Path) -> Path:
    """Create the hidden controller, even when Git still needs installation.

    The Settings/Doctor UI must be reachable precisely when a prerequisite is
    broken.  Configuration files therefore come first; Git initialization is a
    best-effort final step that Doctor can safely complete after the user has
    installed Apple's Command Line Tools.
    """
    root = workspace / ".crossaudit-home"
    config = root / CONFIG_NAME
    if config.is_file():
        return root
    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(
        ".crossaudit/\n*.env\n.DS_Store\n", encoding="utf-8", newline="\n")
    (root / "AUDIT_RULES.md").write_text(
        read("GENERAL_AUDIT_RULES.md"), encoding="utf-8", newline="\n")
    body = CONFIG_TEMPLATE.format(
        science_repo="CrossAudit-Home", audit_repo_line="# audit_repo: (local ledger)",
        constitution="AUDIT_RULES.md", max_rounds=3,
        auditor_vendor="openai", auditor_provider="openai_compat",
        auditor_model="gpt-5.6-sol", base_url_line="",
        generator_vendor="anthropic",
        generator_details=("  provider: anthropic\n  model: claude-sonnet-4-6\n"
                           "  key_env: CROSSAUDIT_ANTHROPIC_KEY"),
        permissive_minimum="false", state_dir=".crossaudit",
        scope_dirs="work", checks=", ".join(GENERAL_CHECKS))
    body = body.replace("key_env: CROSSAUDIT_AUDITOR_KEY",
                        "key_env: CROSSAUDIT_OPENAI_KEY", 1)
    config.write_text(body, encoding="utf-8", newline="\n")
    (root / "DETERMINISTIC_CHECKS.md").write_text(
        "# Deterministic checks\n\n```text\n" + describe_checks(GENERAL_CHECKS)
        + "\n```\n", encoding="utf-8", newline="\n")
    git_path = shutil.which("git")
    git_usable = False
    if git_path:
        try:
            tools_ready = True
            if sys.platform == "darwin" and git_path == "/usr/bin/git":
                tools_ready = subprocess.run(
                    ["/usr/bin/xcode-select", "-p"], capture_output=True,
                    timeout=5).returncode == 0
            if tools_ready:
                probe = subprocess.run([git_path, "--version"], capture_output=True,
                                       timeout=5)
                git_usable = probe.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    if git_usable:
        try:
            _git(root, "init", "-q", "-b", "main")
            _git(root, "add", "-A")
            subprocess.run(
                [git_path, "-c", "user.name=CrossAudit", "-c",
                 "user.email=app@crossaudit.local", "commit", "-q", "-m",
                 f"CrossAudit V{__version__} application controller"],
                cwd=root, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            # The app can still open its local recovery UI. Doctor will show
            # the exact Git failure and offer to initialize this ledger again.
            pass
    return root


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--project-console":
        root = Path(sys.argv[2]).expanduser().resolve()
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        return project_console(root, port)
    os.environ["CROSSAUDIT_APP_MODE"] = "1"
    support = app_support()
    workspace = workspace_root(support)
    support.mkdir(parents=True, exist_ok=True, mode=0o700)
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ["CROSSAUDIT_APP_SUPPORT"] = str(support)
    os.environ["CROSSAUDIT_WORKSPACE_ROOT"] = str(workspace)
    load_into_environment()
    root = _controller_project(workspace)
    cfg = load(root / CONFIG_NAME)
    url, httpd = serve(cfg, port=0)

    def stop(_signum=None, _frame=None) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("CROSSAUDIT_APP_URL=" + url + "#projects", flush=True)
    try:
        httpd.serve_forever(poll_interval=0.2)
    finally:
        httpd.server_close()
    return 0


def project_console(root: Path, port: int = 0) -> int:
    """Bundled daemon entry used for independent per-project backgrounds."""
    os.environ["CROSSAUDIT_APP_MODE"] = "1"
    # CLI commands invoked by the shared console layer call config.load() from
    # the process working directory. Make the entrypoint self-contained rather
    # than relying on every parent launcher to remember cwd=project.
    os.chdir(root)
    load_into_environment()
    cfg = load(root / CONFIG_NAME)
    _url, httpd = serve(cfg, port=port, register=True, idle_timeout=float("inf"))

    def stop(_signum=None, _frame=None) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        httpd.serve_forever(poll_interval=0.2)
    finally:
        daemon.clear_run(cfg)
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
