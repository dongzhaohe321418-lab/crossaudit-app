"""Release claims that must remain executable instead of living in prose."""
from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from crossaudit import __version__
from crossaudit.console.page import PAGE

ROOT = Path(__file__).parents[1]


class _PageContract(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.dialogs: list[dict[str, str | None]] = []
        self.progress: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if values.get("role") == "dialog":
            self.dialogs.append(values)
        if values.get("role") == "progressbar":
            self.progress.append(values)


def test_release_version_has_one_consistent_public_identity():
    pyproject = (ROOT / "pyproject.toml").read_text()
    readme = (ROOT / "README.md").read_text()
    assert re.search(r'^version = "' + re.escape(__version__) + r'"$',
                     pyproject, re.MULTILINE)
    assert f"CrossAudit {__version__}" in readme
    assert f"V{__version__}" in PAGE
    assert f'__version__ = "{__version__}"' in (
        ROOT / "src/crossaudit/__init__.py").read_text()
    assert '"pypdf>=6.15,<7"' in pyproject


def test_ci_tests_installed_wheels_with_timeouts_coverage_and_audit():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert 'pip install -e' not in workflow
    for version in ("3.10", "3.11", "3.12", "3.13"):
        assert f"python: '{version}'" in workflow
    for required in (
        "windows-latest", "macos-latest", "coverage report", "--timeout=30",
        "pip_audit --strict -r", "verify_python_package.py", "twine check",
    ):
        assert required in workflow


def test_release_scripts_verify_frozen_runtime_and_public_notarization():
    build = (ROOT / "packaging/macos/build_dmg.sh").read_text()
    verifier = (ROOT / "packaging/macos/verify_dmg.sh").read_text()
    gate = (ROOT / "scripts/release_gate.sh").read_text()
    assert "CrossAuditCore --self-test" in build
    assert "CROSSAUDIT_PUBLIC_RELEASE" in build
    assert "notarytool submit" in build and "stapler staple" in build
    assert "hdiutil attach" in verifier and "codesign --verify" in verifier
    assert "$CORE --self-test" in verifier
    assert "trusted_certificate_authorities" in build
    assert "trusted_certificate_authorities" in verifier
    assert "coverage run" in gate and "verify_python_package.py" in gate
    assert "#egg=crossaudit$" in gate
    spec = (ROOT / "packaging/macos/CrossAuditCore.spec").read_text()
    assert 'collect_data_files("docx", include_py_files=True)' in spec
    assert 'collect_data_files("certifi")' in spec
    package_verifier = (ROOT / "packaging/verify_python_package.py").read_text()
    assert '"--install-timeout"' in package_verifier
    assert "default=600" in package_verifier


def test_static_ui_has_unique_ids_and_named_modal_and_progress_contracts():
    parser = _PageContract()
    parser.feed(PAGE)
    assert [value for value, count in Counter(parser.ids).items() if count > 1] == []
    known = set(parser.ids)
    assert len(parser.dialogs) >= 8
    for dialog in parser.dialogs:
        assert dialog.get("aria-modal") == "true"
        label = dialog.get("aria-labelledby")
        assert label and label in known
    for progress in parser.progress:
        assert progress.get("aria-label")
    for contract in ("function activeModal()", "function closeActiveModal(modal)",
                     "modalReturnFocus", "ev.key==='Tab'", "ev.key==='Escape'"):
        assert contract in PAGE


def test_spatial_ui_keeps_glass_contextual_and_accessible():
    """The Apple-style shell must remain legible when visual effects are unavailable."""
    for contract in (
        'font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text"',
        ".topbar,.hub-bar{",
        ".sidebar,.inspector{",
        ".composer{",
        "@media(prefers-reduced-transparency:reduce)",
        "@media(prefers-reduced-motion:reduce)",
        "@media(prefers-contrast:more)",
        "@media(forced-colors:active)",
        "@supports not ((-webkit-backdrop-filter:blur(1px))",
        "button:focus-visible",
        "--z-content:1;--z-chrome:40;--z-composer:50;--z-overlay:100",
        ".project-modal.on .wizard{transform-origin:50% 14%;animation:materialize",
        ".icon-button,.compose-button{min-width:44px;min-height:44px}",
        "A single outline icon language avoids font-dependent symbols",
        '-webkit-mask:var(--ui-icon) center/contain no-repeat',
        ".top-project,#current-project-pin,.live-pill,.version{display:none}",
    ):
        assert contract in PAGE

    # Audit evidence and deliverables are opaque content, not decorative glass.
    assert ".run-card{border-color:var(--line);border-radius:var(--r-lg);background:var(--surface)" in PAGE
    assert ".finding,.output-file,.usage-card" in PAGE


def test_complex_setup_flows_use_progressive_disclosure():
    """Creation and preferences expose one decision group at a time."""
    for contract in (
        "[hidden]{display:none!important}",
        'class="wizard project-wizard"',
        'data-project-step="1"',
        'data-project-step="2"',
        'data-project-step="3"',
        'data-project-indicator="1"',
        'id="project-back" hidden',
        'id="project-next"',
        'id="submit-project" hidden',
        'function setProjectStep(step,focus=true)',
        'function validateProjectStep(step)',
        'class="wizard-error" id="wizard-error" role="alert"',
        'class="settings-nav" aria-label="Settings sections"',
        'data-settings-panel="general"',
        'data-settings-panel="providers"',
        'data-settings-pane="general"',
        'data-settings-pane="providers"',
        'function showSettingsPanel(name,focus=true)',
        '<details class="credential-card"',
        'id="toggle-doctor-details" aria-expanded="false"',
        'class="wizard-error" id="settings-error" role="alert"',
    ):
        assert contract in PAGE


def test_live_round_projection_uses_typed_event_fields_not_english_text():
    assert "s.kind === 'round_started'" in PAGE
    assert "roundEvent.round_no" in PAGE
    assert "current.round_no + ' / ' + current.round_limit" in PAGE
    assert "s.text.startsWith('round ')" not in PAGE


def test_embedded_ui_javascript_is_valid_when_node_is_available():
    node = shutil.which("node")
    if not node:
        return  # Python tests remain runnable on a machine without developer Node.
    scripts = re.findall(r"<script>(.*?)</script>", PAGE, re.DOTALL)
    assert scripts
    result = subprocess.run([node, "--check", "-"], input="\n".join(scripts),
                            text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_no_tracked_source_or_document_contains_a_real_provider_credential():
    names = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                           capture_output=True, check=True).stdout.split(b"\0")
    patterns = (
        re.compile(re.escape(b"sk-" + b"proj-") + rb"[A-Za-z0-9_-]{80,}"),
        re.compile(re.escape(b"sk-" + b"ant-api") + rb"[A-Za-z0-9_-]{80,}"),
        re.compile(re.escape(b"gh" + b"o_") + rb"[A-Za-z0-9]{32,}"),
    )
    found = []
    for raw_name in filter(None, names):
        path = ROOT / raw_name.decode()
        try:
            body = path.read_bytes()
        except OSError:
            continue
        if any(pattern.search(body) for pattern in patterns):
            found.append(path.relative_to(ROOT).as_posix())
    assert found == []
