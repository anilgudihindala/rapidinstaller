"""
Developer Toolchains, Runtimes, and Environment Managers Engine for Rapid Installer.

Handles detection, installation, active version queries, shell environment injection,
and clean uninstallation of popular CLI runtimes (nvm, bun, deno, rustup, pyenv, sdkman, uv, go).
"""

import os
import shutil
import subprocess
from typing import Dict, List, Optional

from applaunch.utils.logger import logger
from applaunch.utils.shell_env import (
    inject_shell_profile_block,
    is_shell_profile_injected,
    remove_shell_profile_block,
)


TOOLCHAIN_DEFINITIONS = {
    "nvm": {
        "id": "nvm",
        "display_name": "NVM (Node Version Manager)",
        "category": "JavaScript / Node.js",
        "description": "Manage multiple active Node.js versions cleanly",
        "install_cmd": "curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash",
        "detect_path": "~/.nvm/nvm.sh",
        "version_cmd": "bash -c 'source ~/.nvm/nvm.sh && node -v 2>/dev/null || echo nvm-installed'",
        "shell_code": (
            'export NVM_DIR="$HOME/.nvm"\n'
            '[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"\n'
            '[ -s "$NVM_DIR/bash_completion" ] && \\. "$NVM_DIR/bash_completion"'
        ),
        "uninstall_paths": ["~/.nvm"],
    },
    "bun": {
        "id": "bun",
        "display_name": "Bun JavaScript Runtime",
        "category": "JavaScript / TypeScript",
        "description": "All-in-one fast JavaScript/TypeScript runtime & package manager",
        "install_cmd": "curl -fsSL https://bun.sh/install | bash",
        "detect_path": "~/.bun/bin/bun",
        "version_cmd": "~/.bun/bin/bun --version",
        "shell_code": (
            'export BUN_INSTALL="$HOME/.bun"\n'
            'export PATH="$BUN_INSTALL/bin:$PATH"'
        ),
        "uninstall_paths": ["~/.bun"],
    },
    "deno": {
        "id": "deno",
        "display_name": "Deno Runtime",
        "category": "JavaScript / TypeScript",
        "description": "Secure TypeScript and JavaScript runtime built in Rust",
        "install_cmd": "curl -fsSL https://deno.land/x/install/install.sh | sh",
        "detect_path": "~/.deno/bin/deno",
        "version_cmd": "~/.deno/bin/deno --version",
        "shell_code": (
            'export DENO_INSTALL="$HOME/.deno"\n'
            'export PATH="$DENO_INSTALL/bin:$PATH"'
        ),
        "uninstall_paths": ["~/.deno"],
    },
    "rustup": {
        "id": "rustup",
        "display_name": "Rustup (Rust Toolchain)",
        "category": "Rust Systems Programming",
        "description": "Official Rust compiler (rustc) and Cargo package manager installer",
        "install_cmd": "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
        "detect_path": "~/.cargo/bin/rustc",
        "version_cmd": "~/.cargo/bin/rustc --version",
        "shell_code": 'export PATH="$HOME/.cargo/bin:$PATH"',
        "uninstall_paths": ["~/.cargo", "~/.rustup"],
    },
    "pyenv": {
        "id": "pyenv",
        "display_name": "Pyenv (Python Version Manager)",
        "category": "Python Runtime",
        "description": "Switch between multiple Python 3.x releases effortlessly",
        "install_cmd": "curl -fsSL https://pyenv.run | bash",
        "detect_path": "~/.pyenv/bin/pyenv",
        "version_cmd": "~/.pyenv/bin/pyenv --version",
        "shell_code": (
            'export PYENV_ROOT="$HOME/.pyenv"\n'
            '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"\n'
            'eval "$(pyenv init - 2>/dev/null || true)"'
        ),
        "uninstall_paths": ["~/.pyenv"],
    },
    "sdkman": {
        "id": "sdkman",
        "display_name": "SDKMAN! (Java / Kotlin SDKs)",
        "category": "JVM / Java / Kotlin",
        "description": "Tool for managing parallel versions of Java SDKs, Gradle, and Maven",
        "install_cmd": 'bash -c \'curl -s "https://get.sdkman.io" | bash\'',
        "detect_path": "~/.sdkman/bin/sdkman-init.sh",
        "version_cmd": "bash -c 'source ~/.sdkman/bin/sdkman-init.sh && sdk version 2>/dev/null || echo sdkman-installed'",
        "shell_code": (
            'export SDKMAN_DIR="$HOME/.sdkman"\n'
            '[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "$HOME/.sdkman/bin/sdkman-init.sh"'
        ),
        "uninstall_paths": ["~/.sdkman"],
    },
    "uv": {
        "id": "uv",
        "display_name": "UV Python Package Manager",
        "category": "Python Toolchain",
        "description": "Extremely fast Python package installer and virtual environment resolver",
        "install_cmd": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "detect_path": "~/.cargo/bin/uv",
        "version_cmd": "~/.cargo/bin/uv --version 2>/dev/null || uv --version",
        "shell_code": 'export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"',
        "uninstall_paths": ["~/.cargo/bin/uv", "~/.local/bin/uv"],
    },
}


