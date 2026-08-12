"""Local, privacy-preserving token metering and API-value estimates.

The ledger contains counts and routing metadata only.  Prompts, completions,
provider request ids, and credentials deliberately never enter it.  Token
counts are provider-reported when available and explicitly marked as estimates
when an OpenAI-compatible endpoint omits usage.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .errors import ProviderDenial
from .providers.base import Reply

try:  # Unix advisory locking.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised by Windows CI
    _fcntl = None

try:  # Windows advisory locking.
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised by Unix CI
    _msvcrt = None

LEDGER_NAME = "usage.jsonl"
PRICE_SNAPSHOT = "2026-08-03"
_WRITE_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_SUMMARY_CACHE: dict[str, tuple[tuple, dict]] = {}
_LISTENERS: list[Callable[[], None]] = []


def _lock_file(fd: int) -> bool:
    """Serialize ledger appends across app and CLI processes."""
    if _fcntl is not None:
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        return True
    if _msvcrt is not None:
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_LOCK, 1)
        return True
    return False


def _unlock_file(fd: int) -> None:
    if _fcntl is not None:
        _fcntl.flock(fd, _fcntl.LOCK_UN)
    elif _msvcrt is not None:
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)


def subscribe(listener: Callable[[], None]) -> None:
    """Wake live views immediately after a new usage event is durable."""
    with _CACHE_LOCK:
        _LISTENERS.append(listener)


@dataclass(frozen=True)
class Rates:
    """USD per one million tokens."""

    input: float
    output: float
    cache_write: float
    cache_read: float


# Public list prices at PRICE_SNAPSHOT.  Matching is intentionally conservative:
# unknown models retain exact token counts but never receive an invented price.
_PRICES: tuple[tuple[str, Rates], ...] = (
    ("gpt-5.6-sol", Rates(5.0, 30.0, 6.25, 0.50)),
    ("gpt-5.6-terra", Rates(2.5, 15.0, 3.125, 0.25)),
    ("gpt-5.6-luna", Rates(1.0, 6.0, 1.25, 0.10)),
    ("claude-fable-5", Rates(10.0, 50.0, 12.50, 1.00)),
    ("claude-mythos-5", Rates(10.0, 50.0, 12.50, 1.00)),
    ("claude-opus-5", Rates(5.0, 25.0, 6.25, 0.50)),
    ("claude-opus-4-8", Rates(5.0, 25.0, 6.25, 0.50)),
    ("claude-opus-4-7", Rates(5.0, 25.0, 6.25, 0.50)),
    ("claude-opus-4-6", Rates(5.0, 25.0, 6.25, 0.50)),
    ("claude-opus-4-5", Rates(5.0, 25.0, 6.25, 0.50)),
    ("claude-sonnet-5", Rates(3.0, 15.0, 3.75, 0.30)),
    ("claude-sonnet-4-6", Rates(3.0, 15.0, 3.75, 0.30)),
    ("claude-sonnet-4-5", Rates(3.0, 15.0, 3.75, 0.30)),
    ("claude-haiku-4-5", Rates(1.0, 5.0, 1.25, 0.10)),
)


def _nonnegative(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _rates(model: str) -> Rates | None:
    lowered = model.casefold()
    for prefix, rates in _PRICES:
        if lowered == prefix or lowered.startswith(prefix + "-"):
            return rates
    return None


def normalise_usage(raw: dict, *, system: str = "", prompt: str = "",
                    response: str = "") -> dict:
    """Return one stable token vocabulary from OpenAI, Anthropic, or Codex."""
    usage = raw.get("usage") if isinstance(raw, dict) else None
    usage = usage if isinstance(usage, dict) else {}

    # Codex App Server tokenUsage.last uses camelCase and counts cached input in
    # inputTokens. OpenAI Chat Completions does the same in prompt_tokens.
    if any(k in usage for k in ("inputTokens", "outputTokens", "totalTokens")):
        inclusive = _nonnegative(usage.get("inputTokens"))
        cache_read = _nonnegative(usage.get("cachedInputTokens"))
        cache_write = _nonnegative(usage.get("cacheWriteInputTokens"))
        counts = {
            # Both cache classes are subsets of inputTokens. Keeping the four
            # buckets mutually exclusive makes their sum equal totalTokens.
            "input": max(0, inclusive - cache_read - cache_write),
            "output": _nonnegative(usage.get("outputTokens")),
            "cache_write": cache_write,
            "cache_read": cache_read,
        }
        method = "reported"
    elif any(k in usage for k in ("prompt_tokens", "completion_tokens")):
        details = usage.get("prompt_tokens_details")
        details = details if isinstance(details, dict) else {}
        inclusive = _nonnegative(usage.get("prompt_tokens"))
        cache_read = _nonnegative(details.get("cached_tokens"))
        counts = {
            "input": max(0, inclusive - cache_read),
            "output": _nonnegative(usage.get("completion_tokens")),
            "cache_write": 0,
            "cache_read": cache_read,
        }
        method = "reported"
    elif any(k in usage for k in ("input_tokens", "output_tokens")):
        counts = {
            "input": _nonnegative(usage.get("input_tokens")),
            "output": _nonnegative(usage.get("output_tokens")),
            "cache_write": _nonnegative(usage.get("cache_creation_input_tokens")),
            "cache_read": _nonnegative(usage.get("cache_read_input_tokens")),
        }
        method = "reported"
    else:
        # A transparent fallback for compatible/self-hosted endpoints. This is
        # deliberately approximate and is never presented as provider-reported.
        counts = {
            "input": math.ceil((len(system) + len(prompt)) / 4),
            "output": math.ceil(len(response) / 4),
            "cache_write": 0,
            "cache_read": 0,
        }
        method = "estimated"
    counts["total"] = sum(counts.values())
    counts["method"] = method
    return counts


def _api_value(counts: dict, rates: Rates | None) -> float | None:
    if rates is None:
        return None
    value = (
        counts["input"] * rates.input
        + counts["output"] * rates.output
        + counts["cache_write"] * rates.cache_write
        + counts["cache_read"] * rates.cache_read
    ) / 1_000_000
    return round(value, 10)


def _is_official(provider: str, base_url: str | None) -> bool:
    if provider == "openai_codex":
        return True
    if base_url:
        # Configured base URLs carry paths ("https://api.openai.com/v1"), so a
        # whole-string comparison would treat even the official endpoint as a
        # third-party proxy and silently drop it to "unpriced". Only the
        # origin decides who bills the call; anything else stays unpriced.
        parts = urlsplit(base_url)
        origin = f"{parts.scheme}://{parts.netloc}".casefold()
        return origin in {"https://api.openai.com", "https://api.anthropic.com"}
    return provider in {"openai_compat", "anthropic"}


def record_reply(*, root: Path, state_dir: str, role: str, phase: str,
                 vendor: str, provider: str, model: str, reply: Reply,
                 system: str, prompt: str, base_url: str | None = None) -> dict:
    """Append a completion's metadata, returning the exact persisted event."""
    counts = normalise_usage(reply.raw, system=system, prompt=prompt,
                             response=reply.text)
    rates = _rates(model) if _is_official(provider, base_url) else None
    subscription = provider == "openai_codex"
    event = {
        "v": 1,
        "id": uuid.uuid4().hex,
        "t": int(time.time() * 1000),
        "role": role,
        "phase": phase,
        "vendor": vendor,
        "provider": provider,
        "model": model,
        **counts,
        "api_value_usd": _api_value(counts, rates),
        "billing_kind": ("subscription_api_value" if subscription and rates
                         else "api_value" if rates else "unpriced"),
        "price_snapshot": PRICE_SNAPSHOT,
    }
    path = root / state_dir / LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    with _WRITE_LOCK:
        fd = os.open(path, flags, 0o600)
        locked = False
        try:
            # CLI and app workers are separate processes. O_APPEND protects the
            # offset; an advisory lock plus a complete write protects the record.
            locked = _lock_file(fd)
            os.chmod(path, 0o600)
            pending = memoryview(line.encode("utf-8"))
            while pending:
                written = os.write(fd, pending)
                if written <= 0:
                    raise OSError("usage ledger write made no progress")
                pending = pending[written:]
            os.fsync(fd)
        finally:
            if locked:
                _unlock_file(fd)
            os.close(fd)
    with _CACHE_LOCK:
        _SUMMARY_CACHE.pop(str(path), None)
        listeners = tuple(_LISTENERS)
    for listener in listeners:
        try:
            listener()
        except Exception:
            # Metering can wake a UI, but a view listener can never be allowed
            # to turn a successful provider completion into a failed task.
            continue
    return event


