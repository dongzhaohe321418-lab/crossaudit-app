"""Live provider model catalogues for setup; static choices remain the fallback."""
from __future__ import annotations

from .base import egress_check, get_json, read_key
from .specs import SPECS, endpoint


def list_models(vendor: str, key_env: str, *, endpoint_id: str = "",
                timeout: float = 20.0) -> list[str]:
    """Return models this exact key can see, never a marketing-era hard limit."""
    if vendor not in SPECS:
        raise ValueError(f"no live model catalogue for {vendor}")
    spec = SPECS[vendor]
    _id, _label, api_base, url = endpoint(vendor, endpoint_id)
    origin = api_base.split("/", 3)[:3]
    origin = "/".join(origin)
    egress_check(url, builtin_origin=origin, allow_custom=False)
    key = read_key(key_env)
    if spec.auth == "anthropic":
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    elif spec.auth == "google":
        headers = {"x-goog-api-key": key}
    else:
        headers = {"authorization": f"Bearer {key}"}
    data, _ = get_json(url, headers, timeout=timeout)
    rows = (data.get("data", data.get("models", []))
            if isinstance(data, dict) else data if isinstance(data, list) else [])
    found = []
    for row in rows if isinstance(rows, list) else []:
        value = row.get("id") or row.get("name") if isinstance(row, dict) else None
        if isinstance(value, str) and value.strip():
            value = value.removeprefix("models/")
            low = value.lower()
            actions = row.get("supportedGenerationMethods", [])
            if (vendor == "google" and actions and
                    "generateContent" not in actions):
                continue
            capabilities = row.get("capabilities", {})
            if (isinstance(capabilities, dict)
                    and capabilities.get("completion_chat") is False):
                continue
            if row.get("archived") is True or row.get("active") is False:
                continue
            if ((not spec.prefixes or low.startswith(spec.prefixes))
                    and not any(word in low for word in spec.exclude)):
                found.append(value)
    return sorted(set(found), key=str.casefold)
