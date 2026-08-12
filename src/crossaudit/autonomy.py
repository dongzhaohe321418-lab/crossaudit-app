"""Safe, deterministic autonomy applied before a Generator run.

The model owns reversible presentation choices such as focus, tone, structure,
and filenames.  The controller owns the small number of choices that change
execution semantics.  In particular, an explicit PDF or DOCX request is bound
to CrossAudit's local, auditable renderer instead of relying on the provider to
emit an opaque binary.

This module deliberately does not infer permissions, remote side effects,
Constitution changes, or audit rulings.  Those remain explicit human choices.
"""
from __future__ import annotations

import re

from . import document_export
from .errors import ConfigDenial


_FORMAT_PATTERNS = {
    "pdf": (
        r"\b(?:output|export|deliver|save|render|return|provide|submit)\b"
        r"[^\n.!?]{0,48}\bpdf\b",
        r"\b(?:create|generate|make|write)\b[^\n.!?]{0,32}"
        r"\bpdf\s+(?:file|document|report)\b",
        r"\b(?:as|in)\s+(?:an?\s+)?pdf(?:\s+(?:file|document|format))?\b",
        r"\bpdf\s+(?:output|export|deliverable|version|format)\b",
        r"(?:输出|导出|交付|保存|渲染|返回|提供|提交|生成|制作|创建)"
        r"(?:为|成|至|到)?(?:一个|一份)?\s*PDF(?:文件|文档|报告|格式)?",
        r"(?:格式(?:选|选择|设定|设置)?为|要|需要|希望(?:得到|输出)?)"
        r"(?:一个|一份)?\s*PDF(?:文件|文档|报告)?",
    ),
    "docx": (
        r"\b(?:output|export|deliver|save|render|return|provide|submit)\b"
        r"[^\n.!?]{0,48}\b(?:docx|word)\b",
        r"\b(?:create|generate|make|write)\b[^\n.!?]{0,32}"
        r"\b(?:docx|word)\s+(?:file|document|report)\b",
        r"\b(?:as|in)\s+(?:an?\s+)?(?:docx|word)"
        r"(?:\s+(?:file|document|format))?\b",
        r"\b(?:docx|word)\s+(?:output|export|deliverable|version|format)\b",
        r"(?:输出|导出|交付|保存|渲染|返回|提供|提交|生成|制作|创建)"
        r"(?:为|成|至|到)?(?:一个|一份)?\s*(?:DOCX|Word)(?:文件|文档|报告|格式)?",
        r"(?:格式(?:选|选择|设定|设置)?为|要|需要|希望(?:得到|输出)?)"
        r"(?:一个|一份)?\s*(?:DOCX|Word)(?:文件|文档|报告)?",
    ),
}


def requested_document_format(task: str) -> str | None:
    """Return an explicitly requested rendered format, never a guess.

    Format words used only to identify an input (for example, ``review this
    PDF``) do not count.  The format must occur in a delivery-directed phrase.
    """
    found = {
        format_name
        for format_name, patterns in _FORMAT_PATTERNS.items()
        if any(re.search(pattern, task, flags=re.IGNORECASE) for pattern in patterns)
    }
    if len(found) > 1:
        raise ConfigDenial(
            "choose one primary output format: PDF and Word/DOCX were both requested")
    return next(iter(found), None)


def prepare_task(task: str) -> str:
    """Bind execution-relevant explicit intent; leave ordinary choices to the model."""
    text = task.strip()
    if not text:
        raise ConfigDenial("the task is empty")
    if document_export.parse_export_task(text) is not None:
        return text
    format_name = requested_document_format(text)
    return text + document_export.export_instructions(format_name) if format_name else text
