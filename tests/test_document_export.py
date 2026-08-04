"""Final PDF/DOCX delivery is renderable, inspectable, and fail-closed."""
from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import pytest

from crossaudit.auditor.prompt import render_increment
from crossaudit.dcl import run_checks
from crossaudit.document_export import (
    SOURCE_SUFFIX,
    export_instructions,
    extract_document,
    parse_export_task,
    render_export,
    validate_export_work,
)
from crossaudit.errors import ProviderDenial


SOURCE = """# Verified report

English and 中文混排 are both preserved in the final document.

## Findings

- First auditable point
- 第二个审计要点

| Item | Result |
| --- | --- |
| Accuracy | Passed |
| 中文 | 已通过 |
"""


@pytest.mark.parametrize("format_name,suffix,signature", [
    ("pdf", ".pdf", b"%PDF-"),
    ("docx", ".docx", b"PK"),
])
def test_render_export_yields_only_one_valid_final_binary(
        science: Path, format_name: str, suffix: str, signature: bytes):
    task = "Write the report" + export_instructions(format_name)
    relative = f"experiments/report{SOURCE_SUFFIX}"
    validate_export_work(science, {relative: SOURCE}, task)
    source = science / relative
    source.write_text(SOURCE)

    written = render_export(science, [relative], task)

    assert written == [f"experiments/report{suffix}"]
    assert not source.exists()
    final = science / written[0]
    assert final.read_bytes().startswith(signature)
    view = extract_document(written[0], final.read_bytes())
    assert view.valid and "Verified report" in view.text
    assert "中文" in view.text and len(view.digest) == 64


def test_export_contract_rejects_extra_files_and_unowned_overwrite(science: Path):
    task = "Write" + export_instructions("pdf")
    with pytest.raises(ProviderDenial, match="exactly one"):
        validate_export_work(science, {
            f"experiments/report{SOURCE_SUFFIX}": SOURCE,
            "experiments/notes.txt": "extra",
        }, task)
    target = science / "experiments" / "report.pdf"
    target.write_bytes(b"owner document")
    with pytest.raises(ProviderDenial, match="not previously generated"):
        validate_export_work(science, {
            f"experiments/report{SOURCE_SUFFIX}": SOURCE,
        }, task)


def test_export_marker_is_unambiguous_and_machine_readable():
    task = "Report" + export_instructions("docx")
    request = parse_export_task(task)
    assert request and request.format == "docx" and request.suffix == ".docx"
    with pytest.raises(ProviderDenial, match="conflicting"):
        parse_export_task(task + export_instructions("pdf"))


@pytest.mark.parametrize("path,data", [
    ("experiments/broken.pdf", b"not a PDF"),
    ("experiments/broken.docx", b"not a ZIP"),
])
def test_invalid_office_container_is_a_mandatory_dcl_blocker(path: str, data: bytes):
    result = run_checks({path: data}, [])
    assert result.hard_failures == 1
    finding = result.findings[0].as_dict()
    assert finding["rule"] == "DCL:document-export-integrity"
    assert finding["artifact"] == path


@pytest.mark.parametrize("format_name", ["pdf", "docx"])
def test_auditor_reads_semantics_recovered_from_the_final_binary(
        science: Path, format_name: str):
    task = "Report" + export_instructions(format_name)
    relative = f"experiments/final{SOURCE_SUFFIX}"
    source = science / relative
    source.write_text(SOURCE)
    final_relative = render_export(science, [relative], task)[0]
    final = science / final_relative

    rendered, bounded = render_increment({final_relative: final.read_bytes()})

    assert not bounded
    assert "recovered from final binary" in rendered
    assert "Verified report" in rendered and "中文" in rendered
    assert extract_document(final_relative, final.read_bytes()).digest in rendered


@pytest.mark.parametrize("format_name", ["pdf", "docx"])
def test_build_loop_commits_only_the_final_document(
        science: Path, cfg, format_name: str, monkeypatch):
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod
    from crossaudit.controller import StateStore
    from crossaudit.errors import EXIT_ESCALATED

    task = "Write a verified report" + export_instructions(format_name)
    source = f"experiments/loop{SOURCE_SUFFIX}"
    monkeypatch.setattr(build_mod, "_generator_complete", lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", lambda **_kwargs:
                        generator_mod.Work("write report", {source: SOURCE}))

    def fake_audit(_args):
        from tests.conftest import git

        sha = git("rev-parse", "HEAD", cwd=science)
        store = StateStore(cfg.root / cfg.state_dir / "state.json")
        cycle = store.open_or_advance(cfg.science_repo, sha, None)
        store.record_verdict(cycle["cycle_id"], sha, "BLOCKED", "receipt", 1)
        return EXIT_ESCALATED

    monkeypatch.setattr(build_mod, "cmd_run", fake_audit)
    monkeypatch.chdir(science)
    scoped = replace(cfg, scope_dirs=["experiments"], max_rounds=1)

    assert build_mod.run_loop(scoped, task) == EXIT_ESCALATED
    final = source.removesuffix(SOURCE_SUFFIX) + "." + format_name
    from tests.conftest import git
    committed = git("show", "--pretty=", "--name-only", "HEAD", cwd=science).splitlines()
    assert final in committed and source not in committed
    assert not (science / source).exists()
    assert extract_document(final, (science / final).read_bytes()).valid
