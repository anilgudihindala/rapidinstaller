#!/usr/bin/env bash
# ==============================================================================
# Rapid Installer - Launchpad PPA Source Package Builder
# Builds source package and uploads to Launchpad PPA
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "==> Building Ubuntu Launchpad PPA Source Package..."
cd "$REPO_DIR"

if ! command -v debuild &>/dev/null; then
    echo "[ERROR] debuild not installed. Run: sudo apt install devscripts build-essential debhelper"
    exit 1
fi

# Build source package without binary compilation (for Launchpad builders)
debuild -S -sa -k"$GPG_KEY_ID"

echo "==> Source package built successfully. Upload to PPA with:"
echo "    dput ppa:anilgudihindala/rapid-installer ../rapid-installer_1.0.0-1_source.changes"
