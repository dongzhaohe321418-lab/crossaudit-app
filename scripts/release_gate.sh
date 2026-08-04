#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="$(command -v python3)"; fi
GATE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/crossaudit-release-gate.XXXXXX")"
trap 'rm -rf "$GATE_TMP"' EXIT

VERSION="$($PYTHON_BIN -c 'import sys;sys.path.insert(0,"src");import crossaudit;print(crossaudit.__version__)')"

if [[ "${1:-}" == "--require-clean" && -n "$(git status --short)" ]]; then
  echo "Release gate requires a clean worktree." >&2
  exit 2
fi

echo "[1/7] Static correctness"
$PYTHON_BIN -m ruff check --select E9,F63,F7,F82 src tests packaging/verify_python_package.py
$PYTHON_BIN -m compileall -q src tests packaging/verify_python_package.py
bash -n packaging/macos/build_dmg.sh packaging/macos/verify_dmg.sh
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  swiftc -typecheck -target arm64-apple-macos13.0 -framework AppKit -framework WebKit \
    packaging/macos/CrossAuditApp.swift
fi

echo "[2/7] Full suite with per-test timeout"
PYTHONPATH=src $PYTHON_BIN -m coverage erase
PYTHONPATH=src $PYTHON_BIN -m coverage run -m pytest -q --timeout=30

echo "[3/7] Branch coverage floor"
$PYTHON_BIN -m coverage report

echo "[4/7] Wheel and source distribution"
$PYTHON_BIN -m build --outdir "$GATE_TMP/dist"

echo "[5/7] Fresh-environment wheel install and runtime self-test"
WHEEL="$(find "$GATE_TMP/dist" -maxdepth 1 -name '*.whl' -print -quit)"
$PYTHON_BIN packaging/verify_python_package.py "$WHEEL" --expected-version "$VERSION"

echo "[6/7] Installed dependency audit"
if $PYTHON_BIN -c 'import pip_audit' 2>/dev/null; then
  $PYTHON_BIN -m pip freeze | grep -viE '^crossaudit([=@ ]|$)' > "$GATE_TMP/audit-requirements.txt"
  $PYTHON_BIN -m pip_audit --strict -r "$GATE_TMP/audit-requirements.txt"
else
  echo "pip-audit is not installed locally; CI remains authoritative for this gate."
fi

echo "[7/7] Repository hygiene"
git diff --check
if git ls-files | grep -E '(^|/)(\.env($|\.)|console\.json$|CrossAudit\.log$)' >/dev/null; then
  echo "Tracked runtime credential or log file detected." >&2
  exit 3
fi

echo "CrossAudit $VERSION release gate passed."
