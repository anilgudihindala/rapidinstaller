"""
Data Formatting Utility for AppLaunch Engine.

Transforms messy archive filenames (e.g. "my-app-v2.1_linux_x86_64.tar.gz")
into clean, professional title-cased application names and filesystem slugs.
"""

import os
import re
from typing import Dict, List


# Noise words commonly present in Linux archive releases that should be stripped or cleaned
NOISE_PATTERNS: List[str] = [
    r"\b(linux|ubuntu|debian|fedora|arch|alpine)\b",
    r"\b(x86_64|amd64|x86|x64|i386|i686|arm64|aarch64|armv7l|arm)\b",
    r"\b(release|dist|build|stable|portable|standalone|bin|binary|desktop|linux64|linux32)\b",
    r"\b(tar\.gz|tgz|tar\.xz|txz|tar\.bz2|tbz2|zip|tar)\b",
]

KNOWN_ACRONYMS: Dict[str, str] = {
    "vscode": "VS Code",
    "clion": "CLion",
    "pycharm": "PyCharm",
    "webstorm": "WebStorm",
    "rider": "Rider",
    "goland": "GoLand",
    "datagrip": "DataGrip",
    "phpstorm": "PhpStorm",
    "ij": "IntelliJ IDEA",
    "idea": "IntelliJ IDEA",
    "postman": "Postman",
    "sublime": "Sublime Text",
    "discord": "Discord",
    "slack": "Slack",
    "blender": "Blender",
    "obs": "OBS Studio",
    "gimp": "GIMP",
    "vlc": "VLC Media Player",
    "kdenlive": "Kdenlive",
    "inkscape": "Inkscape",
}


def clean_app_name(archive_path: str) -> Dict[str, str]:
    """
    Transforms messy archive paths into structured application naming formats.

    Args:
        archive_path: Filename or full path of the archive.

    Returns:
        Dict containing:
            - 'display_name': Elegant Title Case string (e.g. "My App V2.1")
            - 'app_id': Lowercase, hyphenated slug for directories (e.g. "my-app-v2-1")
            - 'short_name': Compact core name without version tags (e.g. "My App")
            - 'search_slug': Lowercase token for executable matching (e.g. "myapp")
    """
    basename = os.path.basename(archive_path)
    # Strip browser duplicate download counter suffixes like " (1)", " (2)", " [1]", "_copy"
    basename = re.sub(r"[\s_\-]*[\(\[]\d+[\)\]]", "", basename)

    # 1. Remove all archive and package extensions
    name = re.sub(
        r"\.(tar\.gz|tgz|tar\.xz|txz|tar\.bz2|tbz2|zip|tar|deb|rpm|7z|rar|appimage|gz|xz|bz2)$",
        "",
        basename,
        flags=re.IGNORECASE,
    )

    # 2. Check for known application acronyms before stripping
    raw_name_lower = name.lower()
    for key, val in KNOWN_ACRONYMS.items():
        if raw_name_lower.startswith(key):
            # Extract version or remaining string if any
            remainder = name[len(key) :]
            remainder_clean = format_remainder(remainder)
            display_title = f"{val} {remainder_clean}".strip()
            slug = sanitize_slug(key)
            return {
                "display_name": display_title,
                "app_id": slug,
                "short_name": val,
                "search_slug": re.sub(r"[^a-z0-9]", "", key.lower()),
            }

    # 3. Tokenize by separators (_ - space)
    raw_tokens = [t for t in re.split(r"[_\-\s]+", name) if t]

    noise_words = {
        "linux", "ubuntu", "debian", "fedora", "arch", "alpine", "deb", "rpm",
        "x86_64", "amd64", "x86", "x64", "64", "32", "i386", "i686", "arm64", "aarch64", "armv7l", "arm",
        "release", "dist", "build", "stable", "current", "portable", "standalone", "bin", "binary", "desktop", "linux64", "linux32"
    }

    tokens = [t for t in raw_tokens if t.lower() not in noise_words]

    if not tokens:
        tokens = raw_tokens or [name]

    # Process tokens into Title Case
    formatted_tokens: List[str] = []
    short_tokens: List[str] = []

    for token in tokens:
        # Check if version pattern (e.g. v2.1, 1.85.0)
        if re.match(r"^v?\d+(\.\d+)*$", token, re.IGNORECASE):
            # Keep version tag in display_name, but exclude from short_name
            if token.lower().startswith("v"):
                formatted_tokens.append("V" + token[1:])
            else:
                formatted_tokens.append(token)
        else:
            # Capitalize word
            cap_token = token.capitalize()
            formatted_tokens.append(cap_token)
            short_tokens.append(cap_token)

    display_name = " ".join(formatted_tokens).strip()
    short_name = " ".join(short_tokens).strip() if short_tokens else display_name

    # If display_name ended up empty or single word version
    if not display_name:
        display_name = "Application"
        short_name = "Application"

    app_id = sanitize_slug(short_name)
    search_slug = re.sub(r"[^a-z0-9]", "", short_name.lower())

    return {
        "display_name": display_name,
        "app_id": app_id,
        "short_name": short_name,
        "search_slug": search_slug,
    }


def format_remainder(remainder: str) -> str:
    """Formats version numbers or trailing strings cleanly."""
    clean = re.sub(r"[_\-\s]+", " ", remainder).strip()
    clean = re.sub(
        r"\b(linux|x86_64|amd64|x64|i386|arm64|release|dist|build)\b",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()
    if clean.lower().startswith("v"):
        clean = "V" + clean[1:]
    return clean


def sanitize_slug(name: str) -> str:
    """Converts a string into a clean, filesystem-safe slug (e.g. "my-app-v2-1")."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "installed-app"
