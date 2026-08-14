"""Stability hardening Slice B: a large file must not blow up memory.

Three "OOM/hang under a big input" bugs are closed here, each with a regression
test that uses a real git blob, a real working tree, or a real crafted archive —
never a synthetic seam:

* B1 — ``gitio.read_blob`` streams the blob and stops the child ``git`` at the
  read bound, so peak memory is the bound rather than the blob's full size. The
  bytes are byte-identical to the old buffer-then-truncate for every normal
  input (the receipt manifest hashes exactly what it hashed before — I8), and a
  document blob past the guard is refused with one deterministic marker that the
  audit path and ``receipt/verify.py`` hash identically.
* B2 — the working-tree ``check`` walks lazily, caps each file at the same bound
  as ``blob_limit``, notes an oversized file *unread* (a never-PASS input,
  CA-META-004) instead of reading it, and prunes ``.git``/state/ledger during
  traversal rather than after materialising the whole listing.
* B3 — a DOCX whose declared uncompressed size / ratio / member count is a
  decompression bomb is rejected *before* it is decompressed, on both the
  auditor and the Console preview path; a normal document is unaffected and the
  preview path is size-guarded.
"""
from __future__ import annotations

import hashlib
import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from crossaudit.auditor import dcl_source_digest, run_audit
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_BLOCKED
from crossaudit.gitio import (MAX_BLOB_BYTES, OVERSIZE_DOCUMENT_MARKER, _stream_blob,
                              blob_limit, entries, materialise, parent, read_blob,
                              read_cap, resolve)
from crossaudit.receipt import build
from crossaudit.receipt.verify import verify

from .conftest import GOOD_RESULTS, git, write_increment


def _commit(science: Path, rel: str, data: bytes, msg: str) -> str:
    p = science / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    git("add", "-A", cwd=science)
    git("commit", "-q", "-m", msg, cwd=science)
    return git("rev-parse", "HEAD", cwd=science)


def _blob_of(science: Path, sha: str, rel: str) -> str:
    return {path: blob for _mode, path, blob in entries(science, sha)}[rel]


