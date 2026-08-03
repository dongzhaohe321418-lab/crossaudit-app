"""Application-facing environment diagnostics and narrowly scoped repairs.

The CLI doctor is intentionally terminal-oriented.  This module exposes the
same preflight concerns as structured, non-secret data so the native app can
explain a failure before a user reaches a provider call or project creation.
Checks run off the HTTP request thread and repairs are an explicit allowlist.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .config import CONFIG_NAME, Config
from .errors import ConfigDenial

LATEST_RELEASE_API = (
    "https://api.github.com/repos/dongzhaohe321418-lab/crossaudit_v4/releases/latest"
)
LATEST_RELEASE_URL = (
    "https://github.com/dongzhaohe321418-lab/crossaudit_v4/releases/latest"
)
MINIMUM_GIT = (2, 30, 0)  # ``git init -b`` is part of project creation.
MINIMUM_OPENSSH = (8, 1, 0)  # accept-new and modern host-key algorithms.
MINIMUM_GH = (2, 45, 0)
MINIMUM_CODEX = (0, 146, 0)
VERSION = re.compile(r"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?")
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def _tuple(value: str) -> tuple[int, int, int] | None:
    match = VERSION.search(value)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def _display(value: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in value)


def _run(path: str, *args: str, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        result = subprocess.run([path, *args], capture_output=True, text=True,
                                timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (result.stdout or result.stderr).strip()
    return result.returncode == 0, output[:500]


def _software(check_id: str, label: str, path: str | None,
              args: tuple[str, ...], minimum: tuple[int, int, int], *,
              required: bool, repair: dict) -> dict:
    if not path:
        return {
            "id": check_id, "label": label, "status": "missing",
            "blocking": required, "detail": f"{label} was not found.",
            "minimum": _display(minimum), "repair": repair,
        }
    ok, output = _run(path, *args)
    version = _tuple(output)
    if not ok or version is None:
        detail = output or f"{label} could not be started."
        return {
            "id": check_id, "label": label, "status": "missing",
            "blocking": required, "detail": detail,
            "path": path, "minimum": _display(minimum), "repair": repair,
        }
    if version < minimum:
        return {
            "id": check_id, "label": label, "status": "outdated",
            "blocking": required,
            "detail": (f"Version {_display(version)} is installed; CrossAudit "
                       f"requires {_display(minimum)} or later."),
            "version": _display(version), "minimum": _display(minimum),
            "path": path, "repair": repair,
        }
    return {
        "id": check_id, "label": label, "status": "ready",
        "blocking": False, "detail": f"Version {_display(version)}",
        "version": _display(version), "minimum": _display(minimum), "path": path,
    }


def _latest_release() -> tuple[str | None, str]:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={"accept": "application/vnd.github+json",
                 "user-agent": f"CrossAudit/{__version__}"})
    try:
        # The Request URL is the module-owned HTTPS GitHub release endpoint.
        with urllib.request.urlopen(request, timeout=4) as response:  # nosec B310
            payload = json.loads(response.read(256 * 1024))
        tag = str(payload.get("tag_name", "")).lstrip("v")
        return (tag if _tuple(tag) else None,
                str(payload.get("html_url") or LATEST_RELEASE_URL))
    except (urllib.error.URLError, OSError, ValueError, TypeError):
        return None, LATEST_RELEASE_URL


def collect(cfg: Config, *, online: bool = True) -> dict:
    """Return structured app readiness without exposing credentials."""
    started = time.time()
    checks: list[dict] = []

    python_version = sys.version.split()[0]
    checks.append({
        "id": "python", "label": "Embedded Python", "status": "ready",
        "blocking": False, "version": python_version,
        "minimum": "3.10.0", "detail": f"Version {python_version}",
    } if sys.version_info >= (3, 10) else {
        "id": "python", "label": "Embedded Python", "status": "outdated",
        "blocking": True, "version": python_version, "minimum": "3.10.0",
        "detail": "This application bundle must be replaced.",
        "repair": {"action": "download_update", "label": "Download latest",
                   "url": LATEST_RELEASE_URL},
    })

    if sys.platform == "darwin":
        mac = platform.mac_ver()[0] or "unknown"
        current_mac = _tuple(mac)
        supported = bool(current_mac and current_mac >= (13, 0, 0))
        checks.append({
            "id": "macos", "label": "macOS", "status": "ready" if supported else "outdated",
            "blocking": not supported, "version": mac, "minimum": "13.0.0",
            "detail": (f"macOS {mac}" if supported else
                       "CrossAudit requires macOS 13 or later."),
            **({"repair": {"action": "open_url", "label": "Open Software Update",
                            "url": "https://support.apple.com/guide/mac-help/get-macos-updates-mchlpx1065/mac"}}
               if not supported else {}),
        })

    git_path = shutil.which("git")
    command_line_tools = True
    if sys.platform == "darwin" and git_path in {None, "/usr/bin/git"}:
        command_line_tools, _ = _run("/usr/bin/xcode-select", "-p")
    git_repair = ({"action": "install_git_tools", "label": "Install Git tools"}
                  if sys.platform == "darwin" and not command_line_tools else
                  {"action": "open_url",
                   "label": ("Update Git tools" if sys.platform == "darwin" else
                             "Git installation guide"),
                   "url": ("https://support.apple.com/guide/mac-help/get-macos-updates-mchlpx1065/mac"
                           if sys.platform == "darwin" else
                           "https://git-scm.com/downloads")})
    git_check = ({
        "id": "git", "label": "Git", "status": "missing", "blocking": True,
        "detail": "Apple Command Line Tools are not installed.",
        "minimum": _display(MINIMUM_GIT), "path": git_path,
        "repair": git_repair,
    } if not command_line_tools else _software(
        "git", "Git", git_path, ("--version",), MINIMUM_GIT,
        required=True, repair=git_repair))
    checks.append(git_check)

    ssh_path = shutil.which("ssh")
    checks.append(_software(
        "ssh", "Remote compute client", ssh_path, ("-V",),
        MINIMUM_OPENSSH, required=False,
        repair={"action": "open_url", "label": "Open SSH setup guide",
                "url": "https://support.apple.com/guide/terminal/connect-to-servers-apdbb83aa795/mac"}))

    gh_path = (os.environ.get("CROSSAUDIT_BUNDLED_GH", "").strip()
               or shutil.which("gh"))
    checks.append(_software(
        "github_cli", "GitHub connection tool", gh_path, ("--version",),
        MINIMUM_GH, required=False,
        repair={"action": "download_update", "label": "Reinstall CrossAudit",
                "url": LATEST_RELEASE_URL}))

    codex_path = (os.environ.get("CROSSAUDIT_BUNDLED_CODEX", "").strip()
                  or shutil.which("codex"))
    checks.append(_software(
        "codex", "ChatGPT connection runtime", codex_path, ("--version",),
        MINIMUM_CODEX, required=False,
        repair={"action": "download_update", "label": "Reinstall CrossAudit",
                "url": LATEST_RELEASE_URL}))

    try:
        roots = len(ssl.create_default_context().get_ca_certs())
    except (OSError, ssl.SSLError):
        roots = 0
    checks.append({
        "id": "tls", "label": "Secure network certificates",
        "status": "ready" if roots else "missing", "blocking": not bool(roots),
        "detail": (f"{roots} trusted certificate authorities" if roots else
                   "No trusted certificates are available for provider HTTPS calls."),
        **({"repair": {"action": "download_update", "label": "Reinstall CrossAudit",
                        "url": LATEST_RELEASE_URL}} if not roots else {}),
    })

    workspace = Path(os.environ.get("CROSSAUDIT_WORKSPACE_ROOT", cfg.root.parent))
    workspace_ready = workspace.is_dir() and os.access(workspace, os.R_OK | os.W_OK | os.X_OK)
    checks.append({
        "id": "workspace", "label": "Project workspace",
        "status": "ready" if workspace_ready else "missing",
        "blocking": not workspace_ready, "detail": str(workspace),
        **({"repair": {"action": "choose_workspace", "label": "Choose another folder"}}
           if not workspace_ready else {}),
    })

    repo_ready = False
    if git_check["status"] == "ready":
        repo_ready, _ = _run(git_path or "git", "-C", str(cfg.root),
                             "rev-parse", "--git-dir")
    git_ready = git_check["status"] == "ready"
    checks.append({
        "id": "project_repo", "label": "Project Git ledger",
        "status": "ready" if repo_ready else "missing" if git_ready else "waiting",
        "blocking": bool(git_ready and not repo_ready),
        "detail": (str(cfg.root) if repo_ready else
                   "Initialize this folder after Git is ready." if not git_ready else
                   "This project is not initialized as a Git repository."),
        **({"repair": {"action": "initialize_repository",
                        "label": "Initialize safely"}} if git_ready and not repo_ready else {}),
    })

    if repo_ready:
        _, name = _run(git_path or "git", "-C", str(cfg.root), "config", "user.name")
        _, email = _run(git_path or "git", "-C", str(cfg.root), "config", "user.email")
        identity_ready = bool(name.strip() and email.strip())
        checks.append({
            "id": "git_identity", "label": "Git author identity",
            "status": "ready" if identity_ready else "warning", "blocking": False,
            "detail": (f"{name.strip()} <{email.strip()}>" if identity_ready else
                       "Add a name and email before creating commits."),
            **({"repair": {"action": "set_git_identity",
                            "label": "Save for this project", "inputs": True}}
               if not identity_ready else {}),
        })

    config_ready = cfg.path.is_file()
    constitution = cfg.root / cfg.constitution
    checks.extend(({
        "id": "config", "label": "Project configuration",
        "status": "ready" if config_ready else "missing", "blocking": not config_ready,
        "detail": str(cfg.path),
    }, {
        "id": "constitution", "label": "Audit rules",
        "status": "ready" if constitution.is_file() else "missing",
        "blocking": not constitution.is_file(), "detail": str(constitution),
    }))

    latest, release_url = _latest_release() if online else (None, LATEST_RELEASE_URL)
    current_tuple, latest_tuple = _tuple(__version__), _tuple(latest or "")
    outdated = bool(current_tuple and latest_tuple and current_tuple < latest_tuple)
    update_status = "outdated" if outdated else "ready" if latest else "unknown"
    checks.append({
        "id": "crossaudit", "label": "CrossAudit application",
        "status": update_status, "blocking": False, "version": __version__,
        "detail": (f"Version {__version__} is current." if latest and not outdated else
                   f"Version {latest} is available; this app is {__version__}." if outdated else
                   f"Version {__version__}; the update server could not be reached."),
        **({"latest": latest} if latest else {}),
        **({"repair": {"action": "download_update", "label": "Download update",
                        "url": release_url}} if outdated else {}),
    })

    blockers = sum(row["status"] in {"missing", "outdated"} and row["blocking"]
                   for row in checks)
    attention = sum(row["status"] in {"missing", "outdated", "warning"}
                    for row in checks)
    return {
        "status": "blocked" if blockers else "attention" if attention else "ready",
        "summary": (f"{blockers} required item{'s' if blockers != 1 else ''} need fixing"
                    if blockers else
                    f"{attention} optional item{'s' if attention != 1 else ''} need attention"
                    if attention else "Everything required is ready"),
        "checks": checks, "checked_at": int(time.time()),
        "duration_ms": int((time.time() - started) * 1000),
    }


def repair(cfg: Config, action: str, payload: dict) -> dict:
    """Perform one explicit, local, allowlisted repair."""
    if action == "install_git_tools":
        if sys.platform != "darwin" or not Path("/usr/bin/xcode-select").is_file():
            raise ConfigDenial("Automatic Git tools setup is available only on macOS")
        ok, output = _run("/usr/bin/xcode-select", "-p")
        if ok:
            raise ConfigDenial(
                "Apple Command Line Tools are already installed. Run the check again; "
                "if Git is still unavailable, update macOS or reinstall the tools.")
        try:
            subprocess.Popen(["/usr/bin/xcode-select", "--install"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise ConfigDenial(f"Could not open Apple's installer: {exc}") from exc
        return {"pending": True,
                "message": "Apple's Command Line Tools installer is open. Finish it, then run the check again."}

    git_path = shutil.which("git")
    if action in {"initialize_repository", "set_git_identity"} and not git_path:
        raise ConfigDenial("Git is not available yet. Install Git, then retry.")
    if action == "initialize_repository":
        ok, output = _run(git_path or "git", "init", "-q", "-b", "main",
                          timeout=15) if cfg.root == Path.cwd() else _run(
                              git_path or "git", "-C", str(cfg.root),
                              "init", "-q", "-b", "main", timeout=15)
        if not ok:
            raise ConfigDenial(f"Git could not initialize this project: {output}")
        files = [name for name in (CONFIG_NAME, cfg.constitution,
                                   "DETERMINISTIC_CHECKS.md", ".gitignore")
                 if (cfg.root / name).is_file()]
        if files:
            add_ok, add_output = _run(git_path or "git", "-C", str(cfg.root),
                                      "add", "--", *files, timeout=15)
            if not add_ok:
                raise ConfigDenial(f"Git could not stage the project files: {add_output}")
            _run(git_path or "git", "-C", str(cfg.root), "-c",
                 "user.name=CrossAudit", "-c", "user.email=app@crossaudit.local",
                 "commit", "-q", "-m", "CrossAudit: initialize local ledger",
                 "--", *files, timeout=20)
        return {"message": "The local Git ledger was initialized."}
    if action == "set_git_identity":
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip()
        if not name or len(name) > 100:
            raise ConfigDenial("Enter a Git author name of 100 characters or fewer")
        if len(email) > 200 or not EMAIL.fullmatch(email):
            raise ConfigDenial("Enter a valid Git author email address")
        for key, value in (("user.name", name), ("user.email", email)):
            ok, output = _run(git_path or "git", "-C", str(cfg.root),
                              "config", key, value)
            if not ok:
                raise ConfigDenial(f"Git could not save {key}: {output}")
        return {"message": "The Git identity was saved for this project."}
    raise ConfigDenial("That Doctor repair action is not supported")


class DoctorJobs:
    """One non-blocking scan per project configuration."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, dict] = {}

    def snapshot(self, cfg: Config) -> dict:
        key = str(cfg.root)
        with self._lock:
            return dict(self._states.get(key, {
                "status": "idle", "summary": "Environment has not been checked",
                "checks": [], "checked_at": 0,
            }))

    def start(self, cfg: Config, notify, *, force: bool = False) -> dict:
        key = str(cfg.root)
        with self._lock:
            current = self._states.get(key)
            if current and current.get("status") == "running":
                return dict(current)
            if (not force and current and current.get("checked_at") and
                    time.time() - int(current["checked_at"]) < 300):
                return dict(current)
            self._states[key] = {
                "status": "running", "summary": "Checking this Mac…",
                "checks": current.get("checks", []) if current else [],
                "checked_at": current.get("checked_at", 0) if current else 0,
            }

        def work() -> None:
            try:
                result = collect(cfg)
            except Exception as exc:  # noqa: BLE001 - background boundary
                result = {"status": "failed", "summary": f"Doctor could not finish: {exc}",
                          "checks": [], "checked_at": int(time.time())}
            with self._lock:
                self._states[key] = result
            notify()

        threading.Thread(target=work, daemon=True).start()
        notify()
        return self.snapshot(cfg)

    def fix(self, cfg: Config, action: str, payload: dict, notify) -> dict:
        result = repair(cfg, action, payload)
        self.start(cfg, notify, force=True)
        return {**result, "doctor": self.snapshot(cfg)}


JOBS = DoctorJobs()