def record_completion(**kwargs) -> dict | None:
    """Best-effort application hook: metering must not invalidate model work.

    The explicit ``record_reply`` API still raises for diagnostics and tests.
    Production completion paths use this wrapper because a full disk or a
    permissions problem in local analytics is not an audit-integrity failure.
    """
    try:
        return record_reply(**kwargs)
    except (OSError, ValueError, TypeError):
        return None


def _blank() -> dict:
    return {"calls": 0, "input": 0, "output": 0, "cache_write": 0,
            "cache_read": 0, "tokens": 0, "api_value_usd": 0.0,
            "reported_calls": 0, "estimated_calls": 0, "unpriced_calls": 0}


def _add(bucket: dict, event: dict) -> None:
    bucket["calls"] += 1
    for key in ("input", "output", "cache_write", "cache_read"):
        bucket[key] += _nonnegative(event.get(key))
    bucket["tokens"] += _nonnegative(event.get("total"))
    value = event.get("api_value_usd")
    if isinstance(value, (int, float)) and math.isfinite(value):
        bucket["api_value_usd"] += value
    if event.get("method") == "reported":
        bucket["reported_calls"] += 1
    else:
        bucket["estimated_calls"] += 1
    if value is None:
        bucket["unpriced_calls"] += 1


def _finish(bucket: dict) -> dict:
    bucket["api_value_usd"] = round(bucket["api_value_usd"], 8)
    return bucket


