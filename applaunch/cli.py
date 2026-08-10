"""
CLI Entry Point & Argument Parser for AppLaunch Engine.

Provides command-line interfaces for package installation, listing installed apps,
and uninstallation management.
"""

import argparse
import os
import shutil
import sys
from typing import List

from applaunch import __version__
from applaunch.core.installer import AppInstallerEngine
from applaunch.utils.logger import logger
from applaunch.utils.sys_info import get_environment_info, refresh_desktop_database


def list_installed_apps() -> None:
    """Lists applications managed in ~/.local/opt/ with their shortcuts."""
    env = get_environment_info()
    opt_dir = env["opt_dir"]

    print("\n==========================================")
    print(" AppLaunch Engine - Managed Applications")
    print("==========================================")

    if not os.path.isdir(opt_dir):
        print("No managed applications found (opt directory does not exist).")
        return

    entries = [
        d for d in os.listdir(opt_dir) if os.path.isdir(os.path.join(opt_dir, d))
    ]

    if not entries:
        print("No installed applications found in ~/.local/opt/")
        return

    for idx, app_id in enumerate(sorted(entries), 1):
        app_path = os.path.join(opt_dir, app_id)
        desktop_file = os.path.join(env["apps_dir"], f"{app_id}.desktop")
        has_shortcut = "Yes" if os.path.isfile(desktop_file) else "No"
        print(f"[{idx}] App ID: {app_id}")
        print(f"    Directory: {app_path}")
        print(f"    Desktop Shortcut: {has_shortcut}")

    print("==========================================\n")


def uninstall_app(app_id: str) -> bool:
    """Uninstalls an application by App ID, removing opt folder, icons, and shortcuts."""
    env = get_environment_info()
    opt_path = os.path.join(env["opt_dir"], app_id)
    desktop_path = os.path.join(env["apps_dir"], f"{app_id}.desktop")
    user_desktop_path = os.path.expanduser(f"~/Desktop/{app_id}.desktop")

    found = False
    if os.path.isdir(opt_path):
        shutil.rmtree(opt_path, ignore_errors=True)
        print(f"Removed opt directory: {opt_path}")
        found = True

    if os.path.isfile(desktop_path):
        os.remove(desktop_path)
        print(f"Removed desktop shortcut: {desktop_path}")
        found = True

    if os.path.isfile(user_desktop_path):
        os.remove(user_desktop_path)
        print(f"Removed ~/Desktop shortcut: {user_desktop_path}")

    # Remove icon if exists
    icons_dir = env["icons_dir"]
    if os.path.isdir(icons_dir):
        for f in os.listdir(icons_dir):
            if f.startswith(app_id):
                os.remove(os.path.join(icons_dir, f))
                print(f"Removed icon resource: {f}")

    if found:
        refresh_desktop_database()
        print(f"Successfully uninstalled '{app_id}'.")
        return True
    else:
        print(f"No installed app found with ID '{app_id}'.")
        return False


def main(args_list: Optional[List[str]] = None) -> int:
    """Main CLI entry point routine."""
    parser = argparse.ArgumentParser(
        prog="rapid-installer",
        description="Rapid Installer - The Ultimate Smart Installer for Linux Packages & Archives.",
    )

    parser.add_argument(
        "archive_path",
        nargs="*",
        help="Path to compressed archive (.tar.gz, .tgz, .tar.xz, .zip, etc.)",
    )
    parser.add_argument(
        "--dest-dir",
        "-d",
        help="Custom installation destination directory (default: ~/.local/opt/<app-id>/)",
    )
    parser.add_argument(
        "--no-gui",
        "--cli",
        action="store_true",
        help="Disable Zenity GUI dialogs and run in terminal console mode",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Automatically confirm prompts without interactive user pause",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all managed applications installed via AppLaunch Engine",
    )
    parser.add_argument(
        "--uninstall",
        "-u",
        metavar="APP_ID",
        help="Uninstall a managed application by its App ID",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"AppLaunch Engine v{__version__}",
    )

    parsed = parser.parse_args(args_list)

    if parsed.list:
        list_installed_apps()
        return 0

    if parsed.uninstall:
        success = uninstall_app(parsed.uninstall)
        return 0 if success else 1

    # Recombine space-split file paths
    archive_file = None
    if isinstance(parsed.archive_path, list) and parsed.archive_path:
        joined_path = " ".join(parsed.archive_path)
        if os.path.exists(joined_path):
            archive_file = joined_path
        elif os.path.exists(parsed.archive_path[0]):
            archive_file = parsed.archive_path[0]
        else:
            archive_file = joined_path
    elif isinstance(parsed.archive_path, str) and parsed.archive_path:
        archive_file = parsed.archive_path

    # Check if GTK GUI Dashboard Manager should be launched
    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    if not parsed.no_gui and has_display:
        try:
            from applaunch.ui.gtk_app import launch_gtk_manager
            return launch_gtk_manager(archive_path=archive_file)
        except Exception as err:
            logger.warning(f"Could not launch GTK Manager UI, falling back: {err}")

    if not archive_file:
        parser.print_help()
        return 1

    engine = AppInstallerEngine(
        archive_path=archive_file,
        custom_dest_dir=parsed.dest_dir,
        force_cli=parsed.no_gui,
    )

    metrics = engine.run_installation(auto_confirm=parsed.yes)
    return 0 if metrics.get("status") == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
