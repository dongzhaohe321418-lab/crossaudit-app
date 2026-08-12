"""Denials and exit codes.

Exit codes are part of the CLI contract (installer-design 05a): a caller
scripting the loop must be able to tell *why* it was refused without parsing
prose. Anything unexpected still denies — fail-closed is the default, not a
mode (constraint 3).

A refusal also names *what the person can do about it*, and that has to be
machine-readable for the same reason the exit code is: the desktop surfaces
route on the remedy, and they must not do so by grepping the prose. The
canonical set lives in :class:`RemediationAction` (North Star §14/§15), and a
:class:`Denial` carries an ordered ``remediations`` list, primary first. This
is the same axis slice one introduced for a parked run's ``waiting_reason``
kind — one vocabulary, so a stopped-mid-loop wait and a hard denial describe
their exits in the same words.
"""
from __future__ import annotations

from enum import Enum

# 0 is reserved for the good outcome of whichever verb ran.
EXIT_OK = 0
EXIT_BLOCKED = 10          # DCL hard failure or auditor BLOCKER findings
EXIT_ESCALATED = 11        # ESCALATE / DCL_ONLY: human or a further round owns it
EXIT_CONFIG = 20           # configuration or environment refused the run
EXIT_INTEGRITY = 21        # receipt, manifest, ledger or verifier identity refused
EXIT_PROVIDER = 22         # network or model provider failed


class RemediationAction(str, Enum):
    """The finite set of recovery actions a refusal can offer a person.

    One typed vocabulary so an interface can route on the action instead of
    parsing a sentence. The provider group mirrors North Star §15's
    remediation list; the human-decision group mirrors §14; the rest name the
    connection, workspace, repository and config repairs the console already
    renders. Every value equals the plain ``action=`` string these surfaces
    already switch on, so a typed remediation and a legacy bare action are the
    same wire value and no consumer has to know which minted it.
    """
    # Provider failure and fallback — North Star §15.
    RETRY = "retry"
    VALIDATE_CREDENTIAL = "validate_credential"
    REPLACE_KEY = "replace_key"
    SELECT_MODEL = "select_model"
    USE_FALLBACK = "use_fallback"
    REDUCE_CONTEXT = "reduce_context"
    OPEN_BILLING = "open_billing"
    CONTINUE_LATER = "continue_later"
    STOP = "stop"
    # Human decision on a stalled audit loop — North Star §14.
    REVISE = "revise"
    # Connection, identity and repository repairs the console already exposes.
    CONNECT_GITHUB = "connect_github"
    INSTALL_GITHUB_CLI = "install_github_cli"
    OPEN_GITHUB = "open_github"
    EDIT_REPOSITORIES = "edit_repositories"
    AUTHORIZE_DELETE = "authorize_delete"
    # Workspace and configuration repairs.
    CHOOSE_WORKSPACE = "choose_workspace"
    REVIEW_WORKSPACE = "review_workspace"
    EDIT_CONFIG = "edit_config"
    EDIT_GUIDANCE = "edit_guidance"
    OPEN_APP = "open_app"
    # Transient runtime waits the surface simply re-polls or dismisses.
    WAIT = "wait"
    DISMISS = "dismiss"


def _remediation_values(actions) -> list[str]:
    """Normalise remediations to their stable string values, order preserved.

    ``str(RemediationAction.RETRY)`` is the classic mixed-in-Enum trap (it can
    render ``RemediationAction.RETRY`` rather than ``retry``), so members are
    unwrapped by ``.value`` and bare strings pass through unchanged.
    """
    out: list[str] = []
    for action in actions or ():
        value = action.value if isinstance(action, RemediationAction) else str(action)
        if value and value not in out:
            out.append(value)
    return out


