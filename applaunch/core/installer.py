"""
Main Orchestrator Engine for AppLaunch Engine.

Integrates archive extraction, binary entry point scanning, desktop entry generation,
Zenity UI UX workflows, and metrics reporting into a seamless one-click installation process.
"""

import os
import sys
from typing import Any, Dict, Optional

from applaunch.core.desktop import DesktopShortcutGenerator
from applaunch.core.extractor import ArchiveExtractor, ExtractionError
from applaunch.core.scanner import DirectoryScanner, resolve_preferred_launcher_candidate
from applaunch.ui.zenity import ZenityProgressContext, ZenityUI
from applaunch.utils.formatter import clean_app_name
from applaunch.utils.logger import MetricsTracker, logger
from applaunch.utils.sys_info import ensure_user_directories, get_environment_info


class AppInstallerEngine:
    """Enterprise-grade installer engine orchestrating archive deployment workflows."""

    def __init__(self, archive_path: str, custom_dest_dir: Optional[str] = None, force_cli: bool = False) -> None:
        self.archive_path = os.path.abspath(os.path.expanduser(archive_path))
        self.name_info = clean_app_name(self.archive_path)
        self.env = get_environment_info()

        # Destination opt folder
        if custom_dest_dir:
            self.dest_dir = os.path.abspath(os.path.expanduser(custom_dest_dir))
        else:
            self.dest_dir = os.path.join(self.env["opt_dir"], self.name_info["app_id"])

        self.ui = ZenityUI(force_cli=force_cli)
        self.metrics = MetricsTracker()

    def run_installation(self, auto_confirm: bool = False) -> Dict[str, Any]:
        """
        Executes complete application installation pipeline.

        Args:
            auto_confirm: If True, skips confirmation dialog.

        Returns:
            Metrics dict containing installation details and status.
        """
        self.metrics.set_metric("archive_path", self.archive_path)
        archive_size = os.path.getsize(self.archive_path) if os.path.isfile(self.archive_path) else 0
        self.metrics.set_metric("archive_size_bytes", archive_size)

        ensure_user_directories()

        # 1. Confirmation & Already-Installed Loop
        title_display = self.name_info["display_name"]
        is_already_installed = os.path.exists(self.dest_dir)

        if is_already_installed:
            confirm_msg = (
                f"AppLaunch Smart Installer\n\n"
                f"⚠️ '{title_display}' is ALREADY INSTALLED on your system!\n\n"
                f"Location: {self.dest_dir}\n"
                f"Package File: {os.path.basename(self.archive_path)}\n\n"
                f"Would you like to REINSTALL / UPGRADE '{title_display}' now?"
            )
            dialog_title = f"Already Installed: {title_display}"
        else:
            confirm_msg = (
                f"AppLaunch Smart Installer\n\n"
                f"Application Name: {title_display}\n"
                f"Package File: {os.path.basename(self.archive_path)}\n"
                f"Target Directory: {self.dest_dir}\n\n"
                f"Would you like to install this application now?"
            )
            dialog_title = f"Install {title_display}"

        if not auto_confirm and not self.ui.ask_confirmation(dialog_title, confirm_msg):
            logger.info("Installation cancelled by user.")
            self.metrics.finish(status="CANCELLED")
            return self.metrics.to_dict()

        # 2. Progress Tracker Loop
        try:
            with ZenityProgressContext(
                title=f"Installing {title_display}",
                text="Initializing installation engine...",
                zenity_ui=self.ui,
            ) as progress:

                # --- STEP A: EXTRACTION (0% - 60%) ---
                is_upgrade = os.path.exists(self.dest_dir)
                status_msg = f"Upgrading existing {title_display}..." if is_upgrade else "Preparing extraction target..."
                progress.update(5, status_msg)
                extractor = ArchiveExtractor(self.archive_path, self.dest_dir)

                def extract_cb(p_int: int, p_text: str) -> None:
                    overall = 5 + int(p_int * 0.55)  # Scale 0..100 -> 5..60
                    progress.update(overall, f"Extracting: {p_text}")

                files_count, total_bytes = extractor.extract(progress_callback=extract_cb)
                self.metrics.set_metric("extracted_files_count", files_count)
                self.metrics.set_metric("extracted_total_bytes", total_bytes)
                self.metrics.set_metric("is_upgrade", is_upgrade)

                # --- STEP B: BINARY SCANNING (60% - 80%) ---
                progress.update(65, "Scanning extracted files for entry points...")
                scanner = DirectoryScanner(
                    root_dir=self.dest_dir,
                    app_search_slug=self.name_info["search_slug"],
                )
                candidates = scanner.find_entry_points()
                self.metrics.set_metric("scan_candidates_found", len(candidates))

                if not candidates:
                    raise ExtractionError(
                        f"No executable entry points or launchers found inside extracted directory '{self.dest_dir}'."
                    )

                # Prefer extracted AppRun for AppImages (avoids libfuse2 dependency on Ubuntu 24.04+)
                selected_cand = resolve_preferred_launcher_candidate(self.dest_dir, candidates)
                logger.info(
                    f"Smart launcher automatically selected primary launcher: {selected_cand.rel_path} (Score: {selected_cand.score})"
                )

                self.metrics.set_metric("selected_executable", selected_cand.full_path)

                # --- STEP C: ICON SCANNING & DESKTOP HOOK (80% - 95%) ---
                progress.update(85, "Scanning for application icon resources...")
                discovered_icon = scanner.find_icon()
                self.metrics.set_metric("selected_icon", discovered_icon or "System Generic")

                progress.update(90, "Generating FreeDesktop application shortcut...")
                shortcut_gen = DesktopShortcutGenerator(
                    app_id=self.name_info["app_id"],
                    display_name=self.name_info["display_name"],
                    exec_path=selected_cand.full_path,
                    icon_path=discovered_icon,
                    categories="Utility;Application;",
                    comment=f"Installed via AppLaunch Engine from {os.path.basename(self.archive_path)}",
                )
                primary_desktop_path = shortcut_gen.generate_and_install(install_to_desktop=True)
                self.metrics.set_metric("desktop_entry_path", primary_desktop_path)

                # --- STEP D: FINALIZE & CACHE FLUSH (95% - 100%) ---
                progress.update(98, "Flushing system desktop menu database...")
                progress.update(100, "Installation completed successfully!")

            self.metrics.finish(status="SUCCESS")
            summary_info = (
                f"Installation Successful!\n\n"
                f"Application: {self.name_info['display_name']}\n"
                f"Location: {self.dest_dir}\n"
                f"Launcher Binary: {os.path.basename(selected_cand.full_path)}\n"
                f"Desktop Shortcut: {primary_desktop_path}\n"
                f"Duration: {self.metrics.to_dict()['duration_seconds']}s"
            )
            self.ui.show_info("AppLaunch Engine - Success", summary_info)
            logger.info("Installation completed successfully.")
            return self.metrics.to_dict()

        except Exception as err:
            err_msg = str(err)
            logger.error(f"Installation failed: {err_msg}", exc_info=True)
            self.metrics.finish(status="FAILED", error_msg=err_msg)
            self.ui.show_error(
                "AppLaunch Engine - Error",
                f"Installation encountered an error:\n\n{err_msg}\n\nCheck logs at ~/.local/share/applaunch/logs/applaunch.log",
            )
            return self.metrics.to_dict()
