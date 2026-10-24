"""裁剪 payload：删除运行期用不到的 Qt / OpenCV 组件。

只做「删文件」，不改任何配置。默认 dry-run，加 ``--apply`` 才真正删除。

规则来自实测（PySide6 6.11 / OpenCV 5.0）：widgets 应用不需要 Quick/Qml/Pdf/
VirtualKeyboard，截图找图不需要 cv2 的 videoio ffmpeg 后端。
"""

import argparse
import shutil
from pathlib import Path

# (相对 payload 根的 glob, 说明)
TRIM_RULES = [
    ("_internal/PySide6/Qt6Quick*.dll", "Qt Quick"),
    ("_internal/PySide6/Qt6Qml*.dll", "Qt QML"),
    ("_internal/PySide6/Qt6Pdf*.dll", "Qt PDF"),
    ("_internal/PySide6/Qt6Svg*.dll", "Qt SVG"),
    ("_internal/PySide6/Qt6VirtualKeyboard*.dll", "Qt 虚拟键盘"),
    ("_internal/PySide6/opengl32sw.dll", "Qt 软件 OpenGL（19.7 MB）"),
    ("_internal/PySide6/plugins/imageformats/qsvg.dll", "SVG 图片插件"),
    ("_internal/PySide6/plugins/iconengines/qsvgicon.dll", "SVG 图标引擎"),
    ("_internal/cv2/opencv_videoio_ffmpeg*.dll", "OpenCV 视频后端（找图用不到）"),
]


def _human(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def collect(payload_dir: Path):
    """返回 [(path, size, note)]。"""
    hits = []
    for pattern, note in TRIM_RULES:
        for p in payload_dir.glob(pattern):
            if p.is_file():
                hits.append((p, p.stat().st_size, note))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="裁剪 MaaAuto payload")
    ap.add_argument("payload_dir", type=Path)
    ap.add_argument("--apply", action="store_true", help="真正删除（默认只统计）")
    args = ap.parse_args()

    payload = args.payload_dir.resolve()
    if not (payload / "_internal").is_dir():
        print(f"[error] 不像 onedir 产物（缺 _internal）: {payload}")
        return 1

    hits = collect(payload)
    total = sum(size for _, size, _ in hits)
    for path, size, note in sorted(hits, key=lambda x: -x[1]):
        rel = path.relative_to(payload)
        print(f"  {_human(size):>8}  {rel}  ({note})")
    print(f"\n可裁剪 {len(hits)} 个文件，合计 {_human(total)}")

    if not args.apply:
        print("（dry-run；加 --apply 才会删除）")
        return 0

    for path, _size, _note in hits:
        try:
            path.unlink()
        except Exception as e:
            print(f"[warn] 删除失败 {path.name}: {e}")

    # 清掉空的 plugins 子目录不影响运行，这里不动
    remaining = sum(f.stat().st_size for f in payload.rglob("*") if f.is_file())
    print(f"裁剪完成，payload 现为 {_human(remaining)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
