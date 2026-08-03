"""Non-secret provider connection state for the desktop control plane."""
from __future__ import annotations

import threading
import time
import uuid

from . import app_keys
from .errors import ConfigDenial
from .providers import codex_subscription
from .providers.specs import SPECS


class LoginJobs:
    """Own the browser-login lifecycle without ever receiving OAuth tokens."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: dict | None = None

    def start(self, vendor: str, method: str, notify) -> dict:
        if (vendor, method) != ("openai", "chatgpt"):
            detail = (SPECS.get(vendor).subscription_detail
                      if vendor in SPECS else "that provider login method is not supported")
            raise ConfigDenial(detail)
        account = codex_subscription.account_status()
        if account.get("connected"):
            return {"connected": True, "provider": "openai",
                    "method": "chatgpt"}
        with self._lock:
            if self._job and self._job.get("status") == "running":
                return {"job": self._job["id"]}
        result = codex_subscription.SERVER.start_login()
        login_id = str(result.get("loginId", ""))
        auth_url = str(result.get("authUrl", ""))
        if not login_id or not auth_url.startswith("https://"):
            raise ConfigDenial("the official Codex runtime returned no safe login URL")
        row = {
            "id": uuid.uuid4().hex[:12], "provider": "openai",
            "method": "chatgpt", "status": "running",
            "detail": "Complete sign in in your browser", "url": auth_url,
            "started": time.time(), "login_id": login_id,
        }
        with self._lock:
            self._job = row

        def work() -> None:
            result = codex_subscription.SERVER.wait_login(login_id)
            account = codex_subscription.account_status()
            with self._lock:
                if result.get("success") and account.get("connected"):
                    row.update(status="complete", detail="ChatGPT connected",
                               account={k: account.get(k, "")
                                        for k in ("email", "plan", "type")},
                               finished=time.time())
                else:
                    row.update(status="failed",
                               detail=str(result.get("error") or
                                          "ChatGPT authorization was not completed")[:300],
                               finished=time.time())
            invalidate()
            notify()

        threading.Thread(target=work, daemon=True).start()
        notify()
        return {"job": row["id"], "url": auth_url}

    def snapshot(self) -> dict | None:
        with self._lock:
            if not self._job:
                return None
            return {k: v for k, v in self._job.items() if k != "login_id"}


LOGINS = LoginJobs()

_STATUS_LOCK = threading.Lock()
_STATUS_CACHE: tuple[float, dict] | None = None


def invalidate() -> None:
    global _STATUS_CACHE
    with _STATUS_LOCK:
        _STATUS_CACHE = None


def status(*, force: bool = False) -> dict:
    global _STATUS_CACHE
    now = time.monotonic()
    with _STATUS_LOCK:
        if not force and _STATUS_CACHE and now - _STATUS_CACHE[0] < 2:
            return _STATUS_CACHE[1]
    keys = app_keys.status()
    chatgpt = codex_subscription.account_status()
    result = {}
    for vendor, spec in SPECS.items():
        has_key = bool(keys.get(vendor, {}).get("configured"))
        result[vendor] = {
            "label": spec.label,
            "configured": has_key,
            "api_key": {"configured": has_key},
            "console_url": spec.console_url,
            "docs_url": spec.api_docs_url,
            "subscription": {"supported": False,
                             "detail": spec.subscription_detail},
        }
    result["openai"]["chatgpt"] = chatgpt
    result["openai"]["configured"] = (
        result["openai"]["configured"] or bool(chatgpt.get("connected")))
    with _STATUS_LOCK:
        _STATUS_CACHE = (now, result)
    return result


def ready(vendor: str, method: str) -> bool:
    if method == "chatgpt":
        state = status().get(vendor, {})
        return bool(state.get("chatgpt", {}).get("connected"))
    if method == "api":
        # Environment changes are immediate (including test isolation and a key
        # just written in Settings); do not make readiness wait on the UI cache.
        return bool(app_keys.status().get(vendor, {}).get("configured"))
    return False


def provider_for(vendor: str, method: str) -> str:
    if vendor == "openai" and method == "chatgpt":
        return "openai_codex"
    if method != "api":
        raise ConfigDenial(f"{vendor} does not support connection {method!r}")
    try:
        return SPECS[vendor].provider
    except KeyError:
        raise ConfigDenial(f"unsupported provider vendor {vendor!r}") from None
