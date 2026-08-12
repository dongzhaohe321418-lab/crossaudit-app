"""Bounded provider recovery with durable circuit state and explicit routing.

Retries happen inside one provider turn.  They never masquerade as Generator →
Auditor revision rounds.  A fallback is used only when it was configured by the
user, and the configuration loader proves that the two role pools stay vendor-
separated before a build starts.
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from ..config import Config, Role
from ..errors import ConfigDenial, ProviderDenial
from ..usage import enforce_budget
from .registry import NEEDS_KEY, get_provider

STATE_NAME = "provider-resilience.json"
_LOCK = threading.RLock()
_sleep = time.sleep


def generator_role(cfg: Config) -> Role:
    vendor = cfg.generator_vendor or ""
    if vendor.casefold() == "human":
        raise ConfigDenial(
            "this project selected a human generator: make and commit the change, "
            "then run `crossaudit run`")
    provider = os.environ.get("CROSSAUDIT_GENERATOR_PROVIDER") or cfg.generator_provider
    model = os.environ.get("CROSSAUDIT_GENERATOR_MODEL") or cfg.generator_model
    if not provider or not model:
        raise ConfigDenial("the generator provider and model must be configured")
    return Role(
        provider=provider, model=model, vendor=vendor,
        key_env=cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY",
        base_url=(os.environ.get("CROSSAUDIT_GENERATOR_BASE_URL") or
                  cfg.generator_base_url or None),
        reasoning_effort=cfg.generator_reasoning_effort,
        fallbacks=cfg.generator_fallbacks,
    )


def candidates(role: Role) -> tuple[Role, ...]:
    return (role, *role.fallbacks)


def _route(role: Role, *, fallback: bool = False) -> dict:
    return {"vendor": role.vendor, "provider": role.provider, "model": role.model,
            "key_env": role.key_env, "base_url": role.base_url,
            "reasoning_effort": role.reasoning_effort,
            "fallback": fallback}


def route_from_reply(reply, default: Role) -> dict:
    raw = reply.raw if isinstance(reply.raw, dict) else {}
    value = raw.get("_crossaudit_route")
    return value if isinstance(value, dict) else _route(default)


def _path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / STATE_NAME


def _load(cfg: Config) -> dict:
    try:
        value = json.loads(_path(cfg).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save(cfg: Config, value: dict) -> None:
    path = _path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)


def _id(role_name: str, role: Role) -> str:
    # Key variable names are configuration, not credentials. Including the name
    # gives two explicitly configured credentials independent circuit state.
    return "|".join((role_name, role.vendor.casefold(), role.provider,
                     role.model, role.key_env, role.base_url or ""))


def _circuit(cfg: Config, route_id: str) -> dict:
    with _LOCK:
        return dict((_load(cfg).get("routes") or {}).get(route_id) or {})


def _record(cfg: Config, route_id: str, *, success: bool, reason: str = "") -> dict:
    with _LOCK:
        state = _load(cfg)
        routes = state.setdefault("routes", {})
        row = dict(routes.get(route_id) or {})
        if success:
            row = {"failures": 0, "open_until": 0, "last_success": int(time.time()),
                   "last_error": ""}
        else:
            failures = int(row.get("failures", 0)) + 1
            row.update(failures=failures, last_failure=int(time.time()),
                       last_error=reason[:400])
            if failures >= cfg.resilience.circuit_breaker_failures:
                row["open_until"] = time.time() + cfg.resilience.circuit_breaker_cooldown_seconds
        routes[route_id] = row
        _save(cfg, state)
        return row


def snapshot(cfg: Config) -> dict:
    """Non-secret live state for the console."""
    now = time.time()
    rows = []
    for key, value in (_load(cfg).get("routes") or {}).items():
        if not isinstance(value, dict):
            continue
        role_name, vendor, provider, model, _key_env, _base = (key.split("|", 5) + [""] * 6)[:6]
        rows.append({"role": role_name, "vendor": vendor, "provider": provider,
                     "model": model, "failures": int(value.get("failures", 0)),
                     "state": "open" if float(value.get("open_until", 0)) > now else "ready",
                     "retry_in_seconds": max(0, round(float(value.get("open_until", 0)) - now)),
                     "last_error": str(value.get("last_error", ""))[:400]})
    return {"routes": rows, "policy": asdict(cfg.resilience)}


def reset(cfg: Config, role_name: str = "") -> dict:
    """Close circuits after a user repairs credentials or provider settings."""
    with _LOCK:
        state = _load(cfg)
        routes = state.get("routes") or {}
        if role_name:
            routes = {key: value for key, value in routes.items()
                      if not key.startswith(role_name + "|")}
        else:
            routes = {}
        state["routes"] = routes
        _save(cfg, state)
    return snapshot(cfg)


def complete(cfg: Config, role_name: str, primary: Role, *, system: str,
             prompt: str, allow_custom: bool = False,
             on_event: Callable[[str, str, str], None] | None = None):
    """Complete once, with bounded same-route retries and configured fallbacks."""
    enforce_budget(cfg, system=system, prompt=prompt)
    failures: list[dict] = []
    last: ProviderDenial | None = None
    now = time.time()
    available: list[tuple[int, Role]] = []
    open_rows: list[tuple[float, Role]] = []
    for index, role in enumerate(candidates(primary)):
        row = _circuit(cfg, _id(role_name, role))
        open_until = float(row.get("open_until", 0))
        if open_until > now:
            open_rows.append((open_until, role))
        else:
            available.append((index, role))
    if not available:
        wait = max(1, round(min(t for t, _ in open_rows) - now)) if open_rows else 1
        raise ProviderDenial(
            f"all configured {role_name} provider routes are cooling down; retry in {wait}s",
            category="circuit_open", retryable=True, retry_after_seconds=wait,
            status=503)

    for index, role in available:
        route_id = _id(role_name, role)
        if NEEDS_KEY.get(role.provider, True) and not os.environ.get(role.key_env, "").strip():
            reason = f"{role.vendor} credential ${role.key_env} is not configured"
            failures.append({**_route(role, fallback=index > 0), "reason": reason,
                             "category": "authentication"})
            _record(cfg, route_id, success=False, reason=reason)
            if on_event:
                on_event(role_name, "fallback unavailable", reason)
            continue
        fn = get_provider(role.provider)
        for attempt in range(1, cfg.resilience.max_attempts + 1):
            # Renew the run's liveness lease before every attempt: retries
            # and their backoff sleeps are healthy work, and without this a
            # long recovery sequence reads as a silent worker. The handle
            # rides on the caller's event callable (the run shell's
            # emit.heartbeat convention) so this layer needs no knowledge
            # of the journal.
            heartbeat = getattr(on_event, "heartbeat", None)
            if heartbeat is not None:
                heartbeat()
            try:
                if on_event and (attempt > 1 or index > 0):
                    on_event(role_name, "provider recovery",
                             f"{role.vendor}:{role.model} · attempt {attempt}")
                reply = fn(model=role.model, system=system, prompt=prompt,
                           key_env=role.key_env, base_url=role.base_url,
                           allow_custom=allow_custom,
                           reasoning_effort=role.reasoning_effort)
                _record(cfg, route_id, success=True)
                if isinstance(reply.raw, dict):
                    reply.raw["_crossaudit_route"] = _route(role, fallback=index > 0)
                if on_event and index > 0:
                    on_event(role_name, "fallback connected",
                             f"using {role.vendor}:{role.model}")
                return reply
            except ProviderDenial as exc:
                last = exc
                failures.append({**_route(role, fallback=index > 0),
                                 "attempt": attempt, "reason": exc.reason[:500],
                                 "category": exc.detail.get("category", "provider")})
                circuit = _record(cfg, route_id, success=False, reason=exc.reason)
                retryable = bool(exc.detail.get("retryable"))
                opened = float(circuit.get("open_until", 0)) > time.time()
                if not retryable or opened or attempt >= cfg.resilience.max_attempts:
                    break
                supplied = exc.detail.get("retry_after_seconds")
                if isinstance(supplied, (int, float)):
                    delay = min(float(supplied), cfg.resilience.retry_after_cap_seconds)
                else:
                    delay = min(cfg.resilience.initial_backoff_seconds * (2 ** (attempt - 1)),
                                cfg.resilience.max_backoff_seconds)
                delay *= random.uniform(0.9, 1.1)
                if on_event:
                    on_event(role_name, "waiting to retry",
                             f"{role.vendor}:{role.model} · {delay:.1f}s")
                if delay > 0:
                    _sleep(delay)

    last_status = last.detail.get("status") if last else 0
    summary = "; ".join(
        f"{item['vendor']}:{item['model']} — {item['reason'].splitlines()[0]}"
        for item in failures[-4:])
    raise ProviderDenial(
        f"all configured {role_name} provider routes failed. {summary}",
        category="routes_exhausted", retryable=False,
        status=last_status if last_status is not None else 0,
        attempts=failures,
        recovery={"action": "open_project_controls", "role": role_name})
