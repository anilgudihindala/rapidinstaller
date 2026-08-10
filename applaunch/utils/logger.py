"""
Structured Logger and Performance Metrics Tracker for AppLaunch Engine.

Provides centralized logging functionality with file and console handlers,
metrics recording, and formatted exception tracing.
"""

import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional


class MetricsTracker:
    """Tracks state metrics, execution duration, and resource statistics during installation."""

    def __init__(self) -> None:
        self.start_time: float = time.time()
        self.metrics: Dict[str, Any] = {
            "archive_path": "",
            "archive_size_bytes": 0,
            "extracted_files_count": 0,
            "extracted_total_bytes": 0,
            "scan_candidates_found": 0,
            "selected_executable": "",
            "selected_icon": "",
            "desktop_entry_path": "",
            "duration_seconds": 0.0,
            "status": "INITIALIZED",
            "error": None,
        }

    def set_metric(self, key: str, value: Any) -> None:
        """Sets a metric key-value pair."""
        self.metrics[key] = value

    def finish(self, status: str = "SUCCESS", error_msg: Optional[str] = None) -> None:
        """Finalizes execution metrics with duration calculation."""
        self.metrics["duration_seconds"] = round(time.time() - self.start_time, 3)
        self.metrics["status"] = status
        if error_msg:
            self.metrics["error"] = error_msg

    def to_dict(self) -> Dict[str, Any]:
        """Returns recorded metrics as a dictionary."""
        return self.metrics

    def to_summary_string(self) -> str:
        """Returns a human-readable summary string of metrics."""
        size_mb = self.metrics.get("archive_size_bytes", 0) / (1024 * 1024)
        return (
            f"Status: {self.metrics.get('status')}\n"
            f"Archive Size: {size_mb:.2f} MB\n"
            f"Extracted Files: {self.metrics.get('extracted_files_count')}\n"
            f"Candidates Found: {self.metrics.get('scan_candidates_found')}\n"
            f"Executable: {self.metrics.get('selected_executable')}\n"
            f"Shortcut Path: {self.metrics.get('desktop_entry_path')}\n"
            f"Execution Time: {self.metrics.get('duration_seconds')} seconds"
        )


def setup_logger(name: str = "applaunch", log_to_console: bool = True) -> logging.Logger:
    """
    Configures and returns a structured Python logger.
    Logs are persisted to ~/.local/share/applaunch/logs/applaunch.log.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if setup_logger is called multiple times
    if logger.handlers:
        return logger

    # Log directory setup
    log_dir = os.path.expanduser("~/.local/share/applaunch/logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "applaunch.log")

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("[AppLaunch] %(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


# Default logger instance
logger = setup_logger()
