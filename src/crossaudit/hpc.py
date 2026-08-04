"""Persistent SSH/HPC control plane for the desktop application.

The local process is deliberately only a controller.  Workstation jobs are
detached on the remote host and Slurm jobs belong to the scheduler, so closing
CrossAudit or losing the network cannot terminate compute.  The local state is
a private cache of identifiers that lets a later app process reattach.

OpenSSH remains the trust and authentication boundary.  CrossAudit never reads
private keys, stores passphrases, or implements a second SSH stack.  Every
connection is non-interactive and uses the user's existing ``~/.ssh/config``
(including ProxyJump, IdentityFile and ssh-agent settings).
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import secrets
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Callable

from .config import Config
from .errors import ConfigDenial

ALIAS = re.compile(r"(?!-)[A-Za-z0-9_.-]{1,128}")
RESOURCE = re.compile(r"[A-Za-z0-9_.:@/+,-]{1,128}")
JOB_NAME = re.compile(r"[A-Za-z0-9_. -]{1,80}")
MEMORY = re.compile(r"[1-9][0-9]{0,8}(?:[KMGTP]B?)?", re.I)
WALLTIME = re.compile(r"(?:(?:[0-9]{1,3})-)?[0-9]{1,2}:[0-5][0-9](?::[0-5][0-9])?")
REMOTE_ID = re.compile(r"[0-9]{1,32}")
JOB_ID = re.compile(r"[a-f0-9]{16}")
MAX_SCRIPT_BYTES = 256 * 1024
MAX_DETAILS = 4000
LOG_BYTES = 64 * 1024
MAX_AGENT_RESULT_BYTES = 256 * 1024
POLL_SECONDS = 2.0
TERMINAL_STATES = {"completed", "failed", "cancelled", "timeout", "out_of_memory"}
TEXT_OUTPUT_SUFFIXES = {".csv", ".json", ".jsonl", ".log", ".md", ".txt",
                        ".tsv", ".yaml", ".yml"}
_ALIAS_CACHE: dict[str, tuple[float, list[str]]] = {}

_SSH_OPTIONS = (
    "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
    "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
    "-o", "StrictHostKeyChecking=yes", "-o", "ClearAllForwardings=yes",
    "-o", "PermitLocalCommand=no", "-o", "RequestTTY=no",
)


def _state_root(cfg: Config) -> Path:
    root = cfg.root / cfg.state_dir / "hpc"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def _read(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default
    return value if isinstance(value, type(default)) else default


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


def _remote_path(value: str, label: str = "remote path") -> str:
    raw = str(value).strip()
    if (raw == "/" or not raw.startswith("/") or "\x00" in raw or "\n" in raw or
            "\r" in raw or any(part in {"", ".", ".."}
                                for part in PurePosixPath(raw).parts[1:])):
        raise ConfigDenial(f"{label} must be an absolute normalized POSIX path")
    return posixpath.normpath(raw)


def _relative_output(value: str) -> str:
    raw = str(value).strip()
    path = PurePosixPath(raw)
    if (not raw or path.is_absolute() or "\x00" in raw or "\n" in raw or
            "\r" in raw or any(part in {"", ".", ".."} for part in path.parts)):
        raise ConfigDenial("output path is not a safe relative path")
    return str(path)


def _bounded_int(value, label: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigDenial(f"{label} must be a whole number") from exc
    if not minimum <= number <= maximum:
        raise ConfigDenial(f"{label} must be between {minimum} and {maximum}")
    return number


def _walltime_seconds(value: str) -> int:
    raw = str(value).strip()
    if not WALLTIME.fullmatch(raw):
        raise ConfigDenial("wall time must look like HH:MM:SS or D-HH:MM:SS")
    days, separator, clock = raw.partition("-")
    if not separator:
        days, clock = "0", days
    parts = [int(part) for part in clock.split(":")]
    if len(parts) == 2:
        hours, minutes, seconds = 0, parts[0], parts[1]
    else:
        hours, minutes, seconds = parts
    return int(days) * 86400 + hours * 3600 + minutes * 60 + seconds


def _memory_bytes(value: str) -> int:
    raw = str(value).strip().upper()
    if not raw:
        return 0
    if not MEMORY.fullmatch(raw):
        raise ConfigDenial("memory must look like 16G, 8000M, or 1T")
    match = re.fullmatch(r"([1-9][0-9]{0,8})([KMGTP]?)(?:B)?", raw)
    assert match is not None
    powers = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3,
              "T": 1024 ** 4, "P": 1024 ** 5}
    return int(match.group(1)) * powers[match.group(2)]


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SSHFailure(ConfigDenial):
    """A user-actionable OpenSSH failure with a stable UI code."""

    def __init__(self, reason: str, *, code: str = "ssh_failed") -> None:
        super().__init__(reason)
        self.code = code

    def as_dict(self) -> dict:
        value = super().as_dict()
        value["code"] = self.code
        return value


def _ssh_error(detail: str) -> SSHFailure:
    low = detail.lower()
    if "host key verification failed" in low or "no host key is known" in low:
        return SSHFailure(
            "This host is not trusted yet. Verify the hostname, then choose "
            "Trust first key & connect. CrossAudit will use OpenSSH trust-on-first-use.",
            code="host_key_unknown")
    if "remote host identification has changed" in low:
        return SSHFailure(
            "The saved SSH host key changed. CrossAudit will not replace it. "
            "Contact the cluster administrator and repair known_hosts outside the app.",
            code="host_key_changed")
    if "permission denied" in low:
        return SSHFailure(
            "SSH authentication was refused. Add the correct key to ssh-agent or "
            "fix IdentityFile/User in ~/.ssh/config.", code="authentication_failed")
    if "could not resolve hostname" in low:
        return SSHFailure(
            "The SSH hostname could not be resolved. Check the alias and any "
            "ProxyJump entry in ~/.ssh/config.", code="host_unreachable")
    if "connection timed out" in low or "operation timed out" in low:
        return SSHFailure("The SSH connection timed out. Connect the required VPN and retry.",
                          code="host_unreachable")
    if "connection refused" in low or "no route to host" in low:
        return SSHFailure("The SSH host is unreachable from this Mac.",
                          code="host_unreachable")
    return SSHFailure(detail[:800] or "OpenSSH could not connect to the host")


class OpenSSH:
    """Small argument-vector-only wrapper; it never invokes a local shell."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or shutil.which("ssh") or ""

    def available(self) -> bool:
        return bool(self.path)

    def expanded(self, alias: str) -> dict[str, str]:
        self._alias(alias)
        if not self.path:
            raise SSHFailure("OpenSSH was not found on this computer", code="ssh_missing")
        try:
            result = subprocess.run(
                [self.path, "-G", alias], capture_output=True, text=True,
                timeout=5, env={**os.environ, "LC_ALL": "C"})
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SSHFailure(str(exc), code="ssh_missing") from exc
        if result.returncode:
            raise _ssh_error(result.stderr.strip())
        parsed: dict[str, str] = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition(" ")
            if separator and key in {"hostname", "user", "port", "proxyjump"}:
                parsed[key] = value.strip()
        if not parsed.get("hostname"):
            raise SSHFailure("OpenSSH could not resolve that host alias")
        return parsed

    @staticmethod
    def _alias(alias: str) -> str:
        value = str(alias).strip()
        if not ALIAS.fullmatch(value):
            raise ConfigDenial(
                "SSH alias must start with a letter, number, dot or underscore; "
                "the remaining characters may also include dashes")
        return value

    def run(self, alias: str, command: str, *, input_text: str | None = None,
            timeout: float = 20.0, trust_first_key: bool = False) -> str:
        alias = self._alias(alias)
        if not self.path:
            raise SSHFailure("OpenSSH was not found on this computer", code="ssh_missing")
        options = list(_SSH_OPTIONS)
        if trust_first_key:
            index = options.index("StrictHostKeyChecking=yes")
            options[index] = "StrictHostKeyChecking=accept-new"
        try:
            result = subprocess.run(
                [self.path, *options, alias, command], input=input_text,
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "LC_ALL": "C"})
        except subprocess.TimeoutExpired as exc:
            raise SSHFailure("The remote operation timed out", code="host_unreachable") from exc
        except OSError as exc:
            raise SSHFailure(str(exc), code="ssh_missing") from exc
        if result.returncode:
            raise _ssh_error((result.stderr or result.stdout).strip())
        return result.stdout[:2 * 1024 * 1024]

    def stream(self, alias: str, command: str) -> subprocess.Popen:
        alias = self._alias(alias)
        if not self.path:
            raise SSHFailure("OpenSSH was not found on this computer", code="ssh_missing")
        try:
            return subprocess.Popen(
                [self.path, *_SSH_OPTIONS, alias, command], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env={**os.environ, "LC_ALL": "C"})
        except OSError as exc:
            raise SSHFailure(str(exc), code="ssh_missing") from exc

    def send_file(self, alias: str, source: Path, destination: str,
                  *, timeout: float = 3600.0) -> None:
        """Stream a local file over SSH with constant memory and no app quota."""
        alias = self._alias(alias)
        destination = _remote_path(destination, "remote input path")
        if not source.is_file() or source.is_symlink():
            raise ConfigDenial("HPC input must be a regular local file")
        parent = posixpath.dirname(destination)
        command = (f"umask 077; mkdir -p -- {shlex.quote(parent)} && "
                   f"cat > {shlex.quote(destination)}")
        if not self.path:
            raise SSHFailure("OpenSSH was not found on this computer", code="ssh_missing")
        try:
            with open(source, "rb") as handle:
                result = subprocess.run(
                    [self.path, *_SSH_OPTIONS, alias, command], stdin=handle,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=timeout, env={**os.environ, "LC_ALL": "C"})
            error = result.stderr[:LOG_BYTES].decode("utf-8", "replace")
        except subprocess.TimeoutExpired as exc:
            raise SSHFailure("The remote input transfer timed out",
                             code="host_unreachable") from exc
        except OSError as exc:
            raise _ssh_error(str(exc)) from exc
        if result.returncode:
            raise _ssh_error(error)


