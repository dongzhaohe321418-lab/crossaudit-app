"""North Star §22: Settings is a searchable 12-group architecture.

These tests pin the information architecture (the 12 groups + search shell),
the honesty rule (real controls stay, absent ones are honestly labelled), the
static PAGE contract (unique ids, named dialog), the search filter logic, and
§24 Chinese parity for every new visible string.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from html.parser import HTMLParser

from crossaudit.console.page import PAGE


# ---------------------------------------------------------------- static shell
# The exact §22 set and order. Attribute markers are the stable contract.
GROUPS = [
    "general", "providers", "agent", "audit", "files", "github",
    "compute", "integrations", "usage", "security", "diagnostics", "advanced",
]


def test_settings_exposes_all_twelve_north_star_groups():
    for group in GROUPS:
        assert f'data-settings-panel="{group}"' in PAGE, group
        assert f'data-settings-pane="{group}"' in PAGE, group
    # The nav is the same reused design language (not a new visual system).
    assert 'class="settings-nav" aria-label="Settings sections"' in PAGE
    # Every group nav button is a real button in the one settings modal.
    assert PAGE.count('class="form-section settings-pane"') == len(GROUPS)
    assert PAGE.count('id="settings-modal"') == 1


def test_settings_search_control_is_present_and_accessible():
    assert 'id="settings-search"' in PAGE
    assert 'role="searchbox"' in PAGE
    assert 'aria-label="Search settings"' in PAGE
    assert 'placeholder="Search settings…"' in PAGE
    assert 'id="settings-search-results"' in PAGE
    assert 'role="listbox"' in PAGE
    # Wired to a real filter that runs on input.
    assert "function filterSettings()" in PAGE
    assert "function settingsSearchMatch(entry,q)" in PAGE
    assert "getElementById('settings-search').addEventListener('input',filterSettings)" in PAGE


def test_settings_panel_switcher_signature_is_preserved():
    # Existing tests and callers depend on this exact signature.
    assert "function showSettingsPanel(name,focus=true)" in PAGE
    assert "const SETTINGS_PANELS=[" in PAGE
    for group in GROUPS:
        assert f"'{group}'" in PAGE


def test_preserved_real_controls_still_live_in_the_new_ia():
    # Providers: credential save/validate machinery is untouched.
    assert '<details class="credential-card"' in PAGE
    assert 'id="provider-credentials"' in PAGE
    assert 'class="wizard-error" id="settings-error" role="alert"' in PAGE
    # Diagnostics: the Doctor moved here but keeps its asserted ids.
    assert 'id="doctor-checks"' in PAGE
    assert 'id="run-doctor"' in PAGE
    assert 'id="toggle-doctor-details" aria-expanded="false"' in PAGE
    # Files: the workspace picker moved here but keeps its ids.
    assert 'id="settings-workspace"' in PAGE
    assert 'id="choose-settings-workspace"' in PAGE
    # General: real, immediately-applied appearance + language controls.
    assert 'id="settings-appearance"' in PAGE
    assert 'id="settings-language"' in PAGE
    # Section reset that genuinely changes behaviour (clears stored theme).
    assert 'id="settings-appearance-system"' in PAGE


def test_honest_placeholders_never_fabricate_a_control():
    # §22 items with no real backing are honestly absent, not fake toggles.
    for honest in (
        "Startup, updates, and notifications follow the macOS app and aren't configurable here yet.",
        "Indexing, preview, temporary files, and large-file handling use built-in defaults and aren't configurable here yet.",
        "Provider routing is set per project. Retention, redaction, and log controls aren't configurable here yet.",
        "Logs, support bundles, and per-subsystem reset aren't available here yet.",
        "No developer settings, experiments, local endpoints, or debug logging are configurable here yet.",
        "Admission and source independence are always-on guarantees, not adjustable settings.",
    ):
        assert honest in PAGE, honest
    # Per-project editors are reached by an honest entry point, not duplicated.
    for target in ("runtime", "compute", "tools", "usage", "runtime-budgets"):
        assert f'data-settings-open="{target}"' in PAGE, target


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.dialogs: list[dict] = []

    def handle_starttag(self, tag, attrs):
        v = dict(attrs)
        if v.get("id"):
            self.ids.append(str(v["id"]))
        if v.get("role") == "dialog":
            self.dialogs.append(v)


def test_static_ui_ids_stay_unique_and_dialog_stays_named():
    parser = _Page()
    parser.feed(PAGE)
    assert [v for v, c in Counter(parser.ids).items() if c > 1] == []
    known = set(parser.ids)
    settings = [d for d in parser.dialogs
                if d.get("aria-labelledby") == "settings-title"]
    assert len(settings) == 1
    dialog = settings[0]
    assert dialog.get("aria-modal") == "true"
    assert dialog.get("aria-labelledby") in known


# ---------------------------------------------------------------- filter logic
def _extract(name: str) -> str:
    match = re.search(name + r"\(entry,q\)\{.*?\n\}", PAGE, re.DOTALL)
    assert match, name
    return match.group(0)


def test_search_filter_matches_on_group_heading_purpose_and_label():
    node = shutil.which("node")
    if not node:  # Python-only machines still run the rest of the suite.
        return
    harness = _extract("function settingsSearchMatch") + """
