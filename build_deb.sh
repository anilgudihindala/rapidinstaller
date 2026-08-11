#!/usr/bin/env bash
# ==============================================================================
# Rapid Installer - Debian (.deb) Package Generator
# Builds rapid-installer_1.0.0_all.deb for GitHub Releases
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build/rapid-installer_1.0.0_all"
DIST_DIR="$SCRIPT_DIR/dist"

echo "==> Building Rapid Installer Debian (.deb) package..."

# Clean old build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons"
mkdir -p "$BUILD_DIR/usr/share/rapid-installer"
mkdir -p "$DIST_DIR"

# 1. DEBIAN/control file
cat <<EOF > "$BUILD_DIR/DEBIAN/control"
Package: rapid-installer
Version: 1.0.0
Section: utils
Priority: optional
Architecture: all
Maintainer: Anil Gudihindala <https://github.com/anilgudihindala/RapidInstaller>
Depends: python3, python3-gi, gir1.2-gtk-3.0, python3-pil, zenity
Description: Universal Package Installer & GTK Application Manager for Linux
 Rapid Installer brings macOS-style desktop application deployment
 and package management to Ubuntu, Debian, and Linux platforms.
 Supports 1-click installation of .deb, .tar.gz, .zip, .AppImage, and .rpm.
EOF

# 2. DEBIAN/postinst script
cat <<EOF > "$BUILD_DIR/DEBIAN/postinst"
#!/bin/sh
set -e

chmod +x /usr/share/rapid-installer/smart_installer.py
chmod +x /usr/share/rapid-installer/main.py

ln -sf /usr/share/rapid-installer/smart_installer.py /usr/bin/rapid-installer
ln -sf /usr/share/rapid-installer/smart_installer.py /usr/bin/rapidinstaller
ln -sf /usr/share/rapid-installer/smart_installer.py /usr/bin/applaunch

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

exit 0
EOF
chmod +x "$BUILD_DIR/DEBIAN/postinst"

# 3. Copy Application Payload
cp -r "$SCRIPT_DIR/applaunch" "$BUILD_DIR/usr/share/rapid-installer/"
cp "$SCRIPT_DIR/main.py" "$BUILD_DIR/usr/share/rapid-installer/"
cp "$SCRIPT_DIR/smart_installer.py" "$BUILD_DIR/usr/share/rapid-installer/"
chmod +x "$BUILD_DIR/usr/share/rapid-installer/smart_installer.py" "$BUILD_DIR/usr/share/rapid-installer/main.py"

# Symlink executable entry point
ln -sf /usr/share/rapid-installer/smart_installer.py "$BUILD_DIR/usr/bin/rapid-installer"

# 4. Copy Desktop Entry & Icon
if [ -f "$SCRIPT_DIR/desktop/rapid-installer.desktop" ]; then
    cp "$SCRIPT_DIR/desktop/rapid-installer.desktop" "$BUILD_DIR/usr/share/applications/rapid-installer.desktop"
    chmod +x "$BUILD_DIR/usr/share/applications/rapid-installer.desktop"
fi

if [ -f "$SCRIPT_DIR/assets/rapid-installer.jpg" ]; then
    cp "$SCRIPT_DIR/assets/rapid-installer.jpg" "$BUILD_DIR/usr/share/icons/rapid-installer.jpg"
fi

# 5. Build .deb package via dpkg-deb
DEB_FILE="$DIST_DIR/rapid-installer_1.0.0_all.deb"
dpkg-deb -b "$BUILD_DIR" "$DEB_FILE"

echo "==> Successfully created Debian package: $DEB_FILE"
ls -lh "$DEB_FILE"