def ssh_aliases(config: Path | None = None) -> list[str]:
    """Return explicit, non-wildcard aliases from the user's SSH config.

    Includes are followed only within the user's filesystem.  This is a picker
    convenience, never an authority check; OpenSSH still performs expansion.
    """
    root = (config or Path.home() / ".ssh" / "config").expanduser()
    cache_key = str(root)
    cached = _ALIAS_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < 5:
        return list(cached[1])
    seen: set[Path] = set()
    aliases: set[str] = set()

    def read(path: Path) -> None:
        try:
            resolved = path.resolve()
            if resolved in seen or not resolved.is_file():
                return
            seen.add(resolved)
            lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        for line in lines:
            words = shlex.split(line, comments=True)
            if not words:
                continue
            if words[0].lower() == "host":
                for value in words[1:]:
                    if ALIAS.fullmatch(value) and not any(c in value for c in "*?!"):
                        aliases.add(value)
            elif words[0].lower() == "include":
                for pattern in words[1:]:
                    candidate = Path(pattern).expanduser()
                    if not candidate.is_absolute():
                        candidate = resolved.parent / candidate
                    for included in candidate.parent.glob(candidate.name):
                        read(included)

    read(root)
    result = sorted(aliases, key=str.casefold)
    _ALIAS_CACHE[cache_key] = (time.monotonic(), result)
    return list(result)


