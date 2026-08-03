"""OpenAI-compatible chat completions.

One adapter reaches OpenAI and every service that speaks the same route. The
compatibility promised is narrow and versioned: a non-streaming JSON
request/reply with a system and a user message. It is not a promise about any
provider's extensions, and `base_url` is opt-in precisely because "compatible"
says nothing about who is on the other end.
"""
from __future__ import annotations

from ..errors import ProviderDenial
from .base import Reply, egress_check, read_key, request_json, sha256_text

BUILTIN_ORIGIN = "https://api.openai.com"


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
             max_tokens: int = 4096, timeout: float = 120.0) -> Reply:
    origin = (base_url or BUILTIN_ORIGIN).rstrip("/")
    url = f"{origin}/v1/chat/completions"
    egress_check(url, builtin_origin=BUILTIN_ORIGIN, allow_custom=allow_custom,
                 allow_insecure_localhost=True)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
    }
    # GPT-5 and o-series models only accept their default temperature. Omitting
    # the field preserves that default; legacy chat models retain deterministic
    # temperature=0 behaviour.
    if not _uses_modern_completion_controls(model):
        payload["temperature"] = 0
    payload[_completion_token_parameter(
        model, builtin_openai=origin == BUILTIN_ORIGIN)] = max_tokens
    headers = {"authorization": f"Bearer {read_key(key_env)}"}
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
