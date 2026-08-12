"""One audit cycle: DCL, model audit, verdict synthesis, report, receipt.

Verdict synthesis is code, never model output (I4), and every path that is not
a clean, valid, model-backed PASS lands somewhere other than PASS (I8):

    escalation lock            -> ESCALATE   (an escalated cycle is not routed around)
    DCL hard failure           -> BLOCKED    (dominates any model opinion)
    invalid or failed audit    -> ESCALATE
    prompt bound exceeded      -> ESCALATE   (the model did not see everything)
    no model ran               -> DCL_ONLY   (never a conforming PASS)
    otherwise                  -> the model's own verdict
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..config import Config, Role, heterogeneity
from ..dcl import run_checks
from ..errors import ConfigDenial, Denial, ProviderDenial
from ..providers import resilience as provider_resilience
from ..providers.registry import NON_EVIDENTIAL
from ..usage import record_completion
from . import prompt as prompt_mod
from .validate import known_rules, parse_reply, validate_reply


@dataclass
class AuditOutcome:
    verdict: str
    dcl: dict
    model_reply: dict | None
    invalid_reason: str | None
    integrity: str
    exchange: dict
    prompt_sha256: str
    report: str


def dcl_source_digest() -> str:
    """Hash of the check layer's own source, so a receipt pins what ran."""
    # Allowlisted check packs contribute findings with the same authority as
    # the builtin layer; leave their code out of the digest and two
    # byte-identical receipts could hide different plugin implementations.
    from ..dcl.plugins import loaded_sources
    plugin_sources = loaded_sources()

    if getattr(sys, "frozen", False):
        identity_file = Path(getattr(sys, "_MEIPASS", "")) / "crossaudit-build.json"
        try:
            value = json.loads(identity_file.read_text(encoding="utf-8"))
            digest = str(value["dcl_source_sha256"])
            if len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest):
                if not plugin_sources:
                    return digest
                # The baked identity pins only the bundled layer; packs loaded
                # at runtime are check code it never saw, so fold them in.
                h = hashlib.sha256(digest.encode())
                for tag, data in plugin_sources:
                    h.update(tag.encode() + b"\x00")
                    h.update(data)
                return h.hexdigest()
        except (OSError, ValueError, KeyError, TypeError):
            pass
        raise ConfigDenial(
            "the frozen application is missing its deterministic-layer identity; "
            "reinstall CrossAudit from a verified build")
    import crossaudit.dcl as pkg

    root = Path(pkg.__file__).parent
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    # The mandatory document check delegates container parsing and semantic
    # recovery to this module; bind that implementation into the DCL digest.
    from crossaudit import document_export
    h.update(b"document_export.py")
    h.update(Path(document_export.__file__).read_bytes())
    # With no packs loaded this adds nothing: a receipt minted without plugins
    # hashes exactly as it did before packs could join the digest.
    for tag, data in plugin_sources:
        h.update(tag.encode() + b"\x00")
        h.update(data)
    return h.hexdigest()


def render_report(*, cfg: Config, sha: str, round_: int, verdict: str, dcl: dict,
                  reply: dict | None, invalid: str | None, constitution_commit: str,
                  provider: str, model: str, vendor: str | None = None,
                  reasoning_effort: str | None = None) -> str:
    lines = [
        f"# Audit Report — {cfg.science_repo}@{sha[:12]}",
        "",
        "| | |",
        "|---|---|",
        f"| verdict | **{verdict}** |",
        f"| round | {round_} |",
        f"| constitution | `{constitution_commit[:12]}` |",
        (f"| auditor | `{provider}:{model}` (vendor {vendor or cfg.auditor.vendor}; effort "
         f"{reasoning_effort or 'provider-default'}) |"),
        f"| deterministic layer | {dcl['total_hard_failures']} hard failure(s) |",
        "",
        "## Deterministic findings",
        "",
    ]
    if dcl["findings"]:
        for f in dcl["findings"]:
            lines.append(f"### [{f['severity']}] {f['rule']} — {f['artifact']}")
            if f.get("check"):
                origin = ("mandatory runtime document-integrity boundary"
                          if f["check"] == "document-export-integrity" else
                          "configured in `crossaudit.yml`; not a Constitution amendment")
                lines.append(f"Machine check: `{f['check']}` ({origin})")
            lines.append(f"{f['observation']}")
            lines.append("")
    else:
        lines += ["None.", ""]

    lines += ["## Model findings", ""]
    if invalid:
        lines += ["### [BLOCKER] CA-META-002 — invalid Auditor reply",
                  (f"The model audit was rejected: {invalid}. Under I3 an invalid audit "
                   f"escalates; it can never pass an increment."), ""]
    elif reply:
        if reply.get("findings"):
            for f in reply["findings"]:
                lines.append(f"### [{f['severity']}] {f['rule']} — {f.get('artifact', '?')}")
                lines.append(f"{f['observation']}")
                lines.append("")
        else:
            lines += ["None.", ""]
        lines += [f"Rules applied: {', '.join(reply.get('sections_applied', []))}", ""]
    else:
        lines += ["No model audit ran; this is a deterministic-tier result only.", ""]
    return "\n".join(lines)


