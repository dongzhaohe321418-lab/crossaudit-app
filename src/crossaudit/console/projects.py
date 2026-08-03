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

from ..config import CONFIG_NAME, Config, load
from ..app_keys import env_for_vendor
from .. import connections
from ..providers import codex_subscription
from ..controller import StateStore
from ..errors import ConfigDenial, Denial
from ..providers.catalog import list_models
from ..scaffold import (CONFIG_TEMPLATE, GENERAL_CHECKS, GENERAL_TREE,
                        SCIENCE_CHECKS, SCIENCE_TREE, read, write_tree)
from ..dcl import describe as describe_checks
from ..cli import pair as pair_mod
from ..cli import wizard
from . import daemon

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}")
SETUP_FILE = "project-setup.json"


def workspace_base(current: Config) -> Path:
    """Trusted workspace root selected by the app, or the CLI-era sibling root."""
    override = os.environ.get("CROSSAUDIT_WORKSPACE_ROOT", "").strip()
    return (Path(override).expanduser().resolve() if override
            else current.root.parent.resolve())


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


def _fail_setup(root: Path, detail: str) -> None:
    value = _read_setup(root)
    if value:
        value.update(status="failed", detail=detail[:500], finished=time.time())
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
            failure_root=failure_root)

    def resume(self, current: Config, root: str, notify) -> dict:
        path = Path(root).resolve()
        base = workspace_base(current)
        return self._start(
            current, path.name[:80], notify,
            lambda step: resume_project(base, path, step),
            failure_root=(path if path.parent == base
                          else None))

    def _start(self, current: Config, project: str, notify, operation, *,
               failure_root: Path | None) -> dict:
        job_id = uuid.uuid4().hex[:12]
        row = {"id": job_id, "status": "running", "stage": "validate",
               "detail": "Validating project settings", "started": time.time(),
               "steps": [], "project": project}
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
                if failure_root is not None:
                    _fail_setup(failure_root, why)
                with self._lock:
                    row.update(status="failed", detail=why[:500], finished=time.time())
            except Exception as exc:  # noqa: BLE001 - background boundary
                if failure_root is not None:
                    _fail_setup(failure_root, str(exc))
                with self._lock:
                    row.update(status="failed",
                               detail=f"{type(exc).__name__}: {exc}"[:500],
                               finished=time.time())
            notify()

        threading.Thread(target=work, daemon=True).start()
        return {"job": job_id}

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [dict(v, steps=[dict(s) for s in v["steps"]])
                    for v in self._jobs.values()]


JOBS = ProjectJobs()
_GH_CACHE: tuple[float, dict] | None = None
_RUNTIME_CACHE: dict[str, tuple[float, tuple, dict | None]] = {}


def _runtime(cfg: Config, current: Config) -> dict | None:
    """The small live-progress projection used by the workspace menu."""
    if cfg.root == current.root:
        from .progress import TRACKER
        state = {"progress": TRACKER.snapshot()}
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
    if not isinstance(progress, dict) or progress.get("finished"):
        return None
    steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
    latest = steps[-1] if steps and isinstance(steps[-1], dict) else {}
    return {
        "task": str(progress.get("task", ""))[:160],
        "elapsed": max(0, int(progress.get("elapsed", 0) or 0)),
        "actor": str(latest.get("actor", "starting"))[:30],
        "step": str(latest.get("text", "starting"))[:120],
    }


def _invalidate_runtime(root: Path) -> None:
    _RUNTIME_CACHE.pop(str(root), None)