const A = (cond, msg) => { if (!cond) { throw new Error(msg); } };
// empty query matches everything (restore behaviour)
A(settingsSearchMatch({group:'General'}, ''), 'empty query should match');
// matches on group name
A(settingsSearchMatch({group:'Providers'}, 'prov'), 'group match');
// matches on heading
A(settingsSearchMatch({heading:'Local storage'}, 'storage'), 'heading match');
// matches on purpose text
A(settingsSearchMatch({purpose:'the limits that pause a run'}, 'pause'), 'purpose match');
// matches on control label
A(settingsSearchMatch({label:'Environment Doctor'}, 'doctor'), 'label match');
// matches on hidden keywords
A(settingsSearchMatch({keywords:'keychain redaction'}, 'redaction'), 'keyword match');
// no false positives
A(!settingsSearchMatch({group:'General',label:'Appearance'}, 'zzzz'), 'no false match');
console.log('ok');
"""
    result = subprocess.run([node, "-e", harness],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_search_index_covers_every_group_with_its_purpose():
    # The index a test can read: each group appears with searchable purpose text.
    for group in ("General", "Providers", "Agent behavior", "Audit", "Files",
                  "GitHub", "Compute", "Integrations", "Usage",
                  "Security & privacy", "Diagnostics", "Advanced"):
        assert f"group:'{group}'" in PAGE, group
    for purpose in ("Where CrossAudit keeps projects on this Mac.",
                    "Capabilities the generator can call while it works."):
        assert purpose in PAGE, purpose


# ------------------------------------------------------------------ §24 parity
def test_every_new_settings_string_has_chinese_parity():
    for pair in (
        # 12 group names
        '"Agent behavior":"智能体行为"',
        '"Diagnostics":"诊断"',
        '"Advanced":"高级"',
        '"Security & privacy":"安全与隐私"',
        '"Integrations":"集成"',
        # headings / purposes
        '"Language and appearance":"语言与外观"',
        '"Local storage":"本地存储"',
        '"Where CrossAudit keeps projects on this Mac.":"CrossAudit 在此 Mac 上保存项目的位置。"',
        '"Capabilities the generator can call while it works.":"生成者在工作时可以调用的能力。"',
        # search placeholder + empty state
        '"Search settings…":"搜索设置…"',
        '"No matching settings.":"没有匹配的设置。"',
        # honest "not configurable yet" copy
        '"Startup, updates, and notifications follow the macOS app and aren\'t configurable here yet.":"启动、更新与通知随 macOS 应用一同管理，此处暂不可配置。"',
        # section reset + controls + entry points
        '"Match system":"跟随系统"',
        '"Appearance":"外观"',
        '"Open project controls":"打开项目控制"',
        '"Open remote compute":"打开远程计算"',
    ):
        assert pair in PAGE, pair
