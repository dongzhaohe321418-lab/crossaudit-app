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

BUILTIN_ORIGIN = "https://api.openai.com"
BUILTIN_BASE = "https://api.openai.com/v1"


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _api_base(value: str) -> str:
    """Normalise SDK-style base URLs without doubling a version segment."""
    value = value.rstrip("/")
    return value + "/v1" if not urlparse(value).path.rstrip("/") else value


def _completion_token_parameter(model: str, *, builtin_openai: bool = False) -> str:
    """Return the token-limit field accepted by this OpenAI model family.

    OpenAI's Chat Completions API has replaced ``max_tokens`` with
    ``max_completion_tokens``. Older OpenAI-compatible services generally
    still expect the legacy field, so only apply the API-wide rule to the
    built-in OpenAI origin and keep custom endpoints model-family based.
    """
    if builtin_openai:
        return "max_completion_tokens"
    lowered = model.lower()
    modern_families = ("gpt-5", "o1", "o3", "o4")
    return ("max_completion_tokens" if lowered.startswith(modern_families)
            else "max_tokens")


def _uses_modern_completion_controls(model: str) -> bool:
    lowered = model.lower()
    return lowered.startswith(("gpt-5", "o1", "o3", "o4"))


def _denial_text(exc: ProviderDenial) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return f"{exc.reason}\n{detail.get('detail', '')}".lower()


def _request(url: str, payload: dict, headers: dict, timeout: float):
    """Retry once when the endpoint names a request-control incompatibility."""
    try:
        return request_json(url, payload, headers, timeout=timeout)
    except ProviderDenial as exc:
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
             _temperature: float | None = 0) -> Reply:
    api_base = _api_base(base_url) if base_url else _builtin_base.rstrip("/")
    builtin_origin = _origin(_builtin_base)
    url = f"{api_base}/chat/completions"
    official = {_api_base(value) for value in (_official_bases or (_builtin_base,))}
    trusted_origin = _origin(api_base) if api_base in official else builtin_origin
    egress_check(url, builtin_origin=trusted_origin,
                 allow_custom=allow_custom and api_base not in official,
                 allow_insecure_localhost=True)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
    }
    # GPT-5 and o-series models only accept their default temperature. Omitting
    # the field preserves that default; legacy chat models retain deterministic
    # temperature=0 behaviour.
    if not _uses_modern_completion_controls(model) and _temperature is not None:
        payload["temperature"] = _temperature
    if reasoning_effort:
        # The caller supplies this only after provider/model capability
        # validation. An explicit choice is never silently removed on HTTP 400.
        payload["reasoning_effort"] = reasoning_effort
    payload[_completion_token_parameter(
        model, builtin_openai=(api_base == BUILTIN_BASE))] = max_tokens
    headers = {"authorization": f"Bearer {read_key(key_env)}",
               **(_extra_headers or {})}
    data, rid = _request(url, payload, headers, timeout)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderDenial(f"unexpected chat-completions response shape: {exc}") from exc
    if not text.strip():
        raise ProviderDenial("provider returned an empty completion")
    return Reply(text=text, request_id=rid or data.get("id"),
                 request_sha256=sha256_text(system + "\n" + prompt),
                 response_sha256=sha256_text(text), raw={"usage": data.get("usage", {})})
