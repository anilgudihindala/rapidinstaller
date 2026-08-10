"""
Deep Path Binary Scanner & Entry-Point Evaluator for AppLaunch Engine.

Uses os.walk and os.access(..., os.X_OK) to identify true standalone binary launcher
executables and application icon files without relying on rigid directory naming structures.
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from applaunch.utils.logger import logger


# Common helper binaries and shared libraries to exclude/penalize during candidate scoring
EXCLUDED_PATTERNS = [
    r"\.so(\.\d+)*$",
    r"\.a$",
    r"\.o$",
    r"\.pyc$",
    r"\.h$",
    r"\.c$",
    r"\.cpp$",
    r"^lib.*\.so",
    r"chrome-sandbox$",
    r"crashpad_handler$",
    r"nacl_helper$",
    r"ld-linux.*$",
    r"^uninstall(\.sh)?$",
    r"^install(\.sh)?$",  # Usually installer scripts inside archive, not app main binary
    r"^configure$",
    r"check_.*",
    r".*_helper$",
    r"node_modules/",
]

PREFERRED_LAUNCHER_NAMES = [
    "run",
    "launch",
    "start",
    "main",
    "app",
]

ICON_PATH_BONUS_PATTERNS = [
    (r"/hicolor/\d+x\d+/apps/", 90),
    (r"/hicolor/scalable/apps/", 85),
    (r"resources/app/resources/linux/", 80),
    (r"resources/linux/", 75),
    (r"/share/icons/", 60),
    (r"/icons/", 45),
]

ICON_PATH_PENALTY_PATTERNS = [
    (r"welcome", 80),
    (r"gettingstarted", 80),
    (r"onboarding", 80),
    (r"/dialog/", 60),
    (r"/media/", 40),
    (r"extensions/", 70),
    (r"node_modules/", 90),
]


class ExecutableCandidate:
    """Represents a discovered executable candidate with calculated heuristic score."""

    def __init__(self, full_path: str, score: int, description: str) -> None:
        self.full_path = full_path
        self.score = score
        self.description = description
        self.filename = os.path.basename(full_path)
        self.rel_path = full_path

    def __repr__(self) -> str:
        return f"<ExecutableCandidate {self.filename} (score={self.score})>"


def resolve_appimage_launch_path(executable_path: str) -> str:
    """
    Returns squashfs-root/AppRun when an AppImage was extracted, avoiding libfuse2.

    AppImages require FUSE 2 (libfuse.so.2) which is not installed by default on
    Ubuntu 24.04+. Running the extracted AppRun launcher works without FUSE.
    """
    normalized_path = os.path.abspath(os.path.expanduser(executable_path))
    if not normalized_path.lower().endswith(".appimage"):
        return normalized_path

    installation_directory = os.path.dirname(normalized_path)
    app_run_path = os.path.join(installation_directory, "squashfs-root", "AppRun")
    if os.path.isfile(app_run_path) and os.access(app_run_path, os.X_OK):
        logger.info(f"Resolved AppImage launcher to extracted AppRun: {app_run_path}")
        return app_run_path

    return normalized_path


def resolve_preferred_launcher_candidate(
    installation_directory: str,
    candidates: List[ExecutableCandidate],
) -> ExecutableCandidate:
    """Selects the best launcher, preferring extracted AppRun over raw AppImage files."""
    if not candidates:
        raise ValueError("At least one launcher candidate is required.")

    app_run_path = os.path.join(installation_directory, "squashfs-root", "AppRun")
    if os.path.isfile(app_run_path) and os.access(app_run_path, os.X_OK):
        for candidate in candidates:
            if os.path.abspath(candidate.full_path) == os.path.abspath(app_run_path):
                return candidate
        return ExecutableCandidate(
            app_run_path,
            999,
            "AppImage extracted AppRun launcher (FUSE-free)",
        )

    return candidates[0]


class DirectoryScanner:
    """Scans extracted application directory trees for binaries and icon resources."""

    def __init__(self, root_dir: str, app_search_slug: str = "") -> None:
        self.root_dir = os.path.abspath(os.path.expanduser(root_dir))
        self.app_search_slug = app_search_slug.lower()

    def find_entry_points(self) -> List[ExecutableCandidate]:
        """
        Walks root_dir recursively using os.walk and os.access to evaluate
        all potential executable candidates.

        Returns:
            Sorted list of ExecutableCandidate objects (highest score first).
        """
        candidates: List[ExecutableCandidate] = []

        if not os.path.isdir(self.root_dir):
            logger.warning(f"Scan directory does not exist: {self.root_dir}")
            return candidates

        for dirpath, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(file_path, self.root_dir)

                # Skip non-regular files or missing broken symlinks
                if not os.path.isfile(file_path):
                    continue

                # Check executable permission or script extensions
                is_executable = os.access(file_path, os.X_OK)
                is_script = filename.endswith(".sh") or filename.endswith(".bin")

                if not (is_executable or is_script):
                    continue

                # Evaluate heuristic score
                score, reason = self._score_executable(
                    file_path, rel_path, filename, is_executable
                )

                if score > 0:
                    cand = ExecutableCandidate(file_path, score, reason)
                    cand.rel_path = rel_path
                    candidates.append(cand)

        # Sort candidates descending by score
        candidates.sort(key=lambda c: c.score, reverse=True)
        logger.info(f"Discovered {len(candidates)} executable candidates in {self.root_dir}")
        for c in candidates[:5]:
            logger.debug(f"Candidate: {c.rel_path} | Score: {c.score} | Reason: {c.description}")

        return candidates

    def _score_executable(
        self, full_path: str, rel_path: str, filename: str, is_executable: bool
    ) -> Tuple[int, str]:
        """Calculates candidate score based on path depth, filename match, and binary type."""
        fn_lower = filename.lower()
        rel_path_lower = rel_path.lower()

        # 1. Check disqualification patterns
        for pattern in EXCLUDED_PATTERNS:
            if re.search(pattern, fn_lower) or re.search(pattern, rel_path_lower):
                return 0, f"Disqualified by pattern: {pattern}"

        score = 0
        reasons = []

        # 2. Base executable check
        if is_executable:
            score += 40
            reasons.append("+40 executable bit set")
        elif filename.endswith(".sh"):
            score += 30
            reasons.append("+30 .sh script")

        # 3. Check for ELF magic bytes if file has no extension
        if not "." in filename and is_executable:
            try:
                with open(full_path, "rb") as f:
                    header = f.read(4)
                    if header == b"\x7fELF":
                        score += 30
                        reasons.append("+30 ELF binary file")
            except Exception:
                pass

        # 4. App slug matching (crucial score booster)
        clean_fn = re.sub(r"[^a-z0-9]", "", fn_lower)
        if self.app_search_slug:
            if clean_fn == self.app_search_slug:
                score += 50
                reasons.append(f"+50 exact match to app slug '{self.app_search_slug}'")
            elif self.app_search_slug in clean_fn:
                score += 30
                reasons.append(f"+30 partial match to app slug '{self.app_search_slug}'")
            elif clean_fn in self.app_search_slug and len(clean_fn) > 3:
                score += 25
                reasons.append(f"+25 substring match to app slug '{self.app_search_slug}'")

        # 5. Preferred launcher keyword match
        for pref in PREFERRED_LAUNCHER_NAMES:
            if pref in fn_lower:
                score += 20
                reasons.append(f"+20 contains launcher keyword '{pref}'")

        # 6. Depth penalty (favor binaries located directly in root or bin/ subfolder)
        depth = len(rel_path.split(os.sep)) - 1
        if depth == 0:
            score += 25
            reasons.append("+25 root level directory location")
        elif depth == 1 and rel_path_lower.startswith(("bin/", "app/")):
            score += 20
            reasons.append("+20 in primary bin/ or app/ folder")
        elif depth > 3:
            score -= (depth - 3) * 10
            reasons.append(f"-{(depth - 3) * 10} deep nested location (depth {depth})")

        description = ", ".join(reasons)
        return max(score, 0), description

    def find_icon(self) -> Optional[str]:
        """
        Scans extracted directory tree for application icon (.png, .svg, .xpm, .ico).

        Returns:
            Absolute path to best matching icon file, or None if not found.
        """
        priority_icon = self._find_priority_application_icon()
        if priority_icon:
            logger.info(f"Selected priority application icon: {priority_icon}")
            return priority_icon

        icon_candidates: List[Tuple[str, int]] = []
        valid_extensions = (".png", ".svg", ".xpm", ".ico")

        for dirpath, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                fn_lower = filename.lower()
                if not any(fn_lower.endswith(extension) for extension in valid_extensions):
                    continue

                file_path = os.path.join(dirpath, filename)
                score = self._score_icon_candidate(file_path, filename)
                if score > 0:
                    icon_candidates.append((file_path, score))

        if not icon_candidates:
            logger.info("No explicit icon file discovered during scan.")
            return None

        icon_candidates.sort(key=lambda candidate: candidate[1], reverse=True)
        best_icon = icon_candidates[0][0]
        logger.info(f"Selected icon file: {best_icon} (score={icon_candidates[0][1]})")
        return best_icon

    def _resolve_symlink_icon(self, icon_path: str) -> Optional[str]:
        """Resolves symlinked icon paths such as AppImage .DirIcon entries."""
        if not os.path.lexists(icon_path):
            return None

        resolved_icon_path = os.path.realpath(icon_path)
        if os.path.isfile(resolved_icon_path):
            return resolved_icon_path
        return None

    def _find_priority_application_icon(self) -> Optional[str]:
        """Checks well-known icon locations before heuristic directory scanning."""
        for relative_dir_icon in (".DirIcon", os.path.join("squashfs-root", ".DirIcon")):
            resolved_dir_icon = self._resolve_symlink_icon(
                os.path.join(self.root_dir, relative_dir_icon)
            )
            if resolved_dir_icon:
                return resolved_dir_icon

        hicolor_icon = self._find_hicolor_application_icon()
        if hicolor_icon:
            return hicolor_icon

        electron_linux_icon = self._find_electron_linux_icon()
        if electron_linux_icon:
            return electron_linux_icon

        return None

    def _find_hicolor_application_icon(self) -> Optional[str]:
        """Finds the largest icon from Freedesktop hicolor theme folders."""
        best_icon_path: Optional[str] = None
        best_icon_size = 0

        for dirpath, _, filenames in os.walk(self.root_dir):
            normalized_directory = dirpath.replace("\\", "/").lower()
            if "/hicolor/" not in normalized_directory or "/apps/" not in normalized_directory:
                continue

            size_match = re.search(r"/(\d+)x(\d+)/", normalized_directory)
            icon_dimension = int(size_match.group(1)) if size_match else 128

            for filename in filenames:
                filename_lower = filename.lower()
                if not filename_lower.endswith((".png", ".svg", ".xpm", ".ico")):
                    continue

                if icon_dimension >= best_icon_size:
                    best_icon_size = icon_dimension
                    best_icon_path = os.path.join(dirpath, filename)

        return best_icon_path

    def _find_electron_linux_icon(self) -> Optional[str]:
        """Finds standard Electron/VS Code style icons under resources/linux."""
        preferred_filenames = ("code.png", "app.png", "icon.png")
        fallback_icon_path: Optional[str] = None

        for dirpath, _, filenames in os.walk(self.root_dir):
            normalized_directory = dirpath.replace("\\", "/").lower()
            if not normalized_directory.endswith("resources/linux"):
                continue

            available_png_files = [
                filename for filename in filenames if filename.lower().endswith(".png")
            ]
            if not available_png_files:
                continue

            for preferred_filename in preferred_filenames:
                for available_filename in available_png_files:
                    if available_filename.lower() == preferred_filename:
                        return os.path.join(dirpath, available_filename)

            if not fallback_icon_path:
                fallback_icon_path = os.path.join(dirpath, available_png_files[0])

        return fallback_icon_path

    def _score_icon_candidate(self, file_path: str, filename: str) -> int:
        """Scores icon candidates, favoring standard Linux app icon locations."""
        filename_lower = filename.lower()
        relative_path = os.path.relpath(file_path, self.root_dir).lower()
        normalized_relative_path = relative_path.replace("\\", "/")

        for penalty_pattern, penalty_points in ICON_PATH_PENALTY_PATTERNS:
            if re.search(penalty_pattern, normalized_relative_path):
                return 0

        score = 10
        if filename_lower.endswith(".png"):
            score += 35
        elif filename_lower.endswith(".svg"):
            score += 15
        elif filename_lower.endswith((".xpm", ".ico")):
            score += 10

        if any(keyword in filename_lower for keyword in ("icon", "logo", "app")):
            score += 25

        if self.app_search_slug:
            normalized_filename = re.sub(r"[^a-z0-9]", "", filename_lower)
            if normalized_filename == self.app_search_slug:
                score += 50
            elif self.app_search_slug in normalized_filename:
                score += 30

        for bonus_pattern, bonus_points in ICON_PATH_BONUS_PATTERNS:
            if re.search(bonus_pattern, normalized_relative_path):
                score += bonus_points

        if filename_lower in ("code.png", "app.png", "icon.png"):
            score += 40

        return score
