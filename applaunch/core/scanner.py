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
        icon_candidates: List[Tuple[str, int]] = []
        valid_extensions = (".png", ".svg", ".xpm", ".ico")

        for dirpath, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                fn_lower = filename.lower()
                if any(fn_lower.endswith(ext) for ext in valid_extensions):
                    file_path = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(file_path, self.root_dir).lower()

                    score = 10
                    # Check matching keywords
                    if "icon" in fn_lower or "logo" in fn_lower or "app" in fn_lower or "code" in fn_lower:
                        score += 30
                    if self.app_search_slug and self.app_search_slug in fn_lower:
                        score += 40
                    if "pixmaps" in rel_path or "icons" in rel_path or "resources/linux" in rel_path or "media" in rel_path:
                        score += 35
                    if "extensions/" in rel_path or "node_modules/" in rel_path:
                        score -= 50
                    if fn_lower.endswith(".png") or fn_lower.endswith(".svg"):
                        score += 35
                    elif fn_lower.endswith(".ico") or fn_lower.endswith(".xpm"):
                        score -= 15

                    icon_candidates.append((file_path, score))

        if not icon_candidates:
            logger.info("No explicit icon file discovered during scan.")
            return None

        icon_candidates.sort(key=lambda x: x[1], reverse=True)
        best_icon = icon_candidates[0][0]
        logger.info(f"Selected icon file: {best_icon} (score={icon_candidates[0][1]})")
        return best_icon
