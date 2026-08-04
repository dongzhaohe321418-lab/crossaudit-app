"""Project-scoped Model Context Protocol client and policy gate.

CrossAudit is the MCP *host*.  A server is invisible to the Generator until a
person registers it and explicitly approves individual tools.  Stdio commands
are argument vectors (never a shell string); remote servers use Streamable HTTP
over HTTPS, with loopback HTTP allowed for local development.

Only tool metadata and bounded call results enter the Generator context.  The
Auditor still sees committed project files rather than tool chatter, preserving
the same contextual isolation used for Skills and remote compute.
"""
from __future__ import annotations

import getpass
import hashlib
import ipaddress
import json
import os
import queue
import re
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import __version__
from .config import Config
from .errors import ConfigDenial

PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_VERSIONS = {PROTOCOL_VERSION, "2025-06-18", "2025-03-26"}
SERVER_ID = re.compile(r"[a-f0-9]{16}")
SERVER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,79}")
TOOL_NAME = re.compile(r"[A-Za-z0-9_.:/-]{1,256}")
MAX_MESSAGE_BYTES = 4 * 1024 * 1024
MAX_ARGUMENT_BYTES = 512 * 1024
MAX_AGENT_RESULT_BYTES = 256 * 1024
MAX_CONTEXT_BYTES = 256 * 1024
MAX_STDERR_BYTES = 32 * 1024
MAX_CALLS_PER_TASK = 20
TOKEN_SERVICE_PREFIX = "io.crossaudit.app.mcp"


