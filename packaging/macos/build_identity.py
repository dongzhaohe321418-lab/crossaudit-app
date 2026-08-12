from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src"))

from crossaudit import __version__
from crossaudit._selfid import code_digest
from crossaudit.auditor.run import dcl_source_digest

target = root / "build" / "macos" / "crossaudit-build.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({
    "version": __version__,
    "code_digest_sha256": code_digest(),
    "dcl_source_sha256": dcl_source_digest(),
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
