#!/usr/bin/env bash
# ==============================================================================
# Rapid Installer - Open Source One-Line Installer Script
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${BOLD}======================================================${RESET}"
echo -e "${BOLD}        Rapid Installer - Open Source Installer       ${RESET}"
echo -e "${BOLD}======================================================${RESET}"

# 1. Directory setup
TARGET_BIN_DIR="$HOME/.local/bin"
TARGET_APPS_DIR="$HOME/.local/share/applications"
TARGET_ENGINE_DIR="$HOME/.local/share/applaunch/engine"
TARGET_OPT_DIR="$HOME/.local/opt"
TARGET_ICONS_DIR="$HOME/.local/share/icons"

mkdir -p "$TARGET_BIN_DIR" "$TARGET_APPS_DIR" "$TARGET_ENGINE_DIR" "$TARGET_OPT_DIR" "$TARGET_ICONS_DIR" "$HOME/Desktop"

# Handle one-line curl | bash execution
if [ ! -d "$SCRIPT_DIR/applaunch" ]; then
    echo -e "${BLUE}[INFO]${RESET} Fetching Rapid Installer payload from GitHub..."
    TMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TMP_DIR"' EXIT
    if command -v git &>/dev/null; then
        git clone --depth 1 https://github.com/anilgudihindala/RapidInstaller.git "$TMP_DIR/repo" >/dev/null 2>&1 || true
    fi
    if [ ! -d "$TMP_DIR/repo/applaunch" ]; then
        curl -fsSL https://github.com/anilgudihindala/RapidInstaller/archive/refs/heads/main.zip -o "$TMP_DIR/repo.zip"
        unzip -q "$TMP_DIR/repo.zip" -d "$TMP_DIR"
        mv "$TMP_DIR/RapidInstaller-main" "$TMP_DIR/repo"
    fi
    SCRIPT_DIR="$TMP_DIR/repo"
fi

# 2. Deploy Engine Files
echo -e "${BLUE}[INFO]${RESET} Deploying Rapid Installer engine files to $TARGET_ENGINE_DIR..."
rm -rf "$TARGET_ENGINE_DIR"/*
cp -r "$SCRIPT_DIR/applaunch" "$TARGET_ENGINE_DIR/"
cp "$SCRIPT_DIR/smart_installer.py" "$TARGET_ENGINE_DIR/"
cp "$SCRIPT_DIR/main.py" "$TARGET_ENGINE_DIR/"
chmod +x "$TARGET_ENGINE_DIR/smart_installer.py" "$TARGET_ENGINE_DIR/main.py"

# 3. Create Symlinks in ~/.local/bin
SYMLINK_PATH="$TARGET_BIN_DIR/rapid-installer"
echo -e "${BLUE}[INFO]${RESET} Creating executable symlinks..."
rm -f "$SYMLINK_PATH" "$TARGET_BIN_DIR/applaunch" "$TARGET_BIN_DIR/rapidinstaller"
ln -s "$TARGET_ENGINE_DIR/smart_installer.py" "$SYMLINK_PATH"
ln -s "$TARGET_ENGINE_DIR/smart_installer.py" "$TARGET_BIN_DIR/rapidinstaller"
ln -s "$TARGET_ENGINE_DIR/smart_installer.py" "$TARGET_BIN_DIR/applaunch"
chmod +x "$SYMLINK_PATH"

# 4. Copy Icon & Desktop File
echo -e "${BLUE}[INFO]${RESET} Installing application icons & desktop menu shortcuts..."
if [ -f "$SCRIPT_DIR/assets/rapid-installer.jpg" ]; then
    cp "$SCRIPT_DIR/assets/rapid-installer.jpg" "$TARGET_ICONS_DIR/rapid-installer.jpg"
fi

if [ -f "$SCRIPT_DIR/desktop/rapid-installer.desktop" ]; then
    cp "$SCRIPT_DIR/desktop/rapid-installer.desktop" "$TARGET_APPS_DIR/rapid-installer.desktop"
    chmod +x "$TARGET_APPS_DIR/rapid-installer.desktop"
    cp "$SCRIPT_DIR/desktop/rapid-installer.desktop" "$HOME/Desktop/Rapid Installer.desktop"
    chmod +x "$HOME/Desktop/Rapid Installer.desktop"
    if command -v gio &>/dev/null; then
        gio set "$HOME/Desktop/Rapid Installer.desktop" metadata::trusted true >/dev/null 2>&1 || true
        pkill -f ding.js >/dev/null 2>&1 || true
    fi
fi

# 5. Set MIME Associations
echo -e "${BLUE}[INFO]${RESET} Registering archive & package MIME type associations..."
MIME_FILE="$TARGET_APPS_DIR/mimeapps.list"
mkdir -p "$TARGET_APPS_DIR"
cat <<EOF > "$MIME_FILE"
[Default Applications]
application/x-compressed-tar=rapid-installer.desktop;
application/x-gzip=rapid-installer.desktop;
application/x-tar=rapid-installer.desktop;
application/x-gtar=rapid-installer.desktop;
application/zip=rapid-installer.desktop;
application/x-xz=rapid-installer.desktop;
application/x-bzip2=rapid-installer.desktop;
application/x-7z-compressed=rapid-installer.desktop;
application/x-deb=rapid-installer.desktop;
application/vnd.debian.binary-package=rapid-installer.desktop;
application/x-debian-package=rapid-installer.desktop;
application/x-rpm=rapid-installer.desktop;
application/x-rar=rapid-installer.desktop;
application/x-iso9660-image=rapid-installer.desktop;

[Added Associations]
application/x-compressed-tar=rapid-installer.desktop;
application/x-gzip=rapid-installer.desktop;
application/x-tar=rapid-installer.desktop;
application/x-gtar=rapid-installer.desktop;
application/zip=rapid-installer.desktop;
application/x-xz=rapid-installer.desktop;
application/x-bzip2=rapid-installer.desktop;
application/x-7z-compressed=rapid-installer.desktop;
application/x-deb=rapid-installer.desktop;
application/vnd.debian.binary-package=rapid-installer.desktop;
application/x-debian-package=rapid-installer.desktop;
application/x-rpm=rapid-installer.desktop;
application/x-rar=rapid-installer.desktop;
application/x-iso9660-image=rapid-installer.desktop;
EOF

# 6. Flush Caches
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$TARGET_APPS_DIR" >/dev/null 2>&1 || true
fi

echo -e "\n${GREEN}[SUCCESS]${RESET} Rapid Installer installed successfully!"
echo -e "${BOLD}Usage:${RESET}"
echo -e "  - App Dashboard: Run 'rapid-installer' or click 'Rapid Installer' in Apps menu"
echo -e "  - Graphical Install: Right-click any package (.tar.gz, .deb, .zip, .AppImage) -> Open With Rapid Installer"
echo -e "  - Command Line: rapid-installer /path/to/archive.tar.gz"
echo -e "${BOLD}======================================================${RESET}"
