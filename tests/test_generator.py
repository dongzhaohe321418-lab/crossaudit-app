"""Tests for the generator half of the loop.

The model is stubbed; what is tested is the boundary around it. A generator
inside a supervision system is exactly the component you must not trust by
default, so most of these are refusals.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from crossaudit import generator as gen
from crossaudit.errors import ConfigDenial, ProviderDenial


@dataclass
class Reply:
    text: str


def stub(payload):
    body = payload if isinstance(payload, str) else json.dumps(payload)

    def complete(*, system: str, prompt: str):
        return Reply(text=body)

    return complete


def work_payload(path="work/a.md", content="hello", **kw):
    return {"summary": "wrote a section",
            "files": [{"path": path, "content": content}], "notes": "", **kw}


ALLOWED = ["work"]


def test_a_round_returns_whole_files():
    w = gen.generate(task="write a section", constitution="rules", current={},
                     complete=stub(work_payload()), allowed_dirs=ALLOWED)
    assert w.files == {"work/a.md": "hello"} and w.summary == "wrote a section"


def test_raw_file_envelope_does_not_require_json_escaping():
    reply = '''SUMMARY: write a quoted review
<<<CROSSAUDIT-OUTPUT-FILE path="work/review.md">>>
# Review

The user said "make it readable" and the code uses `x = "y"`.
<<<END-CROSSAUDIT-OUTPUT-FILE>>>
NOTES: ready
'''
    work = gen.parse_work_reply(reply)
    assert work.summary == "write a quoted review"
    assert 'said "make it readable"' in work.files["work/review.md"]
    assert work.notes == "ready"


def test_identical_duplicate_file_blocks_collapse_to_one_unambiguous_write():
    block = '''<<<CROSSAUDIT-OUTPUT-FILE path="work/review.md">>>
# Review
<<<END-CROSSAUDIT-OUTPUT-FILE>>>'''
    work = gen.parse_work_reply("SUMMARY: one file\n" + block + "\n" + block)
    assert work.files == {"work/review.md": "# Review"}


def test_conflicting_duplicate_file_blocks_are_refused():
    reply = '''SUMMARY: ambiguous
<<<CROSSAUDIT-OUTPUT-FILE path="work/review.md">>>
first
<<<END-CROSSAUDIT-OUTPUT-FILE>>>
<<<CROSSAUDIT-OUTPUT-FILE path="work/review.md">>>
second
<<<END-CROSSAUDIT-OUTPUT-FILE>>>'''
    with pytest.raises(ProviderDenial, match="conflicting duplicate"):
        gen.parse_work_reply(reply)


def test_generator_prompt_treats_one_requested_deliverable_as_one_file():
    assert "return exactly one primary file" in gen.GENERATOR_SYSTEM
    assert "Do not add metadata, source notes, specifications" in gen.GENERATOR_SYSTEM
    assert "exact delivery choices" in gen.GENERATOR_SYSTEM


@pytest.mark.parametrize("bad", [
    "/etc/passwd",                       # absolute
    "../outside.md",                     # traversal
    "work/../../escape.md",              # traversal through the allowed dir
    ".git/config",                       # hidden
    "AUDIT_RULES.md",                    # the rules it is judged by
    "crossaudit.yml",                    # the configuration
    "cycles/forged/receipt.json",        # the ledger
    "work/TEMPLATE/results.json",        # starter scaffold, never an increment
])
def test_the_generator_cannot_write_outside_its_working_directories(bad):
    with pytest.raises(ProviderDenial):
        gen.generate(task="t", constitution="r", current={},
                     complete=stub(work_payload(path=bad)), allowed_dirs=ALLOWED)


def test_an_empty_round_is_refused():
    with pytest.raises(ProviderDenial, match="no files"):
        gen.generate(task="t", constitution="r", current={},
                     complete=stub({"summary": "s", "files": []}), allowed_dirs=ALLOWED)


def test_generator_output_has_no_crossaudit_file_size_quota():
    huge = "x" * 900_000
    work = gen.generate(task="t", constitution="r", current={},
                        complete=stub(work_payload(content=huge)), allowed_dirs=ALLOWED)
    assert len(work.files["work/a.md"]) == len(huge)


def test_generator_output_has_no_crossaudit_file_count_quota():
    many = {"summary": "s", "files": [{"path": f"work/{i}.md", "content": "x"}
                                      for i in range(75)]}
    work = gen.generate(task="t", constitution="r", current={}, complete=stub(many),
                        allowed_dirs=ALLOWED)
    assert len(work.files) == 75


def test_prose_instead_of_json_denies_rather_than_writing_nothing():
    with pytest.raises(ProviderDenial):
        gen.generate(task="t", constitution="r", current={},
                     complete=stub("Sure! I'll get started on that."),
                     allowed_dirs=ALLOWED)


def test_an_empty_task_is_refused():
    with pytest.raises(ConfigDenial, match="needs a task"):
        gen.generate(task="   ", constitution="r", current={},
                     complete=stub(work_payload()), allowed_dirs=ALLOWED)


def test_the_prompt_carries_rules_and_findings_but_never_the_auditor_s_report_headers():
    prompt = gen.build_prompt(task="write it", constitution="### CA-X-001\nbe exact",
                              current={"work/a.md": "old"}, findings="[BLOCKER] fix this",
                              allowed_dirs=ALLOWED)
    assert "### CA-X-001" in prompt          # it must know what it is judged by
    assert "[BLOCKER] fix this" in prompt    # and what was wrong last time
    assert "work/a.md" in prompt and "old" in prompt
    assert "may write only inside: work/" in prompt


def test_the_first_generator_round_receives_the_live_machine_contract():
    from crossaudit.dcl import describe

    contract = describe(["schema", "units", "provenance"])
    prompt = gen.build_prompt(task="make it", constitution="### CA-X-001\nbe exact",
                              current={}, deterministic_contract=contract)

    assert "MACHINE-ENFORCED FILE CONTRACT" in prompt
    assert "inputs list of 'path@revision' strings" in prompt
    assert "Every entry in results.json quantities" in prompt


def test_confirmed_attachment_section_is_delimited_from_the_task():
    section = ("ATTACHMENTS FROM THE PROJECT OWNER\n\n"
               "<<<ATTACHMENT name='input.csv'\nvalue\n3\nATTACHMENT")
    prompt = gen.build_prompt(task="summarize the input", constitution="rules",
                              current={}, attachments=section)
    assert "THE TASK\nsummarize the input" in prompt
    assert section in prompt
    assert prompt.index(section) < prompt.index("THE RULES YOUR WORK IS JUDGED BY")


def test_findings_are_extracted_without_the_report_s_provenance():
    report = "\n".join([
        "# Audit Report — repo@abc123", "", "| | |", "|---|---|",
        "| verdict | **BLOCKED** |", "| auditor | `openai:gpt` |", "",
        "## Deterministic findings", "",
        "### [BLOCKER] CA-DATA-001 — results.json",
        "quantities[1] has no unit", "",
    ])
    out = gen.render_findings(report)
    assert "CA-DATA-001" in out and "no unit" in out
    # The generator has no business knowing which vendor judged it, or the sha.
    assert "openai:gpt" not in out and "abc123" not in out


def test_apply_writes_only_what_was_returned(tmp_path: Path):
    w = gen.Work(summary="s", files={"work/deep/a.md": "one", "work/b.md": "two"})
    written = gen.apply(w, tmp_path)
    assert written == ["work/b.md", "work/deep/a.md"]
    assert (tmp_path / "work/deep/a.md").read_text() == "one"
    assert not (tmp_path / "AUDIT_RULES.md").exists()


def test_current_work_hides_the_scaffold_template(tmp_path: Path):
    from types import SimpleNamespace

    from crossaudit.cli.build import _current_work

    (tmp_path / "work" / "TEMPLATE").mkdir(parents=True)
    (tmp_path / "work" / "TEMPLATE" / "results.json").write_text("template")
    (tmp_path / "work" / "real").mkdir()
    (tmp_path / "work" / "real" / "results.json").write_text("real")
    cfg = SimpleNamespace(root=tmp_path, scope_dirs=["work"])

    assert _current_work(cfg) == {"work/real/results.json": "real"}


def test_build_stages_only_files_the_generator_returned(tmp_path: Path):
    import subprocess
    from types import SimpleNamespace

    from crossaudit.cli.build import _stage_generated

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    (tmp_path / "work" / "TEMPLATE").mkdir(parents=True)
    (tmp_path / "work" / "TEMPLATE" / "results.json").write_text("template")
    (tmp_path / "work" / "real").mkdir()
    (tmp_path / "work" / "real" / "results.json").write_text("real")
    cfg = SimpleNamespace(root=tmp_path)

    staged = _stage_generated(cfg, ["work/real/results.json"])

    assert staged == ["work/real/results.json"]
    status = subprocess.run(["git", "status", "--short"], cwd=tmp_path,
                            capture_output=True, text=True, check=True).stdout
    assert "A  work/real/results.json" in status
    assert "?? work/TEMPLATE/" in status