# ---------------------------------------------------------------- B1
def test_capped_blob_streams_exactly_limit_bytes_byte_identical(science):
    """A capped-type blob over its limit returns exactly `limit` bytes, and those
    bytes equal the old buffer-then-truncate result (I8 byte-identity)."""
    big = (b"x" * 1024 + b"\n") * ((MAX_BLOB_BYTES // 1025) + 500)
    assert len(big) > MAX_BLOB_BYTES
    sha = _commit(science, "experiments/demo/big.txt", big, "big text file")
    blob = _blob_of(science, sha, "experiments/demo/big.txt")

    data, truncated = read_blob(science, blob, limit=blob_limit("x.txt"))
    assert truncated is True
    assert len(data) == MAX_BLOB_BYTES
    assert data == big[:MAX_BLOB_BYTES]          # identical to buffer-then-truncate


def test_stream_blob_reads_at_most_cap_plus_one_not_the_whole_blob(science):
    """Memory is bounded: a 5 MiB blob read under a 512 KiB cap yields cap+1
    bytes, proving the child was stopped instead of buffered in full."""
    payload = b"A" * (5 * 1024 * 1024)
    sha = _commit(science, "experiments/demo/huge.bin", payload, "5 MiB blob")
    blob = _blob_of(science, sha, "experiments/demo/huge.bin")

    cap = 512 * 1024
    data, had_more = _stream_blob(science, blob, cap)
    assert had_more is True
    assert len(data) == cap + 1                  # stopped at the bound, never 5 MiB


def test_normal_document_read_is_byte_identical(science):
    """A document larger than the generic blob bound but under the document guard
    is returned whole and unchanged — the receipt hash of a normal document is
    exactly what it was before the streaming change."""
    pdf = b"%PDF-1.7\n" + b"hello world\n" * 120_000     # ~1.3 MiB, > blob bound
    assert len(pdf) > MAX_BLOB_BYTES
    sha = _commit(science, "experiments/demo/report.pdf", pdf, "normal pdf")
    blob = _blob_of(science, sha, "experiments/demo/report.pdf")

    data, truncated = read_blob(science, blob, limit=blob_limit("x.pdf"))
    assert truncated is False
    assert data == pdf                           # whole document, byte-identical


def _commit_with_oversize_pdf(science: Path) -> str:
    (science / "experiments" / "demo" / "report.pdf").write_bytes(
        b"%PDF-1.7\n" + b"Z" * (2 * 1024 * 1024))
    return write_increment(science, GOOD_RESULTS, "Final document attached.",
                           "increment with an oversize final pdf")


def test_oversize_document_marker_is_deterministic_and_agrees_across_reads(
        science, monkeypatch):
    """Two independent reads of the same oversize document return the identical
    non-truncated marker, so the audit-time and verify-time manifest hashes for a
    huge document cannot disagree."""
    monkeypatch.setenv("CROSSAUDIT_MAX_DOC_BYTES", str(1024 * 1024))    # 1 MiB
    sha = _commit_with_oversize_pdf(science)
    blob = _blob_of(science, sha, "experiments/demo/report.pdf")

    d1, t1 = read_blob(science, blob, limit=blob_limit("report.pdf"))
    d2, t2 = read_blob(science, blob, limit=blob_limit("report.pdf"))
    assert d1 == d2 == OVERSIZE_DOCUMENT_MARKER
    # NOT flagged truncated: verify() raises on a truncated re-read, so the
    # oversize signal must ride as ordinary (agreeing) bytes instead.
    assert (t1, t2) == (False, False)
    assert hashlib.sha256(d1).hexdigest() == hashlib.sha256(d2).hexdigest()


def test_oversize_document_receipt_verifies_audit_equals_verify(science, cfg,
                                                                 monkeypatch):
    """The full loop over an oversize document: an offline audit mints a receipt
    and verify() re-derives it without refusal, because both sides read the same
    deterministic marker for the too-large blob."""
    monkeypatch.setenv("CROSSAUDIT_MAX_DOC_BYTES", str(1024 * 1024))    # 1 MiB
    sha = _commit_with_oversize_pdf(science)
    rel = "experiments/demo/report.pdf"

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    assert files[rel] == OVERSIZE_DOCUMENT_MARKER          # audit saw the marker

    const = (cfg.root / cfg.constitution).read_text()
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
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

    # verify() re-reads the oversize blob under the SAME guard and hashes the same
    # marker: the manifest re-derivation must not refuse the intact receipt.
    evidence = verify(receipt, science_root=science, audit_root=science,
                      expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert evidence["verified"]


# ---------------------------------------------------------------- B2
def test_working_tree_check_notes_oversized_file_unread_and_prunes_excluded(
        science, monkeypatch, capsys):
    """An oversized working-tree file is recorded unread (never a silent PASS)
    and its bytes are never read; .git/state/ledger are pruned mid-traversal."""
    import argparse

    from crossaudit.cli.main import cmd_check

    demo = science / "experiments" / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    (demo / "SUMMARY.md").write_text("hello world\n")                 # normal, read
    (demo / "dataset.bin").write_bytes(b"D" * (600 * 1024))          # > blob bound
    assert (demo / "dataset.bin").stat().st_size > read_cap("dataset.bin")

    # Oversized artefacts inside the excluded dirs must be pruned, not walked.
    (science / ".git" / "huge.bin").write_bytes(b"G" * (600 * 1024))
    (science / "cycles").mkdir(exist_ok=True)
    (science / "cycles" / "huge.bin").write_bytes(b"C" * (600 * 1024))
    (science / ".crossaudit").mkdir(exist_ok=True)
    (science / ".crossaudit" / "huge.bin").write_bytes(b"S" * (600 * 1024))

    reads: list[str] = []
    orig = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes",
                        lambda self: (reads.append(self.as_posix()), orig(self))[1])
    monkeypatch.chdir(science)

    args = argparse.Namespace(path=None, sha=None, scope=None, json=False)
    rc = cmd_check(args)
    out = capsys.readouterr().out

    # An input refused as too-large is a hard failure, mirroring a truncated blob
    # (the CA-META-004 / input-bound never-PASS guard).
    assert rc == EXIT_BLOCKED
    assert "too large to read" in out and "input-bound" in out
    # It was noted unread: its bytes were never pulled into memory.
    assert not any(p.endswith("experiments/demo/dataset.bin") for p in reads)
    # A normal file WAS read (semantics unchanged for it).
    assert any(p.endswith("experiments/demo/SUMMARY.md") for p in reads)
    # Excluded dirs were pruned during traversal, never read from.
    assert not any("/.git/" in p for p in reads)
    assert not any("/cycles/" in p for p in reads)
    assert not any("/.crossaudit/" in p for p in reads)


def test_working_tree_check_reads_normal_files_unchanged(science, monkeypatch,
                                                         capsys):
    """A tree of ordinary files is read exactly as before — the lazy walk changes
    nothing for normal inputs."""
    import argparse

    from crossaudit.cli.main import cmd_check

    demo = science / "experiments" / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    (demo / "SUMMARY.md").write_text("a small summary\n")
    (demo / "results.json").write_text('{"ok": true}\n')

    reads: list[str] = []
    orig = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes",
                        lambda self: (reads.append(self.as_posix()), orig(self))[1])
    monkeypatch.chdir(science)

    args = argparse.Namespace(path=None, sha=None, scope=None, json=False)
    cmd_check(args)                                     # must not raise
    assert any(p.endswith("experiments/demo/SUMMARY.md") for p in reads)
    assert any(p.endswith("experiments/demo/results.json") for p in reads)
    # No spurious "unread / too large" finding when nothing is oversized.
    assert "too large to read" not in capsys.readouterr().out


# ---------------------------------------------------------------- B3
def _zip_with_members(count: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "<w:document><w:body/></w:document>")
        for i in range(count):
            archive.writestr(f"word/junk/part{i}.xml", "x")
    return buf.getvalue()


def test_zip_bomb_docx_rejected_by_member_count():
    from crossaudit.document_export import MAX_DOCX_MEMBERS, extract_document

    data = _zip_with_members(MAX_DOCX_MEMBERS + 3)
    view = extract_document("experiments/demo/bomb.docx", data)
    assert not view.valid
    assert "suspicious compression" in view.reason and "members" in view.reason


def test_zip_bomb_docx_rejected_by_ratio():
    """A few-KB archive declaring ~9 MiB of uncompressed zeros is refused on its
    ratio, before testzip()/Document() would decompress it."""
    from crossaudit.document_export import extract_document

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"\x00" * (9 * 1024 * 1024))
    data = buf.getvalue()
    assert len(data) < 512 * 1024                       # tiny on disk (a real bomb)

    view = extract_document("experiments/demo/bomb.docx", data)
    assert not view.valid
    assert "suspicious compression" in view.reason and "ratio" in view.reason