def _state_root(cfg: Config) -> Path:
    root = cfg.root / cfg.state_dir / "mcp"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def _read(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
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


def _security() -> str:
    path = shutil.which("security") or "/usr/bin/security"
    if not Path(path).is_file():
        raise ConfigDenial("macOS Keychain is unavailable for the MCP credential")
    return path


def _token_service(server_id: str) -> str:
    if not SERVER_ID.fullmatch(str(server_id)):
        raise ConfigDenial("invalid MCP server identifier")
    return f"{TOKEN_SERVICE_PREFIX}.{server_id}"


def _read_token(server_id: str) -> str:
    try:
        result = subprocess.run(
            [_security(), "find-generic-password", "-a", getpass.getuser(),
             "-s", _token_service(server_id), "-w"], capture_output=True,
            text=True, timeout=10, check=False)
    except (ConfigDenial, OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.rstrip("\r\n") if result.returncode == 0 else ""


def _write_token(server_id: str, token: str) -> None:
    value = str(token)
    if not value or len(value.encode("utf-8")) > 16_384:
        raise ConfigDenial("MCP bearer token is empty or unexpectedly large")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ConfigDenial("MCP bearer token contains control characters")
    result = subprocess.run(
        [_security(), "add-generic-password", "-U", "-a", getpass.getuser(),
         "-s", _token_service(server_id), "-l", "CrossAudit MCP bearer token",
         "-w"], input=value + "\n" + value + "\n", capture_output=True,
        text=True, timeout=15, check=False)
    if result.returncode:
        raise ConfigDenial(
            f"macOS Keychain refused the MCP credential: {result.stderr.strip()[:240]}")


def _remove_token(server_id: str) -> None:
    try:
        subprocess.run(
            [_security(), "delete-generic-password", "-a", getpass.getuser(),
             "-s", _token_service(server_id)], capture_output=True, text=True,
            timeout=10, check=False)
    except (ConfigDenial, OSError, subprocess.TimeoutExpired):
        pass


def _bounded_json(value, limit: int, label: str) -> bytes:
    try:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    except (TypeError, ValueError) as exc:
        raise ConfigDenial(f"{label} must be valid JSON") from exc
    if len(raw) > limit:
        raise ConfigDenial(f"{label} exceeds the {limit}-byte safety limit")
    return raw


def _safe_command(command: str) -> str:
    value = str(command).strip()
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise ConfigDenial("MCP executable is required")
    resolved = value if Path(value).is_absolute() else (shutil.which(value) or "")
    if not resolved or not Path(resolved).is_file() or not os.access(resolved, os.X_OK):
        raise ConfigDenial(f"MCP executable {value!r} was not found or is not executable")
    return str(Path(resolved).resolve())


def _safe_args(values) -> list[str]:
    if not isinstance(values, list):
        raise ConfigDenial("MCP arguments must be a list")
    rows = []
    for value in values:
        item = str(value)
        if len(item.encode()) > 4096 or "\x00" in item or "\n" in item or "\r" in item:
            raise ConfigDenial("an MCP argument is invalid or too long")
        rows.append(item)
    if sum(len(item.encode()) for item in rows) > 32 * 1024:
        raise ConfigDenial("MCP arguments are unexpectedly large")
    return rows


def _safe_url(value: str, allow_private: bool) -> str:
    raw = str(value).strip()
    parsed = urlsplit(raw)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or
            parsed.fragment or parsed.scheme not in {"http", "https"}):
        raise ConfigDenial("MCP URL must be a plain HTTP(S) endpoint without credentials, query or fragment")
    loopback_name = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not loopback_name:
        raise ConfigDenial("remote MCP servers require HTTPS; HTTP is allowed only on loopback")
    if not loopback_name and not allow_private:
        try:
            addresses = {row[4][0] for row in socket.getaddrinfo(
                parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise ConfigDenial("the MCP hostname could not be resolved") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if (ip.is_private or ip.is_loopback or ip.is_link_local or
                    ip.is_multicast or ip.is_reserved or ip.is_unspecified):
                raise ConfigDenial(
                    "the MCP hostname resolves to a private or reserved address; "
                    "enable private-network access only for a verified enterprise server")
    return raw


class _StdioSession:
    def __init__(self, row: dict) -> None:
        env = {key: os.environ[key] for key in (
            "PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL")
               if os.environ.get(key)}
        try:
            self.process = subprocess.Popen(
                [row["command"], *row.get("args", [])], cwd=row["root"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, start_new_session=True)
        except OSError as exc:
            raise ConfigDenial(f"MCP server could not start: {exc}") from exc
        self.timeout = float(row.get("timeout", 30))
        self.sequence = 0
        self.buffer = b""
        self.stderr = bytearray()
        # ``select()`` can wait on pipes on POSIX, but Windows only accepts
        # sockets and raises WinError 10038 for a subprocess stdout handle.
        # A bounded reader queue gives every platform the same timeout and
        # memory behaviour without polling or platform-specific overlapped IO.
        self._stdout_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=8)
        self._stdout_thread = threading.Thread(target=self._drain_stdout,
                                               daemon=True)
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()
        self.protocol = PROTOCOL_VERSION

    def _drain_stdout(self) -> None:
        assert self.process.stdout is not None
        try:
            while True:
                # readline's limit prevents a server that omits delimiters
                # from growing an unbounded allocation in this process.
                block = self.process.stdout.readline(MAX_MESSAGE_BYTES + 2)
                if not block:
                    self._stdout_queue.put(None)
                    return
                self._stdout_queue.put(block)
        except OSError:
            self._stdout_queue.put(None)

    def _drain_stderr(self) -> None:
        assert self.process.stderr is not None
        try:
            for block in iter(lambda: self.process.stderr.read(4096), b""):
                self.stderr.extend(block)
                if len(self.stderr) > MAX_STDERR_BYTES:
                    del self.stderr[:-MAX_STDERR_BYTES]
        except OSError:
            pass

    def _send(self, message: dict) -> None:
        assert self.process.stdin is not None
        raw = _bounded_json(message, MAX_MESSAGE_BYTES, "MCP message") + b"\n"
        try:
            self.process.stdin.write(raw)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            detail = bytes(self.stderr).decode("utf-8", "replace")[-1000:]
            raise ConfigDenial(f"MCP server closed its input. {detail}".strip()) from exc

    def _message(self, deadline: float) -> dict:
        while True:
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except (UnicodeDecodeError, ValueError) as exc:
                    raise ConfigDenial("MCP server wrote non-JSON data to stdout") from exc
                if not isinstance(value, dict):
                    raise ConfigDenial("MCP server returned a non-object JSON-RPC message")
                return value
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ConfigDenial("MCP request timed out")
            try:
                block = self._stdout_queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise ConfigDenial("MCP request timed out") from exc
            if block is None:
                detail = bytes(self.stderr).decode("utf-8", "replace")[-1000:]
                raise ConfigDenial(f"MCP server exited before replying. {detail}".strip())
            self.buffer += block
            if len(self.buffer) > MAX_MESSAGE_BYTES:
                raise ConfigDenial("MCP server response exceeded the safety limit")

    def request(self, method: str, params: dict | None = None) -> dict:
        self.sequence += 1
        request_id = self.sequence
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + self.timeout
        while True:
            reply = self._message(deadline)
            if reply.get("id") == request_id:
                if isinstance(reply.get("error"), dict):
                    raise ConfigDenial(
                        f"MCP {method} failed: {reply['error'].get('message', 'server error')}")
                result = reply.get("result", {})
                if not isinstance(result, dict):
                    raise ConfigDenial(f"MCP {method} returned an invalid result")
                return result
            if "id" in reply and reply.get("method"):
                self._send({"jsonrpc": "2.0", "id": reply["id"], "error": {
                    "code": -32601, "message": "CrossAudit does not expose client-side MCP methods"}})

    def notify(self, method: str, params: dict | None = None) -> None:
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def initialize(self) -> dict:
        result = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "CrossAudit", "version": __version__},
        })
        version = str(result.get("protocolVersion", ""))
        if version not in SUPPORTED_VERSIONS:
            raise ConfigDenial(f"MCP server negotiated unsupported protocol {version!r}")
        self.protocol = version
        self.notify("notifications/initialized")
        return result

    def close(self) -> None:
        process = self.process
        try:
            if process.stdin:
                process.stdin.close()
            process.wait(timeout=1)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConfigDenial("MCP endpoint redirects are refused; register the final HTTPS URL")