def _probe_script() -> str:
    return r'''set -eu
printf 'kernel\t'; uname -srm 2>/dev/null || true
printf 'cpus\t'; (getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo unknown)
printf 'memory_kb\t'; (awk '/MemTotal/{print $2;exit}' /proc/meminfo 2>/dev/null || echo unknown)
printf 'gpus\t'; (nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | paste -sd ',' - || true)
for tool in sbatch squeue sacct scancel module conda apptainer setsid; do
  if command -v "$tool" >/dev/null 2>&1; then printf '%s\tyes\n' "$tool"; else printf '%s\tno\n' "$tool"; fi
done
if command -v sinfo >/dev/null 2>&1; then
  printf 'partitions\t'; sinfo -h -o '%P' 2>/dev/null | sed 's/[* ]//g' | sort -u | paste -sd ',' - || true
fi
'''


def _parse_probe(output: str) -> dict:
    values: dict[str, object] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("\t")
        if not separator:
            continue
        value = value.strip()
        if key in {"sbatch", "squeue", "sacct", "scancel", "module", "conda", "apptainer", "setsid"}:
            values[key] = value == "yes"
        elif key == "cpus" and value.isdigit():
            values[key] = int(value)
        elif key == "memory_kb" and value.isdigit():
            values[key] = int(value)
        elif key in {"gpus", "partitions"}:
            values[key] = [part for part in value.split(",") if part]
        else:
            values[key] = value
    values["scheduler"] = "slurm" if values.get("sbatch") else "workstation"
    return values