def test_normal_docx_extracts_after_bomb_guard(tmp_path):
    from crossaudit.document_export import extract_document, render_docx

    out = tmp_path / "normal.docx"
    render_docx("# Title\n\nHello world paragraph.\n\n- one\n- two\n", out)
    view = extract_document("experiments/demo/normal.docx", out.read_bytes())
    assert view.valid
    assert "Hello world" in view.text


def test_docx_preview_is_size_guarded(cfg, monkeypatch):
    """The .docx preview refuses an over-ceiling file before read_bytes(), the
    way the text branch caps its read — no whole-file materialisation."""
    from dataclasses import replace

    from crossaudit.console import transfers
    from crossaudit.console.transfers import TransferError, preview_artifact
    from crossaudit.document_export import (SOURCE_SUFFIX, export_instructions,
                                            render_export)

    scoped = replace(cfg, scope_dirs=["experiments"])
    relative = f"experiments/preview{SOURCE_SUFFIX}"
    (cfg.root / relative).write_text("# Audited document\n\nbody content.\n")
    final = render_export(cfg.root, [relative],
                          "Write" + export_instructions("docx"))[0]
    subprocess.run(["git", "add", "--", final], cwd=cfg.root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "produce preview (round 1)"],
                   cwd=cfg.root, check=True)

    monkeypatch.setattr(transfers, "MAX_PREVIEW_DOCX_BYTES", 10)     # below the file
    reads: list[str] = []
    orig = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes",
                        lambda self: (reads.append(self.as_posix()), orig(self))[1])

    with pytest.raises(TransferError) as exc:
        preview_artifact(scoped, final)
    assert exc.value.status == 413
    assert not any(p.endswith(final) for p in reads)    # refused before reading
