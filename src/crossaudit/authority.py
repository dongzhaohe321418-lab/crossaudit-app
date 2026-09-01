"""Evidence-before-authority admission for the Git-native CrossAudit loop.

The Auditor is deliberately useful but deliberately untrusted: it proposes
semantic findings, while this module decides what those findings are allowed to
do.  A hard automated block needs either a reproduced mechanical failure or
corroboration across distinct producers *and* mechanism families.  A lone model
claim therefore enters the existing Git governance lane instead of being fed
straight back to the Generator as an instruction to patch.

This is the seam between the two CrossAudit architectures:

* Evidence Lab supplies the evidence vocabulary and admission rule.
* The original protocol supplies bounded disputes, immutable reports and human
  resolution when evidence is insufficient.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass

POLICY_VERSION = "crossaudit-evidence-authority-v1"
HARD_EVIDENCE = frozenset({
    "deterministic_failure",
    "executable_counterexample",
    "reproducible_observation",
})
STATUSES = frozenset({"PASS", "ADVISORY", "BLOCK", "ESCALATE"})


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _identifier(prefix: str, value: object) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical(value)).hexdigest()[:16]}"


@dataclass(frozen=True)
class EvidenceRecord:
    """One claim plus the provenance needed to assign authority to it."""

    evidence_id: str
    finding_key: str
    severity: str
    evidence_type: str
    claim: str
    artifact: str
    producer_id: str
    mechanism_family: str
    verified: bool
    verification_reason: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AuthorityDecision:
    """Admission decision and the route that must consume it."""

    policy_version: str
    decision_id: str
    status: str
    workflow_verdict: str
    route: str
    requires_human: bool
    blocking_evidence_ids: tuple[str, ...]
    advisory_evidence_ids: tuple[str, ...]
    rationale: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]
    evidence_digest: str

    def as_dict(self) -> dict:
        return {
            **asdict(self),
            "evidence": [item.as_dict() for item in self.evidence],
        }


def _record(*, finding_key: str, severity: str, evidence_type: str,
            claim: str, artifact: str, producer_id: str,
            mechanism_family: str, verified: bool,
            verification_reason: str) -> EvidenceRecord:
    payload = {
        "finding_key": finding_key,
        "severity": severity,
        "evidence_type": evidence_type,
        "claim": claim,
        "artifact": artifact,
        "producer_id": producer_id,
        "mechanism_family": mechanism_family,
        "verified": verified,
        "verification_reason": verification_reason,
    }
    return EvidenceRecord(evidence_id=_identifier("ev", payload), **payload)


def records_from_audit(dcl: Mapping, model_reply: Mapping | None, *,
                       provider: str, model: str, vendor: str) -> tuple[EvidenceRecord, ...]:
    """Normalize deterministic and model findings into one evidence plane."""
    records: list[EvidenceRecord] = []
    for finding in dcl.get("findings", []):
        severity = str(finding.get("severity", "ADVISORY")).upper()
        check = str(finding.get("check") or finding.get("rule") or "registered")
        rule = str(finding.get("rule", "DCL:unknown"))
        artifact = str(finding.get("artifact", "increment"))
        records.append(_record(
            finding_key=f"{rule}@{artifact}", severity=severity,
            evidence_type=("deterministic_failure" if severity == "BLOCKER"
                           else "reproducible_observation"),
            claim=str(finding.get("observation", "")), artifact=artifact,
            producer_id=f"checker:{check}",
            mechanism_family=f"deterministic:{check}", verified=True,
            verification_reason="emitted by a registered check over committed bytes"))

    if model_reply:
        producer = f"auditor:{vendor or 'unknown'}/{provider}:{model}"
        for finding in model_reply.get("findings", []):
            severity = str(finding.get("severity", "ADVISORY")).upper()
            rule = str(finding.get("rule", "CA-UNKNOWN-000"))
            artifact = str(finding.get("artifact", "increment"))
            records.append(_record(
                finding_key=f"{rule}@{artifact}", severity=severity,
                evidence_type="textual_judgment",
                claim=str(finding.get("observation", "")), artifact=artifact,
                producer_id=producer, mechanism_family="model-semantic-review",
                verified=False,
                verification_reason=(
                    "a valid Auditor reply is a proposal, not reproduced evidence")))
    return tuple(records)


def decide(records: Iterable[EvidenceRecord], *, coverage_complete: bool,
           integrity_errors: Iterable[str] = (), escalation_lock: bool = False,
           no_model: bool = False, auditor_requested_escalation: bool = False,
           non_evidential_provider: bool = False) -> AuthorityDecision:
    """Assign authority without trusting confidence, vendor names or prose.

    The consensus path is intentionally available to future registered
    checkers/adapters, even though today's single model Auditor contributes one
    unverified mechanism and therefore cannot satisfy it by cloning findings.
    """
    evidence = tuple(records)
    verified_blockers = [
        item for item in evidence
        if item.verified and item.severity == "BLOCKER"
    ]
    hard = [item for item in verified_blockers
            if item.evidence_type in HARD_EVIDENCE]
    grouped: dict[str, list[EvidenceRecord]] = defaultdict(list)
    for item in verified_blockers:
        grouped[item.finding_key].append(item)
    consensus: list[EvidenceRecord] = []
    for items in grouped.values():
        if (len({item.producer_id for item in items}) >= 2
                and len({item.mechanism_family for item in items}) >= 2):
            consensus.extend(items)

    errors = tuple(str(item) for item in integrity_errors if str(item).strip())
    unresolved = [item for item in evidence
                  if item.severity == "BLOCKER" and item not in hard
                  and item not in consensus]

    if hard or consensus:
        status, verdict, route, human = "BLOCK", "BLOCKED", "automatic-repair", False
        blocking = {item.evidence_id for item in (*hard, *consensus)}
        rationale = ((
            "hard blocking authority came only from reproduced evidence or "
            "independent producer-and-mechanism consensus"),)
    elif escalation_lock:
        status, verdict, route, human = "ESCALATE", "ESCALATE", "git-governance", True
        blocking = set()
        rationale = ("an earlier escalation remains under human jurisdiction",)
    elif no_model:
        status, verdict, route, human = "ESCALATE", "DCL_ONLY", "obtain-audit", True
        blocking = set()
        rationale = ("no semantic Auditor completed the planned coverage",)
    elif errors or not coverage_complete or non_evidential_provider:
        status, verdict, route, human = "ESCALATE", "ESCALATE", "git-governance", True
        blocking = set()
        rationale = errors or (
            "audit coverage or provider identity cannot support admission",
        )
    elif auditor_requested_escalation:
        status, verdict, route, human = "ESCALATE", "ESCALATE", "git-governance", True
        blocking = set()
        rationale = ("the Auditor explicitly requested human judgment",)
    elif unresolved:
        status, verdict, route, human = "ESCALATE", "ESCALATE", "git-governance", True
        blocking = set()
        rationale = ((
            "blocking claims lack reproduced evidence or independent mechanism consensus; "
            "they require bounded dispute or human resolution"),)
    elif evidence:
        status, verdict, route, human = "ADVISORY", "PASS", "admission", False
        blocking = set()
        rationale = ("only non-blocking findings remain; they are preserved as advisories",)
    else:
        status, verdict, route, human = "PASS", "PASS", "admission", False
        blocking = set()
        rationale = ("planned checks and semantic coverage completed with no finding",)

    advisory = tuple(sorted(item.evidence_id for item in evidence
                            if item.evidence_id not in blocking))
    blocking_ids = tuple(sorted(blocking))
    evidence_payload = [item.as_dict() for item in evidence]
    evidence_digest = hashlib.sha256(_canonical(evidence_payload)).hexdigest()
    decision_payload = {
        "policy_version": POLICY_VERSION,
        "status": status,
        "workflow_verdict": verdict,
        "route": route,
        "blocking_evidence_ids": blocking_ids,
        "advisory_evidence_ids": advisory,
        "rationale": rationale,
        "evidence_digest": evidence_digest,
    }
    return AuthorityDecision(
        policy_version=POLICY_VERSION,
        decision_id=_identifier("authority", decision_payload), status=status,
        workflow_verdict=verdict, route=route, requires_human=human,
        blocking_evidence_ids=blocking_ids, advisory_evidence_ids=advisory,
        rationale=rationale, evidence=evidence, evidence_digest=evidence_digest)


def validate_block(raw: Mapping) -> list[str]:
    """Return structural/binding errors for a receipt authority block."""
    errors: list[str] = []
    required = {"policy_version", "decision_id", "status", "workflow_verdict",
                "route", "requires_human", "blocking_evidence_ids",
                "advisory_evidence_ids", "rationale", "evidence", "evidence_digest"}
    missing = sorted(required - set(raw))
    if missing:
        return [f"authority block is missing {missing}"]
    if raw.get("policy_version") != POLICY_VERSION:
        errors.append("authority policy version is not the active policy")
    if raw.get("status") not in STATUSES:
        errors.append("authority status is unknown")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        errors.append("authority evidence is not a list")
    else:
        digest = hashlib.sha256(_canonical(evidence)).hexdigest()
        if digest != raw.get("evidence_digest"):
            errors.append("authority evidence digest does not match its records")
    expected = {"PASS": {"PASS"}, "ADVISORY": {"PASS"},
                "BLOCK": {"BLOCKED"}, "ESCALATE": {"ESCALATE", "DCL_ONLY"}}
    if raw.get("workflow_verdict") not in expected.get(str(raw.get("status")), set()):
        errors.append("authority status and workflow verdict disagree")
    return errors
