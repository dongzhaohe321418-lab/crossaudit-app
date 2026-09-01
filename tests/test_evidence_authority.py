"""The fusion boundary: model proposals, evidence authority and safe repairs."""
from __future__ import annotations

from crossaudit.authority import EvidenceRecord, decide, records_from_audit, validate_block
from crossaudit.generator import render_findings
from crossaudit.repair_guard import RepairGuard


def _evidence(producer: str, mechanism: str, *, verified: bool = True,
              evidence_id: str | None = None) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id or f"ev-{producer}-{mechanism}",
        finding_key="CA-DATA-001@result.json", severity="BLOCKER",
        evidence_type="documentary", claim="the declared total disagrees",
        artifact="result.json", producer_id=producer,
        mechanism_family=mechanism, verified=verified,
        verification_reason="registered fixture")


def test_registered_deterministic_failure_has_blocking_authority():
    dcl = {"findings": [{"severity": "BLOCKER", "rule": "DCL:parseable",
                          "check": "parseable", "artifact": "result.json",
                          "observation": "invalid JSON"}]}
    records = records_from_audit(dcl, None, provider="none", model="none", vendor="none")
    decision = decide(records, coverage_complete=False, no_model=True)
    assert decision.status == "BLOCK"
    assert decision.workflow_verdict == "BLOCKED"
    assert decision.route == "automatic-repair"


def test_one_model_blocker_is_a_governance_case_not_an_automatic_patch():
    reply = {"verdict": "BLOCKED", "findings": [{
        "severity": "BLOCKER", "rule": "CA-DATA-001",
        "artifact": "result.json", "observation": "the explanation seems weak"}]}
    records = records_from_audit({"findings": []}, reply,
                                 provider="openai_compat", model="gpt-x", vendor="openai")
    decision = decide(records, coverage_complete=True)
    assert decision.status == "ESCALATE"
    assert decision.workflow_verdict == "ESCALATE"
    assert decision.route == "git-governance"
    assert not decision.blocking_evidence_ids


def test_cloned_mechanism_cannot_manufacture_consensus():
    records = (_evidence("auditor-a", "model-review"),
               _evidence("auditor-b", "model-review"))
    decision = decide(records, coverage_complete=True)
    assert decision.status == "ESCALATE"


def test_distinct_producers_and_mechanisms_can_corroborate():
    records = (_evidence("checker-a", "static-analysis"),
               _evidence("checker-b", "reproduction"))
    decision = decide(records, coverage_complete=True)
    assert decision.status == "BLOCK"
    assert len(decision.blocking_evidence_ids) == 2


def test_authority_evidence_digest_detects_mutation():
    decision = decide((_evidence("a", "static"), _evidence("b", "runtime")),
                      coverage_complete=True).as_dict()
    decision["evidence"][0]["claim"] = "changed after decision"
    assert "authority evidence digest does not match" in "; ".join(
        validate_block(decision))


def test_repair_guard_rejects_defensive_and_out_of_scope_changes():
    diff = """diff --git a/other.py b/other.py
--- a/other.py
+++ b/other.py
@@ -1 +1,4 @@
-run()
+try:
+    run()
+except Exception:
+    pass
"""
    result = RepairGuard().assess(diff, {"result.py"})
    assert not result.allowed
    assert result.unsupported_files == ("other.py",)
    assert {"broad_exception", "silent_pass"} <= set(result.defensive_patterns)


def test_trusted_local_renderer_may_replace_a_binary_in_scope():
    diff = """diff --git a/report.pdf b/report.pdf
index 1111111..2222222 100644
Binary files a/report.pdf and b/report.pdf differ
"""
    result = RepairGuard().assess(
        diff, set(), locally_rendered_files={"report.pdf"})
    assert result.allowed
    assert result.changed_files == ("report.pdf",)


def test_only_machine_blockers_are_returned_for_automatic_repair():
    report = """# Audit Report

### [BLOCKER] DCL:parseable — result.json
invalid JSON

### [BLOCKER] CA-DATA-001 — SUMMARY.md
the prose may overstate the result

## Authority routing
Route: **git-governance**.
"""
    rendered = render_findings(report, verified_only=True)
    assert "DCL:parseable" in rendered
    assert "CA-DATA-001" not in rendered
