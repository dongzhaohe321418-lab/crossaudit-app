"""Anthropic Messages API, over stdlib urllib."""
from __future__ import annotations

import re

from ..errors import ProviderDenial
from .base import Reply, egress_check, read_key, request_json, sha256_text

BUILTIN_ORIGIN = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


def _supports_temperature(model: str) -> bool:
    """Return whether the model is known to accept an explicit temperature."""
    lowered = model.lower()
    # Opus 4.8 returns a 400 stating that temperature is deprecated. Sonnet
    # 4.6 and Haiku 4.5 still accept it, so generation-number checks alone are
    # not sufficient.
    if lowered.startswith("claude-opus-4-8"):
        return False
    match = re.match(r"^claude-[a-z0-9]+-(\d+)(?:-|$)", lowered)
    return not match or int(match.group(1)) < 5


def _denial_text(exc: ProviderDenial) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return f"{exc.reason}\n{detail.get('detail', '')}".lower()


def _request(url: str, payload: dict, headers: dict, timeout: float):
    """Retry once when Anthropic explicitly rejects an optional control.

    Model capabilities move faster than package releases. A precise HTTP 400
    about ``temperature`` is safe to repair because the provider processed no
    completion; all other errors remain fail-closed.
    """
    try:
        return request_json(url, payload, headers, timeout=timeout)
    except ProviderDenial as exc:
        said = _denial_text(exc)
        rejected_temperature = (
            "temperature" in said
            and any(word in said for word in
                    ("deprecated", "unsupported", "not support", "only the default"))
        )
        if "temperature" not in payload or not rejected_temperature:
            raise
        retry = dict(payload)
        retry.pop("temperature", None)
        return request_json(url, retry, headers, timeout=timeout)


def complete(*, model: str, system: str, prompt: str, key_env: str,
             base_url: str | None = None, allow_custom: bool = False,
             max_tokens: int = 4096, timeout: float = 120.0) -> Reply:
    origin = (base_url or BUILTIN_ORIGIN).rstrip("/")
    url = f"{origin}/v1/messages"
    # Loopback HTTP is useful for explicitly authorised local-compatible
    # providers and end-to-end testing. It still fails the custom-origin check
    # unless the caller opted in, so a configured URL can never redirect a key
    # there by accident.
    egress_check(url, builtin_origin=BUILTIN_ORIGIN, allow_custom=allow_custom,
                 allow_insecure_localhost=True)
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if _supports_temperature(model):
        payload["temperature"] = 0
    headers = {"x-api-key": read_key(key_env), "anthropic-version": API_VERSION}
    data, rid = _request(url, payload, headers, timeout)
    try:
        text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise ProviderDenial(f"unexpected Anthropic response shape: {exc}") from exc
    if not text.strip():
        raise ProviderDenial("Anthropic returned an empty completion")
    return Reply(text=text, request_id=rid or data.get("id"),
                 request_sha256=sha256_text(system + "\n" + prompt),
                 response_sha256=sha256_text(text), raw={"usage": data.get("usage", {})})