class Denial(Exception):
    """A refusal with a machine-readable reason and a stable exit code."""

    exit_code = EXIT_CONFIG
    kind = "denied"

    def __init__(self, reason: str, *, remediations=None, **detail: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.remediations = _remediation_values(remediations)
        self.detail = detail

    def as_dict(self) -> dict:
        out = {"denied": True, "kind": self.kind, "reason": self.reason,
               "exit_code": self.exit_code, **self.detail}
        # Additive: only present when the refusal names remedies, so callers
        # that assert the historical key set keep working.
        if self.remediations:
            out["remediations"] = list(self.remediations)
        return out


class ConfigDenial(Denial):
    exit_code = EXIT_CONFIG
    kind = "config"


class IntegrityDenial(Denial):
    """Receipt, manifest, ledger, verifier identity, or isolation refused."""

    exit_code = EXIT_INTEGRITY
    kind = "integrity"


class ProviderDenial(Denial):
    exit_code = EXIT_PROVIDER
    kind = "provider"


# --------------------------------------------------------------- classification
# Which remedies a provider failure offers, keyed on the adapter's normalized
# error category (providers/base.py, providers/resilience.py). One table so the
# classification-to-remedy mapping lives in one place instead of being reasoned
# out at each construction site. Ordered, primary first (North Star §15).
_A = RemediationAction
PROVIDER_REMEDIATIONS: dict[str, tuple[RemediationAction, ...]] = {
    "authentication": (_A.VALIDATE_CREDENTIAL, _A.REPLACE_KEY, _A.USE_FALLBACK, _A.STOP),
    "permission":     (_A.VALIDATE_CREDENTIAL, _A.USE_FALLBACK, _A.STOP),
    "rate_limit":     (_A.RETRY, _A.CONTINUE_LATER, _A.USE_FALLBACK, _A.STOP),
    "model":          (_A.SELECT_MODEL, _A.USE_FALLBACK, _A.STOP),
    "endpoint":       (_A.SELECT_MODEL, _A.VALIDATE_CREDENTIAL, _A.STOP),
    "request":        (_A.SELECT_MODEL, _A.RETRY, _A.STOP),
    "timeout":        (_A.RETRY, _A.USE_FALLBACK, _A.CONTINUE_LATER, _A.STOP),
    "transport":      (_A.RETRY, _A.USE_FALLBACK, _A.CONTINUE_LATER, _A.STOP),
    "tls":            (_A.VALIDATE_CREDENTIAL, _A.STOP),
    "response":       (_A.RETRY, _A.USE_FALLBACK, _A.STOP),
    "budget":         (_A.OPEN_BILLING, _A.CONTINUE_LATER, _A.STOP),
    "circuit_open":   (_A.RETRY, _A.USE_FALLBACK, _A.CONTINUE_LATER, _A.STOP),
    "routes_exhausted": (_A.RETRY, _A.VALIDATE_CREDENTIAL, _A.SELECT_MODEL, _A.STOP),
}
_DEFAULT_PROVIDER_REMEDIATIONS = (_A.RETRY, _A.USE_FALLBACK, _A.STOP)

# What a stalled cycle offers a person, keyed on the escalation's kind. The
# provider set is the North Star §35/A40 contract (retry / review connection /
# change model or fallback / stop); the audit set is the content path (revise
# and continue, or stop). The kind tokens are the same axis slice one gave a
# parked run's ``waiting_reason``: "provider" here is that same "provider".
ESCALATION_REMEDIATIONS: dict[str, tuple[RemediationAction, ...]] = {
    "provider": (_A.RETRY, _A.VALIDATE_CREDENTIAL, _A.SELECT_MODEL, _A.STOP),
    # A budget (usage-guardrail) pause is not a connection fault: its remedy is
    # to raise or clear the local limit — or stop — never to retry the same
    # blocked call or review the model connection. Kept identical to
    # PROVIDER_REMEDIATIONS["budget"] so a parked run's own denial and the
    # cycle-side escalation for the SAME stop offer a person one set of billing
    # remedies, not two disagreeing ones (this is the cross-slice contract the
    # 'budget' kind exists to keep).
    "budget":   (_A.OPEN_BILLING, _A.CONTINUE_LATER, _A.STOP),
    "audit":    (_A.REVISE, _A.STOP),
}
del _A


def provider_remediations(category: str) -> list[str]:
    """The ordered remedies for a provider failure category, primary first."""
    return _remediation_values(
        PROVIDER_REMEDIATIONS.get(category, _DEFAULT_PROVIDER_REMEDIATIONS))


def escalation_remediations(kind: str) -> list[str]:
    """The ordered remedies a stalled cycle of ``kind`` offers a person."""
    return _remediation_values(
        ESCALATION_REMEDIATIONS.get(kind, ESCALATION_REMEDIATIONS["audit"]))


def park_escalation_kind(waiting_kind: str | None) -> str:
    """The cycle escalation kind for a parked run, from its run-side kind.

    A parked run is a provider wait, and its cycle decision object must name
    the SAME kind the run itself parked with so both surfaces route a person
    to one set of remedies. The run side already made that call once —
    ``runs.waiting_kind`` is the single source: 'budget' for a usage-guardrail
    pause, 'provider' for every other provider wait — and this mirrors it on
    the cycle side. A missing or unrecognised value (a legacy record, a torn
    read) falls back to 'provider', never to the content 'audit' remedies,
    which never fit a provider wait. Non-park content stops are 'audit' and do
    not pass through here.
    """
    return "budget" if (waiting_kind or "").strip() == "budget" else "provider"


#: The prose marker the sole budget producer (usage.enforce_budget) stamps on
#: every guardrail denial. It rides through the reasons the cycle write points
#: mint, so the legacy shim below can still separate a budget pause from a
#: connection failure for records written before ``escalation_kind`` existed.
_BUDGET_REASON_MARKER = "usage guardrail"


def classify_escalation_kind(reason: str) -> str:
    """Infer an escalation's kind from its prose reason — the legacy shim.

    Every provider producer mints its reason with the "provider failure"
    marker, so a record written before ``escalation_kind`` was stored can
    still be routed to the provider remedies. A budget pause carries the
    "provider failure" marker too (it stops a provider call), so its own
    guardrail marker is checked first — otherwise a spending cap would fall
    through to the connection remedies. New code sets the structured kind
    explicitly; this is the one surviving place the markers are read, and only
    for records that predate the field.
    """
    text = (reason or "").lower()
    if _BUDGET_REASON_MARKER in text:
        return "budget"
    return "provider" if "provider failure" in text else "audit"