class ToolchainManager:
    """Manager engine for developer CLI toolchains and environment runtimes."""

    @staticmethod
    def list_all_toolchains() -> List[Dict]:
        """Returns list of supported toolchains with real-time installation status."""
        results = []
        for tool_id, meta in TOOLCHAIN_DEFINITIONS.items():
            detect_p = os.path.expanduser(meta["detect_path"])
            is_installed = os.path.exists(detect_p) or is_shell_profile_injected(tool_id)

            active_ver = "Not Installed"
            if is_installed:
                active_ver = ToolchainManager._query_version(meta["version_cmd"])

            results.append({
                "id": tool_id,
                "display_name": meta["display_name"],
                "category": meta["category"],
                "description": meta["description"],
                "installed": is_installed,
                "version": active_ver,
                "detect_path": detect_p,
            })
        return results

    @staticmethod
    def install_toolchain(tool_id: str) -> Dict:
        """Executes toolchain installation script and registers shell profile code."""
        if tool_id not in TOOLCHAIN_DEFINITIONS:
            return {"status": "ERROR", "msg": f"Unknown toolchain ID '{tool_id}'"}

        meta = TOOLCHAIN_DEFINITIONS[tool_id]
        logger.info(f"Starting installation of developer toolchain '{tool_id}'...")

        try:
            # Run installation pipeline inside bash
            res = subprocess.run(
                meta["install_cmd"],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300,
            )

            # Inject shell profile exports
            inject_shell_profile_block(tool_id, meta["shell_code"])

            # Query active version
            version_str = ToolchainManager._query_version(meta["version_cmd"])

            logger.info(f"Successfully installed developer toolchain '{tool_id}' ({version_str})")
            return {
                "status": "SUCCESS",
                "tool_id": tool_id,
                "display_name": meta["display_name"],
                "version": version_str,
            }
        except Exception as e:
            logger.error(f"Failed to install toolchain '{tool_id}': {e}")
            return {"status": "ERROR", "msg": str(e)}

    @staticmethod
    def uninstall_toolchain(tool_id: str) -> bool:
        """Removes toolchain files and cleans shell environment entries."""
        if tool_id not in TOOLCHAIN_DEFINITIONS:
            return False

        meta = TOOLCHAIN_DEFINITIONS[tool_id]
        logger.info(f"Uninstalling developer toolchain '{tool_id}'...")

        # 1. Strip shell profile tagged block
        remove_shell_profile_block(tool_id)

        # 2. Delete installation directories
        for path_str in meta.get("uninstall_paths", []):
            abs_p = os.path.expanduser(path_str)
            try:
                if os.path.isdir(abs_p):
                    shutil.rmtree(abs_p, ignore_errors=True)
                elif os.path.isfile(abs_p) or os.path.islink(abs_p):
                    os.remove(abs_p)
            except Exception as e:
                logger.warning(f"Error removing toolchain path {abs_p}: {e}")

        logger.info(f"Successfully uninstalled developer toolchain '{tool_id}'")
        return True

    @staticmethod
    def _query_version(cmd: str) -> str:
        """Executes version check shell command and formats clean output string."""
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
            out = res.stdout.strip() or res.stderr.strip()
            if out:
                # Return first line of version output
                return out.splitlines()[0][:40]
        except Exception:
            pass
        return "Installed"
