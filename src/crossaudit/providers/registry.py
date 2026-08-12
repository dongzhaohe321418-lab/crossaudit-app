"""Provider lookup. Unknown names deny; they never fall back to a default."""
from __future__ import annotations

from functools import partial
from typing import Callable

from .. import __version__
from ..errors import ConfigDenial
from . import anthropic, codex_subscription, openai_compat, replay
from .specs import SPECS, endpoints

_PROVIDERS: dict[str, Callable[..., object]] = {
    "anthropic": anthropic.complete,
    "openai_codex": codex_subscription.complete,
    "openai_compat": openai_compat.complete,
    "replay": replay.complete,
}
for _vendor, _spec in SPECS.items():
    if _vendor not in {"openai", "anthropic"}:
        _PROVIDERS[_spec.provider] = partial(
            openai_compat.complete, _builtin_base=_spec.api_base,
            _official_bases=tuple(row[2] for row in endpoints(_vendor)),
            _temperature=(1.0 if _vendor == "minimax" else 0),
            _vendor=_vendor,
            _extra_headers=({"x-goog-api-client": f"crossaudit/{__version__}"}
                            if _vendor == "google" else None))

#: Providers that make no external claim about a model's judgement.
NON_EVIDENTIAL = frozenset({"replay"})

#: Providers that authenticate with a key. The replay provider reads a local
#: transcript and needs none, so its absence must not demote a run to offline.
NEEDS_KEY = {name: name not in {"openai_codex", "replay"}
             for name in _PROVIDERS}


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)


def known() -> frozenset[str]:
    """Registered provider names, for callers that gate on them.

    Gatekeepers (doctor's preflight) must ask the registry rather than keep a
    private allowlist: a copy goes stale the release after a vendor registers,
    and then fails configurations that init created and build runs."""
    return frozenset(_PROVIDERS)


def get_provider(name: str) -> Callable[..., object]:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ConfigDenial(f"unknown provider {name!r}; available: {list_providers()}",
                           provider=name) from None