def run_audit(*, cfg: Config, sha: str, round_: int, files: Mapping[str, bytes],
              notes: list[str], constitution: str, constitution_commit: str,
              task: str = "",
              escalation_lock: bool = False, offline: bool = False,
              allow_custom_endpoint: bool = False, retention: str = "sealed",
              on_event=None
              ) -> AuditOutcome:
    dcl = run_checks(files, cfg.checks, notes, cfg.plugins).as_dict()
    prompt, bounded, prompt_sha = prompt_mod.build(
        constitution, constitution_commit, dcl, files, task)
    reply: dict | None = None
    invalid: str | None = None
    integrity = "OK"
    exchange: dict = {"mode": "none"}
    actual = cfg.auditor

    if not offline:
        ok, why = heterogeneity(cfg)
        if not ok and cfg.generator_vendor:
            raise ConfigDenial(why)                   # a same-vendor pair is not CrossAudit
        try:
            raw = provider_resilience.complete(
                cfg, "auditor", cfg.auditor, system=prompt_mod.SYSTEM,
                prompt=prompt, allow_custom=allow_custom_endpoint,
                on_event=on_event)
            route = provider_resilience.route_from_reply(raw, cfg.auditor)
            record_completion(root=cfg.root, state_dir=cfg.state_dir, role="auditor",
                              phase="audit", vendor=route["vendor"],
                              provider=route["provider"], model=route["model"],
                              reply=raw, system=prompt_mod.SYSTEM, prompt=prompt,
                              base_url=route.get("base_url"))
            actual = Role(provider=route["provider"], model=route["model"],
                          vendor=route["vendor"], key_env=route["key_env"],
                          base_url=route.get("base_url"),
                          reasoning_effort=route.get("reasoning_effort"))
            exchange = {"mode": retention, "provider": actual.provider,
                        "vendor": actual.vendor, "model": actual.model,
                        "fallback": bool(route.get("fallback")),
                        "reasoning_effort": actual.reasoning_effort or "provider-default",
                        **raw.commitments(retention)}
            parsed, perr = parse_reply(raw.text)
            invalid = perr or validate_reply(parsed, known_rules(constitution))
            reply = parsed if invalid is None else None
        except ProviderDenial as exc:
            invalid = f"auditor call failed: {exc.reason}"
            integrity = "PROVIDER_FAILURE"
            exchange = {"mode": "none", "error": exc.reason}
        except Denial:
            raise

    if escalation_lock:
        verdict = "ESCALATE"
    elif dcl["total_hard_failures"] > 0:
        verdict = "BLOCKED"
    elif invalid:
        verdict = "ESCALATE"
        integrity = integrity if integrity != "OK" else "INVALID_REPLY"
    elif bounded:
        verdict = "ESCALATE"
        integrity = "BOUNDS_EXCEEDED"
    elif reply:
        verdict = reply["verdict"]
    else:
        verdict = "DCL_ONLY"

    if actual.provider in NON_EVIDENTIAL and verdict == "PASS":
        # A fixture is not an audit; it may exercise the loop, never bless a commit.
        integrity = "NON_EVIDENTIAL_PROVIDER"

    report = render_report(cfg=cfg, sha=sha, round_=round_, verdict=verdict, dcl=dcl,
                           reply=reply, invalid=invalid,
                           constitution_commit=constitution_commit,
                           provider=actual.provider, model=actual.model,
                           vendor=actual.vendor,
                           reasoning_effort=actual.reasoning_effort)
    return AuditOutcome(verdict=verdict, dcl=dcl, model_reply=reply,
                        invalid_reason=invalid, integrity=integrity, exchange=exchange,
                        prompt_sha256=prompt_sha, report=report)
