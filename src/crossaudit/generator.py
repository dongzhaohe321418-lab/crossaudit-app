"""The generator agent: the half of the loop that writes (DESIGN.md §8, a3).

The auditor judges committed artefacts; this module produces them. It is given
the task, the current state of the work, and — when a round was blocked — the
auditor's findings, and it returns file contents. Nothing else.

Three boundaries this module exists to hold:

* **It writes files, it does not run commands.** The reply is a set of paths and
  contents; the caller writes and commits them. A generator that could execute
  would be a second, unsupervised actor inside a supervision system.
* **Its narrative never reaches the auditor** (P2). The auditor receives the
  committed tree; the reasoning that produced it stays here. That asymmetry is
  the anchoring defence, and it is why the two prompts are built in two places.
* **It is told the rules, and told they are not negotiable.** The generator sees
  the Constitution so it can satisfy it, not so it can argue with it: disputes
  are a human's lane, routed there deliberately.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .constitution import parse_json_reply
from .errors import ConfigDenial, ProviderDenial

GENERATOR_SYSTEM = """You produce work for a supervised project. Another model \
from a different vendor audits everything you commit, against rules you will be \
shown. You cannot talk to that auditor and you cannot argue with the rules; you \
satisfy them, or your work is blocked and returned to you.

How to work:
- Return whole file contents, never diffs or fragments. A file you return \
replaces what is there; a file you omit is left untouched.
- Write only inside the working directories you are told about.
- When findings are shown to you, address every BLOCKER. Do not argue with a \
finding in your output: fix the artefact, or state in `notes` why the finding \
rests on a misreading, so a human can route it as a dispute.
- Keep claims and data consistent with each other. Most blocked rounds are prose \
that disagrees with the file it summarises.
- Prefer editing what exists over adding new files.
- Treat the requested deliverable count as a hard scope boundary. If the task \
asks for one review, report, or document, return exactly one primary file. Do \
not add metadata, source notes, specifications, indexes, or other supporting \
files unless the task, the visible machine contract, or the Constitution \
explicitly requires them.
- Use the exact delivery choices in the task (focus, format, and tone). Do not \
substitute a different file format or create alternate-format copies.
- House skills, if you are shown any, are the owner's guidance on how to work. Follow them. Where a skill conflicts with the rules, the rules win and you should say so in `notes`. No skill widens where you may write.

Reply with this exact envelope. Do not use JSON: long file contents, quotes, and \
newlines are deliberately carried as raw blocks so they cannot break escaping.

SUMMARY: one line for the commit message
<<<CROSSAUDIT-OUTPUT-FILE path="relative/path.md">>>
the entire file, verbatim
<<<END-CROSSAUDIT-OUTPUT-FILE>>>
NOTES: anything a human should know; leave empty if nothing

