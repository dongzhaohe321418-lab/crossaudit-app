"""Live provider model catalogues for setup; static choices remain the fallback."""
from __future__ import annotations

from .base import egress_check, get_json, read_key

CATALOGUES = {
    "openai": ("https://api.openai.com", "/v1/models"),
    "anthropic": ("https://api.anthropic.com", "/v1/models?limit=1000"),
    "google": ("https://generativelanguage.googleapis.com", "/v1beta/openai/models"),
    "deepseek": ("https://api.deepseek.com", "/models"),
}

PREFIXES = {"openai": ("gpt-", "o1", "o3", "o4"),
            "anthropic": ("claude-",), "google": ("gemini-",),
            "deepseek": ("deepseek-",)}
OPENAI_NON_TEXT = ("audio", "image", "realtime", "transcribe", "tts",
                   "search", "whisper", "instruct")


def list_models(vendor: str, key_env: str, *, timeout: float = 20.0) -> list[str]:
    """Return models this exact key can see, never a marketing-era hard limit."""
    if vendor not in CATALOGUES:
        raise ValueError(f"no live model catalogue for {vendor}")
    origin, path = CATALOGUES[vendor]
    url = origin + path
    egress_check(url, builtin_origin=origin, allow_custom=False)
    key = read_key(key_env)
    headers = ({"x-api-key": key, "anthropic-version": "2023-06-01"}
               if vendor == "anthropic" else {"authorization": f"Bearer {key}"})
    data, _ = get_json(url, headers, timeout=timeout)
    rows = data.get("data", data.get("models", [])) if isinstance(data, dict) else []
    found = []
    for row in rows if isinstance(rows, list) else []:
        value = row.get("id") or row.get("name") if isinstance(row, dict) else None
        if isinstance(value, str) and value.strip():
            value = value.removeprefix("models/")
            low = value.lower()
            if (low.startswith(PREFIXES[vendor])
                    and not (vendor == "openai" and
                             any(word in low for word in OPENAI_NON_TEXT))):
                found.append(value)
    return sorted(set(found), key=str.casefold)
