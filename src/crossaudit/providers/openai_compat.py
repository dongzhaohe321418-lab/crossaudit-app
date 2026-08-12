"""OpenAI-compatible chat completions.

One adapter reaches OpenAI and every service that speaks the same route. The
compatibility promised is narrow and versioned: a non-streaming JSON
request/reply with a system and a user message. It is not a promise about any
provider's extensions, and `base_url` is opt-in precisely because "compatible"
says nothing about who is on the other end.
"""
from __future__ import annotations

from urllib.parse import urlparse

from ..errors import ProviderDenial
from .base import Reply, egress_check, read_key, request_json, sha256_text
from .specs import capability_card

BUILTIN_ORIGIN = "https://api.openai.com"
BUILTIN_BASE = "https://api.openai.com/v1"


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _api_base(value: str) -> str:
    """Normalise SDK-style base URLs without doubling a version segment."""
    value = value.rstrip("/")
    return value + "/v1" if not urlparse(value).path.rstrip("/") else value


def _denial_text(exc: ProviderDenial) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return f"{exc.reason}\n{detail.get('detail', '')}".lower()


def _request(url: str, payload: dict, headers: dict, timeout: float, *,
             repair: bool = True):
    """POST once, repairing a named request-control incompatibility.

    ``repair`` is False for a built-in provider's recognised model: its
    capability card already chose the token field and whether to send a
    temperature, so there is nothing to guess and no unsupported-parameter 400
    to recover from.  Custom endpoints keep the single send-reject-swap retry,
    which is the only sound way to reconcile an origin whose capabilities are
    not declared here.
    """
    try:
        return request_json(url, payload, headers, timeout=timeout)
    except ProviderDenial as exc:
        if not repair:
            raise
        said = _denial_text(exc)
        retry = dict(payload)
        changed = False
        if ("temperature" in retry and "temperature" in said
                and any(word in said for word in
                        ("deprecated", "unsupported", "not support",
                         "only the default"))):
            retry.pop("temperature", None)
            changed = True
        elif ("max_tokens" in retry and "max_tokens" in said
              and "max_completion_tokens" in said):
            retry["max_completion_tokens"] = retry.pop("max_tokens")
            changed = True
        elif ("max_completion_tokens" in retry
              and "use 'max_tokens' instead" in said):
            retry["max_tokens"] = retry.pop("max_completion_tokens")
            changed = True
        if not changed:
            raise
        return request_json(url, retry, headers, timeout=timeout)


def complete(*, model: str, system: str, prompt: str, key_env: str,
             base_url: str | None = None, allow_custom: bool = False,
             max_tokens: int = 4096, timeout: float = 120.0,
             reasoning_effort: str | None = None,
             _builtin_base: str = BUILTIN_BASE,
             _extra_headers: dict[str, str] | None = None,
             _official_bases: tuple[str, ...] = (),
             _temperature: float | None = 0,
             _vendor: str = "openai") -> Reply:
    api_base = _api_base(base_url) if base_url else _builtin_base.rstrip("/")
    builtin_origin = _origin(_builtin_base)
    url = f"{api_base}/chat/completions"
    official = {_api_base(value) for value in (_official_bases or (_builtin_base,))}
    is_builtin = api_base in official
    trusted_origin = _origin(api_base) if is_builtin else builtin_origin
    egress_check(url, builtin_origin=trusted_origin,
                 allow_custom=allow_custom and not is_builtin,
                 allow_insecure_localhost=True)
    # One capability record decides the request shape. On a built-in origin a
    # recognised model sends exactly what it supports; a custom endpoint has no
    # card, so the family-based guess plus the send-reject-swap retry stand in.
    card = capability_card(_vendor, model, official=is_builtin)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
    }
    # Modern reasoning models accept only their default temperature; the card
    # withholds the field for them. Models that do take one keep deterministic
    # temperature=0 (1.0 where a vendor mandates it).
    if card.temperature and _temperature is not None:
        payload["temperature"] = _temperature
    if reasoning_effort:
        # The caller supplies this only after provider/model capability
        # validation. An explicit choice is never silently removed on HTTP 400.
        payload["reasoning_effort"] = reasoning_effort
    payload[card.token_param] = max_tokens
    headers = {"authorization": f"Bearer {read_key(key_env)}",
               **(_extra_headers or {})}
    data, rid = _request(url, payload, headers, timeout, repair=card.compat_retry)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderDenial(f"unexpected chat-completions response shape: {exc}") from exc
    if not text.strip():
        raise ProviderDenial("provider returned an empty completion")
    return Reply(text=text, request_id=rid or data.get("id"),
                 request_sha256=sha256_text(system + "\n" + prompt),
                 response_sha256=sha256_text(text), raw={"usage": data.get("usage", {})})
