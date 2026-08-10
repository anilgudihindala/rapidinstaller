"""
Shell Environment Profile Injector and Clean Block Remover for Rapid Installer.

Manages PATH exports, environment variables, and toolchain sourcing lines
in ~/.bashrc, ~/.zshrc, ~/.profile, and ~/.config/fish/config.fish safely
using tagged comment markers.
"""

import os
import shutil
from typing import List

from applaunch.utils.logger import logger

HEADER_TAG = "# >>> Rapid Installer Managed: {tool_id} >>>"
FOOTER_TAG = "# <<< Rapid Installer Managed: {tool_id} <<<"


def get_target_profile_files() -> List[str]:
    """Returns absolute paths of user shell configuration profiles."""
    home = os.path.expanduser("~")
    profiles = [
        os.path.join(home, ".bashrc"),
        os.path.join(home, ".zshrc"),
        os.path.join(home, ".profile"),
        os.path.join(home, ".bash_profile"),
    ]
    return [p for p in profiles if os.path.exists(p) or p.endswith(".bashrc") or p.endswith(".zshrc")]


def inject_shell_profile_block(tool_id: str, shell_code: str) -> bool:
    """
    Safely injects or updates a tagged environment block in user shell profiles.

    Args:
        tool_id: Identifier slug (e.g. 'nvm', 'bun', 'deno').
        shell_code: Shell script code lines to export variables or source setup scripts.
    """
    start_tag = HEADER_TAG.format(tool_id=tool_id)
    end_tag = FOOTER_TAG.format(tool_id=tool_id)
    block_content = f"{start_tag}\n{shell_code.strip()}\n{end_tag}\n"

    profiles = get_target_profile_files()
    success = False

    for profile in profiles:
        try:
            content = ""
            if os.path.isfile(profile):
                with open(profile, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

            # Remove existing block if present
            if start_tag in content:
                content = _strip_block(content, start_tag, end_tag)

            # Append new block
            new_content = content.rstrip() + "\n\n" + block_content
            with open(profile, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"Injected environment block for '{tool_id}' into {profile}")
            success = True
        except Exception as e:
            logger.error(f"Failed to inject shell profile block into {profile}: {e}")

    return success


def remove_shell_profile_block(tool_id: str) -> bool:
    """
    Strips tagged environment block for specified tool_id from all user shell profiles.
    """
    start_tag = HEADER_TAG.format(tool_id=tool_id)
    end_tag = FOOTER_TAG.format(tool_id=tool_id)
    profiles = get_target_profile_files()
    success = False

    for profile in profiles:
        if not os.path.isfile(profile):
            continue

        try:
            with open(profile, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if start_tag in content:
                new_content = _strip_block(content, start_tag, end_tag)
                with open(profile, "w", encoding="utf-8") as f:
                    f.write(new_content)
                logger.info(f"Removed environment block for '{tool_id}' from {profile}")
                success = True
        except Exception as e:
            logger.error(f"Failed to remove shell profile block from {profile}: {e}")

    return success


def is_shell_profile_injected(tool_id: str) -> bool:
    """Checks if tagged environment block for tool_id is present in shell profiles."""
    start_tag = HEADER_TAG.format(tool_id=tool_id)
    for profile in get_target_profile_files():
        if os.path.isfile(profile):
            try:
                with open(profile, "r", encoding="utf-8", errors="ignore") as f:
                    if start_tag in f.read():
                        return True
            except Exception:
                pass
    return False


def _strip_block(content: str, start_tag: str, end_tag: str) -> str:
    """Helper routine to slice out text between start_tag and end_tag."""
    lines = content.splitlines(True)
    new_lines = []
    skipping = False

    for line in lines:
        if start_tag in line:
            skipping = True
            continue
        if end_tag in line:
            skipping = False
            continue
        if not skipping:
            new_lines.append(line)

    return "".join(new_lines)
