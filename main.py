#!/usr/bin/env python3
"""
AppLaunch Engine - Main Entry Point Script.
"""

import sys
import os

package_root = os.path.dirname(os.path.abspath(__file__))
if package_root not in sys.path:
    sys.path.insert(0, package_root)

from applaunch.cli import main

if __name__ == "__main__":
    sys.exit(main())
