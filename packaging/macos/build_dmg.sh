#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$ROOT/build/macos"
DIST="$ROOT/dist"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VERSION="$($PYTHON_BIN -c 'import sys;sys.path.insert(0,"src");import crossaudit;print(crossaudit.__version__)' 2>/dev/null)"
BUILD_NUMBER="${CROSSAUDIT_BUILD_NUMBER:-1}"
ARCH="$(uname -m)"

if [[ "$ARCH" != "arm64" ]]; then
  echo "This build currently targets Apple Silicon; found $ARCH." >&2
  exit 2
fi

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/crossaudit-v4-release.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/CrossAudit.app"
DMG_ROOT="$STAGE/dmg-root"

mkdir -p "$BUILD" "$DIST"
rm -rf "$BUILD/pyinstaller-dist" "$BUILD/pyinstaller-work" "$BUILD/icon.iconset" \
       "$DIST/CrossAudit.app" "$DIST/CrossAudit-$VERSION-arm64.dmg"

if [[ ! -x "$BUILD/venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$BUILD/venv"
fi
"$BUILD/venv/bin/python" -m pip install --disable-pip-version-check -q --upgrade pip wheel
"$BUILD/venv/bin/python" -m pip install --disable-pip-version-check -q "pyinstaller>=6.15" "$ROOT"

cd "$ROOT"
"$BUILD/venv/bin/python" packaging/macos/build_identity.py
"$BUILD/venv/bin/pyinstaller" --noconfirm --clean \
  --distpath "$BUILD/pyinstaller-dist" --workpath "$BUILD/pyinstaller-work" \
  packaging/macos/CrossAuditCore.spec

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/core" \
         "$APP/Contents/Resources/bin" "$APP/Contents/Resources/licenses"
xcrun swiftc -O -target arm64-apple-macos13.0 \
  -framework AppKit -framework WebKit \
  packaging/macos/CrossAuditApp.swift -o "$APP/Contents/MacOS/CrossAudit"
ditto "$BUILD/pyinstaller-dist/CrossAuditCore" "$APP/Contents/Resources/core"

GH_BIN="$(command -v gh || true)"
if [[ -z "$GH_BIN" ]]; then
  echo "GitHub CLI is required to build the complete app bundle." >&2
  exit 3
fi
cp "$GH_BIN" "$APP/Contents/Resources/bin/gh"
chmod 755 "$APP/Contents/Resources/bin/gh"
cp packaging/macos/GITHUB_CLI_LICENSE "$APP/Contents/Resources/licenses/GitHub-CLI-LICENSE"
cp LICENSE "$APP/Contents/Resources/licenses/CrossAudit-LICENSE"

sed -e "s/@VERSION@/$VERSION/g" -e "s/@BUILD@/$BUILD_NUMBER/g" \
  packaging/macos/Info.plist.in > "$APP/Contents/Info.plist"
xcrun swift packaging/macos/make_icon.swift "$BUILD/icon.iconset"
iconutil -c icns "$BUILD/icon.iconset" -o "$APP/Contents/Resources/AppIcon.icns"

# Finder tags, quarantine state, and AppleDouble/resource-fork metadata are not
# application resources. Copying a source tree from a user workspace can attach
# them to nested files, and strict code signing must fail rather than seal that
# machine-local detritus into a release.
xattr -cr "$APP"
codesign --force --deep --sign - --options runtime --timestamp=none "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
plutil -lint "$APP/Contents/Info.plist"

mkdir -p "$DMG_ROOT"
ditto "$APP" "$DMG_ROOT/CrossAudit.app"
ln -s /Applications "$DMG_ROOT/Applications"
hdiutil create -quiet -volname "CrossAudit $VERSION" -srcfolder "$DMG_ROOT" \
  -ov -format UDZO "$DIST/CrossAudit-$VERSION-arm64.dmg"
hdiutil verify "$DIST/CrossAudit-$VERSION-arm64.dmg"
(cd "$DIST" && shasum -a 256 "CrossAudit-$VERSION-arm64.dmg" > \
  "CrossAudit-$VERSION-arm64.dmg.sha256")

echo
echo "Built $DIST/CrossAudit-$VERSION-arm64.dmg"