def _budget_view(cfg, today: dict, month: dict) -> dict:
    policy = getattr(cfg, "budgets", None)
    if policy is None:
        return {"state": "unconfigured", "warnings": [], "blocked": False}
    warnings: list[str] = []
    reasons: list[str] = []
    daily_tokens = int(today.get("tokens", 0))
    month_cost = float(month.get("api_value_usd", 0.0))
    unpriced = int(month.get("unpriced_calls", 0))
    if policy.daily_token_warning and daily_tokens >= policy.daily_token_warning:
        warnings.append(
            f"Daily usage reached {daily_tokens:,} tokens (warning {policy.daily_token_warning:,}).")
    if policy.daily_token_limit and daily_tokens >= policy.daily_token_limit:
        reasons.append(
            f"Daily token limit reached: {daily_tokens:,} / {policy.daily_token_limit:,}.")
    if policy.monthly_cost_warning_usd and month_cost >= policy.monthly_cost_warning_usd:
        warnings.append(
            f"Monthly API value reached ${month_cost:.2f} "
            f"(warning ${policy.monthly_cost_warning_usd:.2f}).")
    if policy.monthly_cost_limit_usd:
        if unpriced:
            reasons.append(
                "The monthly cost limit cannot be proven because one or more calls use "
                "an unpriced model. Remove the cost limit or select priced models.")
        elif month_cost >= policy.monthly_cost_limit_usd:
            reasons.append(
                f"Monthly API-value limit reached: ${month_cost:.2f} / "
                f"${policy.monthly_cost_limit_usd:.2f}.")
    configured = any((policy.daily_token_warning, policy.daily_token_limit,
                      policy.monthly_cost_warning_usd,
                      policy.monthly_cost_limit_usd))
    return {
        "state": "blocked" if reasons else "warning" if warnings else
                 "ok" if configured else "unconfigured",
        "warnings": warnings,
        "reasons": reasons,
        "blocked": bool(reasons),
        "daily_tokens": daily_tokens,
        "daily_token_warning": policy.daily_token_warning,
        "daily_token_limit": policy.daily_token_limit,
        "monthly_api_value_usd": round(month_cost, 8),
        "monthly_cost_warning_usd": policy.monthly_cost_warning_usd,
        "monthly_cost_limit_usd": policy.monthly_cost_limit_usd,
        "unpriced_calls": unpriced,
    }


def enforce_budget(cfg, *, system: str = "", prompt: str = "") -> dict:
    """Refuse a new provider call after a configured hard guardrail is reached."""
    view = summary(cfg).get("budget", {})
    if view.get("blocked"):
        raise ProviderDenial(
            "Local usage guardrail paused provider calls. " + " ".join(view["reasons"])
            + " Open Project controls to raise or clear the limit, then retry.",
            category="budget", retryable=False, budget=view)
    projected_input = math.ceil((len(system) + len(prompt)) / 4)
    limit = view.get("daily_token_limit")
    if limit and int(view.get("daily_tokens", 0)) + projected_input > int(limit):
        projected = dict(view)
        projected.update(blocked=True, state="blocked",
                         projected_input_tokens=projected_input)
        reason = (f"The next request is estimated to exceed the daily token limit: "
                  f"{int(view.get('daily_tokens', 0)):,} used + approximately "
                  f"{projected_input:,} input > {int(limit):,}.")
        projected["reasons"] = [*view.get("reasons", []), reason]
        raise ProviderDenial(
            "Local usage guardrail paused provider calls. " + reason
            + " Open Project controls to raise or clear the limit, then retry.",
            category="budget", retryable=False, budget=projected)
    return view


