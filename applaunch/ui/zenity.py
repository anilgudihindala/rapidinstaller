"""
Enterprise UI/UX Wrapper & Zenity UI Integration Module.

Provides system native GUI dialogs, status progress bars, selection menus,
and informational dialog loops with CLI fallback mechanisms.
"""

import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

from applaunch.utils.logger import logger


class ZenityUI:
    """Wrapper class around Zenity CLI tool with graceful console fallbacks."""

    def __init__(self, force_cli: bool = False) -> None:
        self.force_cli = force_cli
        self._has_zenity = not force_cli and self._check_zenity()

    def _check_zenity(self) -> bool:
        """Verifies if zenity command is available in PATH and DISPLAY is set."""
        if not shutil.which("zenity"):
            return False
        # Check if X display / Wayland display is available
        if not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
            logger.info("No GUI DISPLAY detected, falling back to CLI mode.")
            return False
        return True

    def is_gui_available(self) -> bool:
        """Returns True if Zenity GUI mode is active."""
        return self._has_zenity

    def show_info(self, title: str, text: str) -> None:
        """Displays an informational confirmation dialog."""
        logger.info(f"UI INFO: [{title}] {text}")
        if self._has_zenity:
            cmd = [
                "zenity",
                "--info",
                "--title",
                title,
                "--text",
                text,
                "--width=450",
            ]
            subprocess.run(cmd, stderr=subprocess.DEVNULL)
        else:
            print(f"\n========================================")
            print(f" INFO: {title}")
            print(f"========================================")
            print(text)
            print(f"========================================\n")

    def show_error(self, title: str, text: str) -> None:
        """Displays an error dialogue loop with diagnostic typography."""
        logger.error(f"UI ERROR: [{title}] {text}")
        if self._has_zenity:
            cmd = [
                "zenity",
                "--error",
                "--title",
                title,
                "--text",
                text,
                "--width=450",
            ]
            subprocess.run(cmd, stderr=subprocess.DEVNULL)
        else:
            print(f"\n========================================")
            print(f" ERROR: {title}")
            print(f"========================================")
            print(text)
            print(f"========================================\n")

    def ask_confirmation(self, title: str, text: str) -> bool:
        """
        Presents a confirmation dialogue loop.

        Returns:
            True if user confirmed, False otherwise.
        """
        logger.info(f"UI PROMPT: [{title}] {text}")
        if self._has_zenity:
            cmd = [
                "zenity",
                "--question",
                "--title",
                title,
                "--text",
                text,
                "--width=450",
            ]
            res = subprocess.run(cmd, stderr=subprocess.DEVNULL)
            return res.returncode == 0
        else:
            if not sys.stdin.isatty():
                logger.info("Non-interactive environment detected; auto-confirming installation.")
                return True
            print(f"\n{title}")
            print(text)
            try:
                resp = input("Proceed? [Y/n]: ").strip().lower()
                return resp in ("", "y", "yes")
            except (EOFError, KeyboardInterrupt):
                return True

    def select_executable(
        self, candidates: List[Tuple[str, int, str]], default_path: str
    ) -> str:
        """
        Presents a selection dialog when multiple executable launcher candidates exist.

        Args:
            candidates: List of tuples (rel_path, score, description)
            default_path: Fallback path if selection is cancelled.

        Returns:
            Selected relative path string.
        """
        if not candidates:
            return default_path

        if self._has_zenity and len(candidates) > 1:
            cmd = [
                "zenity",
                "--list",
                "--radiolist",
                "--title=Select Executable Launcher",
                "--text=Multiple entry points were discovered. Select primary application launcher:",
                "--column=Select",
                "--column=Path",
                "--column=Score",
                "--column=Reason",
                "--width=650",
                "--height=300",
            ]
            for idx, (rel_path, score, desc) in enumerate(candidates):
                is_selected = "TRUE" if idx == 0 else "FALSE"
                cmd.extend([is_selected, rel_path, str(score), desc])

            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            if res.returncode == 0 and res.stdout.strip():
                selected = res.stdout.strip()
                logger.info(f"User selected executable via Zenity: {selected}")
                return selected

        # CLI fallback selection
        if len(candidates) > 1:
            print("\nMultiple binary entry points discovered:")
            for idx, (rel_path, score, desc) in enumerate(candidates):
                prefix = "*" if idx == 0 else " "
                print(f" {prefix} [{idx+1}] {rel_path} (Score: {score}) - {desc}")
            try:
                ans = input(f"Select binary launcher [1-{len(candidates)}] (default 1): ").strip()
                if ans.isdigit() and 1 <= int(ans) <= len(candidates):
                    return candidates[int(ans) - 1][0]
            except Exception:
                pass

        return candidates[0][0]


class ZenityProgressContext:
    """
    Context manager for streaming progress percentages to system native 'zenity --progress'.
    """

    def __init__(self, title: str, text: str, zenity_ui: ZenityUI) -> None:
        self.title = title
        self.text = text
        self.zenity_ui = zenity_ui
        self.process: Optional[subprocess.Popen] = None

    def __enter__(self) -> "ZenityProgressContext":
        if self.zenity_ui.is_gui_available():
            cmd = [
                "zenity",
                "--progress",
                "--title",
                self.title,
                "--text",
                self.text,
                "--percentage=0",
                "--auto-close",
                "--width=450",
            ]
            self.process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
            )
        else:
            print(f"==> {self.title}: {self.text}")
        return self

    def update(self, percent: int, text: Optional[str] = None) -> None:
        """Updates the progress percentage (0-100) and optional label text."""
        percent = max(0, min(100, percent))
        if self.process and self.process.stdin:
            try:
                if text:
                    self.process.stdin.write(f"# {text}\n")
                self.process.stdin.write(f"{percent}\n")
                self.process.stdin.flush()
            except Exception:
                pass
        else:
            if text:
                print(f"[{percent:3d}%] {text}")

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=1)
            except Exception:
                pass
