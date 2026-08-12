"""Third-party check packs, loaded only when the deployment names them.

An entry point is arbitrary code execution inside a process that will shortly
hold API keys and write a ledger. Discovery is therefore not automatic: a pack
runs because `plugins:` in crossaudit.yml names it, and the name that was
allowed is what gets loaded — nothing else on the machine.

What a pack may contribute is also bounded. Checks are deterministic by
definition; a "check" that calls a model is a second auditor wearing the
mechanical layer's authority, and I4 says the mechanical layer is the one whose
failure modes are least entangled with any model. Packs declare the API version
they were written against, and a mismatch is refused rather than guessed at.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from ..errors import ConfigDenial

DCL_API_VERSION = 1
_LOADED: dict[str, object] = {}


def load_allowed(allowed: list[str] | None) -> list[str]:
    """Load exactly the named packs. Returns what was newly loaded."""
    if not allowed:
        return []
    from importlib.metadata import entry_points

    available = {ep.name: ep for ep in entry_points(group="crossaudit.checks")}
    loaded = []
    for name in allowed:
        if name in _LOADED:
            continue
        ep = available.get(name)
        if ep is None:
            raise ConfigDenial(
                f"check pack {name!r} is named in plugins: but is not installed; "
                f"available: {sorted(available) or 'none'}")
        pack = ep.load()
        declared = getattr(pack, "DCL_API_VERSION", None)
        if declared != DCL_API_VERSION:
            raise ConfigDenial(
                f"check pack {name!r} declares dcl api {declared!r}, this build "
                f"speaks {DCL_API_VERSION}; refusing rather than guessing")
        register = getattr(pack, "register_checks", None)
        if not callable(register):
            raise ConfigDenial(f"check pack {name!r} exposes no register_checks()")
        register()
        _LOADED[name] = pack
        loaded.append(name)
    return loaded


def loaded_sources() -> list[tuple[str, bytes]]:
    """Source bytes of every loaded pack, tagged by pack name, sorted.

    A pack's checks shape the verdict exactly as the builtin layer's do, so the
    receipt's deterministic-layer digest must cover its implementation — two
    byte-identical receipts must not be able to hide different plugin code. A
    pack whose source cannot be read back (a namespace package, a frozen
    import, code defined at a prompt) cannot be pinned, and a receipt that
    cannot pin the check code that ran must not be minted.
    """
    sources = []
    for name in sorted(_LOADED):
        pack = _LOADED[name]
        module = pack if inspect.ismodule(pack) else inspect.getmodule(pack)
        origin = getattr(module, "__file__", None)
        if not origin:
            raise ConfigDenial(
                f"check pack {name!r} has no source file to hash (namespace or "
                f"frozen import); refusing to mint a receipt that cannot pin "
                f"the check code that ran")
        try:
            data = Path(origin).read_bytes()
        except OSError as exc:
            raise ConfigDenial(
                f"check pack {name!r} source at {origin} is unreadable ({exc}); "
                f"refusing to mint a receipt that cannot pin the check code "
                f"that ran") from exc
        sources.append((f"plugin:{name}:{Path(origin).name}", data))
    return sources
