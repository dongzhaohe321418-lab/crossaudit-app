"""Static guard around automatic Generator repair rounds.

The guard does not claim that every flagged construct is wrong.  It claims the
narrower and more useful thing: broad exception handling, silent suppression,
new retry/fallback paths and out-of-scope edits are too consequential to enter
an audited artifact merely because a model was asked to clear a finding.  Such
patches require a human decision or a more explicit task.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import asdict, dataclass

DEFENSIVE_PATTERNS = {
    "broad_exception": re.compile(
        r"\bexcept\s+(?:Exception|BaseException)\b|\bexcept\s*:"),
    "silent_pass": re.compile(r"^\s*pass\s*(?:#.*)?$"),
    "retry_or_fallback": re.compile(
        r"(?i)\b(?:retry|retries|fallback|best[_ -]?effort)\b"),
    "suppression": re.compile(
        r"(?i)\b(?:suppress|noqa|type:\s*ignore|eslint-disable|noinspection)\b"),
    "disabled_assertion": re.compile(
        r"(?i)\b(?:skip|xfail)\b|\bassert\s+(?:True|1)\b"),
}


@dataclass(frozen=True)
class RepairAssessment:
    allowed: bool
    changed_files: tuple[str, ...]
    changed_lines: int
    unsupported_files: tuple[str, ...]
    defensive_patterns: tuple[str, ...]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


class RepairGuard:
    def __init__(self, max_changed_lines: int = 200) -> None:
        if max_changed_lines < 1:
            raise ValueError("max_changed_lines must be positive")
        self.max_changed_lines = max_changed_lines

    def assess(self, unified_diff: str, allowed_files: set[str], *,
               locally_rendered_files: set[str] | None = None) -> RepairAssessment:
        changed_files: list[str] = []
        added_lines: list[str] = []
        changed_lines = 0
        binary_files: set[str] = set()
        current_file = ""
        for line in unified_diff.splitlines():
            if line.startswith("diff --git "):
                try:
                    parts = shlex.split(line)
                except ValueError:
                    parts = []
                if len(parts) == 4:
                    current_file = parts[3].removeprefix("b/")
                    changed_files.append(current_file)
                continue
            if line.startswith("+++ "):
                path = line[4:].strip()
                path = path.removeprefix("b/")
                current_file = "" if path == "/dev/null" else path
                if current_file:
                    changed_files.append(current_file)
                continue
            if line.startswith(("Binary files ", "GIT binary patch")):
                if current_file:
                    binary_files.add(current_file)
                continue
            if line.startswith(("--- ", "@@", "index ")):
                continue
            if line.startswith("+"):
                changed_lines += 1
                added_lines.append(line[1:])
            elif line.startswith("-"):
                changed_lines += 1

        rendered = locally_rendered_files or set()
        unsupported = sorted(set(changed_files) - set(allowed_files) - rendered)
        patterns = sorted(
            name for name, pattern in DEFENSIVE_PATTERNS.items()
            if any(pattern.search(line) for line in added_lines)
        )
        untrusted_binary = sorted(binary_files - rendered)
        reasons: list[str] = []
        if not changed_files:
            reasons.append("repair contains no changed file")
        if unsupported:
            reasons.append("repair changes files outside the verified finding scope")
        if changed_lines > self.max_changed_lines:
            reasons.append(
                f"repair changes {changed_lines} lines, above the "
                f"{self.max_changed_lines}-line automatic budget")
        if patterns:
            reasons.append(
                "repair adds defensive-programming patterns requiring explicit review")
        if untrusted_binary:
            reasons.append("repair introduces an unverified binary patch")
        return RepairAssessment(
            allowed=not reasons,
            changed_files=tuple(dict.fromkeys(changed_files)),
            changed_lines=changed_lines,
            unsupported_files=tuple(unsupported),
            defensive_patterns=tuple(patterns),
            reasons=tuple(reasons))