class _HTTPSession:
    def __init__(self, row: dict, token: str) -> None:
        self.row = row
        self.token = token
        self.timeout = float(row.get("timeout", 30))
        self.sequence = 0
        self.session_id = ""
        self.protocol = PROTOCOL_VERSION
        self.opener = build_opener(_NoRedirect())

    def _post(self, message: dict, *, initialization: bool = False) -> dict:
        body = _bounded_json(message, MAX_MESSAGE_BYTES, "MCP message")
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["MCP-Session-Id"] = self.session_id
        if not initialization:
            headers["MCP-Protocol-Version"] = self.protocol
        request = Request(self.row["url"], data=body, headers=headers, method="POST")
        try:
            response = self.opener.open(request, timeout=self.timeout)
            content_type = response.headers.get("Content-Type", "").lower()
            if initialization:
                self.session_id = response.headers.get("MCP-Session-Id", "")
            raw = response.read(MAX_MESSAGE_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 401:
                raise ConfigDenial(
                    "MCP server requires authorization. Add a valid bearer token; "
                    "interactive MCP OAuth is not configured for this server.") from exc
            raise ConfigDenial(f"MCP server returned HTTP {exc.code}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise ConfigDenial(f"MCP server connection failed: {exc}") from exc
        if len(raw) > MAX_MESSAGE_BYTES:
            raise ConfigDenial("MCP server response exceeded the safety limit")
        if not raw:
            return {}
        if "text/event-stream" in content_type:
            candidates = []
            for event in raw.decode("utf-8", "replace").split("\n\n"):
                data = "\n".join(line[5:].lstrip() for line in event.splitlines()
                                   if line.startswith("data:"))
                if data:
                    try:
                        candidates.append(json.loads(data))
                    except ValueError:
                        continue
            expected = message.get("id")
            value = next((item for item in candidates
                          if isinstance(item, dict) and item.get("id") == expected), None)
            if value is None:
                raise ConfigDenial("MCP event stream ended without the requested response")
            return value
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ConfigDenial("MCP server returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ConfigDenial("MCP server returned a non-object JSON-RPC message")
        return value

    def request(self, method: str, params: dict | None = None,
                *, initialization: bool = False) -> dict:
        self.sequence += 1
        message = {"jsonrpc": "2.0", "id": self.sequence, "method": method}
        if params is not None:
            message["params"] = params
        reply = self._post(message, initialization=initialization)
        if isinstance(reply.get("error"), dict):
            raise ConfigDenial(
                f"MCP {method} failed: {reply['error'].get('message', 'server error')}")
        result = reply.get("result", {})
        if not isinstance(result, dict):
            raise ConfigDenial(f"MCP {method} returned an invalid result")
        return result

    def notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method})

    def initialize(self) -> dict:
        result = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "CrossAudit", "version": __version__},
        }, initialization=True)
        version = str(result.get("protocolVersion", ""))
        if version not in SUPPORTED_VERSIONS:
            raise ConfigDenial(f"MCP server negotiated unsupported protocol {version!r}")
        self.protocol = version
        self.notify("notifications/initialized")
        return result

    def close(self) -> None:
        return