def summary(cfg) -> dict:
    """Aggregate one project's local ledger for the live console snapshot."""
    path = cfg.root / cfg.state_dir / LEDGER_NAME
    now = datetime.now().astimezone()
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size, now.date().toordinal())
    except OSError:
        signature = (0, 0, now.date().toordinal())
    policy = getattr(cfg, "budgets", None)
    signature += tuple(getattr(policy, name, None) for name in (
        "daily_token_warning", "daily_token_limit", "monthly_cost_warning_usd",
        "monthly_cost_limit_usd"))
    cache_key = str(path)
    with _CACHE_LOCK:
        cached = _SUMMARY_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return cached[1]

    events: list[dict] = []
    malformed = 0
    if signature[:2] != (0, 0):
        try:
            with path.open(encoding="utf-8") as source:
                for line in source:
                    try:
                        item = json.loads(line)
                        if isinstance(item, dict):
                            events.append(item)
                        else:
                            malformed += 1
                    except (ValueError, TypeError):
                        malformed += 1
        except OSError:
            events = []

    today = now.date()
    month = (now.year, now.month)
    today_total, month_total, all_total = _blank(), _blank(), _blank()
    days = {today - timedelta(days=i): _blank() for i in range(6, -1, -1)}
    roles: dict[str, dict] = defaultdict(_blank)
    models: dict[tuple[str, str, str], dict] = defaultdict(_blank)
    recent: list[dict] = []
    for event in events:
        _add(all_total, event)
        try:
            when = datetime.fromtimestamp(int(event.get("t", 0)) / 1000,
                                         tz=now.tzinfo)
        except (TypeError, ValueError, OSError, OverflowError):
            continue
        if when.date() == today:
            _add(today_total, event)
        if (when.year, when.month) == month:
            _add(month_total, event)
            role = str(event.get("role", "unknown"))[:40]
            _add(roles[role], event)
            key = (str(event.get("model", "unknown"))[:160], role,
                   str(event.get("provider", "unknown"))[:80])
            _add(models[key], event)
        if when.date() in days:
            _add(days[when.date()], event)
        recent.append({
            "t": int(event.get("t", 0) or 0),
            "role": str(event.get("role", "unknown"))[:40],
            "phase": str(event.get("phase", "completion"))[:80],
            "provider": str(event.get("provider", "unknown"))[:80],
            "model": str(event.get("model", "unknown"))[:160],
            "input": _nonnegative(event.get("input")),
            "output": _nonnegative(event.get("output")),
            "cache_write": _nonnegative(event.get("cache_write")),
            "cache_read": _nonnegative(event.get("cache_read")),
            "tokens": _nonnegative(event.get("total")),
            "method": "reported" if event.get("method") == "reported" else "estimated",
            "api_value_usd": event.get("api_value_usd"),
            "billing_kind": str(event.get("billing_kind", "unpriced")),
        })
    model_rows = []
    for (model, role, provider), value in models.items():
        model_rows.append({"model": model, "role": role, "provider": provider,
                           **_finish(value)})
    model_rows.sort(key=lambda row: (-row["tokens"], row["model"], row["role"]))
    result = {
        "today": _finish(today_total),
        "month": _finish(month_total),
        "all": _finish(all_total),
        "days": [{"date": day.isoformat(), **_finish(value)}
                 for day, value in days.items()],
        "roles": [{"role": role, **_finish(value)}
                  for role, value in sorted(roles.items())],
        "models": model_rows,
        "recent": sorted(recent, key=lambda row: row["t"], reverse=True)[:30],
        "price_snapshot": PRICE_SNAPSHOT,
        "malformed_lines": malformed,
        "local_only": True,
        "cost_label": "API-value estimate",
    }
    result["budget"] = _budget_view(cfg, result["today"], result["month"])
    with _CACHE_LOCK:
        _SUMMARY_CACHE[cache_key] = (signature, result)
    return result
