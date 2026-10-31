"""Shared pytest configuration: put MaaAutoInstaller on the import path.

The installer/updater core layer does not depend on Qt, so these tests run quickly
and need no graphical environment.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "MaaAutoInstaller")
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)
