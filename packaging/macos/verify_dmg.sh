#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: verify_dmg.sh /path/to/CrossAudit.dmg [expected-version]" >&2
  exit 2
fi

DMG="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
EXPECTED_VERSION="${2:-}"
MOUNT="$(mktemp -d "${TMPDIR:-/tmp}/crossaudit-dmg.XXXXXX")"
ATTACHED=0

cleanup() {
  if [[ "$ATTACHED" == "1" ]]; then
    hdiutil detach -quiet "$MOUNT" || hdiutil detach -quiet -force "$MOUNT" || true
  fi
  rmdir "$MOUNT" 2>/dev/null || true
}
trap cleanup EXIT

[[ -f "$DMG" ]] || { echo "DMG not found: $DMG" >&2; exit 3; }
hdiutil verify "$DMG"
hdiutil attach -quiet -readonly -nobrowse -mountpoint "$MOUNT" "$DMG"
ATTACHED=1

APP="$MOUNT/CrossAudit.app"
CORE="$APP/Contents/Resources/core/CrossAuditCore"
[[ -x "$APP/Contents/MacOS/CrossAudit" && -x "$CORE" ]] || {
  echo "DMG does not contain a complete CrossAudit.app" >&2
  exit 4
}
plutil -lint "$APP/Contents/Info.plist"
codesign --verify --deep --strict --verbose=2 "$APP"
ARCHS="$(lipo -archs "$APP/Contents/MacOS/CrossAudit")"
[[ " $ARCHS " == *" arm64 "* ]] || { echo "native shell is not arm64" >&2; exit 5; }

VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' \
  "$APP/Contents/Info.plist")"
if [[ -n "$EXPECTED_VERSION" && "$VERSION" != "$EXPECTED_VERSION" ]]; then
  echo "DMG version $VERSION does not match expected $EXPECTED_VERSION" >&2
  exit 6
fi

RESULT="$($CORE --self-test)"
SELF_TEST_JSON="$RESULT" EXPECTED_VERSION="$VERSION" python3 - <<'PY'
import json, os
result = json.loads(os.environ["SELF_TEST_JSON"])
if result.get("ok") is not True:
    raise SystemExit("installed frozen runtime self-test failed")
if result.get("version") != os.environ["EXPECTED_VERSION"]:
    raise SystemExit("frozen runtime and bundle versions differ")
if result.get("loopback_token_enforced") is not True:
    raise SystemExit("loopback authentication was not enforced")
for kind in ("pdf", "docx"):
    row = result.get("documents", {}).get(kind, {})
    if row.get("valid") is not True or int(row.get("bytes", 0)) < 100:
        raise SystemExit(f"{kind} round-trip failed")
PY

if [[ "${CROSSAUDIT_PUBLIC_RELEASE:-0}" == "1" ]]; then
  codesign --verify --deep --strict --verbose=2 --check-notarization "$APP"
  xcrun stapler validate "$DMG"
fi

echo "Verified CrossAudit $VERSION DMG, signature, architecture, and frozen runtime."