class RuntimeRelays:
    """Relay sibling daemon SSE into this project's event-driven menu stream."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: set[tuple[str, int, int]] = set()

    def ensure(self, current: Config, notify) -> None:
        try:
            candidates = tuple(workspace_base(current).iterdir())
        except OSError:
            return
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
            with urllib.request.urlopen(url, timeout=20) as response:
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
        value = {"connected": False, "owner": None, "detail": exc.reason}
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
                "Install the GitHub CLI from https://cli.github.com first")
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


def refresh_models(current: Config, vendor: str, role: str,
                   method: str = "api") -> dict:
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
        rows = list_models(vendor, key_env)
    if not rows:
        raise ConfigDenial(f"{vendor} returned no models visible to this key")
    return {"vendor": vendor, "role": role, "method": method, "models": rows,
            "refreshed": int(time.time())}


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
        return {
            "name": cfg.root.name, "label": cfg.science_repo, "root": str(cfg.root),
            "current": cfg.root == current.root, "paired": pair_ready,
            "status": ("running" if progress else
                       "setting_up" if setup_running else
                       "setup_failed" if recoverable else
                       "interrupted" if interrupted else
                       latest["status"].lower() if latest else "ready"),
            "cycles": len(cycles),
            "progress": progress,
            "interrupted": interrupted,
            "setup": ({"status": setup.get("status"),
                       "detail": str(setup.get("detail", ""))[:300],
                       "steps": setup.get("steps", [])[-8:],
                       "recoverable": recoverable} if setup else None),
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
    try:
        candidates = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError:
        candidates = [current.root]
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
    rows.sort(key=lambda p: (not p["current"], -p["updated"], p["name"].lower()))
    return {"workspace": str(base), "items": rows, "jobs": JOBS.snapshot(),
            "capacity": daemon.workspace_capacity(current),
            "github_auth": GITHUB_AUTH.snapshot(),
            "github": github_status(), "models": models(),
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
    if auditor_vendor not in wizard.VENDORS or auditor_vendor == "other":
        raise ConfigDenial("choose a supported auditor vendor")
    if generator_vendor not in (*wizard.VENDORS, "human") or generator_vendor == "other":
        raise ConfigDenial("choose a supported generator vendor")
    if generator_vendor == auditor_vendor:
        raise ConfigDenial("auditor and generator must use different vendors")
    if not MODEL.fullmatch(auditor_model) or (generator_model and
                                             not MODEL.fullmatch(generator_model)):
        raise ConfigDenial("model ids contain unsupported characters")
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
        status = github_status()
        if not status["connected"]:
            raise ConfigDenial(status["detail"])
        owner = status["owner"]
        science = _repo(str(payload.get("science_repo", "")), owner, name)
        audit = _repo(str(payload.get("audit_repo", "")), owner,
                      f"{science.split('/', 1)[1]}-audit")
        if science == audit:
            raise ConfigDenial("science and audit repositories must be different")

    progress("local", f"Creating {target}")
    gitignore_existed = (target / ".gitignore").exists()
    wizard.prepare(target)
    setup = {"version": 1, "name": name, "project_type": project_type,
             "status": "running",
             "detail": "Creating the local project", "started": time.time(),
             "steps": [], "github": github, "science": science,
             "audit": audit, "private": payload.get("public") is not True}
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
                description, auditor_provider, auditor_model or default_model, "",
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
        auditor_model=auditor_model, base_url_line="",
        generator_vendor=generator_vendor,
        generator_details=(f"  provider: {generator_provider}\n  model: {generator_model}\n"
                           f"  key_env: {generator_key_env}"
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
            progress=record)
    setup.update(status="complete", detail="Project ready", finished=time.time())
    _write_setup(target, setup)
    return {"name": name, "project_type": project_type, "root": str(target),
            "config": str(target / CONFIG_NAME),
            "setup_commit": commit, "drafted_rules": drafted, "pairing": pairing}


def resume_project(base: Path, target: Path, progress) -> dict:
    target = target.resolve()
    if target.parent != base.resolve():
        raise ConfigDenial("that project is outside this workspace")
    setup = _read_setup(target)
    if not setup or setup.get("status") != "failed" or not setup.get("github"):
        raise ConfigDenial("this project has no recoverable GitHub setup")
    cfg = load(target / CONFIG_NAME)
    science = str(setup.get("science") or cfg.science_repo)
    audit = str(setup.get("audit") or cfg.audit_repo or "")
    if not audit:
        raise ConfigDenial("the failed setup did not record an audit repository")
    setup.update(status="running", detail="Resuming GitHub setup")
    _write_setup(target, setup)

    def record(stage: str, detail: str) -> None:
        setup["detail"] = detail
        setup.setdefault("steps", []).append({"stage": stage, "detail": detail,
                                               "at": time.time()})
        _write_setup(target, setup)
        progress(stage, detail)

    pairing = pair_mod.apply_pair(
        cfg, science, audit, private=setup.get("private") is not False,
        progress=record)
    setup.update(status="complete", detail="Project ready", finished=time.time())
    _write_setup(target, setup)
    return {"name": target.name, "root": str(target), "config": str(cfg.path),
            "resumed": True, "pairing": pairing}


def open_project(current: Config, root: str) -> dict:
    path = Path(root).resolve()
    if path.parent != workspace_base(current) or not (path / CONFIG_NAME).is_file():
        raise ConfigDenial("that project is outside this workspace")
    cfg = load(path / CONFIG_NAME)
    info = daemon.live(cfg) or daemon.spawn(cfg, 0)
    return {"url": daemon.url_for(info), "project": cfg.science_repo}
