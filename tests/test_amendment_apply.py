"""Tests for apply_amendment: the edit and its ledger must never disagree.

Every change set is appended to the Amendments log, so an action that quietly
edits nothing turns the rulebook into a file that lies about its own history —
the exact failure a receipts-first tool cannot tolerate. These tests pin each
action to a real edit, in particular the once-broken case of an "add" whose
rule ID already exists, which must replace rather than no-op.
"""
from __future__ import annotations

from crossaudit.constitution import apply_amendment

MARKER = "<!-- Amend by talking"

OLD_CRITERION = "Each numeric claim names a source."
NEW_CRITERION = "Every numeric claim names a source and the edition it came from."

BASE = (
    "# Constitution — demo\n"
    "\n"
    "### CA-DATA-001\n"
    "**BLOCKER.** Numbers trace to sources\n"
    "\n"
    f"{OLD_CRITERION}\n"
    "\n"
    "---\n"
    "\n"
    "<!-- Amend by talking to CrossAudit: `crossaudit amend \"from now on ...\"`. -->\n"
)


def change_set(action: str, rid: str, now: str) -> dict:
    return {
        "intent": "test the edit",
        "changes": [{"action": action, "id": rid, "severity": "BLOCKER",
                     "title": "Edited title", "was": "", "now": now,
                     "why": "the test asked"}],
    }


def test_add_on_missing_inserts_before_the_marker():
    after = apply_amendment(BASE, change_set("add", "CA-NEW-001", "A brand new criterion."))
    assert "### CA-NEW-001" in after
    assert "A brand new criterion." in after
    assert after.index("### CA-NEW-001") < after.index(MARKER)
    assert OLD_CRITERION in after            # untouched rule survives
    assert "## Amendments" in after


def test_add_on_existing_replaces_instead_of_silently_dropping():
    # The historic bug: add+exists matched neither branch, the text was returned
    # unchanged, and the Amendments log still claimed the change was applied.
    after = apply_amendment(BASE, change_set("add", "CA-DATA-001", NEW_CRITERION))
    assert NEW_CRITERION in after
    assert OLD_CRITERION not in after
    assert after.count("### CA-DATA-001") == 1
    assert "## Amendments" in after
    assert "`CA-DATA-001` add" in after


def test_modify_on_missing_appends_the_rule():
    after = apply_amendment(BASE, change_set("modify", "CA-NEW-002", "An appended criterion."))
    assert "### CA-NEW-002" in after
    assert "An appended criterion." in after
    assert OLD_CRITERION in after            # untouched rule survives
    assert "## Amendments" in after


def test_modify_on_existing_replaces_the_criterion():
    after = apply_amendment(BASE, change_set("modify", "CA-DATA-001", NEW_CRITERION))
    assert NEW_CRITERION in after
    assert OLD_CRITERION not in after
    assert after.count("### CA-DATA-001") == 1
    assert "## Amendments" in after


def test_remove_removes_the_rule_but_the_history_names_it():
    after = apply_amendment(BASE, change_set("remove", "CA-DATA-001", ""))
    assert "### CA-DATA-001" not in after
    assert OLD_CRITERION not in after
    assert "`CA-DATA-001` remove" in after   # the log is how a removal stays visible


def test_every_action_lands_in_the_amendments_log():
    for action, rid in (("add", "CA-NEW-001"),     # add on missing
                        ("add", "CA-DATA-001"),    # add on existing (the bug)
                        ("modify", "CA-DATA-001"), # modify on existing
                        ("modify", "CA-NEW-003"),  # modify on missing
                        ("remove", "CA-DATA-001")):
        after = apply_amendment(BASE, change_set(action, rid, "criterion text"))
        assert "## Amendments" in after
        assert f"`{rid}` {action}" in after
