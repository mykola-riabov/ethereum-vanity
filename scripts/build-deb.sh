#!/usr/bin/env bash
# Build a self-contained .deb with bundled Python venv, GUI launcher, and CLI tools.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PKG="ethereum-vanity"
ARCH="all"
VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
MAINTAINER="Mykola Riabov <mykola-riabov@users.noreply.github.com>"

BUILD_DIR="$ROOT/build/deb"
STAGE="$BUILD_DIR/root"
VENV_DIR="$BUILD_DIR/venv"
OUT_DIR="$ROOT/dist"
DEB_FILE="$OUT_DIR/${PKG}_${VERSION}_${ARCH}.deb"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need python3
need fakeroot
need dpkg-deb

if ! python3 -m venv -h >/dev/null 2>&1; then
  echo "python3-venv is required. Install: sudo apt install python3-venv" >&2
  exit 1
fi

echo "==> Building ${PKG} ${VERSION} (${ARCH})"

rm -rf "$BUILD_DIR"
mkdir -p "$STAGE/usr/lib/$PKG" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps" "$OUT_DIR"

echo "==> Creating virtualenv and installing Python package"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV_DIR/bin/pip" install "$ROOT" >/dev/null

echo "==> Staging application files"
cp -a "$VENV_DIR" "$STAGE/usr/lib/$PKG/venv"

install -m 755 /dev/stdin "$STAGE/usr/bin/eth-vanity-gui" <<'EOF'
#!/bin/sh
exec /usr/lib/ethereum-vanity/venv/bin/python3 -m gui "$@"
EOF

install -m 755 /dev/stdin "$STAGE/usr/bin/eth-vanity" <<'EOF'
#!/bin/sh
exec /usr/lib/ethereum-vanity/venv/bin/eth-vanity "$@"
EOF

install -m 755 /dev/stdin "$STAGE/usr/bin/eth-scan" <<'EOF'
#!/bin/sh
exec /usr/lib/ethereum-vanity/venv/bin/eth-scan "$@"
EOF

install -m 644 "$ROOT/debian/ethereum-vanity.desktop" \
  "$STAGE/usr/share/applications/ethereum-vanity.desktop"

if [ -f "$ROOT/debian/icons/ethereum-vanity.svg" ]; then
  install -m 644 "$ROOT/debian/icons/ethereum-vanity.svg" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps/ethereum-vanity.svg"
  if [ -d "$ROOT/debian/icons/hicolor" ]; then
    for png in "$ROOT/debian/icons/hicolor"/*/apps/ethereum-vanity.png; do
      [ -f "$png" ] || continue
      size="$(basename "$(dirname "$(dirname "$png")")")"
      mkdir -p "$STAGE/usr/share/icons/hicolor/${size}/apps"
      install -m 644 "$png" "$STAGE/usr/share/icons/hicolor/${size}/apps/ethereum-vanity.png"
    done
  elif command -v rsvg-convert >/dev/null 2>&1; then
    for size in 16 32 48 64 128 256; do
      mkdir -p "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps"
      rsvg-convert -w "$size" -h "$size" "$ROOT/debian/icons/ethereum-vanity.svg" \
        -o "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps/ethereum-vanity.png"
    done
  fi
fi

mkdir -p "$STAGE/DEBIAN"
install -m 644 /dev/stdin "$STAGE/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10), libxcb-cursor0
Maintainer: ${MAINTAINER}
Homepage: https://github.com/mykola-riabov/ethereum-vanity
Description: Ethereum vanity address generator (CPU)
 GUI and CLI for generating custom EVM addresses (0x…).
 Same address on Ethereum, Polygon, BSC, and other EVM chains.
 .
 Installed commands:
  - eth-vanity-gui  desktop GUI
  - eth-vanity      CLI generator
  - eth-scan        balance scanner via JSON-RPC
EOF

install -m 755 /dev/stdin "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
EOF

install -m 755 /dev/stdin "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
  fi
fi
EOF

echo "==> Building .deb package"
fakeroot dpkg-deb --root-owner-group -Zgzip -b "$STAGE" "$DEB_FILE"

echo
echo "Done: $DEB_FILE"
echo "Install: sudo apt install ./dist/${PKG}_${VERSION}_${ARCH}.deb"
echo "Launch GUI: eth-vanity-gui"
