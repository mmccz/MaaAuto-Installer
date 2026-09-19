# MaaAutoInstaller

MaaAuto 的独立安装器 + 未来更新器。

## 定位

- **不依赖** MaaAuto 源码，把 `MaaAutoProject/` 当作"待部署的数据"。
- **零污染**：安装器自己不 import MaaAuto，也不会被 MaaAuto 影响。
- **可复用**：`installer/core/` 的所有模块同时服务于"首次安装"和"未来更新"。

## 交付形态

用户从 GitHub Release 下载一个 zip：

```
MaaAuto_v2.0.0-Beta2.zip
├── MaaAuto_Setup.exe         # 安装器（~35MB）
├── MaaAuto_Source.zip        # 源码（~2MB）
└── README.txt                # 使用说明
```

用户解压后双击 `MaaAuto_Setup.exe`，安装器会：

1. 检测系统 Python 3.11.9 → 无则下载 embeddable（走镜像）
2. 部署源码到安装目录，编译为 `.pyc` 后删除 `.py`
3. pip 安装依赖（走镜像）
4. 释放 `MaaAuto.exe` 启动器 + `uninstall.exe` 卸载器
5. 创建桌面 + 开始菜单快捷方式
6. 写 `.maaauto.json` 元数据（供未来更新器读）
7. 清理临时文件（`__pycache__`、pip 缓存、下载文件）
8. 询问是否立即启动

## 目录结构

```
MaaAutoInstaller/
├── build_installer.py            # 一键构建脚本
├── requirements.txt              # 安装器依赖
├── VERSION                       # 安装器版本号
│
├── installer/                    # 安装器源码
│   ├── __init__.py
│   ├── __main__.py               # python -m installer 入口
│   ├── app.py                    # QApplication 主入口
│   ├── wizard.py                 # 向导主窗口
│   │
│   ├── core/                     # 核心逻辑（可复用）
│   │   ├── manifest.py           # .maaauto.json 读写
│   │   ├── mirror.py             # 镜像源选择
│   │   ├── python_env.py         # 系统 Python 检测 / embeddable 下载
│   │   ├── pip_installer.py      # pip 安装依赖
│   │   ├── source_deployer.py    # 源码部署 + .pyc 编译
│   │   ├── launcher.py           # MaaAuto.exe 启动器释放
│   │   ├── shortcut.py           # 快捷方式创建
│   │   ├── uninstall.py          # uninstall.exe 生成
│   │   └── cleanup.py            # 临时文件清理
│   │
│   ├── pages/                    # 向导页
│   │   ├── welcome.py
│   │   ├── choose_dir.py
│   │   ├── options.py
│   │   ├── progress.py
│   │   └── finish.py
│   │
│   └── i18n/
│       ├── __init__.py
│       ├── zh_CN.json
│       └── en_US.json
│
├── tools/
│   ├── launcher_stub.py          # MaaAuto.exe 启动器源码
│   └── build_launcher.py         # 把上面打包成 launcher.exe
│
├── resources/                    # 图标等静态资源（用户自备）
│   └── icon.ico
│
└── _embedded/                    # 构建时自动生成（不提交 git）
    ├── launcher.exe              # 由 tools/build_launcher.py 产出
    └── source.zip                # 由 build_installer.py 从 ../MaaAutoProject 打包
```

## 构建

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 2. 一键构建（会自动打包 MaaAutoProject 源码 + 打包安装器 exe + 打包 launcher.exe）
python build_installer.py

# 产物：
#   dist/MaaAuto_v2.0.0-Beta2.zip      ← 最终交付给用户的压缩包
#   dist/MaaAuto_Setup.exe             ← 单独拿出去也能用（需同级有 MaaAuto_Source.zip）
#   dist/MaaAuto_Source.zip
```

### 常用参数

```bash
python build_installer.py --source-dir ../MaaAutoProject   # 指定源码目录
python build_installer.py --debug                          # 保留控制台 + 打包 launcher 时也保留
python build_installer.py --no-launcher-rebuild            # 复用已有 _embedded/launcher.exe（跳过打 8MB 小 exe，加快迭代）
python build_installer.py --keep-build                     # 不清理 build/ dist/ _embedded/
```

## 未来更新器（尚未实现，但 core 已就绪）

更新器将来会：
1. 从 GitHub Releases API 拿最新版本
2. 下载 `MaaAuto_vX.X.X.zip`
3. 读取安装目录的 `.maaauto.json`，比对 `requirements_hash`
4. 若变了 → 调 `core.pip_installer.install(...)` 更新依赖
5. **必定**调 `core.source_deployer.deploy(..., mode="update")` 覆盖源码
6. 调 `core.manifest.write(...)` 更新元数据

因为 core 模块全部无 GUI 依赖、无状态，更新器可以直接复用。

## 许可

MIT（与 MaaAuto 一致）