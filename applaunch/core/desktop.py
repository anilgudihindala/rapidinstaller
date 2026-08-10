"""
Universal Environment Injection & Desktop Shortcut Hook Generator.

Dynamically formats and installs standardized FreeDesktop '.desktop' application shortcuts,
handling icon deployment, execution flags, and universal $HOME user path mapping.
"""

import os
import shutil
import subprocess
from typing import Dict, Optional

from applaunch.utils.logger import logger
from applaunch.utils.sys_info import get_environment_info, refresh_desktop_database


def derive_startup_wm_class(display_name: str, app_id: str) -> str:
    """Derives a window class name that matches how desktop environments group app windows."""
    if display_name:
        first_display_token = display_name.strip().split()[0]
        if first_display_token:
            return first_display_token
    return app_id.replace("-", " ").title().split()[0]


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
        startup_wm_class: Optional[str] = None,
    ) -> None:
        self.app_id = app_id
        self.display_name = display_name
        self.exec_path = os.path.abspath(os.path.expanduser(exec_path))
        self.icon_path = (
            os.path.abspath(os.path.expanduser(icon_path)) if icon_path else None
        )
        self.categories = categories
        self.comment = comment
        self.startup_wm_class = startup_wm_class or derive_startup_wm_class(display_name, app_id)
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
            f"StartupWMClass={self.startup_wm_class}\n"
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

        # Create CLI symlink in ~/.local/bin/<app_id>
        bin_dir = self.env["bin_dir"]
        os.makedirs(bin_dir, exist_ok=True)
        symlink_path = os.path.join(bin_dir, self.app_id)
        try:
            if os.path.islink(symlink_path) or os.path.isfile(symlink_path):
                os.remove(symlink_path)
            os.symlink(self.exec_path, symlink_path)
            logger.info(f"Created CLI executable symlink: {symlink_path} -> {self.exec_path}")
        except Exception as e:
            logger.warning(f"Could not create CLI symlink for {self.app_id}: {e}")

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
        Copies application icon into the hicolor theme and returns the theme icon name.
        """
        if not self.icon_path or not os.path.isfile(self.icon_path):
            logger.info("Using standard generic fallback icon 'application-x-executable'")
            return "application-x-executable"

        icon_extension = os.path.splitext(self.icon_path)[1].lower()
        icons_root_directory = os.path.join(self.env["home"], ".local", "share", "icons")
        os.makedirs(icons_root_directory, exist_ok=True)

        try:
            if icon_extension == ".svg":
                scalable_icon_directory = os.path.join(
                    icons_root_directory, "hicolor", "scalable", "apps"
                )
                os.makedirs(scalable_icon_directory, exist_ok=True)
                scalable_icon_path = os.path.join(scalable_icon_directory, f"{self.app_id}.svg")
                shutil.copy2(self.icon_path, scalable_icon_path)
            else:
                for icon_size in ("512x512", "256x256", "128x128", "64x64"):
                    sized_icon_directory = os.path.join(
                        icons_root_directory, "hicolor", icon_size, "apps"
                    )
                    os.makedirs(sized_icon_directory, exist_ok=True)
                    sized_icon_path = os.path.join(
                        sized_icon_directory, f"{self.app_id}{icon_extension}"
                    )
                    shutil.copy2(self.icon_path, sized_icon_path)

            flat_icon_path = os.path.join(icons_root_directory, f"{self.app_id}{icon_extension}")
            shutil.copy2(self.icon_path, flat_icon_path)
            self._refresh_icon_theme_cache(icons_root_directory)
            logger.info(
                f"Installed application icon into hicolor theme as '{self.app_id}' from {self.icon_path}"
            )
            return self.app_id
        except Exception as error:
            logger.warning(f"Could not install themed application icon: {str(error)}")
            return "application-x-executable"

    def _refresh_icon_theme_cache(self, icons_root_directory: str) -> None:
        """Updates GTK icon cache when gtk-update-icon-cache is available."""
        cache_command = shutil.which("gtk-update-icon-cache")
        if not cache_command:
            return

        try:
            subprocess.run(
                [cache_command, "-f", "-t", icons_root_directory],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception as error:
            logger.warning(f"Could not refresh icon theme cache: {error}")
