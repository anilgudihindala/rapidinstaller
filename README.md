# Rapid Installer ⚡
> **The Ultimate Smart Package Installer & Application Manager for Linux**

Rapid Installer is a modern, enterprise-grade Linux application installer and manager that brings macOS-style desktop application deployment to Ubuntu, Debian, and Linux platforms. It eliminates manual terminal extraction, binary hunting, and shell script configuration when installing software archives and packages (`.tar.gz`, `.deb`, `.zip`, `.AppImage`, `.rpm`, `.7z`, `.tar.xz`).

---

## 🌟 Key Features

- 📦 **Universal Multi-Format Package Extraction**: Automatically extracts and deploys `.deb`, `.tar.gz`, `.zip`, `.AppImage`, `.rpm`, `.7z`, `.tar.xz`, and `.tar.bz2` packages in user-space (`~/.local/opt/`) without requiring `sudo` or root permissions.
- 🚀 **GTK Application Manager Dashboard**: Modern GTK3 dark-mode dashboard displaying all installed applications, storage space analytics, live search filtering, and one-click app launch / clean uninstallation.
- 🔍 **Smart Heuristic Binary Scanner**: Automatically scans extracted directory trees and ranks true binary entry points using scoring heuristics, ignoring background helper binaries like `chrome-sandbox`.
- ⚠️ **Already-Installed Detection**: Prompts with options (🚀 *Launch Existing App*, 🔄 *Reinstall / Upgrade*, or *Cancel*) when opening a package for an already-installed application.
- 🖱️ **Drag & Drop Package Installation**: Drag any package archive from Nautilus/Dolphin directly into the Rapid Installer window to install instantly.
- ★ **One-Click Default System Installer**: Register Rapid Installer as your default system handler for all Linux packages and archives with a single click.

---

## ⚡ Quick Start

### 1. Installation
Clone the repository and run the setup installer:
```bash
git clone https://github.com/anilgudihindala/RapidInstaller.git
cd RapidInstaller
./install.sh
```

### 2. Launching the App Manager
```bash
rapid-installer
```
*(Or click **Rapid Installer** in your system Applications menu)*

### 3. Graphical Package Installation
1. Open your file manager (Nautilus, Dolphin, Thunar).
2. Right-click any package or archive (`.deb`, `.tar.gz`, `.zip`, `.AppImage`).
3. Select **Open With Rapid Installer**.

### 4. Command Line Usage
```bash
# Install a package archive
rapid-installer /path/to/my-app-v1.0.tar.gz

# Headless / Automated mode
rapid-installer /path/to/my-app-v1.0.tar.gz --no-gui --yes

# List installed applications
rapid-installer --list

# Uninstall an application
rapid-installer --uninstall my-app
```

---

## 📄 License
Licensed under the [MIT License](LICENSE).
