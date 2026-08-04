"""Project discovery and the browser-driven new-project workflow.

The console remains one process per project.  This module is the small local
control plane above those consoles: it may discover sibling CrossAudit projects,
create one inside the same workspace, and hand the browser the tokenised URL of
that project's own daemon.  It never scans the whole home directory and never
accepts an arbitrary output path from the browser.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import yaml

from ..config import CONFIG_NAME, Config, heterogeneity, load
from ..app_keys import backup_env_for_vendor, env_for_vendor
from .. import connections, skills as skills_mod
from ..providers import codex_subscription
from ..controller import StateStore
from ..errors import ConfigDenial, Denial
from ..providers.catalog import list_models
from ..providers.specs import (EFFORT_HINTS, SPECS, endpoint as provider_endpoint,
                               endpoints as provider_endpoints,
                               reasoning_efforts)
from ..gitio import git, is_repo
from .. import workspace as workspace_mod
from ..scaffold import (CONFIG_TEMPLATE, GENERAL_CHECKS, GENERAL_TREE,
                        SCIENCE_CHECKS, SCIENCE_TREE, read, write_tree)
from ..dcl import describe as describe_checks
from ..cli import pair as pair_mod
from ..cli import wizard
from . import chats, daemon

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}")
SKILL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,59}")
GITHUB_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SETUP_FILE = "project-setup.json"
_RUNTIME_CONFIG_LOCK = threading.Lock()


def workspace_base(current: Config) -> Path:
    """Trusted workspace root selected by the app, or the CLI-era sibling root."""
    override = os.environ.get("CROSSAUDIT_WORKSPACE_ROOT", "").strip()
    return (Path(override).expanduser().resolve() if override
            else current.root.parent.resolve())


def workspace_roots(current: Config) -> tuple[Path, ...]:
    """Folders explicitly selected in the app, plus the current project parent."""
    roots = [workspace_base(current)]
    support_raw = os.environ.get("CROSSAUDIT_APP_SUPPORT", "").strip()
    if os.environ.get("CROSSAUDIT_APP_MODE") == "1" and support_raw:
        roots.extend(workspace_mod.known_workspaces(Path(support_raw)))
    if current.root.name != ".crossaudit-home":
        roots.append(current.root.parent.resolve())
    return tuple(dict.fromkeys(root.resolve() for root in roots))


def _trusted_project(current: Config, path: Path) -> bool:
    return path.parent in workspace_roots(current)


def _setup_path(root: Path) -> Path:
    return root / ".crossaudit" / SETUP_FILE


def _read_setup(root: Path) -> dict | None:
    path = _setup_path(root)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _write_setup(root: Path, value: dict) -> None:
    path = _setup_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8",
                   newline="\n")
    tmp.replace(path)


def _guidance(exc: Exception) -> dict:
    detail = exc.detail if isinstance(exc, Denial) else {}
    code = str(detail.get("issue", "")).strip()
    action = str(detail.get("action", "")).strip()
    url = str(detail.get("url", "")).strip()
    reason = exc.reason if isinstance(exc, Denial) else str(exc)
    low = reason.casefold()
    if not code:
        if "not authenticated" in low or "connect github" in low:
            code, action = "github_auth", "connect_github"
        elif "already exists" in low or "name exists" in low:
            code, action = "repo_exists", "edit_repositories"
        elif "permission" in low or "forbidden" in low or "403" in low:
            code, action = "github_permission", "open_github"
        elif "rate" in low and "limit" in low:
            code, action = "github_rate_limit", "retry"
        elif "origin" in low:
            code, action = "origin_conflict", "edit_repositories"
        elif "workspace" in low or "folder" in low:
            code, action = "workspace", "choose_workspace"
        else:
            code, action = "setup", "retry"
    titles = {
        "github_auth": "Connect GitHub to continue",
        "github_sso": "Authorize your organisation's SSO",
        "github_permission": "GitHub permission is required",
        "github_rate_limit": "GitHub is temporarily rate-limited",
        "repo_exists": "One or both repository names are already used",
        "origin_conflict": "The local Git remote needs attention",
        "workspace": "Choose a writable workspace",
        "workspace_permission": "Choose a writable workspace",
        "setup": "Project setup needs your attention",
    }
    return {"code": code[:60], "title": titles.get(code, titles["setup"]),
            "action": action[:60] or "retry", "url": url[:500] or None,
            "retryable": action in {"retry", "connect_github",
                                     "edit_repositories", "choose_workspace"}}


def _fail_setup(root: Path, detail: str, issue: dict | None = None) -> None:
    value = _read_setup(root)
    if value:
        value.update(status="failed", detail=detail[:500], finished=time.time())
        if issue:
            value["issue"] = issue
        _write_setup(root, value)


class ProjectJobs:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}

    def start(self, current: Config, payload: dict, notify) -> dict:
        project = str(payload.get("name", ""))[:80]
        base = workspace_base(current)
        candidate = (base / project).resolve()
        failure_root = (candidate if NAME.fullmatch(project or "") and
                        candidate.parent == base else None)
        return self._start(
            current, project, notify,
            lambda step: create_project(base, payload, step),
            failure_root=failure_root,
            context={"science": str(payload.get("science_repo", ""))[:170],
                     "audit": str(payload.get("audit_repo", ""))[:170],
                     "workspace": str(base), "github": payload.get("github") is True})

    def resume(self, current: Config, root: str, payload: dict, notify) -> dict:
        path = Path(root).resolve()
        base = path.parent if _trusted_project(current, path) else workspace_base(current)
        return self._start(
            current, path.name[:80], notify,
            lambda step: resume_project(base, path, step, payload),
            failure_root=(path if path.parent == base
                          else None), context={"science": str(payload.get("science_repo", ""))[:170],
                                              "audit": str(payload.get("audit_repo", ""))[:170],
                                              "github": True})

    def _start(self, current: Config, project: str, notify, operation, *,
               failure_root: Path | None, context: dict | None = None) -> dict:
        job_id = uuid.uuid4().hex[:12]
        row = {"id": job_id, "status": "running", "stage": "validate",
               "detail": "Validating project settings", "started": time.time(),
               "steps": [], "project": project,
               "root": str(failure_root) if failure_root is not None else None}
        row.update(context or {})
        with self._lock:
            if any(j["status"] == "running" and
                   j["project"].casefold() == project.casefold()
                   for j in self._jobs.values()):
                raise ConfigDenial(f"setup is already running for {project}")
            finished = sorted(
                (j for j in self._jobs.values() if j["status"] != "running"),
                key=lambda j: j.get("finished", j["started"]))
            for old in finished[:-39]:
                self._jobs.pop(old["id"], None)
            self._jobs[job_id] = row

        def step(stage: str, detail: str) -> None:
            with self._lock:
                row["stage"], row["detail"] = stage, detail
                row["steps"].append({"stage": stage, "detail": detail,
                                     "at": time.time()})
            notify()

        def work() -> None:
            try:
                result = operation(step)
                with self._lock:
                    row.update(status="complete", stage="ready", detail="Project ready",
                               result=result, finished=time.time())
            except (Denial, OSError, ValueError) as exc:
                why = exc.reason if isinstance(exc, Denial) else str(exc)
                issue = _guidance(exc)
                if failure_root is not None:
                    _fail_setup(failure_root, why, issue)
                with self._lock:
                    row.update(status="failed", detail=why[:500], issue=issue,
                               recoverable=bool(failure_root and
                                                (failure_root / CONFIG_NAME).is_file()),
                               finished=time.time())
            except Exception as exc:  # noqa: BLE001 - background boundary
                issue = _guidance(exc)
                if failure_root is not None:
                    _fail_setup(failure_root, str(exc), issue)
                with self._lock:
                    row.update(status="failed",
                               detail=f"{type(exc).__name__}: {exc}"[:500],
                               issue=issue,
                               recoverable=bool(failure_root and
                                                (failure_root / CONFIG_NAME).is_file()),
                               finished=time.time())
            notify()

        threading.Thread(target=work, daemon=True).start()
        return {"job": job_id}

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [dict(v, steps=[dict(s) for s in v["steps"]])
                    for v in self._jobs.values()]

    def running_for(self, root: Path) -> bool:
        """Whether project creation/recovery still owns this exact folder."""
        resolved = str(root.resolve())
        with self._lock:
            return any(row.get("status") == "running" and
                       (row.get("root") == resolved or
                        (not row.get("root") and row.get("project") == root.name))
                       for row in self._jobs.values())


JOBS = ProjectJobs()
_GH_CACHE: tuple[float, dict] | None = None
_RUNTIME_CACHE: dict[str, tuple[float, tuple, dict | None]] = {}


def _runtime(cfg: Config, current: Config) -> dict | None:
    """The small live-progress projection used by the workspace menu."""
    if cfg.root == current.root:
        from .. import hpc
        from .progress import TRACKER
        state = {"progress": TRACKER.snapshot(),
                 "compute": hpc.MANAGER.snapshot(cfg)}
    else:
        info = daemon.read_run(cfg)
        if not info:
            return None
        identity = (info.get("pid"), info.get("port"), info.get("started"))
        key, now = str(cfg.root), time.monotonic()
        cached = _RUNTIME_CACHE.get(key)
        if cached and cached[1] == identity and now - cached[0] < 0.35:
            state = cached[2]
        else:
            state = daemon.fetch_state(info)
            _RUNTIME_CACHE[key] = (now, identity, state)
        if not state:
            return None
    progress = state.get("progress")
    if isinstance(progress, dict) and not progress.get("finished"):
        steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
        latest = steps[-1] if steps and isinstance(steps[-1], dict) else {}
        return {
            "task": str(progress.get("task", ""))[:160],
            "elapsed": max(0, int(progress.get("elapsed", 0) or 0)),
            "actor": str(latest.get("actor", "starting"))[:30],
            "step": str(latest.get("text", "starting"))[:120],
        }
    compute = state.get("compute") if isinstance(state, dict) else None
    jobs = compute.get("jobs", []) if isinstance(compute, dict) else []
    active = next((row for row in jobs if isinstance(row, dict) and
                   row.get("status") not in {"completed", "failed", "cancelled",
                                              "timeout", "out_of_memory"}), None)
    if active:
        return {
            "task": str(active.get("name", "Remote compute"))[:160],
            "elapsed": max(0, int(time.time() - float(active.get("submitted", time.time())))),
            "actor": f"HPC · {str(active.get('host', 'remote'))[:22]}",
            "step": f"{str(active.get('name', 'job'))[:80]} · {active.get('status', 'running')}",
        }
    return None


def _invalidate_runtime(root: Path) -> None:
    _RUNTIME_CACHE.pop(str(root), None)


class RuntimeRelays:
    """Relay sibling daemon SSE into this project's event-driven menu stream."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: set[tuple[str, int, int]] = set()

    def ensure(self, current: Config, notify) -> None:
        candidates = []
        for base in workspace_roots(current):
            try:
                candidates.extend(base.iterdir())
            except OSError:
                continue
        for root in candidates:
            if root.resolve() == current.root or not (root / CONFIG_NAME).is_file():
                continue
            try:
                cfg = load(root / CONFIG_NAME)
                info = daemon.read_run(cfg)
                if not info:
                    continue
                identity = (str(cfg.root), int(info["pid"]), int(info["port"]))
                with self._lock:
                    if identity in self._active:
                        continue
                    self._active.add(identity)
                threading.Thread(target=self._watch,
                                 args=(cfg, info, identity, notify),
                                 daemon=True).start()
            except (Denial, OSError, KeyError, TypeError, ValueError):
                continue

    def _watch(self, cfg: Config, info: dict, identity: tuple, notify) -> None:
        url = (f"http://127.0.0.1:{int(info['port'])}/api/stream"
               f"?t={info['token']}")
        try:
            # Child console URLs are always generated from a local run record.
            with urllib.request.urlopen(url, timeout=20) as response:  # nosec B310
                for raw in response:
                    if raw.startswith(b"data:"):
                        _invalidate_runtime(cfg.root)
                        notify()
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            pass
        finally:
            with self._lock:
                self._active.discard(identity)


