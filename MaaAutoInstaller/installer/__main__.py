"""
入口脚本。
    python -m installer
以及 PyInstaller 打包时的入口。
"""

import os
import sys

# PyInstaller 打包时本文件被当作顶层脚本执行，
# 需要把父目录加入 sys.path 才能 import installer 包。
_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from installer.app import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())