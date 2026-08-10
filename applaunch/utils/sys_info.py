"""
System and Environment Information Utility for AppLaunch Engine.

Provides platform detection, binary resolution, environment path expansion,
and dependency verification helpers.
"""

import json
import os
import shutil
import subprocess
from typing import Dict, Optional


def get_environment_info() -> Dict[str, str]:
    """Retrieves Linux system environment variables and path specs."""
    home_dir = os.path.expanduser("~")
    opt_dir = os.path.join(home_dir, ".local", "opt")
    apps_dir = os.path.join(home_dir, ".local", "share", "applications")
    icons_dir = os.path.join(home_dir, ".local", "share", "icons")
    bin_dir = os.path.join(home_dir, ".local", "bin")

    return {
        "user": os.getenv("USER", os.getenv("LOGNAME", "unknown")),
        "home": home_dir,
        "opt_dir": opt_dir,
        "apps_dir": apps_dir,
        "icons_dir": icons_dir,
        "bin_dir": bin_dir,
        "desktop_env": os.getenv("XDG_CURRENT_DESKTOP", "GNOME"),
    }


def ensure_user_directories() -> None:
    """Ensures all standard user local directories (~/.local/opt, etc.) exist."""
    env = get_environment_info()
    for dir_path in [env["opt_dir"], env["apps_dir"], env["icons_dir"], env["bin_dir"]]:
        os.makedirs(dir_path, exist_ok=True)


def is_binary_available(binary_name: str) -> bool:
    """Checks if a command-line executable exists in system PATH."""
    return shutil.which(binary_name) is not None


def refresh_desktop_database() -> bool:
    """Flushes Linux application menu caches via update-desktop-database."""
    apps_dir = os.path.expanduser("~/.local/share/applications")
    if is_binary_available("update-desktop-database"):
        ret = os.system(f"update-desktop-database '{apps_dir}' >/dev/null 2>&1")
        return ret == 0
    return False


