"""The task a routed utterance commits must be the task the user said.

`lane_generator` hands the task to `cmd_build` as argv-style words, and
`build.resolve_task` re-joins those words with single spaces before writing
TASK.md into the ledger. If the lane splits a multi-line task into words,
every newline — including the export-instructions block `prepare_task`
appends — is flattened to a single line, and the ledger records a task
nobody wrote.
"""
from __future__ import annotations

from types import SimpleNamespace

from crossaudit import router as router_mod
from crossaudit.cli import build as build_mod
from crossaudit.cli import talk
from crossaudit.document_export import EXPORT_MARKER


def _generator_routing(restated: str) -> router_mod.Routing:
    return router_mod.Routing(
        utterance=restated, lane="generator", confidence=1.0,
        reasoning="explicit", restated=restated,
        addressed_to="generator", routing_mode="explicit")


def _capture_build(monkeypatch) -> dict:
    """Stop the lane at cmd_build and keep the words it was handed."""
    captured = {}

    def fake_cmd_build(args):
        captured["words"] = args.words
        return 0

    # lane_generator imports cmd_build from the build module at call time,
    # so the patch must land on build, not on talk.
    monkeypatch.setattr(build_mod, "cmd_build", fake_cmd_build)
    return captured


def test_a_multiline_task_reaches_build_letter_for_letter(monkeypatch, capsys):
    captured = _capture_build(monkeypatch)
    task = ("Write the quarterly review.\n\n"
            "Cover:\n- revenue against plan\n- churn by cohort")

    result = talk.lane_generator(SimpleNamespace(), _generator_routing(task))

    assert result == "built and audited (exit 0)"
    # A single element is what makes resolve_task's join the identity; any
    # further slicing would silently rewrite the task on its way to TASK.md.
    assert captured["words"] == [task]
    assert " ".join(captured["words"]) == task


def test_the_appended_export_block_survives_unflattened(monkeypatch, capsys):
    captured = _capture_build(monkeypatch)

    talk.lane_generator(SimpleNamespace(), _generator_routing(
        "Summarise the findings and deliver the result as a PDF"))

    joined = " ".join(captured["words"])
    # prepare_task appends a multi-line machine-readable clause; if the lane
    # had word-split the task, the marker line and its bullets would have
    # collapsed into the user's sentence.
    assert f"\n\n[{EXPORT_MARKER} format=pdf" in joined
    assert joined.count("\n") >= 6
