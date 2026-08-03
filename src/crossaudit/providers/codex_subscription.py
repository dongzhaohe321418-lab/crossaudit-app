"""OpenAI Codex subscription bridge through the official App Server.

This provider never reads ChatGPT tokens.  The official ``codex`` executable
owns browser login, refresh, and credential storage; CrossAudit speaks its
documented JSON-RPC protocol over stdio and keeps only non-secret account state.

Each completion runs in an ephemeral, read-only thread.  A CrossAudit model
role returns text only: command/file-change events are treated as a provider
boundary violation and the round fails closed.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from ..errors import ConfigDenial, ProviderDenial
from .base import Reply

CLIENT = {"name": "crossaudit", "title": "CrossAudit", "version": "4.6.0"}
DEFAULT_TIMEOUT_S = 300.0
FORBIDDEN_ITEM_TYPES = {
    "commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall",
    "webSearch", "imageGeneration", "collabAgentToolCall",
}


def executable() -> str:
    """Resolve only the explicit bundled binary or an installed official CLI."""
    configured = os.environ.get("CROSSAUDIT_BUNDLED_CODEX", "").strip()
    path = configured or shutil.which("codex") or ""
    if not path or not Path(path).is_file() or not os.access(path, os.X_OK):
        raise ConfigDenial(
            "ChatGPT subscription access needs the official Codex runtime. "
            "Install Codex or use the CrossAudit macOS app, which bundles it.")
    return path


@dataclass
class _Collector:
    thread_id: str
    text: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    status: str | None = None
    error: str = ""
    turn_id: str = ""
    usage: dict = field(default_factory=dict)
    done: threading.Event = field(default_factory=threading.Event)

    def accept(self, message: dict) -> None:
        params = message.get("params") or {}
        if params.get("threadId") != self.thread_id:
            return
        method = message.get("method")
        if method == "item/agentMessage/delta":
            self.text.append(str(params.get("delta", "")))
        elif method == "item/completed":
            item = params.get("item") or {}
            kind = str(item.get("type", ""))
            if kind in FORBIDDEN_ITEM_TYPES:
                self.forbidden.append(kind)
        elif method == "thread/tokenUsage/updated":
            token_usage = params.get("tokenUsage") or {}
            last = token_usage.get("last") if isinstance(token_usage, dict) else None
            if isinstance(last, dict):
                self.usage = dict(last)
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            self.turn_id = str(turn.get("id", ""))
            self.status = str(turn.get("status", "failed"))
            error = turn.get("error")
            if isinstance(error, dict):
                self.error = str(error.get("message") or error.get("detail") or error)
            elif error:
                self.error = str(error)
            self.done.set()


class CodexAppServer:
    """One process-safe App Server connection shared by local project workers."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path
        self._proc: subprocess.Popen | None = None
        self._start_lock = threading.Lock()
        self._initialized = False
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._next_id = 1
        self._pending: dict[int, queue.Queue] = {}
        self._collectors: dict[str, _Collector] = {}
        self._notifications: list[dict] = []
        self._notification_signal = threading.Condition(self._state_lock)

    def _start(self) -> None:
        # A second HTTP worker may arrive while the first is still initializing.
        # Serialize the whole handshake so no request can race ahead of it.
        with self._start_lock:
            with self._state_lock:
                if (self._proc and self._proc.poll() is None and
                        self._initialized):
                    return
                if self._proc and self._proc.poll() is None:
                    self._proc.terminate()
                path = self.path or executable()
                try:
                    proc = subprocess.Popen(
                        [path, "app-server"], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1)
                except OSError as exc:
                    raise ConfigDenial(
                        f"could not start the official Codex runtime: {exc}") from exc
                self._proc = proc
                self._initialized = False
                threading.Thread(target=self._read, args=(proc,), daemon=True).start()
            self.call("initialize", {"clientInfo": CLIENT, "capabilities": {}},
                      timeout=15)
            self.notify("initialized", {})
            with self._state_lock:
                self._initialized = True

    def _read(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                message = json.loads(line)
            except (ValueError, TypeError):
                continue
            request_id = message.get("id")
            if request_id is not None:
                # Server-initiated tool/approval requests are outside this
                # adapter's text-only contract. Refuse the request immediately
                # instead of leaving the runtime (and UI) waiting for a timeout.
                if message.get("method"):
                    params = message.get("params") or {}
                    thread_id = str(params.get("threadId", ""))
                    with self._state_lock:
                        collector = self._collectors.get(thread_id)
                    if collector:
                        collector.forbidden.append(str(message["method"]))
                        collector.error = "the subscription runtime requested a tool"
                        collector.status = "failed"
                        collector.done.set()
                    try:
                        self._send({"id": request_id, "error": {
                            "code": -32601,
                            "message": "CrossAudit allows text completions only"}})
                    except ConfigDenial:
                        pass
                    continue
                with self._state_lock:
                    waiter = self._pending.get(request_id)
                if waiter:
                    waiter.put(message)
                continue
            with self._notification_signal:
                self._notifications.append(message)
                if len(self._notifications) > 256:
                    del self._notifications[:-256]
                collectors = list(self._collectors.values())
                self._notification_signal.notify_all()
            for collector in collectors:
                collector.accept(message)
        reason = "the official Codex runtime stopped unexpectedly"
        with self._state_lock:
            if self._proc is not proc:
                return
            pending = list(self._pending.values())
            collectors = list(self._collectors.values())
        for waiter in pending:
            waiter.put({"error": {"message": reason}})
        for collector in collectors:
            collector.error = reason
            collector.status = "failed"
            collector.done.set()

    def _send(self, message: dict) -> None:
        proc = self._proc
        if not proc or proc.poll() is not None or not proc.stdin:
            raise ConfigDenial("the official Codex runtime is not running")
        with self._write_lock:
            try:
                proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise ConfigDenial("the official Codex runtime connection closed") from exc

    def notify(self, method: str, params: dict) -> None:
        self._send({"method": method, "params": params})

    def call(self, method: str, params: dict | None, *, timeout: float = 30) -> dict:
        if method != "initialize":
            self._start()
        with self._state_lock:
            request_id = self._next_id
            self._next_id += 1
            waiter: queue.Queue = queue.Queue(maxsize=1)
            self._pending[request_id] = waiter
        try:
            message = {"method": method, "id": request_id}
            if params is not None:
                message["params"] = params
            self._send(message)
            try:
                response = waiter.get(timeout=timeout)
            except queue.Empty as exc:
                raise ProviderDenial(
                    f"the official Codex runtime did not answer {method!r} in time",
                    category="timeout", retryable=True) from exc
            if response.get("error"):
                error = response["error"]
                detail = (error.get("message") if isinstance(error, dict) else str(error))
                raise ProviderDenial(
                    f"the official Codex runtime refused {method!r}: {detail}",
                    category="provider")
            result = response.get("result")
            return result if isinstance(result, dict) else {}
        finally:
            with self._state_lock:
                self._pending.pop(request_id, None)

    def account(self, *, refresh: bool = False) -> dict:
        result = self.call("account/read", {"refreshToken": refresh}, timeout=20)
        account = result.get("account") or {}
        auth_type = str(account.get("type", "")) if account else ""
        connected = auth_type.casefold() == "chatgpt"
        # Deliberate allowlist: tokens and opaque credential material can never
        # reach CrossAudit's HTTP UI even if a future protocol adds them.
        return {
            "available": True,
            "connected": connected,
            "type": auth_type,
            "email": str(account.get("email", ""))[:320] if account else "",
            "plan": str(account.get("planType", ""))[:80] if account else "",
            **({"detail": "The official Codex runtime is using API-key login; "
                           "choose Connect to use a ChatGPT subscription."}
               if account and not connected else {}),
        }

    def model_catalog(self) -> list[dict]:
        result = self.call(
            "model/list", {"limit": 100, "includeHidden": False}, timeout=30)
        rows = result.get("data") or []
        return [row for row in rows if isinstance(row, dict)]

    def models(self) -> list[str]:
        found = []
        for row in self.model_catalog():
            model = row.get("id") or row.get("model")
            if isinstance(model, str) and model and model not in found:
                found.append(model)
        return found

    def start_login(self) -> dict:
        result = self.call("account/login/start", {
            "type": "chatgpt", "appBrand": "codex",
            "codexStreamlinedLogin": False,
            "useHostedLoginSuccessPage": True,
        }, timeout=30)
        auth_url = str(result.get("authUrl", ""))
        host = (urlparse(auth_url).hostname or "").casefold()
        if host not in {"chatgpt.com", "auth.openai.com"}:
            raise ProviderDenial(
                "the official Codex runtime returned an unexpected login origin",
                category="boundary")
        return result

    def wait_login(self, login_id: str, timeout: float = 600) -> dict:
        deadline = time.monotonic() + timeout
        with self._notification_signal:
            while True:
                for message in reversed(self._notifications):
                    if message.get("method") != "account/login/completed":
                        continue
                    params = message.get("params") or {}
                    if params.get("loginId") == login_id:
                        return dict(params)
                left = deadline - time.monotonic()
                if left <= 0:
                    return {"success": False, "error": "ChatGPT authorization timed out"}
                self._notification_signal.wait(min(left, 5))

    def complete(self, *, model: str, system: str, prompt: str,
                 reasoning_effort: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT_S) -> Reply:
        # Empty, non-project cwd plus disabled network for the model's sandbox:
        # the role receives only the exact prompt CrossAudit constructed.
        cwd = os.environ.get("CROSSAUDIT_CODEX_CWD", "").strip()
        if not cwd:
            cwd = str(Path(os.environ.get("TMPDIR", "/tmp")) / "crossaudit-codex-empty")
        Path(cwd).mkdir(parents=True, exist_ok=True)
        thread = self.call("thread/start", {
            "model": model, "cwd": cwd, "developerInstructions": system,
            "approvalPolicy": "never", "sandbox": "read-only",
            "ephemeral": True,
            "config": {"features.shell_tool": False, "web_search": "disabled"},
        }, timeout=30).get("thread") or {}
        thread_id = str(thread.get("id", ""))
        if not thread_id:
            raise ProviderDenial("the official Codex runtime returned no thread id",
                                 category="response")
        collector = _Collector(thread_id)
        with self._state_lock:
            self._collectors[thread_id] = collector
        request = {"model": model, "system": system, "prompt": prompt,
                   "reasoning_effort": reasoning_effort}
        try:
            turn_params = {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            }
            if reasoning_effort:
                # Current Codex app-server protocol calls this turn-level field
                # `effort`; applying it here leaves the user's global Codex
                # configuration untouched.
                turn_params["effort"] = reasoning_effort
            turn = self.call("turn/start", turn_params,
                             timeout=30).get("turn") or {}
            turn_id = str(turn.get("id", ""))
            if not collector.done.wait(timeout):
                try:
                    if turn_id:
                        self.call("turn/interrupt", {
                            "threadId": thread_id, "turnId": turn_id}, timeout=5)
                except ProviderDenial:
                    pass
                raise ProviderDenial("ChatGPT subscription completion timed out",
                                     category="timeout", retryable=True)
        finally:
            with self._state_lock:
                self._collectors.pop(thread_id, None)
        if collector.forbidden:
            raise ProviderDenial(
                "the subscription agent attempted tools outside CrossAudit's "
                "text-only provider boundary; the round was refused",
                category="boundary")
        if collector.status != "completed":
            raise ProviderDenial(
                "ChatGPT subscription completion failed" +
                (f": {collector.error}" if collector.error else ""),
                category="provider")
        text = "".join(collector.text).strip()
        if not text:
            raise ProviderDenial("ChatGPT subscription returned an empty completion",
                                 category="response")
        request_bytes = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
        return Reply(
            text=text, request_id=collector.turn_id or thread_id,
            request_sha256=hashlib.sha256(request_bytes).hexdigest(),
            response_sha256=hashlib.sha256(text.encode()).hexdigest(),
            raw={"transport": "codex-app-server", "thread": thread_id,
                 "usage": collector.usage})

    def close(self) -> None:
        with self._state_lock:
            proc, self._proc = self._proc, None
            self._initialized = False
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


SERVER = CodexAppServer()
atexit.register(SERVER.close)


def complete(*, model: str, system: str, prompt: str, key_env: str = "",
             base_url: str | None = None, allow_custom: bool = False,
             reasoning_effort: str | None = None) -> Reply:
    """Provider-compatible subscription completion; endpoint/key args are denied."""
    if base_url:
        raise ConfigDenial(
            "ChatGPT subscription access uses the official Codex service and "
            "cannot be redirected to a custom endpoint")
    return SERVER.complete(model=model, system=system, prompt=prompt,
                           reasoning_effort=reasoning_effort)


def account_status() -> dict:
    try:
        return SERVER.account()
    except (ConfigDenial, ProviderDenial) as exc:
        return {"available": False, "connected": False, "type": "", "email": "",
                "plan": "", "detail": exc.reason}


def list_models() -> list[str]:
    account = SERVER.account()
    if not account["connected"]:
        raise ConfigDenial("Sign in with ChatGPT in Settings before refreshing models")
    rows = SERVER.models()
    if not rows:
        raise ConfigDenial("ChatGPT returned no Codex models for this subscription")
    return rows


def list_model_efforts(model: str) -> list[str]:
    """Return effort values advertised for one signed-in Codex model."""
    account = SERVER.account()
    if not account["connected"]:
        raise ConfigDenial("Sign in with ChatGPT in Settings before reading model options")
    for row in SERVER.model_catalog():
        row_model = row.get("id") or row.get("model")
        if row_model != model:
            continue
        found = []
        for item in row.get("supportedReasoningEfforts") or []:
            effort = (item.get("reasoningEffort") if isinstance(item, dict)
                      else item)
            if isinstance(effort, str) and effort and effort not in found:
                found.append(effort)
        return found
    return []