def get_installed_apps() -> list:
    """Returns detailed metadata for all applications managed in ~/.local/opt/."""
    env = get_environment_info()
    opt_dir = env["opt_dir"]
    apps = []

    if not os.path.isdir(opt_dir):
        return apps

    for entry in sorted(os.listdir(opt_dir)):
        full_path = os.path.join(opt_dir, entry)
        if not os.path.isdir(full_path):
            continue

        # Compute directory disk usage
        total_size = 0
        try:
            for root, _, files in os.walk(full_path):
                for f in files:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        except Exception:
            pass

        size_mb = round(total_size / (1024 * 1024), 1)

        # Inspect desktop file for metadata
        desktop_file = os.path.join(env["apps_dir"], f"{entry}.desktop")
        display_name = entry.replace("-", " ").replace("_", " ").title()
        icon_path = None
        exec_cmd = None
        has_shortcut = os.path.isfile(desktop_file)

        if has_shortcut:
            try:
                with open(desktop_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str.startswith("Name=") and not line_str.startswith("Name["):
                            display_name = line_str.split("=", 1)[1]
                        elif line_str.startswith("Icon="):
                            icon_path = line_str.split("=", 1)[1]
                        elif line_str.startswith("Exec="):
                            exec_cmd = line_str.split("=", 1)[1]
            except Exception:
                pass

        # Fallback icon search if desktop file didn't specify valid path
        if not icon_path or not os.path.isfile(icon_path):
            for ext in [".png", ".svg", ".jpg"]:
                cand = os.path.join(env["icons_dir"], f"{entry}{ext}")
                if os.path.isfile(cand):
                    icon_path = cand
                    break

        apps.append({
            "app_id": entry,
            "display_name": display_name,
            "path": full_path,
            "size_mb": size_mb,
            "icon_path": icon_path,
            "exec_cmd": exec_cmd,
            "has_shortcut": has_shortcut,
            "desktop_file": desktop_file if has_shortcut else None,
        })

    return apps


def is_default_installer() -> bool:
    """Returns True if Rapid Installer is registered as default in mimeapps.list."""
    mime_file = os.path.expanduser("~/.local/share/applications/mimeapps.list")
    if os.path.isfile(mime_file):
        try:
            with open(mime_file, "r", encoding="utf-8") as f:
                content = f.read()
                return "application/x-compressed-tar=rapid-installer.desktop" in content
        except Exception:
            pass
    return False


def set_as_default_installer() -> bool:
    """Registers Rapid Installer as default application installer for all archive & package formats."""
    apps_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(apps_dir, exist_ok=True)
    mime_file = os.path.join(apps_dir, "mimeapps.list")

    mime_types = [
        "application/x-compressed-tar",
        "application/x-gzip",
        "application/x-tar",
        "application/x-gtar",
        "application/zip",
        "application/x-xz",
        "application/x-bzip2",
        "application/x-7z-compressed",
        "application/x-deb",
        "application/vnd.debian.binary-package",
        "application/x-debian-package",
        "application/x-rpm",
        "application/x-rar",
        "application/x-iso9660-image",
    ]

    lines_to_write = ["[Default Applications]\n"]
    for m in mime_types:
        lines_to_write.append(f"{m}=rapid-installer.desktop;\n")

    lines_to_write.append("\n[Added Associations]\n")
    for m in mime_types:
        lines_to_write.append(f"{m}=rapid-installer.desktop;\n")

    with open(mime_file, "w", encoding="utf-8") as f:
        f.writelines(lines_to_write)

    refresh_desktop_database()
    if is_binary_available("update-mime-database"):
        os.system("update-mime-database ~/.local/share/mime >/dev/null 2>&1")

    return True


CONFIG_PATH = os.path.expanduser("~/.config/rapid-installer/config.json")


def load_config() -> dict:
    """Loads user configuration settings from ~/.config/rapid-installer/config.json."""
    defaults = {
        "auto_trash_installer": False,
        "prompt_trash_installer": True,
    }
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults


def save_config(config_dict: dict) -> bool:
    """Saves user configuration settings to ~/.config/rapid-installer/config.json."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)
        return True
    except Exception:
        return False


def get_app_residual_paths(app_id: str) -> list:
    """Scans user environment for residual configuration & cache directories."""
    home_dir = os.path.expanduser("~")
    candidates = [
        os.path.join(home_dir, ".config", app_id),
        os.path.join(home_dir, ".cache", app_id),
        os.path.join(home_dir, ".local", "share", app_id),
    ]

    clean_id = app_id.replace("-", "").replace("_", "")
    candidates.append(os.path.join(home_dir, ".config", clean_id))
    candidates.append(os.path.join(home_dir, ".cache", clean_id))

    found = []
    for path in candidates:
        if os.path.exists(path) and path not in found:
            if path != os.path.join(home_dir, ".local", "opt", app_id):
                found.append(path)

    return found


def move_to_trash(file_path: str) -> bool:
    """Moves a file or directory to Linux system trash."""
    if not file_path:
        return False

    abs_path = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.exists(abs_path):
        return False

    # 1. Try gio trash
    if is_binary_available("gio"):
        try:
            res = subprocess.run(["gio", "trash", abs_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0 and not os.path.exists(abs_path):
                return True
        except Exception:
            pass

    # 2. Try trash-cli
    if is_binary_available("trash-put"):
        try:
            res = subprocess.run(["trash-put", abs_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0 and not os.path.exists(abs_path):
                return True
        except Exception:
            pass

    # 3. Fallback: move to ~/.local/share/Trash/files/
    try:
        trash_dir = os.path.expanduser("~/.local/share/Trash/files")
        os.makedirs(trash_dir, exist_ok=True)
        dest_p = os.path.join(trash_dir, os.path.basename(abs_path))
        shutil.move(abs_path, dest_p)
        return True
    except Exception:
        return False