class Manager:
    def __init__(self, transport: OpenSSH | None = None) -> None:
        self.transport = transport or OpenSSH()
        self._lock = threading.RLock()
        self._watchers: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}

    def _paths(self, cfg: Config) -> tuple[Path, Path]:
        root = _state_root(cfg)
        return root / "hosts.json", root / "jobs.json"

    def _hosts(self, cfg: Config) -> list[dict]:
        return _read(self._paths(cfg)[0], [])

    def _jobs(self, cfg: Config) -> list[dict]:
        return _read(self._paths(cfg)[1], [])

    def _save_hosts(self, cfg: Config, rows: list[dict]) -> None:
        _write(self._paths(cfg)[0], rows)

    def _save_jobs(self, cfg: Config, rows: list[dict]) -> None:
        _write(self._paths(cfg)[1], rows)

    def _host(self, cfg: Config, host_id: str) -> dict:
        host = next((row for row in self._hosts(cfg) if row.get("id") == host_id), None)
        if not host:
            raise ConfigDenial("that compute host is not registered in this project")
        return host

    def _job(self, cfg: Config, job_id: str) -> dict:
        if not JOB_ID.fullmatch(str(job_id)):
            raise ConfigDenial("invalid compute job identifier")
        job = next((row for row in self._jobs(cfg) if row.get("id") == job_id), None)
        if not job:
            raise ConfigDenial("that compute job does not exist")
        return job

    def register(self, cfg: Config, payload: dict) -> dict:
        alias = self.transport._alias(str(payload.get("alias", "")))
        scratch = _remote_path(str(payload.get("scratch", "")), "scratch directory")
        details = str(payload.get("details", "")).strip()
        if len(details) > MAX_DETAILS:
            raise ConfigDenial(f"host details must be at most {MAX_DETAILS} characters")
        limit = _bounded_int(payload.get("concurrency", 100), "concurrent job limit", 1, 100)
        agent_enabled = payload.get("agent_enabled") is True
        agent_policy = {
            "enabled": agent_enabled,
            "max_jobs_per_task": _bounded_int(
                payload.get("agent_max_jobs", 2), "Generator jobs per task", 1, 10),
            "max_nodes": _bounded_int(
                payload.get("agent_max_nodes", 1), "Generator node limit", 1, 64),
            "max_cpus": _bounded_int(
                payload.get("agent_max_cpus", 8), "Generator CPU limit", 1, 4096),
            "max_gpus": _bounded_int(
                payload.get("agent_max_gpus", 0), "Generator GPU limit", 0, 64),
            "max_memory": str(payload.get("agent_max_memory", "16G")).strip().upper(),
            "max_walltime": str(payload.get(
                "agent_max_walltime", "01:00:00")).strip(),
        }
        _memory_bytes(agent_policy["max_memory"])
        _walltime_seconds(agent_policy["max_walltime"])
        for key in ("partition", "account", "qos"):
            value = str(payload.get(f"agent_{key}", "")).strip()
            if value and not RESOURCE.fullmatch(value):
                raise ConfigDenial(f"Generator {key} contains unsupported characters")
            agent_policy[key] = value
        expanded = self.transport.expanded(alias)
        trust = payload.get("trust_first_key") is True
        output = self.transport.run(alias, _probe_script(), timeout=25,
                                    trust_first_key=trust)
        probe = _parse_probe(output)
        now = time.time()
        with self._lock:
            rows = self._hosts(cfg)
            existing = next((row for row in rows if row.get("alias") == alias), None)
            row = existing or {"id": secrets.token_hex(8), "created": now}
            row.update({
                "alias": alias, "scratch": scratch, "details": details,
                "concurrency": limit, "hostname": expanded.get("hostname", alias),
                "user": expanded.get("user", ""), "port": expanded.get("port", "22"),
                "proxy_jump": bool(expanded.get("proxyjump") and
                                   expanded.get("proxyjump") != "none"),
                "probe": probe, "status": "ready", "checked": now,
                "agent_policy": agent_policy,
            })
            if existing is None:
                rows.append(row)
            self._save_hosts(cfg, rows)
        return self._public_host(row)

    def probe(self, cfg: Config, host_id: str) -> dict:
        with self._lock:
            host = self._host(cfg, host_id)
        probe = _parse_probe(self.transport.run(host["alias"], _probe_script(), timeout=25))
        with self._lock:
            rows = self._hosts(cfg)
            for row in rows:
                if row.get("id") == host_id:
                    row.update({"probe": probe, "status": "ready", "checked": time.time()})
                    host = row
                    break
            self._save_hosts(cfg, rows)
        return self._public_host(host)

    def remove(self, cfg: Config, host_id: str) -> dict:
        with self._lock:
            active = [row for row in self._jobs(cfg)
                      if row.get("host_id") == host_id and row.get("status") not in TERMINAL_STATES]
            if active:
                raise ConfigDenial("cancel or finish this host's active jobs before removing it")
            rows = self._hosts(cfg)
            kept = [row for row in rows if row.get("id") != host_id]
            if len(kept) == len(rows):
                raise ConfigDenial("that compute host is not registered")
            self._save_hosts(cfg, kept)
        return {"removed": host_id}

    @staticmethod
    def _public_host(row: dict) -> dict:
        return {key: row.get(key) for key in (
            "id", "alias", "scratch", "details", "concurrency", "hostname",
            "user", "port", "proxy_jump", "probe", "status", "checked",
            "agent_policy")}

    @staticmethod
    def _resources(payload: dict) -> dict:
        name = str(payload.get("name", "CrossAudit job")).strip() or "CrossAudit job"
        if not JOB_NAME.fullmatch(name):
            raise ConfigDenial("job name may use letters, numbers, spaces, dots, dashes and underscores")
        result = {
            "name": name,
            "nodes": _bounded_int(payload.get("nodes", 1), "nodes", 1, 1024),
            "cpus": _bounded_int(payload.get("cpus", 1), "CPUs per task", 1, 4096),
            "gpus": _bounded_int(payload.get("gpus", 0), "GPUs", 0, 1024),
        }
        for key in ("partition", "account", "qos"):
            value = str(payload.get(key, "")).strip()
            if value and not RESOURCE.fullmatch(value):
                raise ConfigDenial(f"{key} contains unsupported characters")
            result[key] = value
        memory = str(payload.get("memory", "")).strip().upper()
        if memory and not MEMORY.fullmatch(memory):
            raise ConfigDenial("memory must look like 16G, 8000M, or 1T")
        walltime = str(payload.get("walltime", "30:00")).strip()
        if not WALLTIME.fullmatch(walltime):
            raise ConfigDenial("wall time must look like HH:MM:SS or D-HH:MM:SS")
        result.update({"memory": memory, "walltime": walltime})
        return result

    @staticmethod
    def _script(resources: dict, body: str, scheduler: str, directory: str) -> str:
        lines = ["#!/usr/bin/env bash"]
        if scheduler == "slurm":
            directives = [
                ("job-name", resources["name"]), ("nodes", resources["nodes"]),
                ("cpus-per-task", resources["cpus"]), ("time", resources["walltime"]),
                ("output", f"{directory}/stdout.log"),
                ("error", f"{directory}/stderr.log"),
            ]
            if resources["gpus"]:
                directives.append(("gpus", resources["gpus"]))
            for key in ("memory", "partition", "account", "qos"):
                if resources[key]:
                    directives.append(({"memory": "mem"}.get(key, key), resources[key]))
            lines.extend(f"#SBATCH --{key}={value}" for key, value in directives)
        lines.extend(["set -o pipefail", f"cd -- {shlex.quote(directory)}", body.rstrip(), ""])
        return "\n".join(lines)

    def submit(self, cfg: Config, payload: dict, *, attachments=(),
               origin: str = "user", chat_id: str = "",
               requested_outputs=()) -> dict:
        host = self._host(cfg, str(payload.get("host_id", "")))
        script_body = str(payload.get("script", ""))
        if not script_body.strip():
            raise ConfigDenial("job script is required")
        if "\x00" in script_body or len(script_body.encode("utf-8")) > MAX_SCRIPT_BYTES:
            raise ConfigDenial(f"job script must be at most {MAX_SCRIPT_BYTES} UTF-8 bytes")
        resources = self._resources(payload)
        scheduler = str((host.get("probe") or {}).get("scheduler", "workstation"))
        if scheduler == "slurm" and not (host.get("probe") or {}).get("sbatch"):
            raise ConfigDenial("the latest host probe did not find Slurm sbatch")
        with self._lock:
            active = [row for row in self._jobs(cfg)
                      if row.get("host_id") == host["id"] and row.get("status") not in TERMINAL_STATES]
            if len(active) >= int(host.get("concurrency", 100)):
                raise ConfigDenial("this host has reached its configured concurrent job limit")
        job_id = secrets.token_hex(8)
        directory = posixpath.join(host["scratch"], "crossaudit-jobs", job_id)
        script = self._script(resources, script_body, scheduler, directory)
        now = time.time()
        row = {
            "id": job_id, "host_id": host["id"], "host": host["alias"],
            "scheduler": scheduler, "remote_id": "", "directory": directory,
            "name": resources["name"], "resources": resources, "inputs": [],
            "status": "submitting", "detail": "Preparing remote job",
            "submitted": now, "updated": now, "elapsed": "0:00", "exit_code": "",
            "origin": origin, "chat_id": chat_id,
            "requested_outputs": list(requested_outputs),
        }
        local = _state_root(cfg) / "jobs" / job_id
        local.mkdir(parents=True, exist_ok=False)
        try:
            local.chmod(0o700)
            script_path = local / "job.sh"
            with open(script_path, "x", encoding="utf-8") as handle:
                handle.write(script)
                handle.flush()
                os.fsync(handle.fileno())
            script_path.chmod(0o600)
            with self._lock:
                rows = self._jobs(cfg)
                rows.append(row)
                self._save_jobs(cfg, rows)
        except Exception:
            shutil.rmtree(local, ignore_errors=True)
            raise
        upload = (f"umask 077; mkdir -p -- {shlex.quote(directory)} && "
                  f"cat > {shlex.quote(directory + '/job.sh')} && "
                  f"chmod 700 -- {shlex.quote(directory + '/job.sh')}")
        inputs = []
        try:
            self.transport.run(host["alias"], upload, input_text=script, timeout=30)
            for attachment in attachments:
                name = str(attachment.name)
                destination = posixpath.join(directory, "inputs", name)
                self.transport.send_file(host["alias"], attachment.source, destination)
                inputs.append({"name": name, "bytes": attachment.source.stat().st_size,
                               "sha256": str(attachment.digest)})
            if scheduler == "slurm":
                command = (f"cd -- {shlex.quote(directory)} && "
                           "sbatch --parsable job.sh")
                output = self.transport.run(host["alias"], command, timeout=20).strip()
                remote_id = output.split(";", 1)[0].strip()
            else:
                if not (host.get("probe") or {}).get("setsid"):
                    raise ConfigDenial(
                        "this workstation does not provide setsid, so CrossAudit cannot "
                        "guarantee that a detached process and its children can be managed safely")
                wrapper = (f"cd -- {shlex.quote(directory)} && "
                           "nohup setsid sh -c 'bash job.sh >stdout.log 2>stderr.log; "
                           "code=$?; printf \"%s\\n\" \"$code\" >.exit_code' "
                           "</dev/null >/dev/null 2>&1 & echo $!")
                remote_id = self.transport.run(host["alias"], wrapper, timeout=20).strip()
        except Exception as exc:
            try:
                self.transport.run(host["alias"],
                                   f"rm -rf -- {shlex.quote(directory)}", timeout=15)
            except Exception:
                pass
            with self._lock:
                rows = self._jobs(cfg)
                for stored in rows:
                    if stored.get("id") == job_id:
                        stored.update({"status": "failed", "detail": str(exc)[:500],
                                       "updated": time.time()})
                        break
                self._save_jobs(cfg, rows)
            raise
        if not REMOTE_ID.fullmatch(remote_id):
            error = SSHFailure("the remote scheduler returned an invalid job identifier")
            with self._lock:
                rows = self._jobs(cfg)
                for stored in rows:
                    if stored.get("id") == job_id:
                        stored.update({"status": "failed", "detail": error.reason,
                                       "updated": time.time()})
                        break
                self._save_jobs(cfg, rows)
            raise error
        with self._lock:
            rows = self._jobs(cfg)
            for stored in rows:
                if stored.get("id") == job_id:
                    stored.update({
                        "remote_id": remote_id, "inputs": inputs,
                        "status": "queued" if scheduler == "slurm" else "running",
                        "detail": ("Submitted to Slurm" if scheduler == "slurm" else
                                   "Detached on host"), "updated": time.time(),
                    })
                    row = stored
                    break
            self._save_jobs(cfg, rows)
        return self._public_job(row)

    def agent_context(self, cfg: Config) -> list[dict]:
        """Capabilities the Generator may see; disabled hosts stay invisible."""
        rows = []
        for host in self._hosts(cfg):
            policy = dict(host.get("agent_policy") or {})
            if not policy.get("enabled"):
                continue
            probe = host.get("probe") or {}
            rows.append({
                "host_id": host["id"], "label": host["alias"],
                "scheduler": probe.get("scheduler", "workstation"),
                "available_cpus": probe.get("cpus"),
                "available_gpus": probe.get("gpus", []),
                "partitions": probe.get("partitions", []),
                "instructions": host.get("details", ""),
                "policy": policy,
            })
        return rows

    def _agent_inputs(self, cfg: Config, values) -> list[SimpleNamespace]:
        if not isinstance(values, list):
            raise ConfigDenial("Generator compute inputs must be a list of project paths")
        allowed = set(cfg.scope_dirs or [])
        allowed_roots = [(cfg.root / value).resolve() for value in allowed]
        names: set[str] = set()
        rows = []
        root = cfg.root.resolve()
        for value in values:
            relative = _relative_output(str(value))
            path = PurePosixPath(relative)
            if not path.parts or path.parts[0] not in allowed:
                raise ConfigDenial(
                    f"Generator compute input {relative!r} is outside project work scope")
            requested = cfg.root / Path(*path.parts)
            source = requested.resolve()
            try:
                source.relative_to(root)
            except ValueError as exc:
                raise ConfigDenial("Generator compute input escapes the project") from exc
            if not any(source == work_root or source.is_relative_to(work_root)
                       for work_root in allowed_roots):
                raise ConfigDenial(
                    f"Generator compute input {relative!r} resolves outside project work scope")
            if not source.is_file() or requested.is_symlink():
                raise ConfigDenial(
                    f"Generator compute input {relative!r} is not a regular file")
            name = path.name
            if name.casefold() in names:
                raise ConfigDenial(
                    "Generator compute inputs must have unique file names")
            names.add(name.casefold())
            rows.append(SimpleNamespace(name=name, source=source,
                                        digest=_digest_file(source)))
        return rows

    def submit_agent(self, cfg: Config, request: dict, *, chat_id: str = "",
                     ordinal: int = 1) -> dict:
        """Submit one model-authored job inside a host policy approved in the UI."""
        if not isinstance(request, dict):
            raise ConfigDenial("Generator compute request must be an object")
        host = self._host(cfg, str(request.get("host_id", "")))
        policy = dict(host.get("agent_policy") or {})
        if not policy.get("enabled"):
            raise ConfigDenial(
                "this host is not enabled as an automatic Generator compute tool")
        if not 1 <= ordinal <= int(policy.get("max_jobs_per_task", 1)):
            raise ConfigDenial(
                "the Generator reached this host's automatic jobs-per-task limit")
        outputs = request.get("outputs", [])
        if not isinstance(outputs, list):
            raise ConfigDenial("Generator compute outputs must be a list of relative paths")
        safe_outputs = [_relative_output(str(value)) for value in outputs]
        if len({value.casefold() for value in safe_outputs}) != len(safe_outputs):
            raise ConfigDenial("Generator compute output paths must be unique")
        resources = self._resources({
            "name": request.get("name", "Generator compute"),
            **(request.get("resources") if isinstance(request.get("resources"), dict)
               else {}),
        })
        limits = {
            "nodes": int(policy.get("max_nodes", 1)),
            "cpus": int(policy.get("max_cpus", 1)),
            "gpus": int(policy.get("max_gpus", 0)),
        }
        for key, maximum in limits.items():
            if resources[key] > maximum:
                raise ConfigDenial(
                    f"Generator requested {resources[key]} {key}; this host allows {maximum}")
        if _memory_bytes(resources["memory"]) > _memory_bytes(
                str(policy.get("max_memory", ""))):
            raise ConfigDenial("Generator memory request exceeds this host's policy")
        if _walltime_seconds(resources["walltime"]) > _walltime_seconds(
                str(policy.get("max_walltime", "00:30:00"))):
            raise ConfigDenial("Generator wall time exceeds this host's policy")
        for key in ("partition", "account", "qos"):
            resources[key] = str(policy.get(key, ""))
        payload = {**resources, "host_id": host["id"],
                   "script": str(request.get("script", ""))}
        attachments = self._agent_inputs(cfg, request.get("inputs", []))
        return self.submit(
            cfg, payload, attachments=attachments, origin="generator",
            chat_id=chat_id, requested_outputs=safe_outputs)

    def _agent_result(self, cfg: Config, job: dict) -> dict:
        try:
            logs = self.logs(cfg, job["id"])
        except (ConfigDenial, SSHFailure) as exc:
            logs = {"stdout": "", "stderr": "", "error": exc.reason}
        try:
            available = {row["path"]: row for row in self.outputs(cfg, job["id"])}
        except (ConfigDenial, SSHFailure) as exc:
            available = {}
            logs.setdefault("error", exc.reason)
        host = self._host(cfg, job["host_id"])
        remaining = MAX_AGENT_RESULT_BYTES
        contents = []
        for relative in job.get("requested_outputs", []):
            meta = available.get(relative)
            row = {"path": relative, "available": bool(meta)}
            if meta:
                row["bytes"] = meta["bytes"]
                suffix = PurePosixPath(relative).suffix.lower()
                if suffix in TEXT_OUTPUT_SUFFIXES and remaining > 0:
                    limit = min(int(meta["bytes"]), remaining, 128 * 1024)
                    full = posixpath.join(job["directory"], relative)
                    row["content"] = self.transport.run(
                        host["alias"],
                        f"tail -c {limit} -- {shlex.quote(full)}", timeout=30)
                    row["truncated"] = int(meta["bytes"]) > limit
                    remaining -= len(row["content"].encode("utf-8", "replace"))
            contents.append(row)
        return {
            "job_id": job["id"], "status": job["status"],
            "exit_code": job.get("exit_code", ""), "elapsed": job.get("elapsed", ""),
            "stdout": str(logs.get("stdout", ""))[-LOG_BYTES:],
            "stderr": str(logs.get("stderr", ""))[-LOG_BYTES:],
            "monitoring_error": logs.get("error", ""), "outputs": contents,
        }

    def run_agent(self, cfg: Config, request: dict, *, chat_id: str = "",
                  ordinal: int = 1, notify: Callable[[str, str], None] | None = None,
                  poll_seconds: float = POLL_SECONDS,
                  timeout_seconds: float | None = None) -> dict:
        """Run the Generator's approved remote calculation and return bounded data."""
        job = self.submit_agent(cfg, request, chat_id=chat_id, ordinal=ordinal)
        if notify:
            notify("submitted", f"{job['name']} · {job['host']} · {job['id']}")
        maximum = timeout_seconds
        if maximum is None:
            maximum = _walltime_seconds(job["resources"]["walltime"]) + 300
        deadline = time.monotonic() + max(1.0, float(maximum))
        previous = ""
        while job.get("status") not in TERMINAL_STATES:
            if time.monotonic() >= deadline:
                result = self._agent_result(cfg, job)
                result.update({"status": "detached", "remote_status": job.get("status"),
                               "message": "The remote job continues, but the Generator stopped waiting."})
                return result
            if poll_seconds:
                time.sleep(poll_seconds)
            self.refresh(cfg)
            job = self._public_job(self._job(cfg, job["id"]))
            if notify and job.get("status") != previous:
                notify(str(job.get("status")), str(job.get("detail", "")))
                previous = str(job.get("status"))
        return self._agent_result(cfg, job)

    @staticmethod
    def _map_slurm(value: str) -> str:
        state = value.split()[0].split("+", 1)[0].upper()
        return {
            "PENDING": "queued", "CONFIGURING": "queued", "RUNNING": "running",
            "COMPLETING": "running", "COMPLETED": "completed", "FAILED": "failed",
            "CANCELLED": "cancelled", "TIMEOUT": "timeout", "OUT_OF_MEMORY": "out_of_memory",
            "NODE_FAIL": "failed", "PREEMPTED": "failed", "BOOT_FAIL": "failed",
        }.get(state, state.lower() or "unknown")

    def _poll_job(self, cfg: Config, job: dict, host: dict) -> dict:
        rid = str(job["remote_id"])
        if not REMOTE_ID.fullmatch(rid):
            raise ConfigDenial("stored remote job identifier is invalid")
        if job["scheduler"] == "slurm":
            command = (f"row=$(squeue -h -j {rid} -o '%T|%M|%R' 2>/dev/null | head -n1); "
                       "if [ -n \"$row\" ]; then printf 'queue|%s\\n' \"$row\"; "
                       "elif command -v sacct >/dev/null 2>&1; then "
                       f"sacct -n -P -X -j {rid} --format=State,Elapsed,ExitCode | "
                       "sed '/^[[:space:]]*$/d' | head -n1 | sed 's/^/acct|/'; "
                       "else printf 'gone|UNKNOWN|||\\n'; fi")
            output = self.transport.run(host["alias"], command, timeout=15).strip()
            source, _, body = output.partition("|")
            parts = body.split("|")
            state = parts[0] if parts else "UNKNOWN"
            job["status"] = self._map_slurm(state)
            job["elapsed"] = parts[1] if len(parts) > 1 else job.get("elapsed", "")
            job["detail"] = parts[2] if len(parts) > 2 else source
            if source == "acct" and len(parts) > 2:
                job["exit_code"] = parts[2]
        else:
            directory = shlex.quote(job["directory"])
            command = (f"cd -- {directory}; if [ -f .exit_code ]; then "
                       "printf 'done|'; cat .exit_code; "
                       f"elif kill -0 -- -{rid} 2>/dev/null; then printf 'running|'; "
                       "else printf 'lost|'; fi")
            output = self.transport.run(host["alias"], command, timeout=15).strip()
            source, _, code = output.partition("|")
            if source == "done":
                job["exit_code"] = code.strip()
                job["status"] = "completed" if code.strip() == "0" else "failed"
                job["detail"] = "Remote process finished"
            elif source == "running":
                job["status"], job["detail"] = "running", "Detached process is running"
            else:
                job["status"], job["detail"] = "unknown", "Process state is unavailable"
        job["updated"] = time.time()
        return job

    def refresh(self, cfg: Config) -> bool:
        changed = False
        with self._lock:
            rows = self._jobs(cfg)
            hosts = {row["id"]: row for row in self._hosts(cfg)}
        for row in rows:
            if row.get("status") in TERMINAL_STATES:
                continue
            if row.get("status") == "submitting" and not row.get("remote_id"):
                if time.time() - float(row.get("updated") or 0) >= 60:
                    row.update({
                        "status": "failed",
                        "detail": "Submission was interrupted before a remote job ID was recorded",
                        "updated": time.time(),
                    })
                    changed = True
                continue
            before = (row.get("status"), row.get("detail"), row.get("elapsed"),
                      row.get("exit_code"))
            host = hosts.get(row.get("host_id"))
            if not host:
                continue
            try:
                self._poll_job(cfg, row, host)
                row.pop("connection_error", None)
            except (ConfigDenial, SSHFailure) as exc:
                row["connection_error"] = exc.reason
                row["updated"] = time.time()
            after = (row.get("status"), row.get("detail"), row.get("elapsed"),
                     row.get("exit_code"))
            changed = changed or before != after
        if rows:
            with self._lock:
                self._save_jobs(cfg, rows)
        return changed

    def watch(self, cfg: Config, notify: Callable[[], None]) -> None:
        key = str(cfg.root.resolve())
        with self._lock:
            thread = self._watchers.get(key)
            if thread and thread.is_alive():
                return
            stop = threading.Event()
            self._stops[key] = stop

            def loop() -> None:
                while not stop.wait(POLL_SECONDS):
                    try:
                        if self.refresh(cfg):
                            notify()
                        if not any(row.get("status") not in TERMINAL_STATES
                                   for row in self._jobs(cfg)):
                            break
                    except Exception:  # noqa: BLE001 - resilient observer boundary
                        continue

            thread = threading.Thread(target=loop, name=f"crossaudit-hpc-{cfg.root.name}",
                                      daemon=True)
            self._watchers[key] = thread
            thread.start()

    def logs(self, cfg: Config, job_id: str) -> dict:
        job = self._job(cfg, job_id)
        host = self._host(cfg, job["host_id"])
        directory = job["directory"]
        command = (f"for f in stdout.log stderr.log; do printf '---%s---\\n' \"$f\"; "
                   f"tail -c {LOG_BYTES} -- {shlex.quote(directory)}/\"$f\" 2>/dev/null || true; "
                   "printf '\\n'; done")
        output = self.transport.run(host["alias"], command, timeout=20)
        _, _, remainder = output.partition("---stdout.log---\n")
        stdout, _, stderr = remainder.partition("\n---stderr.log---\n")
        return {"job_id": job_id, "stdout": stdout[-LOG_BYTES:],
                "stderr": stderr[-LOG_BYTES:], "updated": time.time()}

    def cancel(self, cfg: Config, job_id: str) -> dict:
        job = self._job(cfg, job_id)
        if job.get("status") in TERMINAL_STATES:
            return self._public_job(job)
        host = self._host(cfg, job["host_id"])
        rid = str(job["remote_id"])
        if not REMOTE_ID.fullmatch(rid):
            raise ConfigDenial("stored remote job identifier is invalid")
        command = (f"scancel -- {rid}" if job["scheduler"] == "slurm" else
                   f"kill -TERM -- -{rid}")
        self.transport.run(host["alias"], command, timeout=15)
        with self._lock:
            rows = self._jobs(cfg)
            for row in rows:
                if row.get("id") == job_id:
                    row.update({"status": "cancelled", "detail": "Cancelled by user",
                                "updated": time.time()})
                    job = row
                    break
            self._save_jobs(cfg, rows)
        return self._public_job(job)

    def outputs(self, cfg: Config, job_id: str) -> list[dict]:
        job = self._job(cfg, job_id)
        host = self._host(cfg, job["host_id"])
        directory = job["directory"]
        # Keep discovery portable to BSD/macOS workstations: -maxdepth,
        # -printf and stat -c are GNU extensions not guaranteed off Linux.
        command = (f"cd -- {shlex.quote(directory)} && "
                   "find . -type f ! -name job.sh ! -name .exit_code 2>/dev/null | "
                   "while IFS= read -r f; do p=${f#./}; "
                   "case \"$p\" in */*/*/*) continue;; esac; "
                   "n=$(wc -c < \"$f\" 2>/dev/null) || continue; "
                   "printf '%s\\t%s\\n' \"$p\" \"$n\"; done | head -n 1000")
        output = self.transport.run(host["alias"], command, timeout=20)
        rows = []
        for line in output.splitlines():
            path, separator, size = line.rpartition("\t")
            if not separator or not size.isdigit():
                continue
            try:
                safe = _relative_output(path)
            except ConfigDenial:
                continue
            rows.append({"path": safe, "name": PurePosixPath(safe).name,
                         "bytes": int(size)})
        return rows

    def open_output(self, cfg: Config, job_id: str, relative: str) -> tuple[subprocess.Popen, str, int]:
        job = self._job(cfg, job_id)
        host = self._host(cfg, job["host_id"])
        relative = _relative_output(relative)
        full = posixpath.join(job["directory"], relative)
        check = (f"test -f {shlex.quote(full)} && "
                 f"wc -c < {shlex.quote(full)}")
        raw = self.transport.run(host["alias"], check, timeout=15).strip()
        if not raw.isdigit():
            raise ConfigDenial("remote output is not a regular file")
        process = self.transport.stream(host["alias"], f"cat -- {shlex.quote(full)}")
        return process, PurePosixPath(relative).name, int(raw)

    @staticmethod
    def _public_job(row: dict) -> dict:
        return {key: row.get(key) for key in (
            "id", "host_id", "host", "scheduler", "remote_id", "directory",
            "name", "resources", "status", "detail", "submitted", "updated",
            "elapsed", "exit_code", "connection_error", "inputs", "origin",
            "chat_id", "requested_outputs")}

    def snapshot(self, cfg: Config, notify: Callable[[], None] | None = None) -> dict:
        with self._lock:
            hosts = [self._public_host(row) for row in self._hosts(cfg)]
            jobs = [self._public_job(row) for row in self._jobs(cfg)]
        jobs.sort(key=lambda row: float(row.get("submitted") or 0), reverse=True)
        if notify and any(row.get("status") not in TERMINAL_STATES for row in jobs):
            self.watch(cfg, notify)
        return {
            "ssh_available": self.transport.available(),
            "aliases": ssh_aliases(), "hosts": hosts, "jobs": jobs,
            "active": sum(row.get("status") not in TERMINAL_STATES for row in jobs),
            "updated": time.time(),
        }


MANAGER = Manager()