Repeat the CROSSAUDIT-OUTPUT-FILE block for each file. Never put Markdown fences around \
the envelope."""


@dataclass
class Work:
    summary: str
    files: dict[str, str]
    notes: str = ""

    def validate(self, *, allowed_dirs: list[str] | None) -> None:
        if not self.files:
            raise ProviderDenial("the generator returned no files; nothing to commit")
        for path, content in self.files.items():
            p = Path(path)
            if p.is_absolute() or ".." in p.parts:
                raise ProviderDenial(f"refusing a path that escapes the project: {path!r}")
            if p.parts and p.parts[0].startswith("."):
                raise ProviderDenial(f"refusing a hidden path: {path!r}")
            if "TEMPLATE" in p.parts:
                raise ProviderDenial(
                    f"refusing to edit scaffold template {path!r}; create a new "
                    f"increment directory instead")
            if allowed_dirs and (not p.parts or p.parts[0] not in allowed_dirs):
                raise ProviderDenial(
                    f"{path!r} is outside the working directories {allowed_dirs}; the "
                    f"generator may not write rules, ledger or configuration")

    @staticmethod
    def from_json(raw: dict) -> "Work":
        try:
            files = {str(f["path"]).strip(): str(f["content"]) for f in raw["files"]}
        except (KeyError, TypeError) as exc:
            raise ProviderDenial(f"the generator returned an unusable shape: {exc}") from exc
        return Work(summary=str(raw.get("summary", "work")).strip() or "work",
                    files=files, notes=str(raw.get("notes", "")).strip())


FILE_BLOCK = re.compile(
    r'<<<CROSSAUDIT-OUTPUT-FILE\s+path=(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))>>>'
    r'\n?(.*?)\n?<<<END-CROSSAUDIT-OUTPUT-FILE>>>', re.DOTALL)


def parse_work_reply(text: str) -> Work:
    """Parse the raw-file envelope, retaining JSON replies for compatibility."""
    if "<<<CROSSAUDIT-OUTPUT-FILE" not in text:
        return Work.from_json(parse_json_reply(text))
    files: dict[str, str] = {}
    matches = list(FILE_BLOCK.finditer(text))
    if not matches:
        raise ProviderDenial("the generator returned malformed file blocks")
    for match in matches:
        path = next(value for value in match.groups()[:3] if value is not None).strip()
        content = match.group(4)
        if path in files:
            # Providers occasionally repeat the exact same block while trying to
            # emphasise that only one deliverable exists. Identical bytes are one
            # unambiguous write, so collapse them. Different bytes for the same
            # path remain fail-closed because choosing either would invent intent.
            if files[path] == content:
                continue
            raise ProviderDenial(
                f"the generator returned conflicting duplicate file {path!r}")
        files[path] = content
    prefix = text[:matches[0].start()].strip()
    summary_match = re.search(r"(?:^|\n)SUMMARY:\s*(.+)", prefix)
    summary = summary_match.group(1).strip() if summary_match else "work"
    suffix = text[matches[-1].end():].strip()
    notes_match = re.search(r"(?:^|\n)NOTES:\s*(.*)", suffix, re.DOTALL)
    notes = notes_match.group(1).strip() if notes_match else ""
    return Work(summary=summary or "work", files=files, notes=notes)


def render_findings(report: str) -> str:
    """The auditor's findings, as the generator should see them.

    Only the findings travel: the report's headers and provenance are the
    ledger's business, and a generator shown its own past reasoning would drift
    toward defending it rather than fixing the artefact.
    """
    keep, capture = [], False
    for line in report.splitlines():
        if line.startswith("### ["):
            capture = True
        elif line.startswith("## ") or line.startswith("| "):
            capture = line.startswith("## ") and "findings" in line.lower()
            continue
        if capture and line.strip():
            keep.append(line)
    return "\n".join(keep) if keep else "(no findings recorded)"


def build_prompt(*, task: str, constitution: str, current: dict[str, str],
                 findings: str = "", allowed_dirs: list[str] | None = None,
                 skills: str = "", deterministic_contract: str = "",
                 attachments: str = "") -> str:
    parts = [f"THE TASK\n{task.strip()}", ""]
    if attachments:
        # The Console requires a second, provider-specific confirmation before
        # it may populate this section. CLI callers leave it empty.
        parts.append("\n" + attachments)
    parts.append("THE RULES YOUR WORK IS JUDGED BY (not negotiable here)\n"
                 f"<<<RULES\n{constitution}\nRULES")
    if deterministic_contract:
        parts.append(
            "\nTHE MACHINE-ENFORCED FILE CONTRACT (also non-negotiable in this "
            "build; change `checks:` in crossaudit.yml between cycles to change it)\n"
            f"<<<CHECKS\n{deterministic_contract}\nCHECKS")
    if skills:
        # After the rules and visibly separate from them: guidance shapes how the
        # work is done, and can never quietly become what it is judged by.
        parts.append("\n" + skills)
    if allowed_dirs:
        parts.append(f"\nYou may write only inside: {', '.join(allowed_dirs)}/")
    if current:
        rendered = "\n".join(f"--- {p} ---\n{c}" for p, c in sorted(current.items()))
        parts.append(f"\nTHE WORK AS IT STANDS\n<<<WORK\n{rendered}\nWORK")
    else:
        parts.append("\nTHE WORK AS IT STANDS\n(nothing yet; this is the first round)")
    if findings:
        parts.append(f"\nTHE AUDITOR BLOCKED THE LAST ROUND WITH THESE FINDINGS\n"
                     f"<<<FINDINGS\n{findings}\nFINDINGS\n\n"
                     f"Address every BLOCKER. Return the whole of each file you change.")
    return "\n".join(parts)


def generate(*, task: str, constitution: str, current: dict[str, str],
             complete, findings: str = "",
             allowed_dirs: list[str] | None = None, skills: str = "",
             deterministic_contract: str = "", attachments: str = "") -> Work:
    """One round of work. `complete` is a provider bound to the generator role."""
    if not task.strip():
        raise ConfigDenial("the generator needs a task; say what you want built")
    reply = complete(system=GENERATOR_SYSTEM,
                     prompt=build_prompt(task=task, constitution=constitution,
                                         current=current, findings=findings,
                                         allowed_dirs=allowed_dirs, skills=skills,
                                         deterministic_contract=deterministic_contract,
                                         attachments=attachments))
    work = parse_work_reply(reply.text)
    work.validate(allowed_dirs=allowed_dirs)
    return work


def apply(work: Work, root: Path) -> list[str]:
    """Write the returned files. Paths were validated before we got here."""
    written = []
    for rel, content in sorted(work.files.items()):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        written.append(rel)
    return written