RELAYS = RuntimeRelays()


def github_status(*, force: bool = False) -> dict:
    global _GH_CACHE
    now = time.monotonic()
    if not force and _GH_CACHE and now - _GH_CACHE[0] < 30:
        return _GH_CACHE[1]
    try:
        owner = pair_mod._owner()
        value = {"connected": True, "owner": owner, "detail": f"Connected as {owner}"}
    except Denial as exc:
        value = {"connected": False, "owner": None, "detail": exc.reason,
                 "issue": exc.detail.get("issue"),
                 "action": exc.detail.get("action"),
                 "url": exc.detail.get("url")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        value = {"connected": False, "owner": None,
                 "detail": f"GitHub connection unavailable: {exc}"}
    _GH_CACHE = (now, value)
    return value


class GithubAuthJobs:
    """A user-triggered GitHub CLI device flow, surfaced safely in the UI."""

    CODE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: dict | None = None
        self._proc = None

    def start(self, notify) -> dict:
        status = github_status(force=True)
        if status["connected"]:
            return {"connected": True, "owner": status["owner"]}
        path = shutil.which("gh")
        if not path:
            raise ConfigDenial(
                "Install the GitHub CLI before connecting an account",
                issue="github_cli", action="install_github_cli",
                url="https://cli.github.com")
        with self._lock:
            if self._job and self._job["status"] == "running":
                return {"job": self._job["id"]}
            row = {"id": uuid.uuid4().hex[:12], "status": "running",
                   "detail": "Starting GitHub authorization", "code": "",
                   "url": "https://github.com/login/device",
                   "started": time.time()}
            self._job = row

        def work() -> None:
            proc = None
            timer = None
            timed_out = threading.Event()
            try:
                proc = subprocess.Popen(
                    [path, "auth", "login", "--hostname", "github.com",
                     "--git-protocol", "https", "--web", "--skip-ssh-key"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                    env=dict(os.environ, GH_PROMPT_DISABLED="1",
                             BROWSER="/usr/bin/false"))
                with self._lock:
                    self._proc = proc

                def expire() -> None:
                    timed_out.set()
                    if proc and proc.poll() is None:
                        proc.terminate()

                timer = threading.Timer(600, expire)
                timer.daemon = True
                timer.start()
                if proc.stdout:
                    for line in proc.stdout:
                        match = self.CODE.search(line)
                        if match:
                            with self._lock:
                                row["code"] = match.group(0)
                                row["detail"] = "Authorize CrossAudit in GitHub"
                            notify()
                result = proc.wait()
                connected = github_status(force=True)
                with self._lock:
                    if result == 0 and connected["connected"]:
                        row.update(status="complete", detail=connected["detail"],
                                   owner=connected["owner"], finished=time.time())
                    else:
                        detail = ("GitHub authorization timed out" if timed_out.is_set()
                                  else "GitHub authorization was not completed")
                        row.update(status="failed", detail=detail,
                                   finished=time.time())
            except (OSError, ValueError) as exc:
                with self._lock:
                    row.update(status="failed",
                               detail=f"Could not start GitHub authorization: {exc}"[:300],
                               finished=time.time())
            finally:
                if timer:
                    timer.cancel()
                with self._lock:
                    self._proc = None
                notify()

        threading.Thread(target=work, daemon=True).start()
        notify()
        return {"job": row["id"]}

    def snapshot(self) -> dict | None:
        with self._lock:
            return dict(self._job) if self._job else None

    def cancel(self) -> None:
        """Do not leave a device-flow child behind when the console exits."""
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


GITHUB_AUTH = GithubAuthJobs()
atexit.register(GITHUB_AUTH.cancel)


def models() -> dict:
    return {
        vendor: [{"id": model, "hint": hint} for model, hint in entries]
        for vendor, entries in wizard.VENDOR_MODELS.items() if vendor != "other"
    }


def endpoint_choices() -> dict:
    return {
        vendor: [{"id": row[0], "label": row[1]} for row in provider_endpoints(vendor)]
        for vendor in models()
    }


def refresh_models(current: Config, vendor: str, role: str,
                   method: str = "api", endpoint_id: str = "") -> dict:
    """Ask the provider which models this role's exact credential can access."""
    if vendor not in models():
        raise ConfigDenial(f"{vendor!r} has no supported model catalogue")
    if role not in {"auditor", "generator"}:
        raise ConfigDenial("model role must be auditor or generator")
    if vendor == "openai" and method == "chatgpt":
        rows = codex_subscription.list_models()
    else:
        if method != "api":
            raise ConfigDenial(f"{vendor} does not support connection {method!r}")
        vendor_env = env_for_vendor(vendor)
        role_env = (current.auditor.key_env if role == "auditor"
                    else "CROSSAUDIT_GENERATOR_KEY")
        key_env = vendor_env if os.environ.get(vendor_env, "").strip() else role_env
        try:
            rows = list_models(vendor, key_env, endpoint_id=endpoint_id)
        except ValueError as exc:
            raise ConfigDenial(str(exc)) from exc
    if not rows:
        raise ConfigDenial(f"{vendor} returned no models visible to this key")
    return {"vendor": vendor, "role": role, "method": method,
            "endpoint": endpoint_id, "models": rows,
            "refreshed": int(time.time())}


def _runtime_role(current: Config, role: str, model: str | None = None, *,
                  live_capabilities: bool = False) -> dict:
    if role == "auditor":
        vendor = current.auditor.vendor
        provider = current.auditor.provider
        selected_model = model or current.auditor.model
        selected_effort = current.auditor.reasoning_effort or ""
        base_url = current.auditor.base_url or ""
        fallback_roles = current.auditor.fallbacks
    elif role == "generator":
        vendor = current.generator_vendor or ""
        provider = current.generator_provider or ""
        selected_model = model or current.generator_model or ""
        selected_effort = current.generator_reasoning_effort or ""
        base_url = current.generator_base_url or ""
        fallback_roles = current.generator_fallbacks
    else:
        raise ConfigDenial("runtime role must be auditor or generator")
    if vendor == "human":
        return {"role": role, "vendor": vendor, "label": "Human", "provider": "",
                "model": "", "reasoning_effort": "", "models": [], "efforts": [],
                "adjustable": False, "detail": "A human generator has no model settings."}
    if vendor not in SPECS:
        raise ConfigDenial(f"{vendor!r} has no supported runtime catalogue")
    rows = [{"id": item, "hint": hint} for item, hint in SPECS[vendor].models]
    if selected_model and selected_model not in {row["id"] for row in rows}:
        rows.insert(0, {"id": selected_model, "hint": "current project model"})
    efforts = list(reasoning_efforts(vendor, selected_model, provider))
    if live_capabilities and provider == "openai_codex":
        advertised = codex_subscription.list_model_efforts(selected_model)
        if advertised:
            efforts = advertised
    endpoint_id = ""
    for item in provider_endpoints(vendor):
        if base_url and item[2].rstrip("/") == base_url.rstrip("/"):
            endpoint_id = item[0]
            break
    return {
        "role": role, "vendor": vendor, "label": SPECS[vendor].label,
        "provider": provider, "connection": ("chatgpt" if provider == "openai_codex"
                                                else "api"),
        "endpoint": endpoint_id,
        "model": selected_model, "reasoning_effort": selected_effort,
        "models": rows,
        "efforts": [{"id": item, "hint": EFFORT_HINTS.get(item, "provider option")}
                    for item in efforts],
        "adjustable": bool(efforts),
        "detail": ("The provider controls reasoning automatically for this model."
                   if not efforts else
                   "The selected effort is sent on the next provider request."),
        "fallbacks": [{"vendor": item.vendor, "provider": item.provider,
                       "model": item.model, "reasoning_effort":
                       item.reasoning_effort or "",
                       "credential": ("backup" if item.key_env ==
                                      backup_env_for_vendor(item.vendor)
                                      else "primary")} for item in fallback_roles],
    }


def _fallback_catalog() -> list[dict]:
    return [{"vendor": vendor, "label": item.label, "provider": item.provider,
             "models": [{"id": model, "hint": hint} for model, hint in item.models],
             "connected": connections.ready(vendor, "api"),
             "backup_connected": bool(os.environ.get(
                 backup_env_for_vendor(vendor), "").strip())}
            for vendor, item in SPECS.items()]


def runtime_options(current: Config, role: str = "", model: str = "", *,
                    live_capabilities: bool = False) -> dict:
    """Project model controls, with no credentials or provider-side reasoning."""
    if role:
        if not MODEL.fullmatch(model):
            raise ConfigDenial("model ids contain unsupported characters")
        return _runtime_role(current, role, model,
                             live_capabilities=live_capabilities)
    try:
        skill_rows, skill_error = skill_options(current), ""
    except Denial as exc:
        # A manually edited guidance file must not take down the entire live
        # console. Keep every other project control usable and surface the
        # narrow validation error beside the affected editor.
        skill_rows, skill_error = [], exc.reason
    return {
        "roles": {name: _runtime_role(current, name)
                  for name in ("generator", "auditor")},
        "max_rounds": current.max_rounds,
        "fallback_catalog": _fallback_catalog(),
        "resilience": {
            "max_attempts": current.resilience.max_attempts,
            "initial_backoff_seconds": current.resilience.initial_backoff_seconds,
            "max_backoff_seconds": current.resilience.max_backoff_seconds,
            "retry_after_cap_seconds": current.resilience.retry_after_cap_seconds,
            "circuit_breaker_failures": current.resilience.circuit_breaker_failures,
            "circuit_breaker_cooldown_seconds":
                current.resilience.circuit_breaker_cooldown_seconds,
        },
        "budgets": {
            "daily_token_warning": current.budgets.daily_token_warning,
            "daily_token_limit": current.budgets.daily_token_limit,
            "monthly_cost_warning_usd": current.budgets.monthly_cost_warning_usd,
            "monthly_cost_limit_usd": current.budgets.monthly_cost_limit_usd,
        },
        "skills": skill_rows,
        "skills_error": skill_error,
        "applies": "next_provider_call",
    }


def skill_options(current: Config) -> list[dict]:
    """Return editable generator guidance without exposing audit internals."""
    return [{"name": item.name, "path": item.path,
             "applies_to": list(item.applies_to), "body": item.body}
            for item in skills_mod.load(current.root)]


def update_skill(current: Config, payload: dict) -> dict:
    """Create or update one committed generator skill from Project controls."""
    if not is_repo(current.root):
        raise ConfigDenial("project guidance requires this project to be a git repository")
    name = str(payload.get("name", "")).strip()
    if not SKILL_NAME.fullmatch(name):
        raise ConfigDenial(
            "guidance names use letters, numbers, hyphens or underscores (60 characters max)")
    body = str(payload.get("body", "")).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not body:
        raise ConfigDenial("project guidance cannot be empty")
    if len(body.encode("utf-8")) > skills_mod.MAX_SKILL_BYTES:
        raise ConfigDenial(
            f"project guidance is larger than {skills_mod.MAX_SKILL_BYTES} bytes")
    raw_scopes = payload.get("applies_to", [])
    if isinstance(raw_scopes, str):
        raw_scopes = raw_scopes.split(",")
    if not isinstance(raw_scopes, list):
        raise ConfigDenial("guidance paths must be a comma-separated list")
    scopes = []
    for raw in raw_scopes:
        scope = str(raw).strip().strip("/")
        if (not scope or scope.startswith(".") or "\\" in scope or
                any(part in {"", ".", ".."} for part in scope.split("/"))):
            raise ConfigDenial("guidance paths must be safe project-relative prefixes")
        if len(scope) > 160:
            raise ConfigDenial("a guidance path is too long")
        scopes.append(scope)
    scopes = list(dict.fromkeys(scopes))

    base = current.root / skills_mod.SKILLS_DIR
    target = base / f"{name}.md"
    if target.is_symlink() or base.is_symlink():
        raise ConfigDenial("refusing to edit symlinked project guidance")
    dirty = git("status", "--porcelain", "--", skills_mod.SKILLS_DIR,
                cwd=current.root, check=False)
    if dirty:
        raise ConfigDenial(
            "project guidance has uncommitted changes. Commit or discard that edit, then retry; "
            "the UI will not overwrite it.", issue="skill_dirty", action="edit_guidance")
    header = ("---\napplies_to: " + ", ".join(scopes) + "\n---\n\n") if scopes else ""
    revised = header + body + "\n"
    original = target.read_text(encoding="utf-8") if target.is_file() else None
    if original == revised:
        return {"skills": skill_options(current), "changed": False, "commit": ""}
    base.mkdir(parents=True, exist_ok=True)
    temp = base / f".{name}.tmp"
    try:
        temp.write_text(revised, encoding="utf-8", newline="\n")
        temp.replace(target)
        # Validate the complete guidance set before recording it.
        skills_mod.load(current.root)
        rel = target.relative_to(current.root).as_posix()
        git("add", "--", rel, cwd=current.root)
        git("-c", "user.name=CrossAudit", "-c",
            "user.email=crossaudit@local.invalid", "commit", "-q", "--only",
            "-m", f"guidance: update {name}", "--", rel, cwd=current.root)
        commit = git("rev-parse", "HEAD", cwd=current.root)
    except Exception:
        if original is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(original, encoding="utf-8", newline="")
        temp.unlink(missing_ok=True)
        subprocess.run(["git", "restore", "--staged", "--",
                        target.relative_to(current.root).as_posix()],
                       cwd=current.root, capture_output=True, check=False)
        raise
    return {"skills": skill_options(current), "changed": True, "commit": commit}


def _replace_role_runtime(text: str, role: str, model: str, effort: str) -> str:
    """Patch one block-style role while preserving comments and file layout."""
    lines = text.splitlines(keepends=True)
    header = next((i for i, line in enumerate(lines)
                   if re.fullmatch(rf"{role}:\s*(?:#.*)?\n?", line)), None)
    if header is None:
        raise ConfigDenial(
            f"{role} must use block-style YAML before the UI can edit it",
            issue="runtime_config_format", action="edit_config")
    end = len(lines)
    for i in range(header + 1, len(lines)):
        if lines[i].strip() and not lines[i].startswith((" ", "\t", "#")):
            end = i
            break
    model_at = next((i for i in range(header + 1, end)
                     if re.match(r"\s+model\s*:", lines[i])), None)
    if model_at is None:
        raise ConfigDenial(f"{role}.model is missing from crossaudit.yml")
    newline = "\r\n" if lines[model_at].endswith("\r\n") else "\n"
    indent = re.match(r"\s*", lines[model_at]).group(0)
    lines[model_at] = f"{indent}model: {model}{newline}"
    effort_at = next((i for i in range(header + 1, end)
                      if re.match(r"\s+reasoning_effort\s*:", lines[i])), None)
    if effort_at is not None:
        if effort:
            lines[effort_at] = f"{indent}reasoning_effort: {effort}{newline}"
        else:
            lines.pop(effort_at)
    elif effort:
        lines.insert(model_at + 1, f"{indent}reasoning_effort: {effort}{newline}")
    return "".join(lines)


def _replace_max_rounds(text: str, value: int) -> str:
    """Patch the top-level loop budget without rewriting user YAML formatting."""
    lines = text.splitlines(keepends=True)
    at = next((i for i, line in enumerate(lines)
               if re.match(r"^max_rounds\s*:", line)), None)
    if at is not None:
        newline = "\r\n" if lines[at].endswith("\r\n") else "\n"
        lines[at] = f"max_rounds: {value}{newline}"
        return "".join(lines)
    version_at = next((i for i, line in enumerate(lines)
                       if re.match(r"^version\s*:", line)), -1)
    newline = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    lines.insert(version_at + 1, f"max_rounds: {value}{newline}")
    return "".join(lines)


def _replace_top_mapping(text: str, name: str, value: dict) -> str:
    """Replace one generated top-level mapping without rewriting user YAML."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines)
                  if re.match(rf"^{re.escape(name)}\s*:", line)), None)
    if start is not None:
        end = len(lines)
        for i in range(start + 1, len(lines)):
            if lines[i].strip() and not lines[i].startswith((" ", "\t", "#")):
                end = i
                break
        del lines[start:end]
    block = yaml.safe_dump({name: value}, sort_keys=False, default_flow_style=False)
    if lines and lines[-1] and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += "\n"
    lines.extend(part + "\n" for part in block.rstrip("\n").splitlines())
    return "".join(lines)


def _fallback_payload(rows: object, role: str) -> list[dict]:
    if rows in (None, ""):
        return []
    if not isinstance(rows, list) or len(rows) > 8:
        raise ConfigDenial(f"{role} supports up to 8 fallback routes")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ConfigDenial(f"{role} fallback routes must be objects")
        vendor = str(row.get("vendor", "")).strip().lower()
        if vendor not in SPECS:
            raise ConfigDenial(f"unsupported fallback provider {vendor!r}")
        model = str(row.get("model", "")).strip()
        if not MODEL.fullmatch(model):
            raise ConfigDenial("fallback model ids contain unsupported characters")
        credential = str(row.get("credential", "primary"))
        if credential not in {"primary", "backup"}:
            raise ConfigDenial("fallback credential must be primary or backup")
        result.append({"provider": SPECS[vendor].provider, "model": model,
                       "vendor": vendor,
                       "key_env": (backup_env_for_vendor(vendor)
                                   if credential == "backup" else env_for_vendor(vendor))})
    return result


def _replace_role_fallbacks(text: str, role: str, rows: list[dict]) -> str:
    lines = text.splitlines(keepends=True)
    header = next((i for i, line in enumerate(lines)
                   if re.fullmatch(rf"{role}:\s*(?:#.*)?\n?", line)), None)
    if header is None:
        raise ConfigDenial(f"{role} must use block-style YAML before fallbacks can be edited")
    end = len(lines)
    for i in range(header + 1, len(lines)):
        if lines[i].strip() and not lines[i].startswith((" ", "\t", "#")):
            end = i
            break
    start = next((i for i in range(header + 1, end)
                  if re.match(r"^  fallbacks\s*:", lines[i])), None)
    if start is not None:
        stop = end
        for i in range(start + 1, end):
            if lines[i].strip() and not lines[i].startswith(("    ", "\t", "#")):
                stop = i
                break
        del lines[start:stop]
        end -= stop - start
    if rows:
        dumped = yaml.safe_dump({"fallbacks": rows}, sort_keys=False,
                                default_flow_style=False).rstrip("\n")
        parts = dumped.splitlines()
        block = ["  " + parts[0] + "\n",
                 *("    " + part + "\n" for part in parts[1:])]
        lines[end:end] = block
    return "".join(lines)


def _bounded_number(payload: dict, key: str, low: float, high: float,
                    default, *, integer: bool = False):
    raw = payload.get(key, default)
    try:
        value = int(raw) if integer else float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ConfigDenial(f"{key.replace('_', ' ')} must be a number") from exc
    if not low <= value <= high:
        raise ConfigDenial(
            f"{key.replace('_', ' ')} must be between {low:g} and {high:g}")
    return value


def _optional_positive(payload: dict, key: str, default=None, *, integer: bool = False):
    raw = payload.get(key, default)
    if raw in (None, ""):
        return None
    try:
        value = int(raw) if integer else float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ConfigDenial(f"{key.replace('_', ' ')} must be a positive number") from exc
    if value <= 0:
        raise ConfigDenial(f"{key.replace('_', ' ')} must be a positive number")
    return value


def update_runtime(current: Config, payload: dict) -> dict:
    """Atomically commit model, effort and loop-budget choices from the UI."""
    with _RUNTIME_CONFIG_LOCK:
        if not is_repo(current.root):
            raise ConfigDenial("runtime settings require this project to be a git repository")
        dirty = git("status", "--porcelain", "--", CONFIG_NAME,
                    cwd=current.root, check=False)
        if dirty:
            raise ConfigDenial(
                "crossaudit.yml has uncommitted changes. Commit or discard that edit, then retry; "
                "the UI will not overwrite it.", issue="runtime_config_dirty",
                action="edit_config")
        try:
            max_rounds = int(payload.get("max_rounds", current.max_rounds))
        except (TypeError, ValueError) as exc:
            raise ConfigDenial("maximum rounds must be a number between 1 and 10") from exc
        if not 1 <= max_rounds <= 10:
            raise ConfigDenial("maximum rounds must be between 1 and 10")
        choices = {}
        for role in ("generator", "auditor"):
            current_role = _runtime_role(current, role)
            if current_role["vendor"] == "human":
                choices[role] = ("", "")
                continue
            model = _clean_text(payload, f"{role}_model", 120)
            if not MODEL.fullmatch(model):
                raise ConfigDenial("model ids contain unsupported characters")
            effort = str(payload.get(f"{role}_reasoning_effort", "")).strip()
            allowed = set(reasoning_efforts(current_role["vendor"], model,
                                            current_role["provider"]))
            if current_role["provider"] == "openai_codex" and effort not in allowed:
                # Subscription catalogues advertise capabilities per model and
                # can include values newer than this release.
                advertised = set(codex_subscription.list_model_efforts(model))
                allowed |= advertised
            if effort and effort not in allowed:
                if allowed:
                    raise ConfigDenial(
                        f"{current_role['label']} does not advertise {effort!r} for "
                        f"{model}. Choose Automatic or one of {sorted(allowed)}.")
                raise ConfigDenial(
                    f"{current_role['label']} does not expose an adjustable effort "
                    f"for {model}. Choose Automatic.")
            choices[role] = (model, effort)

        resilience = {
            "max_attempts": _bounded_number(payload, "max_attempts", 1, 10,
                                             current.resilience.max_attempts, integer=True),
            "initial_backoff_seconds": _bounded_number(
                payload, "initial_backoff_seconds", 0, 60,
                current.resilience.initial_backoff_seconds),
            "max_backoff_seconds": _bounded_number(
                payload, "max_backoff_seconds", 0, 300,
                current.resilience.max_backoff_seconds),
            "retry_after_cap_seconds": _bounded_number(
                payload, "retry_after_cap_seconds", 0, 900,
                current.resilience.retry_after_cap_seconds),
            "circuit_breaker_failures": _bounded_number(
                payload, "circuit_breaker_failures", 1, 20,
                current.resilience.circuit_breaker_failures, integer=True),
            "circuit_breaker_cooldown_seconds": _bounded_number(
                payload, "circuit_breaker_cooldown_seconds", 1, 3600,
                current.resilience.circuit_breaker_cooldown_seconds),
        }
        if resilience["max_backoff_seconds"] < resilience["initial_backoff_seconds"]:
            raise ConfigDenial("maximum retry delay cannot be below the initial delay")
        budgets = {
            "daily_token_warning": _optional_positive(
                payload, "daily_token_warning", current.budgets.daily_token_warning,
                integer=True),
            "daily_token_limit": _optional_positive(
                payload, "daily_token_limit", current.budgets.daily_token_limit,
                integer=True),
            "monthly_cost_warning_usd": _optional_positive(
                payload, "monthly_cost_warning_usd",
                current.budgets.monthly_cost_warning_usd),
            "monthly_cost_limit_usd": _optional_positive(
                payload, "monthly_cost_limit_usd",
                current.budgets.monthly_cost_limit_usd),
        }
        if (budgets["daily_token_warning"] and budgets["daily_token_limit"] and
                budgets["daily_token_warning"] > budgets["daily_token_limit"]):
            raise ConfigDenial("daily token warning cannot exceed the hard limit")
        if (budgets["monthly_cost_warning_usd"] and budgets["monthly_cost_limit_usd"] and
                budgets["monthly_cost_warning_usd"] > budgets["monthly_cost_limit_usd"]):
            raise ConfigDenial("monthly cost warning cannot exceed the hard limit")
        existing_fallbacks = {
            "generator": current.generator_fallbacks,
            "auditor": current.auditor.fallbacks,
        }
        fallbacks = {}
        for role in ("generator", "auditor"):
            key = f"{role}_fallbacks"
            if key in payload:
                fallbacks[role] = _fallback_payload(payload[key], role)
            else:
                fallbacks[role] = [
                    {"provider": item.provider, "model": item.model,
                     "vendor": item.vendor, "key_env": item.key_env,
                     **({"base_url": item.base_url} if item.base_url else {}),
                     **({"reasoning_effort": item.reasoning_effort}
                        if item.reasoning_effort else {})}
                    for item in existing_fallbacks[role]]

        original = current.path.read_text(encoding="utf-8")
        revised = _replace_max_rounds(original, max_rounds)
        if current.generator_vendor != "human":
            revised = _replace_role_runtime(revised, "generator", *choices["generator"])
        revised = _replace_role_runtime(revised, "auditor", *choices["auditor"])
        revised = _replace_role_fallbacks(revised, "generator", fallbacks["generator"])
        revised = _replace_role_fallbacks(revised, "auditor", fallbacks["auditor"])
        revised = _replace_top_mapping(revised, "resilience", resilience)
        revised = _replace_top_mapping(revised, "budgets", budgets)
        if revised == original:
            return {**runtime_options(current), "changed": False, "commit": ""}
        temp = current.path.with_suffix(".runtime.tmp")
        try:
            temp.write_text(revised, encoding="utf-8", newline="")
            temp.replace(current.path)
            updated = load(current.path)
            ok, why = heterogeneity(updated)
            if not ok:
                raise ConfigDenial(why)
            commit_message = (f"config: {choices['generator'][0] or 'human'} -> "
                              f"{choices['auditor'][0]}, {max_rounds} rounds")
            git("-c", "user.name=CrossAudit", "-c",
                "user.email=crossaudit@local.invalid", "commit", "-q", "--only",
                "-m", commit_message, "--", CONFIG_NAME, cwd=current.root)
            commit = git("rev-parse", "HEAD", cwd=current.root)
        except Exception:
            current.path.write_text(original, encoding="utf-8", newline="")
            temp.unlink(missing_ok=True)
            raise
        return {**runtime_options(updated), "changed": True, "commit": commit}


def _project_row(path: Path, current: Config) -> dict | None:
    try:
        cfg = load(path / CONFIG_NAME)
        cycles = StateStore(cfg.root / cfg.state_dir / "state.json").snapshot().get(
            "cycles", {})
        latest = list(cycles.values())[-1] if cycles else None
        progress = _runtime(cfg, current)
        interrupted = daemon.interrupted(cfg)
        setup = _read_setup(cfg.root)
        setup_running = bool(setup and setup.get("status") == "running")
        recoverable = bool(setup and setup.get("status") == "failed"
                           and setup.get("github"))
        pair_ready = bool(cfg.audit_repo and
                          (not setup or setup.get("status") == "complete"))
        chat_state = chats.snapshot(cfg)
        return {
            "name": cfg.root.name, "label": cfg.science_repo, "root": str(cfg.root),
            "current": cfg.root == current.root, "paired": pair_ready,
            "status": ("running" if progress else
                       "setting_up" if setup_running else
                       "setup_failed" if recoverable else
                       "interrupted" if interrupted else
                       latest["status"].lower() if latest else "ready"),
            "cycles": len(cycles),
            "chats": len(chat_state["items"]),
            "pinned": chat_state["project_pinned"],
            "progress": progress,
            "interrupted": interrupted,
            "setup": ({"status": setup.get("status"),
                       "detail": str(setup.get("detail", ""))[:300],
                       "steps": setup.get("steps", [])[-8:],
                       "recoverable": recoverable,
                       "issue": setup.get("issue"),
                       "science": setup.get("science"),
                       "audit": setup.get("audit"),
                       "private": setup.get("private") is not False}
                      if setup else None),
            "auditor": f"{cfg.auditor.vendor} · {cfg.auditor.model}",
            "generator": ("human" if cfg.generator_vendor == "human" else
                          f"{cfg.generator_vendor or 'unset'} · "
                          f"{cfg.generator_model or 'unset'}"),
            "updated": int((path / CONFIG_NAME).stat().st_mtime),
        }
    except (Denial, OSError, KeyError):
        return None


def snapshot(current: Config) -> dict:
    base = workspace_base(current)
    rows = []
    candidates = []
    for root in workspace_roots(current):
        try:
            candidates.extend(p for p in root.iterdir() if p.is_dir())
        except OSError:
            continue
    candidates = sorted(dict.fromkeys(path.resolve() for path in candidates))
    app_home = os.environ.get("CROSSAUDIT_APP_MODE") == "1"
    if current.root not in candidates and not (app_home and current.root.name == ".crossaudit-home"):
        candidates.append(current.root)
    for path in candidates:
        if app_home and path.name == ".crossaudit-home":
            continue
        if (path / CONFIG_NAME).is_file():
            row = _project_row(path, current)
            if row:
                rows.append(row)
    rows.sort(key=lambda p: (not p["pinned"], not p["current"],
                             -p["updated"], p["name"].lower()))
    return {"workspace": str(base), "items": rows, "jobs": JOBS.snapshot(),
            "capacity": daemon.workspace_capacity(current),
            "github_auth": GITHUB_AUTH.snapshot(),
            "github": github_status(), "models": models(),
            "endpoints": endpoint_choices(),
            "connections": connections.status()}


def _clean_text(payload: dict, key: str, limit: int, *, required: bool = True) -> str:
    value = str(payload.get(key, "")).strip()
    if required and not value:
        raise ConfigDenial(f"{key.replace('_', ' ')} is required")
    if len(value) > limit:
        raise ConfigDenial(f"{key.replace('_', ' ')} is too long")
    return value


def _repo(value: str, owner: str, fallback: str) -> str:
    value = value.strip() or fallback
    if "/" not in value:
        value = f"{owner}/{value}"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ConfigDenial(f"repository must be owner/name, got {value!r}")
    return value


def select_workspace(current: Config, selected: str) -> dict:
    if os.environ.get("CROSSAUDIT_APP_MODE") != "1":
        raise ConfigDenial(
            "Choose folder is available in the CrossAudit macOS app",
            issue="workspace_app_required", action="open_app")
    support_raw = os.environ.get("CROSSAUDIT_APP_SUPPORT", "").strip()
    if not support_raw:
        raise ConfigDenial("The application support folder is unavailable")
    root = workspace_mod.select_workspace(Path(support_raw), selected)
    _RUNTIME_CACHE.clear()
    return {"workspace": str(root), "selected": True}


def check_repositories(payload: dict, *, enforce: bool = False) -> dict:
    status = github_status(force=True)
    if not status["connected"]:
        raise ConfigDenial(
            status["detail"], issue="github_auth", action="connect_github")
    owner = str(status["owner"])
    fallback = _clean_text(payload, "name", 80)
    science = _repo(str(payload.get("science_repo", "")), owner, fallback)
    audit = _repo(str(payload.get("audit_repo", "")), owner,
                  f"{science.split('/', 1)[1]}-audit")
    if science == audit:
        raise ConfigDenial(
            "Work and audit repositories must use different names",
            issue="repo_names", action="edit_repositories")
    rows = [{"repo": repo, "exists": pair_mod._exists(repo)}
            for repo in (science, audit)]
    existing = [row["repo"] for row in rows if row["exists"]]
    adopt = payload.get("adopt_existing") is True
    if enforce and existing and not adopt:
        raise ConfigDenial(
            "Already exists: " + ", ".join(existing) + ". Edit the names, or "
            "explicitly allow CrossAudit to use repositories you can access.",
            issue="repo_exists", action="edit_repositories",
            repositories=existing)
    return {"owner": owner, "science": science, "audit": audit,
            "repositories": rows, "ready": not existing or adopt,
            "adopt_existing": adopt}


def create_project(base: Path, payload: dict, progress) -> dict:
    name = _clean_text(payload, "name", 80)
    if not NAME.fullmatch(name) or name in {".", ".."}:
        raise ConfigDenial("project name may use letters, numbers, dots, dashes and underscores")
    description = _clean_text(payload, "description", 4000)
    project_type = str(payload.get("project_type", "general")).strip().lower()
    if project_type not in {"general", "science"}:
        raise ConfigDenial("project type must be general or science")
    checks = GENERAL_CHECKS if project_type == "general" else SCIENCE_CHECKS
    scope_dir = "work" if project_type == "general" else "experiments"
    tree = GENERAL_TREE if project_type == "general" else SCIENCE_TREE
    auditor_vendor = _clean_text(payload, "auditor_vendor", 30)
    generator_vendor = _clean_text(payload, "generator_vendor", 30)
    auditor_connection = str(payload.get("auditor_connection", "api")).strip()
    generator_connection = str(payload.get("generator_connection", "api")).strip()
    auditor_model = _clean_text(payload, "auditor_model", 120)
    generator_model = (_clean_text(payload, "generator_model", 120,
                                   required=generator_vendor != "human")
                       if generator_vendor != "human" else "")
    auditor_endpoint_id = str(payload.get("auditor_endpoint", "")).strip()
    generator_endpoint_id = str(payload.get("generator_endpoint", "")).strip()
    if auditor_vendor not in wizard.VENDORS or auditor_vendor == "other":
        raise ConfigDenial("choose a supported auditor vendor")
    if generator_vendor not in (*wizard.VENDORS, "human") or generator_vendor == "other":
        raise ConfigDenial("choose a supported generator vendor")
    if generator_vendor == auditor_vendor:
        raise ConfigDenial("auditor and generator must use different vendors")
    if not MODEL.fullmatch(auditor_model) or (generator_model and
                                             not MODEL.fullmatch(generator_model)):
        raise ConfigDenial("model ids contain unsupported characters")
    try:
        _aeid, _aelabel, auditor_base_url, _amodels_url = provider_endpoint(
            auditor_vendor, auditor_endpoint_id)
        # Single-origin adapters already own their exact base. Persist a URL
        # only where the user made a regional choice; this also avoids feeding
        # an SDK-style /v1 base into adapters whose optional override expects an
        # origin (notably Anthropic).
        if len(provider_endpoints(auditor_vendor)) == 1:
            auditor_base_url = ""
        if generator_vendor != "human":
            _geid, _gelabel, generator_base_url, _gmodels_url = provider_endpoint(
                generator_vendor, generator_endpoint_id)
            if len(provider_endpoints(generator_vendor)) == 1:
                generator_base_url = ""
        else:
            generator_base_url = ""
    except ValueError as exc:
        raise ConfigDenial(str(exc)) from exc
    auditor_key_env = env_for_vendor(auditor_vendor)
    generator_key_env = env_for_vendor(generator_vendor)
    auditor_provider = connections.provider_for(auditor_vendor, auditor_connection)
    generator_provider = (connections.provider_for(generator_vendor,
                                                     generator_connection)
                          if generator_vendor != "human" else "")
    if os.environ.get("CROSSAUDIT_APP_MODE") == "1":
        if not connections.ready(auditor_vendor, auditor_connection):
            raise ConfigDenial(
                f"Connect {auditor_vendor.title()} "
                f"{'API key' if auditor_connection == 'api' else 'subscription'} in "
                "Settings before creating this project")
        if (generator_vendor != "human" and
                not connections.ready(generator_vendor, generator_connection)):
            raise ConfigDenial(
                f"Connect {generator_vendor.title()} "
                f"{'API key' if generator_connection == 'api' else 'subscription'} in "
                "Settings before creating this project")

    requested_workspace = str(payload.get("workspace", "")).strip()
    if requested_workspace and Path(requested_workspace).expanduser().resolve() != base.resolve():
        raise ConfigDenial(
            "The workspace changed in another window. Review the selected folder "
            "and create the project again.",
            issue="workspace_changed", action="choose_workspace")
    target = (base / name).resolve()
    if target.parent != base.resolve():
        raise ConfigDenial("projects can only be created inside this workspace")
    if (target / CONFIG_NAME).exists():
        raise ConfigDenial(f"{name} is already a CrossAudit project")

    github = payload.get("github") is True
    owner = ""
    science = name
    audit = ""
    if github:
        checked = check_repositories(payload, enforce=True)
        owner = checked["owner"]
        science, audit = checked["science"], checked["audit"]

    progress("local", f"Creating {target}")
    gitignore_existed = (target / ".gitignore").exists()
    wizard.prepare(target)
    setup = {"version": 1, "name": name, "project_type": project_type,
             "status": "running",
             "detail": "Creating the local project", "started": time.time(),
             "steps": [], "github": github, "science": science,
             "audit": audit, "private": payload.get("public") is not True,
             "adopt_existing": payload.get("adopt_existing") is True}
    _write_setup(target, setup)

    def record(stage: str, detail: str) -> None:
        setup["detail"] = detail
        setup["steps"].append({"stage": stage, "detail": detail,
                               "at": time.time()})
        _write_setup(target, setup)
        progress(stage, detail)

    const_name = "AUDIT_RULES.md"
    const_path = target / const_name
    _default_provider, default_model, _url = wizard.VENDORS[auditor_vendor]
    drafted = False
    can_draft = (connections.ready(auditor_vendor, auditor_connection)
                 if os.environ.get("CROSSAUDIT_APP_MODE") == "1" else
                 bool(os.environ.get(auditor_key_env, "").strip()) or
                 auditor_provider == "openai_codex")
    if can_draft:
        record("constitution", "Drafting the Constitution with the auditor")
        try:
            draft = wizard._distil(
                description, auditor_provider, auditor_model or default_model,
                auditor_base_url,
                key_env=auditor_key_env, usage_root=target,
                vendor=auditor_vendor)
            const_path.write_text(draft.render(name), encoding="utf-8", newline="\n")
            drafted = True
        except Denial as exc:
            record("constitution", f"Draft unavailable; using the starter rules ({exc.reason})")
    if not drafted:
        starter = ("GENERAL_AUDIT_RULES.md" if project_type == "general"
                   else const_name)
        const_path.write_text(read(starter), encoding="utf-8", newline="\n")

    try:
        max_rounds = int(payload.get("max_rounds", 3))
    except (TypeError, ValueError) as exc:
        raise ConfigDenial("maximum audit rounds must be a number") from exc
    if not 1 <= max_rounds <= 10:
        raise ConfigDenial("maximum audit rounds must be between 1 and 10")
    config_body = CONFIG_TEMPLATE.format(
        science_repo=science,
        audit_repo_line=f"audit_repo: {audit}" if audit else "# audit_repo: (local ledger)",
        constitution=const_name, max_rounds=max_rounds,
        auditor_vendor=auditor_vendor, auditor_provider=auditor_provider,
        auditor_model=auditor_model,
        base_url_line=(f"  base_url: {auditor_base_url}\n"
                       if auditor_base_url else ""),
        generator_vendor=generator_vendor,
        generator_details=(f"  provider: {generator_provider}\n  model: {generator_model}\n"
                           f"  key_env: {generator_key_env}"
                           + (f"\n  base_url: {generator_base_url}"
                              if generator_base_url else "")
                           if generator_vendor != "human" else
                           "  # Human-written changes are committed first."),
        permissive_minimum="true" if github else "false", state_dir=".crossaudit",
        scope_dirs=scope_dir, checks=", ".join(checks))
    config_body = config_body.replace(
        "key_env: CROSSAUDIT_AUDITOR_KEY", f"key_env: {auditor_key_env}", 1)
    (target / CONFIG_NAME).write_text(config_body, encoding="utf-8", newline="\n")
    (target / "DETERMINISTIC_CHECKS.md").write_text(
        "# Deterministic checks\n\nGenerated from `checks:` in `crossaudit.yml`.\n\n"
        "```text\n" + describe_checks(checks) + "\n```\n",
        encoding="utf-8", newline="\n")
    owned = [CONFIG_NAME, const_name, "DETERMINISTIC_CHECKS.md"]
    if not gitignore_existed:
        owned.append(".gitignore")
    owned.extend(write_tree(target, tree))
    commit = wizard.commit_setup(target, owned)
    record("local", f"Committed local project {commit[:12]}")

    cfg = load(target / CONFIG_NAME)
    pairing = None
    if github:
        record("github", "Creating and connecting the two GitHub repositories")
        pairing = pair_mod.apply_pair(
            cfg, science, audit, private=payload.get("public") is not True,
            progress=record,
            allow_existing=payload.get("adopt_existing") is True)
    setup.update(status="complete", detail="Project ready", finished=time.time())
    _write_setup(target, setup)
    return {"name": name, "project_type": project_type, "root": str(target),
            "config": str(target / CONFIG_NAME),
            "setup_commit": commit, "drafted_rules": drafted, "pairing": pairing}


def resume_project(base: Path, target: Path, progress,
                   payload: dict | None = None) -> dict:
    target = target.resolve()
    if target.parent != base.resolve():
        raise ConfigDenial("that project is outside this workspace")
    setup = _read_setup(target)
    if not setup or setup.get("status") != "failed" or not setup.get("github"):
        raise ConfigDenial("this project has no recoverable GitHub setup")
    cfg = load(target / CONFIG_NAME)
    payload = payload or {}
    checked = check_repositories({
        "name": target.name,
        "science_repo": payload.get("science_repo") or setup.get("science")
                        or cfg.science_repo,
        "audit_repo": payload.get("audit_repo") or setup.get("audit")
                      or cfg.audit_repo or "",
        "adopt_existing": True,
    })
    science, audit = checked["science"], checked["audit"]
    if not audit:
        raise ConfigDenial("the failed setup did not record an audit repository")
    setup.update(status="running", detail="Resuming GitHub setup",
                 science=science, audit=audit, issue=None)
    _write_setup(target, setup)

    def record(stage: str, detail: str) -> None:
        setup["detail"] = detail
        setup.setdefault("steps", []).append({"stage": stage, "detail": detail,
                                               "at": time.time()})
        _write_setup(target, setup)
        progress(stage, detail)

    pairing = pair_mod.apply_pair(
        cfg, science, audit, private=setup.get("private") is not False,
        progress=record, allow_existing=True)
    setup.update(status="complete", detail="Project ready", finished=time.time())
    _write_setup(target, setup)
    return {"name": target.name, "root": str(target), "config": str(cfg.path),
            "resumed": True, "pairing": pairing}


def open_project(current: Config, root: str) -> dict:
    path = Path(root).resolve()
    if not _trusted_project(current, path) or not (path / CONFIG_NAME).is_file():
        raise ConfigDenial("that project is outside your selected workspaces")
    cfg = load(path / CONFIG_NAME)
    info = daemon.live(cfg) or daemon.spawn(cfg, 0)
    return {"url": daemon.url_for(info), "project": cfg.science_repo}


def _deletion_target(current: Config, root: str) -> tuple[Path, Config]:
    path = Path(root).resolve()
    if not _trusted_project(current, path) or not (path / CONFIG_NAME).is_file():
        raise ConfigDenial("that project is outside your selected workspaces")
    if path == current.root:
        raise ConfigDenial(
            "return to the main Projects window before deleting the project that is open")
    if path.name == ".crossaudit-home":
        raise ConfigDenial("the CrossAudit application controller cannot be deleted")
    return path, load(path / CONFIG_NAME)


def _remote_repositories(cfg: Config) -> list[str]:
    # A lone science_repo is also the human-readable project identity in local
    # projects. Only a configured audit_repo proves that the two-repository
    # pairing flow supplied GitHub repository names.
    if not cfg.audit_repo:
        return []
    return list(dict.fromkeys(
        value for value in (cfg.science_repo, cfg.audit_repo or "")
        if GITHUB_REPO.fullmatch(value)))


def _project_activity(cfg: Config) -> list[str]:
    reasons = []
    if JOBS.running_for(cfg.root):
        reasons.append("project setup is still running")
    info = daemon.live(cfg)
    state = daemon.fetch_state(info) if info else None
    progress = state.get("progress") if isinstance(state, dict) else None
    if isinstance(progress, dict) and not progress.get("finished"):
        reasons.append("a Generator/Auditor task is running")
    compute = state.get("compute") if isinstance(state, dict) else None
    if isinstance(compute, dict) and int(compute.get("active", 0) or 0):
        reasons.append(f"{int(compute['active'])} remote compute job(s) are active")
    return reasons


def project_deletion_preview(current: Config, root: str) -> dict:
    """Describe exactly what deletion would affect, without mutating anything."""
    path, cfg = _deletion_target(current, root)
    activity = _project_activity(cfg)
    dirty_lines = [line for line in git("status", "--porcelain", cwd=path,
                                        check=False).splitlines() if line.strip()]
    ahead = 0
    upstream = subprocess.run(
        ["git", "rev-list", "--count", "@{upstream}..HEAD"], cwd=str(path),
        capture_output=True, text=True, check=False)
    if upstream.returncode == 0 and upstream.stdout.strip().isdigit():
        ahead = int(upstream.stdout.strip())
    trash = path.parent / ".crossaudit-trash"
    return {
        "root": str(path), "name": path.name,
        "trash": str(trash), "recoverable": True,
        "activity": activity, "can_delete": not activity,
        "dirty_count": len(dirty_lines),
        "dirty_sample": [line[3:][:120] for line in dirty_lines[:6]],
        "unpushed_commits": ahead,
        "repositories": _remote_repositories(cfg),
    }


def delete_project(current: Config, root: str, payload: dict) -> dict:
    """Atomically move one trusted project into a hidden, recoverable archive.

    GitHub repositories are deliberately a separate, opt-in irreversible act.
    The local folder is archived first so a partial remote failure never loses
    the only recoverable copy of the project metadata.
    """
    path, cfg = _deletion_target(current, root)
    if str(payload.get("confirmation", "")) != path.name:
        raise ConfigDenial(f"type {path.name!r} exactly to confirm project deletion")
    activity = _project_activity(cfg)
    if activity:
        raise ConfigDenial("project cannot be deleted while " + "; ".join(activity))
    delete_github = payload.get("delete_github") is True
    repositories = _remote_repositories(cfg)
    existing_repositories = {repo: True for repo in repositories}
    if delete_github:
        if str(payload.get("github_confirmation", "")) != "DELETE GITHUB":
            raise ConfigDenial("type DELETE GITHUB to confirm permanent repository deletion")
        if not repositories:
            raise ConfigDenial("this project has no configured GitHub repositories")
        # Complete every read-only remote preflight before touching local data.
        pair_mod.gh()
        existing_repositories = {repo: pair_mod._exists(repo) for repo in repositories}

    info = daemon.live(cfg)
    if info:
        stopped = daemon.stop(cfg)
        if "did not stop" in stopped:
            raise ConfigDenial(stopped)

    trash = path.parent / ".crossaudit-trash"
    trash.mkdir(mode=0o700, exist_ok=True)
    try:
        trash.chmod(0o700)
    except OSError:
        pass
    destination = trash / (
        f"{time.strftime('%Y%m%d-%H%M%S')}-{path.name}-{uuid.uuid4().hex[:8]}")
    path.replace(destination)
    _invalidate_runtime(path)

    remote_results = []
    if delete_github:
        for repo in repositories:
            if not existing_repositories[repo]:
                remote_results.append({"repo": repo, "status": "already_absent"})
                continue
            try:
                pair_mod._gh("repo", "delete", repo, "--yes")
                remote_results.append({"repo": repo, "status": "deleted"})
            except Denial as exc:
                remote_results.append({"repo": repo, "status": "failed",
                                       "detail": exc.reason[:300]})
    return {
        "deleted": True, "name": path.name, "root": str(path),
        "archive": str(destination), "recoverable": True,
        "github": remote_results,
        "github_complete": (not delete_github or
                            all(row["status"] in {"deleted", "already_absent"}
                                for row in remote_results)),
    }


def set_project_pin(current: Config, root: str, pinned: bool) -> dict:
    path = Path(root).resolve()
    if not _trusted_project(current, path) or not (path / CONFIG_NAME).is_file():
        raise ConfigDenial("that project is outside your selected workspaces")
    cfg = load(path / CONFIG_NAME)
    return {"root": str(path), "pinned": chats.set_project_pin(cfg, pinned)}