def _list_tools(session) -> tuple[dict, list[dict]]:
    info = session.initialize()
    tools = []
    cursor = None
    while True:
        params = {"cursor": cursor} if cursor else None
        result = session.request("tools/list", params)
        page = result.get("tools", [])
        if not isinstance(page, list):
            raise ConfigDenial("MCP tools/list returned an invalid tool list")
        for item in page:
            if not isinstance(item, dict) or not TOOL_NAME.fullmatch(str(item.get("name", ""))):
                raise ConfigDenial("MCP server advertised an invalid tool")
            tools.append({
                "name": str(item["name"]),
                "title": str(item.get("title", ""))[:200],
                "description": str(item.get("description", ""))[:4000],
                "inputSchema": item.get("inputSchema")
                if isinstance(item.get("inputSchema"), dict) else {"type": "object"},
                "annotations": item.get("annotations")
                if isinstance(item.get("annotations"), dict) else {},
            })
            if len(tools) > 1000:
                raise ConfigDenial("MCP server advertised more than 1000 tools")
        cursor = result.get("nextCursor")
        if not cursor:
            break
        if not isinstance(cursor, str) or len(cursor) > 2048:
            raise ConfigDenial("MCP server returned an invalid pagination cursor")
    return info, tools


class Manager:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def _paths(self, cfg: Config) -> tuple[Path, Path]:
        root = _state_root(cfg)
        return root / "servers.json", root / "calls.json"

    def _servers(self, cfg: Config) -> list[dict]:
        return _read(self._paths(cfg)[0], [])

    def _save_servers(self, cfg: Config, rows: list[dict]) -> None:
        _write(self._paths(cfg)[0], rows)

    def _calls(self, cfg: Config) -> list[dict]:
        return _read(self._paths(cfg)[1], [])

    def _server(self, cfg: Config, server_id: str) -> dict:
        if not SERVER_ID.fullmatch(str(server_id)):
            raise ConfigDenial("invalid MCP server identifier")
        row = next((item for item in self._servers(cfg) if item.get("id") == server_id), None)
        if not row:
            raise ConfigDenial("that MCP server is not registered in this project")
        # The project folder may have moved since registration. The command's
        # working directory is always the currently loaded project, never a
        # stale path copied from mutable local state.
        row["root"] = str(cfg.root)
        return row

    def _session(self, row: dict, token_override: str = ""):
        if row["transport"] == "stdio":
            return _StdioSession(row)
        return _HTTPSession(row, token_override or _read_token(row["id"]))

    def _probe_row(self, row: dict, token: str = "") -> tuple[dict, list[dict]]:
        session = self._session(row, token)
        try:
            return _list_tools(session)
        finally:
            session.close()

    def register(self, cfg: Config, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ConfigDenial("MCP server settings must be an object")
        name = str(payload.get("name", "")).strip()
        if not SERVER_NAME.fullmatch(name):
            raise ConfigDenial("MCP server name uses unsupported characters")
        transport = str(payload.get("transport", "stdio"))
        if transport not in {"stdio", "http"}:
            raise ConfigDenial("MCP transport must be stdio or Streamable HTTP")
        server_id = str(payload.get("server_id", ""))
        if server_id and not SERVER_ID.fullmatch(server_id):
            raise ConfigDenial("invalid MCP server identifier")
        is_new = not server_id
        server_id = server_id or secrets.token_hex(8)
        timeout = payload.get("timeout", 30)
        try:
            timeout = int(timeout)
        except (TypeError, ValueError) as exc:
            raise ConfigDenial("MCP timeout must be a whole number") from exc
        if not 1 <= timeout <= 300:
            raise ConfigDenial("MCP timeout must be between 1 and 300 seconds")
        row = {"id": server_id, "name": name, "transport": transport,
               "timeout": timeout, "root": str(cfg.root), "updated": time.time()}
        token = str(payload.get("bearer_token", "")).strip()
        if transport == "stdio":
            if payload.get("approve_local_code") is not True:
                raise ConfigDenial("approve the exact local MCP command before it runs")
            row.update({"command": _safe_command(str(payload.get("command", ""))),
                        "args": _safe_args(payload.get("args", []))})
        else:
            allow_private = payload.get("allow_private_network") is True
            row.update({"url": _safe_url(str(payload.get("url", "")), allow_private),
                        "allow_private_network": allow_private,
                        "token_present": bool(token or _read_token(server_id))})
        info, tools = self._probe_row(row, token)
        available = {item["name"] for item in tools}
        requested = payload.get("allowed_tools", [])
        if isinstance(requested, str):
            requested = [item.strip() for item in requested.split(",") if item.strip()]
        if not isinstance(requested, list):
            raise ConfigDenial("allowed MCP tools must be a list")
        allowed = list(available) if payload.get("allow_all_tools") is True else [
            str(item) for item in requested]
        if any(item not in available for item in allowed):
            raise ConfigDenial("an allowed MCP tool is not advertised by this server")
        enabled = payload.get("enabled") is True
        if is_new and enabled and payload.get("allow_all_tools") is True:
            raise ConfigDenial(
                "connect the MCP server without Generator access first, review the "
                "advertised tool list, then configure and enable it")
        if enabled and not allowed:
            raise ConfigDenial("select at least one MCP tool before enabling Generator access")
        max_calls = payload.get("max_calls_per_task", 5)
        try:
            max_calls = int(max_calls)
        except (TypeError, ValueError) as exc:
            raise ConfigDenial("MCP calls per task must be a whole number") from exc
        if not 1 <= max_calls <= MAX_CALLS_PER_TASK:
            raise ConfigDenial(
                f"MCP calls per task must be between 1 and {MAX_CALLS_PER_TASK}")
        row.update({
            "enabled": enabled, "allowed_tools": sorted(set(allowed)),
            "max_calls_per_task": max_calls, "status": "ready",
            "protocol_version": str(info.get("protocolVersion", "")),
            "server_info": info.get("serverInfo") if isinstance(
                info.get("serverInfo"), dict) else {}, "tools": tools,
        })
        if token:
            _write_token(server_id, token)
            row["token_present"] = True
        with self._lock:
            rows = self._servers(cfg)
            existing = next((item for item in rows if item.get("id") == server_id), None)
            if existing is None:
                rows.append(row)
            else:
                existing.clear()
                existing.update(row)
            self._save_servers(cfg, rows)
        return self._public_server(row)

    def probe(self, cfg: Config, server_id: str) -> dict:
        row = self._server(cfg, server_id)
        info, tools = self._probe_row(row)
        available = {item["name"] for item in tools}
        row.update({
            "tools": tools, "allowed_tools": [item for item in row.get(
                "allowed_tools", []) if item in available], "status": "ready",
            "protocol_version": str(info.get("protocolVersion", "")),
            "server_info": info.get("serverInfo") if isinstance(
                info.get("serverInfo"), dict) else {}, "updated": time.time(),
        })
        if row.get("enabled") and not row["allowed_tools"]:
            row["enabled"] = False
        with self._lock:
            rows = self._servers(cfg)
            for stored in rows:
                if stored.get("id") == server_id:
                    stored.clear()
                    stored.update(row)
                    break
            self._save_servers(cfg, rows)
        return self._public_server(row)

    def remove(self, cfg: Config, server_id: str) -> dict:
        self._server(cfg, server_id)
        with self._lock:
            rows = [item for item in self._servers(cfg) if item.get("id") != server_id]
            self._save_servers(cfg, rows)
        _remove_token(server_id)
        return {"removed": server_id}

    @staticmethod
    def _public_server(row: dict) -> dict:
        return {key: row.get(key) for key in (
            "id", "name", "transport", "command", "args", "url", "timeout",
            "allow_private_network", "token_present", "enabled", "allowed_tools",
            "max_calls_per_task", "status", "protocol_version", "server_info",
            "tools", "updated")}

    def agent_context(self, cfg: Config) -> list[dict]:
        result = []
        used = 0
        for row in self._servers(cfg):
            if not row.get("enabled"):
                continue
            allowed = set(row.get("allowed_tools", []))
            tools = []
            for item in row.get("tools", []):
                if item.get("name") not in allowed:
                    continue
                public = {"name": item["name"], "title": item.get("title", ""),
                          "description": item.get("description", ""),
                          "inputSchema": item.get("inputSchema", {"type": "object"})}
                size = len(_bounded_json(public, MAX_MESSAGE_BYTES, "MCP tool metadata"))
                if used + size > MAX_CONTEXT_BYTES:
                    break
                used += size
                tools.append(public)
            if tools:
                result.append({"server_id": row["id"], "name": row["name"],
                               "max_calls_per_task": row["max_calls_per_task"],
                               "tools": tools})
        return result

    def _record_call(self, cfg: Config, row: dict) -> None:
        with self._lock:
            rows = self._calls(cfg)
            rows.append(row)
            _write(self._paths(cfg)[1], rows[-200:])

    def call_agent(self, cfg: Config, request: dict, *, chat_id: str = "",
                   ordinal: int = 1,
                   notify: Callable[[str, str], None] | None = None) -> dict:
        if not isinstance(request, dict):
            raise ConfigDenial("Generator MCP request must be an object")
        server = self._server(cfg, str(request.get("server_id", "")))
        if not server.get("enabled"):
            raise ConfigDenial("this MCP server is not enabled for the Generator")
        tool = str(request.get("tool", ""))
        if tool not in server.get("allowed_tools", []):
            raise ConfigDenial("this MCP tool is not approved for automatic use")
        if not 1 <= ordinal <= int(server.get("max_calls_per_task", 1)):
            raise ConfigDenial("the Generator reached this MCP server's calls-per-task limit")
        arguments = request.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ConfigDenial("MCP tool arguments must be an object")
        args_raw = _bounded_json(arguments, MAX_ARGUMENT_BYTES, "MCP tool arguments")
        started = time.time()
        if notify:
            notify("calling", f"{server['name']} · {tool}")
        session = self._session(server)
        status = "failed"
        result = {}
        failure = None
        try:
            session.initialize()
            result = session.request("tools/call", {"name": tool, "arguments": arguments})
            status = "error" if result.get("isError") is True else "completed"
        except ConfigDenial as exc:
            failure = exc
            result = {"isError": True, "content": []}
        finally:
            session.close()
        bounded = self._agent_result(result)
        result_raw = json.dumps(bounded, ensure_ascii=False, sort_keys=True).encode()
        call_id = secrets.token_hex(8)
        self._record_call(cfg, {
            "id": call_id, "server_id": server["id"], "server": server["name"],
            "tool": tool, "status": status, "chat_id": chat_id, "started": started,
            "duration_ms": int((time.time() - started) * 1000),
            "arguments_sha256": hashlib.sha256(args_raw).hexdigest(),
            "result_sha256": hashlib.sha256(result_raw).hexdigest(),
        })
        if notify:
            notify(status, f"{server['name']} · {tool}")
        if failure is not None:
            raise failure
        return {"call_id": call_id, "server_id": server["id"], "server": server["name"],
                "tool": tool, "status": status, **bounded}

    @staticmethod
    def _agent_result(result: dict) -> dict:
        remaining = MAX_AGENT_RESULT_BYTES
        content = []
        for block in result.get("content", []) if isinstance(result.get("content"), list) else []:
            if not isinstance(block, dict):
                continue
            kind = str(block.get("type", ""))
            if kind == "text":
                text = str(block.get("text", ""))
                encoded = text.encode("utf-8")
                clipped = encoded[:remaining].decode("utf-8", "ignore")
                content.append({"type": "text", "text": clipped,
                                "truncated": len(encoded) > len(clipped.encode())})
                remaining -= len(clipped.encode())
            elif kind in {"image", "audio"}:
                content.append({"type": kind, "omitted": True,
                                "mimeType": str(block.get("mimeType", ""))[:100]})
            elif kind in {"resource", "resource_link"}:
                public = {key: block.get(key) for key in (
                    "type", "name", "title", "uri", "description", "mimeType")
                          if block.get(key) is not None}
                content.append(public)
        structured = result.get("structuredContent")
        if structured is not None:
            try:
                raw = _bounded_json(structured, max(1, remaining), "MCP structured result")
                structured = json.loads(raw)
            except ConfigDenial:
                structured = {"truncated": True}
        return {"is_error": result.get("isError") is True,
                "content": content, "structured_content": structured}

    def snapshot(self, cfg: Config) -> dict:
        return {"servers": [self._public_server(row) for row in self._servers(cfg)],
                "calls": list(reversed(self._calls(cfg)[-40:])),
                "protocol_version": PROTOCOL_VERSION}


MANAGER = Manager()
