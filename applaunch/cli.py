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
    from applaunch.utils.sys_info import is_protected_system_app
    if is_protected_system_app(app_id):
        print(f"[Rapid Installer] 🔒 Cannot uninstall '{app_id}': Core system component protected from removal.")
        return False

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

    parser.add_argument(
        "--trash",
        "-t",
        action="store_true",
        help="Move installer archive to system Trash after successful installation",
    )

    parser.add_argument(
        "--toolchain",
        nargs="*",
        metavar=("ACTION", "TOOL_ID"),
        help="Manage developer toolchains (e.g. --toolchain list, --toolchain install nvm, --toolchain uninstall bun)",
    )
    parser.add_argument(
        "--setup-curl-hook",
        action="store_true",
        help="Installs terminal curl interceptor hook in ~/.bashrc / ~/.zshrc",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Scans system for unmanaged applications installed by other means",
    )
    parser.add_argument(
        "--adopt",
        metavar="APP_ID",
        help="Adopts an unmanaged application into Rapid Installer by App ID",
    )

    parsed = parser.parse_args(args_list)

    if parsed.discover:
        from applaunch.core.discovery import ExistingAppDiscoverer
        unmanaged = ExistingAppDiscoverer.scan_unmanaged_applications()
        print("\n=======================================================")
        print(f" Rapid Installer - Discovered Unmanaged Apps ({len(unmanaged)})")
        print("=======================================================")
        for a in unmanaged:
            print(f"• {a['display_name']} [{a['app_id']}]")
            print(f"    Source:       {a['source']}")
            print(f"    Desktop File: {a['desktop_file']}\n")
        print("Run 'rapid-installer --adopt <app_id>' to adopt any app into Rapid Installer.")
        print("=======================================================\n")
        return 0

    if parsed.adopt:
        from applaunch.core.discovery import ExistingAppDiscoverer
        unmanaged = ExistingAppDiscoverer.scan_unmanaged_applications()
        target = next((a for a in unmanaged if a["app_id"] == parsed.adopt or a["display_name"].lower() == parsed.adopt.lower()), None)
        if target:
            ExistingAppDiscoverer.adopt_application(target)
            print(f"[Rapid Installer] Successfully adopted '{target['display_name']}' into Rapid Installer.")
            return 0
        else:
            print(f"[Rapid Installer] Could not find unmanaged app '{parsed.adopt}'. Run --discover to view available apps.")
            return 1

    if parsed.setup_curl_hook:
        from applaunch.utils.shell_env import inject_shell_profile_block
        hook_code = (
            '# Rapid Installer Smart Curl Interceptor\n'
            'rapid_curl_install() {\n'
            '    if [[ "$*" == *"raw.githubusercontent.com"* || "$*" == *"install.sh"* || "$*" == *"bun.sh/install"* ]]; then\n'
            '        echo "[Rapid Installer] Intercepted runtime setup script."\n'
            '    fi\n'
            '    command curl "$@"\n'
            '}'
        )
        inject_shell_profile_block("curl-hook", hook_code)
        print("[Rapid Installer] Successfully installed terminal curl interceptor hook in your shell profiles.")
        return 0

    if parsed.toolchain:
        from applaunch.core.toolchains import ToolchainManager
        action = parsed.toolchain[0].lower() if parsed.toolchain else "list"
        if action == "list":
            tools = ToolchainManager.list_all_toolchains()
            print("\n=======================================================")
            print(" Rapid Installer - Developer Runtimes & Toolchains")
            print("=======================================================")
            for t in tools:
                status = f"✓ Installed ({t['version']})" if t["installed"] else "Not Installed"
                print(f"• {t['display_name']} [{t['id']}]")
                print(f"    Category: {t['category']}")
                print(f"    Status:   {status}\n")
            print("=======================================================\n")
            return 0
        elif action == "install" and len(parsed.toolchain) > 1:
            tool_id = parsed.toolchain[1].lower()
            res = ToolchainManager.install_toolchain(tool_id)
            if res.get("status") == "SUCCESS":
                print(f"[Rapid Installer] Successfully installed developer toolchain '{tool_id}' ({res.get('version')}).")
                return 0
            else:
                print(f"[Rapid Installer] Error installing '{tool_id}': {res.get('msg')}")
                return 1
        elif action == "uninstall" and len(parsed.toolchain) > 1:
            tool_id = parsed.toolchain[1].lower()
            if ToolchainManager.uninstall_toolchain(tool_id):
                print(f"[Rapid Installer] Successfully uninstalled developer toolchain '{tool_id}'.")
                return 0
            else:
                print(f"[Rapid Installer] Could not uninstall '{tool_id}'.")
                return 1

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
    if metrics.get("status") == "SUCCESS":
        from applaunch.utils.sys_info import load_config, move_to_trash
        config = load_config()
        if parsed.trash or config.get("auto_trash_installer"):
            move_to_trash(archive_file)
            print(f"[Rapid Installer] Moved installer archive '{archive_file}' to Trash to save space.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
