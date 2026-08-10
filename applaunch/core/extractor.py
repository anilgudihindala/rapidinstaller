"""
Archive Extraction Engine for AppLaunch Engine.

Handles secure extraction of .tar.gz, .tgz, .tar.xz, .txz, .tar.bz2, and .zip archives
with progress callbacks, security path-traversal validation, and state metric tracking.
"""

import os
import shutil
import subprocess
import tarfile
import zipfile
from typing import Callable, Dict, Optional, Tuple

from applaunch.utils.logger import logger


class ExtractionError(Exception):
    """Custom exception raised when archive extraction encounters an error."""

    pass


class ArchiveExtractor:
    """Smart Extraction Engine capable of handling multiple compressed archive formats."""

    SUPPORTED_EXTENSIONS = (
        ".tar.gz",
        ".tgz",
        ".tar.xz",
        ".txz",
        ".tar.bz2",
        ".tbz2",
        ".tar.zst",
        ".tzst",
        ".zip",
        ".deb",
        ".rpm",
        ".7z",
        ".rar",
        ".appimage",
        ".tar",
    )

    def __init__(self, archive_path: str, target_dir: str) -> None:
        self.archive_path = os.path.abspath(os.path.expanduser(archive_path))
        self.target_dir = os.path.abspath(os.path.expanduser(target_dir))
        self._validate_archive_file()

    def _validate_archive_file(self) -> None:
        """Verifies archive existence and format compatibility."""
        if not os.path.isfile(self.archive_path):
            raise ExtractionError(f"Archive file does not exist: {self.archive_path}")

        if not any(
            self.archive_path.lower().endswith(ext)
            for ext in self.SUPPORTED_EXTENSIONS
        ):
            raise ExtractionError(
                f"Unsupported archive format for file: {self.archive_path}. "
                f"Supported formats: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """Checks if a given file path has a supported archive extension."""
        file_lower = file_path.lower()
        return any(file_lower.endswith(ext) for ext in cls.SUPPORTED_EXTENSIONS)

    def extract(
        self, progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Tuple[int, int]:
        """
        Extracts the archive to target_dir.

        Args:
            progress_callback: Optional callable(percent_int, status_text)

        Returns:
            Tuple of (extracted_files_count, total_bytes_extracted)
        """
        logger.info(f"Starting extraction of {self.archive_path} -> {self.target_dir}")

        if os.path.exists(self.target_dir):
            logger.info(f"Target directory exists, cleaning up: {self.target_dir}")
            shutil.rmtree(self.target_dir, ignore_errors=True)

        os.makedirs(self.target_dir, exist_ok=True)

        file_lower = self.archive_path.lower()
        try:
            if file_lower.endswith(".appimage"):
                return self._extract_appimage(progress_callback)
            elif file_lower.endswith(".deb"):
                return self._extract_deb(progress_callback)
            elif file_lower.endswith(".zip"):
                return self._extract_zip(progress_callback)
            elif file_lower.endswith((".7z", ".rar", ".rpm")):
                return self._extract_external_archive(progress_callback)
            else:
                return self._extract_tar(progress_callback)
        except Exception as e:
            # Clean up target directory if extraction failed mid-way
            shutil.rmtree(self.target_dir, ignore_errors=True)
            logger.error(f"Extraction failed: {str(e)}", exc_info=True)
            raise ExtractionError(f"Failed to extract archive: {str(e)}") from e

    def _extract_appimage(
        self, progress_callback: Optional[Callable[[int, str], None]]
    ) -> Tuple[int, int]:
        """Copies and prepares AppImage binary with execution permissions."""
        if progress_callback:
            progress_callback(10, "Preparing AppImage binary...")

        basename = os.path.basename(self.archive_path)
        dest_appimage = os.path.join(self.target_dir, basename)
        shutil.copy2(self.archive_path, dest_appimage)
        os.chmod(dest_appimage, 0o755)

        # Attempt AppImage extraction if supported to get icons
        try:
            cmd = [dest_appimage, "--appimage-extract"]
            subprocess.run(cmd, cwd=self.target_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except Exception:
            pass

        size_bytes = os.path.getsize(dest_appimage)
        if progress_callback:
            progress_callback(100, "AppImage deployed successfully.")
        return 1, size_bytes

    def _extract_deb(
        self, progress_callback: Optional[Callable[[int, str], None]]
    ) -> Tuple[int, int]:
        """Extracts .deb package contents without requiring root permissions."""
        if progress_callback:
            progress_callback(10, "Extracting Debian package payload...")

        if shutil.which("dpkg-deb"):
            cmd = ["dpkg-deb", "-x", self.archive_path, self.target_dir]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                count = 0
                total_bytes = 0
                for root, _, files in os.walk(self.target_dir):
                    for f in files:
                        count += 1
                        fp = os.path.join(root, f)
                        if not os.path.islink(fp):
                            total_bytes += os.path.getsize(fp)
                if progress_callback:
                    progress_callback(100, "Debian payload extracted successfully.")
                logger.info(f"Successfully extracted DEB payload ({count} files, {total_bytes} bytes).")
                return count, total_bytes
            else:
                raise ExtractionError(f"dpkg-deb failed: {res.stderr}")
        else:
            raise ExtractionError("dpkg-deb tool not available for extracting .deb package.")

    def _extract_external_archive(
        self, progress_callback: Optional[Callable[[int, str], None]]
    ) -> Tuple[int, int]:
        """Extracts 7z, RPM, RAR archives using system utilities or bsdtar."""
        if progress_callback:
            progress_callback(10, "Extracting package archive...")

        extractor_bin = None
        if shutil.which("7z"):
            extractor_bin = ["7z", "x", f"-o{self.target_dir}", "-y", self.archive_path]
        elif shutil.which("bsdtar"):
            extractor_bin = ["bsdtar", "-xf", self.archive_path, "-C", self.target_dir]

        if extractor_bin:
            res = subprocess.run(extractor_bin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                count = 0
                total_bytes = 0
                for root, _, files in os.walk(self.target_dir):
                    for f in files:
                        count += 1
                        fp = os.path.join(root, f)
                        if not os.path.islink(fp):
                            total_bytes += os.path.getsize(fp)
                return count, total_bytes
        raise ExtractionError(f"No suitable extraction tool found for {self.archive_path}")

    def _extract_zip(
        self, progress_callback: Optional[Callable[[int, str], None]]
    ) -> Tuple[int, int]:
        """Extracts ZIP archives securely with member path traversal checks."""
        with zipfile.ZipFile(self.archive_path, "r") as zip_ref:
            members = zip_ref.infolist()
            total_members = len(members)
            extracted_count = 0
            extracted_bytes = 0

            target_dir_abs = os.path.realpath(self.target_dir)

            for idx, member in enumerate(members):
                # Path traversal check (Zip Slip vulnerability prevention)
                member_path = os.path.realpath(
                    os.path.join(self.target_dir, member.filename)
                )
                if not member_path.startswith(target_dir_abs):
                    raise ExtractionError(
                        f"Security Warning: Attempted path traversal in ZIP member '{member.filename}'"
                    )

                zip_ref.extract(member, self.target_dir)
                extracted_count += 1
                extracted_bytes += member.file_size

                if progress_callback and total_members > 0:
                    percent = int((idx + 1) / total_members * 100)
                    progress_callback(
                        percent, f"Extracting {member.filename[:30]}..."
                    )

            logger.info(
                f"Successfully extracted {extracted_count} ZIP entries ({extracted_bytes} bytes)."
            )
            return extracted_count, extracted_bytes

    def _extract_tar(
        self, progress_callback: Optional[Callable[[int, str], None]]
    ) -> Tuple[int, int]:
        """Extracts TAR archives (.tar.gz, .tar.xz, .tar.bz2) securely."""
        with tarfile.open(self.archive_path, "r:*") as tar_ref:
            members = tar_ref.getmembers()
            total_members = len(members)
            extracted_count = 0
            extracted_bytes = 0

            target_dir_abs = os.path.realpath(self.target_dir)

            for idx, member in enumerate(members):
                # Path traversal check (Tar Slip vulnerability prevention)
                member_path = os.path.realpath(
                    os.path.join(self.target_dir, member.name)
                )
                if not member_path.startswith(target_dir_abs):
                    raise ExtractionError(
                        f"Security Warning: Attempted path traversal in TAR member '{member.name}'"
                    )

                # Extract individual member
                tar_ref.extract(member, path=self.target_dir, numeric_owner=False)
                extracted_count += 1
                extracted_bytes += member.size

                if progress_callback and total_members > 0:
                    percent = int((idx + 1) / total_members * 100)
                    progress_callback(
                        percent, f"Extracting {member.name[:30]}..."
                    )

            logger.info(
                f"Successfully extracted {extracted_count} TAR entries ({extracted_bytes} bytes)."
            )
            return extracted_count, extracted_bytes
