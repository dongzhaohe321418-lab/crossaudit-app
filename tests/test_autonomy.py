from __future__ import annotations

import pytest

from crossaudit.autonomy import prepare_task, requested_document_format
from crossaudit.errors import ConfigDenial


@pytest.mark.parametrize("task", [
    "Write a rigorous review of the paper.",
    "Review this PDF in detail and cite its weak claims.",
    "分析这个 PDF，并重点检查方法部分。",
])
def test_ordinary_tasks_leave_reversible_delivery_choices_to_the_generator(task):
    assert prepare_task(task) == task
    assert requested_document_format(task) is None


@pytest.mark.parametrize("task,format_name", [
    ("Output the review as a PDF.", "pdf"),
    ("Please deliver a Word document with the findings.", "docx"),
    ("把详细报告输出为PDF文件", "pdf"),
    ("请生成一份 Word 文档", "docx"),
])
def test_explicit_document_delivery_is_bound_to_the_local_renderer(task, format_name):
    prepared = prepare_task(task)

    assert requested_document_format(task) == format_name
    assert f"[CROSSAUDIT-DOCUMENT-EXPORT format={format_name}" in prepared
    assert "Return exactly one Markdown source file" in prepared


def test_input_format_is_not_mistaken_for_output_format():
    prepared = prepare_task("Review this PDF and output a Word document.")

    assert "format=docx" in prepared
    assert "format=pdf" not in prepared


def test_conflicting_primary_formats_require_one_short_human_decision():
    with pytest.raises(ConfigDenial, match="choose one primary output format"):
        prepare_task("Deliver the report as both PDF and DOCX.")


def test_existing_machine_export_contract_is_not_duplicated():
    first = prepare_task("Output the review as PDF")
    assert prepare_task(first) == first
