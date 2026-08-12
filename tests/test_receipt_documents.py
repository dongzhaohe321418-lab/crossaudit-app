"""Receipts over large final documents: audit and verification must read alike.

The receipt manifest hashes a PDF/DOCX container complete (bounded semantic
extraction happens elsewhere); verification re-derives those hashes from the
tree. If the verify-time read were bounded while the audit-time read was not,
every document past the generic blob bound would be denied as "manifest
mismatch" forever — an intact receipt refused by the verifier's own read
policy, not by any tampering.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from crossaudit.auditor import dcl_source_digest, run_audit
from crossaudit.controller import StateStore
from crossaudit.gitio import (MAX_BLOB_BYTES, blob_limit, entries, materialise,
                              parent, read_blob, resolve)
from crossaudit.receipt import build
from crossaudit.receipt.verify import verify

from .conftest import GOOD_RESULTS, write_increment

PDF_REL = "experiments/demo/report.pdf"


def _large_pdf_bytes() -> bytes:
    """A deterministic document comfortably past the generic blob bound."""
    filler = b"0123456789abcdef" * 63 + b"\n"
    body = filler * (600 * 1024 // len(filler) + 1)
    data = b"%PDF-1.7\n" + body
    assert len(data) > MAX_BLOB_BYTES
    return data


def _commit_with_large_pdf(science: Path) -> str:
    (science / PDF_REL).write_bytes(_large_pdf_bytes())
    return write_increment(science, GOOD_RESULTS, "Final document attached.",
                           "increment with a large final pdf")


def test_receipt_over_a_large_pdf_survives_verification(science, cfg):
    """The full loop: offline audit mints a receipt, verify() must not refuse it."""
    sha = _commit_with_large_pdf(science)

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    assert len(files[PDF_REL]) > MAX_BLOB_BYTES     # the regression needs real size
    const = (cfg.root / cfg.constitution).read_text()
    cc = subprocess.run(["git", "log", "-1", "--format=%H", "--", cfg.constitution],
                        cwd=str(cfg.root), capture_output=True, text=True,
                        check=False).stdout.strip()
    outcome = run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files,
                        notes=notes, constitution=const, constitution_commit=cc,
                        offline=True)

    manifest = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
    ledger = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{cycle['round']}"
    ledger.mkdir(parents=True, exist_ok=True)
    (ledger / "report.md").write_text(outcome.report)
    _sha, tree = resolve(cfg.root, sha)
    receipt = build(cfg=cfg, subject={"sha": sha, "tree": tree, "scope": "experiments"},
                    cycle=cycle, manifest=manifest, constitution_path=cfg.constitution,
                    constitution_bytes=(cfg.root / cfg.constitution).read_bytes(),
                    constitution_commit=cc, dcl_source_sha256=dcl_source_digest(),
                    prompt_sha256=outcome.prompt_sha256, checks=cfg.checks,
                    verdict=outcome.verdict, exchange=outcome.exchange,
                    retention="sealed",
                    report_bytes=(ledger / "report.md").read_bytes(),
                    report_commit="", cycle_path=str(ledger.relative_to(cfg.root)),
                    audit_repo=cfg.audit_repo or "local", mode="local",
                    integrity=outcome.integrity)

    evidence = verify(receipt, science_root=science, audit_root=science,
                      expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert evidence["verified"]


def test_audit_and_verify_read_identical_bytes_for_a_large_pdf(science, cfg):
    """The two read paths share one policy, so their hashes cannot disagree."""
    sha = _commit_with_large_pdf(science)

    files, _notes = materialise(science, sha, "experiments")
    assert len(files[PDF_REL]) > MAX_BLOB_BYTES
    blobs = {path: blob for _mode, path, blob in entries(science, sha)}
    data, truncated = read_blob(science, blobs[PDF_REL], limit=blob_limit(PDF_REL))

    assert not truncated
    assert (hashlib.sha256(data).hexdigest()
            == hashlib.sha256(files[PDF_REL]).hexdigest())
    # Documents read complete; everything else keeps the generic bound.
    assert blob_limit(PDF_REL) is None
    assert blob_limit("experiments/demo/Report.DOCX") is None
    assert blob_limit("experiments/demo/results.json") == MAX_BLOB_BYTES
