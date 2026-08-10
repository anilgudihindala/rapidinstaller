"""
System-Wide Existing Application Discovery & Adoption Engine for Rapid Installer.

Scans Linux environment (~/.local/share/applications/, /usr/share/applications/,
/opt/, Flatpak, Snap, ~/.local/bin/) to discover user applications installed via other means,
filtering out system core utilities, and offering 1-click adoption into Rapid Installer.
"""

import os
import re
import shutil
from typing import Dict, List, Optional

from applaunch.utils.logger import logger
from applaunch.utils.sys_info import get_environment_info, refresh_desktop_database

# System default utilities to ignore during discovery
SYSTEM_IGNORE_KEYWORDS = [
    "system-settings", "gnome-terminal", "nautilus", "baobab", "eog",
    "evince", "gucharmap", "yelp", "gnome-calculator", "gnome-calendar",
    "gnome-clocks", "gnome-contacts", "gnome-logs", "gnome-maps",
    "gnome-font-viewer", "gnome-disk-utility", "im-config", "nm-connection-editor",
    "htop", "top", "bash", "sh", "python", "perl", "vim", "nano"
]


class ExistingAppDiscoverer:
    """Scans FreeDesktop applications and system directories for unmanaged user apps."""

    @staticmethod
    def scan_unmanaged_applications() -> List[Dict]:
        """
        Scans environment for third-party user applications installed via other means.

        Returns:
            List of application dicts containing app_id, display_name, exec_cmd, desktop_path, source.
        """
        env = get_environment_info()
        managed_opt_dir = env["opt_dir"]
        home = os.path.expanduser("~")

        managed_app_ids = set()
        if os.path.isdir(managed_opt_dir):
            managed_app_ids = {d for d in os.listdir(managed_opt_dir) if os.path.isdir(os.path.join(managed_opt_dir, d))}

        search_desktop_dirs = [
            os.path.join(home, ".local", "share", "applications"),
            "/usr/share/applications",
            "/var/lib/flatpak/exports/share/applications",
            "/var/lib/snapd/desktop/applications",
        ]

        discovered = []
        seen_slugs = set()

        for d in search_desktop_dirs:
            if not os.path.isdir(d):
                continue

            for fname in os.listdir(d):
                if not fname.endswith(".desktop"):
                    continue

                app_slug = fname[:-8].lower()
                if app_slug in managed_app_ids or app_slug in seen_slugs:
                    continue

                if any(kw in app_slug for kw in SYSTEM_IGNORE_KEYWORDS):
                    continue

                desktop_path = os.path.join(d, fname)
                app_info = ExistingAppDiscoverer._parse_desktop_file(desktop_path)
                if not app_info:
                    continue

                # Filter out NoDisplay=true or Non-user applications
                if app_info.get("no_display"):
                    continue

                display_name = app_info.get("name", app_slug.title())
                seen_slugs.add(app_slug)

                source_type = "System / DPKG"
                if "flatpak" in d:
                    source_type = "Flatpak"
                elif "snap" in d:
                    source_type = "Snap"
                elif ".local" in d:
                    source_type = "User Custom (~/.local)"

                discovered.append({
                    "app_id": app_slug,
                    "display_name": display_name,
                    "exec_cmd": app_info.get("exec", ""),
                    "icon": app_info.get("icon", ""),
                    "desktop_file": desktop_path,
                    "source": source_type,
                })

        return sorted(discovered, key=lambda x: x["display_name"].lower())

    @staticmethod
    def adopt_application(app_data: Dict) -> bool:
        """
        Adopts an unmanaged application into Rapid Installer.
        Creates a managed directory in ~/.local/opt/<app_id>/, links execution binary and desktop file.
        """
        env = get_environment_info()
        app_id = app_data["app_id"]
        display_name = app_data["display_name"]
        exec_cmd = app_data["exec_cmd"]
        src_desktop = app_data["desktop_file"]

        opt_path = os.path.join(env["opt_dir"], app_id)
        os.makedirs(opt_path, exist_ok=True)

        # Write managed wrapper marker
        meta_file = os.path.join(opt_path, ".rapid-installer-adopted.json")
        try:
            import json
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(app_data, f, indent=2)
        except Exception:
            pass

        # Create CLI symlink in ~/.local/bin/ if exec binary exists
        clean_binary = exec_cmd.split()[0].replace('"', '').replace("'", "") if exec_cmd else ""
        if clean_binary and os.path.isfile(clean_binary):
            bin_dir = env["bin_dir"]
            os.makedirs(bin_dir, exist_ok=True)
            sym_p = os.path.join(bin_dir, app_id)
            try:
                if os.path.islink(sym_p) or os.path.isfile(sym_p):
                    os.remove(sym_p)
                os.symlink(clean_binary, sym_p)
            except Exception:
                pass

        # Create/Copy desktop file to ~/.local/share/applications/
        dest_desktop = os.path.join(env["apps_dir"], f"{app_id}.desktop")
        if os.path.isfile(src_desktop) and src_desktop != dest_desktop:
            try:
                shutil.copy2(src_desktop, dest_desktop)
            except Exception:
                pass

        refresh_desktop_database()
        logger.info(f"Successfully adopted application '{display_name}' [{app_id}] into Rapid Installer!")
        return True

    @staticmethod
    def _parse_desktop_file(filepath: str) -> Optional[Dict]:
        """Parses Name, Exec, Icon, and NoDisplay from a .desktop file."""
        info = {}
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                in_entry = False
                for line in f:
                    line = line.strip()
                    if line == "[Desktop Entry]":
                        in_entry = True
                        continue
                    elif line.startswith("[") and line.endswith("]"):
                        in_entry = False

                    if in_entry and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k == "Name" and "name" not in info:
                            info["name"] = v
                        elif k == "Exec" and "exec" not in info:
                            info["exec"] = v
                        elif k == "Icon" and "icon" not in info:
                            info["icon"] = v
                        elif k == "NoDisplay" and v.lower() == "true":
                            info["no_display"] = True
            return info if "name" in info or "exec" in info else None
        except Exception:
            return None
