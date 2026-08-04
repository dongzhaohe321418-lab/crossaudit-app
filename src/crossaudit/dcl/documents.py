"""Mandatory final-document container and semantic-readability check."""
from __future__ import annotations

from typing import Mapping

from ..document_export import INTEGRITY_CONTRACT, extract_document
from .framework import BLOCKER, Finding

CHECK_NAME = "document-export-integrity"


def validate(files: Mapping[str, bytes]) -> list[Finding]:
    findings: list[Finding] = []
    for path, data in files.items():
        if not path.lower().endswith((".pdf", ".docx")):
            continue
        view = extract_document(path, data)
        if not view.valid:
            findings.append(Finding(
                BLOCKER, "CA-META-005", path,
                f"final document cannot be independently inspected: {view.reason}",
                check=CHECK_NAME))
    return findings


__all__ = ["CHECK_NAME", "INTEGRITY_CONTRACT", "validate"]
