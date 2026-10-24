"""pytest 公共配置：把 MaaAutoInstaller 加进 import 路径。

安装器/升级器的 core 层不依赖 Qt，所以这些测试跑得很快，也不需要图形环境。
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "MaaAutoInstaller")
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)
