"""Anthropic Messages API, over stdlib urllib."""
from __future__ import annotations

from ..errors import ProviderDenial
from .base import Reply, egress_check, read_key, request_json, sha256_text
from .specs import capability_card

BUILTIN_ORIGIN = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


def _denial_text(exc: ProviderDenial) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return f"{exc.reason}\n{detail.get('detail', '')}".lower()


def _request(url: str, payload: dict, headers: dict, timeout: float, *,
             repair: bool = True):
    """POST once, repairing a rejected temperature only for unknown endpoints.

    A built-in, recognised model never reaches here with a temperature it does
    not accept — its capability card already decided that, so ``repair`` is
    False and the request is not gambled.  Custom endpoints keep the single
    retry: their capabilities are unknown, and a precise HTTP 400 about
    ``temperature`` is safe to repair because the provider processed no
    completion.  All other errors remain fail-closed.
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
        if not repair or "temperature" not in payload or not rejected_temperature:
            raise
        retry = dict(payload)
        retry.pop("temperature", None)
        return request_json(url, retry, headers, timeout=timeout)


def complete(*, model: str, system: str, prompt: str, key_env: str,
             base_url: str | None = None, allow_custom: bool = False,
             max_tokens: int = 4096, timeout: float = 120.0,
             reasoning_effort: str | None = None) -> Reply:
    origin = (base_url or BUILTIN_ORIGIN).rstrip("/")
    url = f"{origin}/v1/messages"
    # Loopback HTTP is useful for explicitly authorised local-compatible
    # providers and end-to-end testing. It still fails the custom-origin check
    # unless the caller opted in, so a configured URL can never redirect a key
    # there by accident.
    egress_check(url, builtin_origin=BUILTIN_ORIGIN, allow_custom=allow_custom,
                 allow_insecure_localhost=True)
    card = capability_card("anthropic", model, official=(origin == BUILTIN_ORIGIN))
    payload = {
        "model": model,
        card.token_param: max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if card.temperature:
        payload["temperature"] = 0
    if reasoning_effort:
        payload["output_config"] = {"effort": reasoning_effort}
    headers = {"x-api-key": read_key(key_env), "anthropic-version": API_VERSION}
    data, rid = _request(url, payload, headers, timeout, repair=card.compat_retry)
    try:
        text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise ProviderDenial(f"unexpected Anthropic response shape: {exc}") from exc
    if not text.strip():
        raise ProviderDenial("Anthropic returned an empty completion")
    return Reply(text=text, request_id=rid or data.get("id"),
                 request_sha256=sha256_text(system + "\n" + prompt),
                 response_sha256=sha256_text(text), raw={"usage": data.get("usage", {})})
