"""
Universal Environment Injection & Desktop Shortcut Hook Generator.

Dynamically formats and installs standardized FreeDesktop '.desktop' application shortcuts,
handling icon deployment, execution flags, and universal $HOME user path mapping.
"""

import os
import shutil
from typing import Dict, Optional

from applaunch.utils.logger import logger
from applaunch.utils.sys_info import get_environment_info, refresh_desktop_database


class DesktopShortcutGenerator:
    """Generates standardized FreeDesktop '.desktop' shortcuts."""

    DEFAULT_CATEGORIES = "Utility;Application;"

    def __init__(
        self,
        app_id: str,
        display_name: str,
        exec_path: str,
        icon_path: Optional[str] = None,
        categories: str = DEFAULT_CATEGORIES,
        comment: str = "Installed via AppLaunch Engine",
    ) -> None:
        self.app_id = app_id
        self.display_name = display_name
        self.exec_path = os.path.abspath(os.path.expanduser(exec_path))
        self.icon_path = (
            os.path.abspath(os.path.expanduser(icon_path)) if icon_path else None
        )
        self.categories = categories
        self.comment = comment
        self.env = get_environment_info()

    def generate_and_install(self, install_to_desktop: bool = True) -> str:
        """
        Creates and installs the .desktop shortcut file.

        Args:
            install_to_desktop: If True, also creates a shortcut on ~/Desktop.

        Returns:
            Absolute path to primary .desktop file in ~/.local/share/applications/.
        """
        # Ensure icon is in place
        installed_icon_name = self._setup_icon()

        # Check if binary is Electron-based requiring --no-sandbox
        app_dir = os.path.dirname(self.exec_path)
        sandbox_path = os.path.join(app_dir, "chrome-sandbox")
        if os.path.isfile(sandbox_path):
            exec_cmd = f'"{self.exec_path}" --no-sandbox %F'
        else:
            exec_cmd = f'"{self.exec_path}" %F'

        # Content structure conforming to FreeDesktop spec
        desktop_content = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            f"Name={self.display_name}\n"
            f"Comment={self.comment}\n"
            f"Exec={exec_cmd}\n"
            f"Icon={installed_icon_name}\n"
            "Terminal=false\n"
            f"Categories={self.categories}\n"
            f"StartupWMClass={self.app_id}\n"
        )

        # Primary location: ~/.local/share/applications/
        apps_dir = self.env["apps_dir"]
        os.makedirs(apps_dir, exist_ok=True)

        primary_desktop_file = os.path.join(apps_dir, f"{self.app_id}.desktop")

        with open(primary_desktop_file, "w", encoding="utf-8") as f:
            f.write(desktop_content)

        # Apply executable permission flag
        os.chmod(primary_desktop_file, 0o755)
        logger.info(f"Created primary desktop shortcut: {primary_desktop_file}")

        # Optional: Desktop shortcut on ~/Desktop
        if install_to_desktop:
            desktop_folder = os.path.expanduser("~/Desktop")
            if os.path.isdir(desktop_folder):
                user_desktop_file = os.path.join(
                    desktop_folder, f"{self.app_id}.desktop"
                )
                try:
                    shutil.copy2(primary_desktop_file, user_desktop_file)
                    os.chmod(user_desktop_file, 0o755)
                    logger.info(f"Copied desktop shortcut to: {user_desktop_file}")
                except Exception as e:
                    logger.warning(
                        f"Failed to copy shortcut to ~/Desktop: {str(e)}"
                    )

        # Refresh desktop menu database
        refresh_desktop_database()

        return primary_desktop_file

    def _setup_icon(self) -> str:
        """
        Copies application icon to ~/.local/share/icons/ or returns icon specifier.
        """
        if not self.icon_path or not os.path.isfile(self.icon_path):
            logger.info("Using standard generic fallback icon 'application-x-executable'")
            return "application-x-executable"

        icons_dir = self.env["icons_dir"]
        os.makedirs(icons_dir, exist_ok=True)

        ext = os.path.splitext(self.icon_path)[1].lower()
        target_icon_name = f"{self.app_id}{ext}"
        target_icon_path = os.path.join(icons_dir, target_icon_name)

        try:
            shutil.copy2(self.icon_path, target_icon_path)
            logger.info(f"Copied application icon to: {target_icon_path}")
            return target_icon_path
        except Exception as e:
            logger.warning(f"Could not copy custom icon: {str(e)}")
            return "application-x-executable"
