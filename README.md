# MaaAuto Installer

> MaaAuto 的**在线轻便版**安装器 —— 45 MB 下载，用户端本地下载依赖并打包主程序。

![Python](https://img.shields.io/badge/Python-3.11-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6+-green)
![Size](https://img.shields.io/badge/Download-45%20MB-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📖 这是什么

**MaaAuto Installer** 是 [MaaAuto](../MaaAutoProject/) 的图形化安装程序。

它**不预打包**主程序（那样安装包会膨胀到 250 MB+），而是让用户的机器**自己下载 Python + 依赖 + 本地 PyInstaller 打包**。这样安装器本体只有 ~45 MB，便于分发。

### 两种分发形式

| 版本 | 下载大小 | 安装耗时 | 特点 |
|---|---|---|---|
| **🟢 在线轻便版**（本项目） | ~45 MB | 6~20 分钟 | 联网下载依赖 + 本地打包，推荐 |
| **⚪ 全量离线版**（旧版） | ~246 MB | 1~2 分钟 | 预打包，无需联网打包 |

**两种版本装完后完全一样**，只是安装过程不同。

---

## 🚀 用户使用指南

### 系统要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10 / 11（64 位） |
| 磁盘空间 | 约 1 GB（安装过程中峰值 ~1.5 GB） |
| 网络 | **必须联网**（首次安装需下载约 200 MB 依赖） |
| CPU / 内存 | 无特殊要求，打包阶段建议 4 核 + 8 GB |
| 管理员权限 | **不需要** |

### 安装步骤

#### 1. 下载

从 [GitHub Releases](https://github.com/mmccz/MaaAuto-Tool-works/releases) 下载最新的：

```
MaaAuto_Online_vX.X.X-Windows-x64.zip
```

#### 2. 解压

解压到任意目录，**保持三个文件在同一文件夹**：

```
MaaAuto_Setup.exe      ← 安装器（~45 MB）
MaaAuto_Source.zip     ← 主程序源码（~100 KB）
README.txt             ← 使用说明
```

> ⚠️ **不要单独移动** `MaaAuto_Setup.exe`，它需要读取同级的 `MaaAuto_Source.zip`。

#### 3. 运行

双击 `MaaAuto_Setup.exe`，按向导操作：

| 步骤 | 操作 |
|---|---|
| **① 欢迎页** | 选语言（简体中文 / English） |
| **② 选择目录** | 默认 `D:\MaaAuto`，推荐非系统盘、纯英文路径 |
| **③ 安装选项** | 选镜像源、是否创建快捷方式 |
| **④ 进度页** | 自动执行（见下方流程） |
| **⑤ 完成页** | 打开目录 / 立即启动 |

#### 4. 等待

安装过程约 **6~20 分钟**，取决于网速和 CPU。进度页会实时显示日志：

```
准备中...
下载独立 Python 3.11.9...         ← ~10 MB
解压程序源码...
安装 pip...
安装程序依赖（约 200 MB）...       ← 最耗时
安装打包工具 PyInstaller...
在本地打包主程序（数分钟）...       ← CPU 占用高
释放卸载器 / 升级器...
创建快捷方式...
写入元数据...
清理临时文件...
安装完成！
```

> 💡 **提示**：PyInstaller 打包阶段 CPU 占用较高，属正常现象，请勿关闭窗口。

#### 5. 完成

从桌面快捷方式启动 MaaAuto。

### 安装后目录

```
D:\MaaAuto\
├── MaaAuto.exe             ← 主程序
├── _internal/              ← PyInstaller 运行时依赖
├── resources/              ← 图标 / 图像识别素材
├── themes/                 ← 主题 QSS
├── i18n/                   ← 语言包
├── requirements.txt
├── README.md / LICENSE / CHANGELOG.md
├── _version_info.txt
├── uninstall.exe           ← 卸载程序
├── upgrade.exe             ← 升级程序（占位）
├── .maaauto.json           ← 安装元数据
├── config/                 ← 用户配置（首次启动生成）
└── logs/                   ← 运行日志（首次启动生成）
```

### 卸载

双击 `D:\MaaAuto\uninstall.exe`：

1. 确认卸载 → 点"是"
2. 是否保留 `config/` 和 `logs/` → 推荐"否"
3. 弹窗提示后，几秒内目录被清理

### 升级

> 🚧 升级功能开发中，当前 `upgrade.exe` 会弹提示引导手动升级。

**当前手动升级方式**：下载新版安装包，安装到**同一目录**（覆盖旧文件）。

---

## 🛠️ 开发者指南

### 环境要求

- Windows 10 / 11
- Python 3.11.9
- PyInstaller

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

### 目录结构

```
MaaAutoInstaller/
├── build_installer.py      # 一键构建脚本（产物 = 交付 zip）
├── VERSION                 # 安装器版本号
├── requirements.txt        # 安装器依赖（PySide6 + pywin32）
├── README.md               # 本文件
│
├── installer/              # 安装器源码
│   ├── __init__.py         # 版本号
│   ├── __main__.py         # PyInstaller 入口
│   ├── app.py              # QApplication 启动
│   ├── wizard.py           # 向导主窗口
│   ├── state.py            # 安装状态对象
│   │
│   ├── core/               # 核心逻辑（无 GUI 依赖，可复用）
│   │   ├── manifest.py     # .maaauto.json 读写
│   │   ├── mirror.py       # 镜像源选择
│   │   ├── downloader.py   # urllib 下载工具
│   │   ├── python_env.py   # embeddable Python 部署
│   │   ├── pip_installer.py# pip 安装 + 升级
│   │   ├── pyinstaller_builder.py  # 本地打包主程序
│   │   ├── source_deployer.py      # 源码解压
│   │   ├── uninstall.py    # 卸载器部署
│   │   ├── upgrade.py      # 升级器部署
│   │   ├── shortcut.py     # 快捷方式创建
│   │   └── cleanup.py      # 临时文件清理
│   │
│   ├── pages/              # 向导页
│   │   ├── base.py         # 页基类
│   │   ├── welcome.py      # 欢迎 + 语言
│   │   ├── choose_dir.py   # 选择目录
│   │   ├── options.py      # 安装选项
│   │   ├── progress.py     # 进度 + 后台 Worker
│   │   └── finish.py       # 完成
│   │
│   └── i18n/               # 语言包
│       ├── __init__.py
│       ├── zh_CN.json
│       └── en_US.json
│
├── tools/                  # 独立小工具
│   ├── uninstall_stub.py   # 卸载器源码（VBS 后端）
│   ├── upgrade_stub.py     # 升级器源码（占位）
│   ├── build_stubs.py      # 打包上面两个
│   └── _out/               # 产物
│       ├── uninstall.exe
│       └── upgrade.exe
│
└── resources/
    └── icon.ico
```

### 构建

```powershell
python build_installer.py
```

**构建流程**：

1. 打包 `../MaaAutoProject/` 为 `_embedded/source.zip`（排除 `__pycache__` / `build` / `dist` / `config` / `logs`）
2. 打包 `tools/uninstall_stub.py` → `tools/_out/uninstall.exe`
3. 打包 `tools/upgrade_stub.py` → `tools/_out/upgrade.exe`
4. 打包 `installer/` → `dist/MaaAuto_Setup.exe`（**onefile**，内嵌两个 stubs + `resources/`）
5. 组合最终 zip → `dist/MaaAuto_Online_vX.X.X-Windows-x64.zip`

**产物**：

```
dist/MaaAuto_Online_vX.X.X-Windows-x64.zip
├── MaaAuto_Setup.exe      ← 安装器（~45 MB）
├── MaaAuto_Source.zip     ← 主程序源码（~100 KB）
└── README.txt             ← 使用说明
```

**参数**：

| 参数 | 说明 |
|---|---|
| `--debug` | 保留控制台，便于排查；stubs 也保留 |
| `--no-stub-rebuild` | 复用已有 stubs（加快迭代，省 1 分钟） |
| `--keep-build` | 保留 `build/` `dist/` `_embedded/` 中间产物 |
| `--source-dir PATH` | 指定主程序源码路径（默认 `../MaaAutoProject`） |

### 单独更新 stub

改完 `tools/uninstall_stub.py` 或 `tools/upgrade_stub.py` 后：

```powershell
python tools\build_stubs.py
python build_installer.py --no-stub-rebuild
```

### 清理临时文件

```powershell
# 构建产物
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Remove-Item -Force MaaAuto_Setup.spec -ErrorAction SilentlyContinue

# __pycache__
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force

# PyInstaller 临时目录
Remove-Item -Recurse -Force tools\_work_uninstall, tools\_work_upgrade -ErrorAction SilentlyContinue
```

### 发布

1. 确认 `../MaaAutoProject/app_info.py` 里 `APP_VERSION` 已更新
2. 跑 `python build_installer.py`
3. 上传 `dist/MaaAuto_Online_vX.X.X-Windows-x64.zip` 到 GitHub Release
4. **Tag 必须**与 `APP_VERSION`（去 v 后）一致

| GitHub Tag | APP_VERSION |
|---|---|
| `v2.0.2` | `2.0.2` ✅ |
| `2.0.2` | `2.0.2` ✅ |

---

## 🏗️ 架构

### 工作流程

```
┌────────────────────────────────────────────────────────┐
│ 开发者本地：                                             │
│                                                         │
│  MaaAutoProject/  →  python build.py  →  dist/MaaAuto/  │
│                                                         │
│  MaaAutoInstaller/                                      │
│    ↓ python build_installer.py                          │
│  MaaAuto_Online_vX.X.X-Windows-x64.zip                  │
│    ├── MaaAuto_Setup.exe   （45 MB，内嵌 2 stubs）      │
│    ├── MaaAuto_Source.zip  （100 KB，主程序源码）       │
│    └── README.txt                                       │
│                                                         │
│  上传到 GitHub Release                                   │
└────────────────────────────────────────────────────────┘
                      ↓ 用户下载 ~45 MB
┌────────────────────────────────────────────────────────┐
│ 用户端（双击 MaaAuto_Setup.exe）：                       │
│                                                         │
│  1. 选安装目录                                           │
│  2. 下载 embeddable Python 3.11.9（10 MB，走镜像）       │
│  3. 解压 source.zip 到临时目录                            │
│  4. 安装 pip → 升级到最新                                │
│  5. pip install 主程序依赖（~200 MB，走镜像）             │
│  6. pip install pyinstaller                             │
│  7. 调 build.py，本地打包主程序                           │
│  8. 拷贝 dist/MaaAuto/ 到安装目录                         │
│  9. 释放 uninstall.exe / upgrade.exe                    │
│  10. 创建快捷方式                                         │
│  11. 写 .maaauto.json                                   │
│  12. 删除临时工作目录                                     │
└────────────────────────────────────────────────────────┘
                      ↓
                  D:\MaaAuto\（成品）
```

### 关键设计决策

| 决策 | 原因 |
|---|---|
| **不在安装包内预置 PyInstaller 产物** | 否则安装包会膨胀到 250 MB+ |
| **用户端本地打包** | 安装包仅 45 MB，便于分发 |
| **下载 embeddable Python** | 用户机器无需预装 Python |
| **不保留 Python 环境** | 安装目录保持干净（~200 MB） |
| **VBS 后端卸载** | 避免 bat 的编码/管道坑，`wscript.exe` 从 XP 起就有 |
| **镜像源自动选择** | 中文系统 → 清华/阿里云；其他 → 官方 PyPI |
| **`core/` 无 GUI 依赖** | 未来升级器直接复用 |

### `.maaauto.json` 元数据

安装完成后在安装根目录生成，供未来升级器读取：

```json
{
  "version": "2.0.2",
  "installer_version": "1.0.0",
  "manifest_version": 2,
  "install_dir": "D:\\MaaAuto",
  "app_exe": "D:\\MaaAuto\\MaaAuto.exe",
  "uninstall_exe": "D:\\MaaAuto\\uninstall.exe",
  "upgrade_exe": "D:\\MaaAuto\\upgrade.exe",
  "requirements_hash": "a3f2b1c4d5e6f7...",
  "mirror": "tuna",
  "installed_at": "2026-09-19T15:30:00",
  "updated_at": "2026-09-19T15:30:00",
  "extra": {}
}
```

| 字段 | 用途 |
|---|---|
| `version` | 主程序版本 |
| `requirements_hash` | 依赖清单 sha256，升级时判断依赖是否变化 |
| `mirror` | 记录用户选择的镜像源 |
| `installed_at` / `updated_at` | 安装时间 |

### 更新机制（预留）

未来升级器 `upgrade.exe` 的计划流程：

```
1. 读 .maaauto.json → 拿当前版本 + requirements_hash
2. 请求 GitHub Release API → 拿最新版本
3. 对比版本号
4. 下载新版 MaaAuto_Source.zip
5. 比对 requirements_hash：
   - 变了 → 重新走完整安装（重建 Python + 依赖）
   - 没变 → 只覆盖源码，跳过依赖安装（快）
6. 更新 .maaauto.json
7. 重启主程序
```

**为什么现在不做**：先跑通首次安装，让基础稳固。

---

## 📚 模块参考

### `installer/core/` 各模块职责

| 模块 | 职责 |
|---|---|
| `manifest.py` | 读写 `.maaauto.json` |
| `mirror.py` | PyPI / Python 镜像源解析（自动检测中文系统） |
| `downloader.py` | 通用 HTTP 下载（带进度回调） |
| `python_env.py` | 下载解压 embeddable Python + 修改 `._pth` |
| `pip_installer.py` | 安装 pip + 升级到最新 + 装依赖/PyInstaller |
| `pyinstaller_builder.py` | 调 `build.py` 打包主程序 + 拷贝产物 |
| `source_deployer.py` | 解压 `source.zip` |
| `uninstall.py` | 释放 `uninstall.exe` |
| `upgrade.py` | 释放 `upgrade.exe` |
| `shortcut.py` | 创建/删除桌面和开始菜单快捷方式（pywin32） |
| `cleanup.py` | 删工作目录、pip 缓存、系统临时文件 |

### 数据流

```
向导页（pages/*.py）
    ↓ 读写
InstallState（state.py）
    ↓ 传给
后台 Worker（pages/progress.py::InstallWorker）
    ↓ 调用
core/*（纯逻辑，无 GUI）
    ↓ 输出
日志信号 / 进度信号 → 向导页 UI
```

---

## ❓ 常见问题

### 用户侧

#### Q1：安装时提示"找不到 MaaAuto_Source.zip"

**原因**：三个文件没放在一起。

**解决**：解压时确保在同一目录，**不要单独移动** `MaaAuto_Setup.exe`。

#### Q2：pip 阶段很慢

**原因**：默认镜像源可能是官方 PyPI。

**解决**：安装向导第 3 步选"清华大学镜像"或"阿里云镜像"。

#### Q3：PyInstaller 打包阶段特别久

**正常现象**：打包 PySide6 项目耗时 2~5 分钟，CPU 占用高。

**解决**：耐心等待，不要关窗口。

#### Q4：主程序报 `ModuleNotFoundError`

**原因**：依赖没装全。

**解决**：
1. 检查安装目录下的 `requirements.txt` 是否完整
2. 重装，**不要**中断 pip 阶段

#### Q5：卸载程序双击无反应

**原因**：可能被杀毒软件拦截，或 VBS 执行失败。

**解决**：
1. 检查 `%TEMP%\MaaAuto_uninstall_*.vbs` 是否生成
2. 手动执行 `wscript <vbs路径>` 看是否报错
3. 若无法自动卸载，手动删除安装目录

#### Q6：首次启动安装器很慢

**原因**：PyInstaller onefile 需要在 `%TEMP%` 解压 PySide6（~3~8 秒）。

**解决**：正常现象，第二次启动就快了。

### 开发者侧

#### Q7：`build_installer.py` 报 `UnboundLocalError: 'count'`

**原因**：`build_source_zip` 函数里 `count = 0` 初始化丢了。

**解决**：检查函数体开头有没有 `count = 0`。

#### Q8：主程序 `build.py` 报 `UnicodeEncodeError: 'gbk' codec`

**原因**：`build.py` 里有 emoji print（如 `print("打包成功 ✅")`），GBK 控制台编不出来。

**解决**：把 emoji 换成 ASCII（如 `[OK]`）。

#### Q9：安装器窗口左上角没图标

**原因**：`build_installer.py` 里没把 `resources/` 通过 `--add-data` 打进安装器。

**解决**：在 PyInstaller 命令里加：
```python
"--add-data", f"{ROOT / 'resources'}{os.pathsep}resources",
```

#### Q10：`pip install` 报 `UnicodeDecodeError: 'gbk' codec`

**原因**：`requirements.txt` 含中文注释，pip 用系统编码读取。

**解决**：`pip_installer._sanitize_requirements()` 会自动剥离非 ASCII 字符后重写，**无需手动处理**。若仍报错，检查 `pip_installer.py` 是否为最新版。

#### Q11：想改 `source.zip` 里包含什么

**解决**：编辑 `build_installer.py`：

```python
SOURCE_EXCLUDE_DIRS = {
    "__pycache__", ".git", "build", "dist",
    "config", "logs", "venv", ".venv",
    # 加你想排除的
}
SOURCE_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".log", ".spec")
```

#### Q12：想改 `uninstall.exe` 的行为

**解决**：编辑 `tools/uninstall_stub.py`，改完跑：

```powershell
python tools\build_stubs.py
python build_installer.py --no-stub-rebuild
```

#### Q13：想改 `upgrade.exe` 的行为

**解决**：编辑 `tools/upgrade_stub.py`，同上。

---

## 📦 版本号约定

本项目有**两个独立版本号**：

| 版本号 | 位置 | 含义 |
|---|---|---|
| **主程序版本** | `../MaaAutoProject/app_info.py` → `APP_VERSION` | 用户最终运行的软件版本 |
| **安装器版本** | `VERSION` | 安装器工具本身的版本 |

**规则**：
- 改主程序 → `APP_VERSION` +1，`VERSION` **不变**
- 改安装器逻辑 → `VERSION` +1，`APP_VERSION` **不变**
- 两个都改 → 都 +1

**文件名**：使用**主程序版本号**（因为用户关心的是装完得到什么版本）：

```
MaaAuto_Online_v{APP_VERSION}-Windows-x64.zip
```

---

## 📜 许可证

[MIT License](../LICENSE) © 2024-2026 MaaAuto

---

## 📮 联系

- **GitHub**：https://github.com/mmccz/MaaAuto-Tool-works
- **Issues**：https://github.com/mmccz/MaaAuto-Tool-works/issues
- **邮箱**：Frank010700@outlook.com

---

<p align="center">
  <sub>MaaAuto Installer · Made with ❤️ by MaaAuto Team</sub>
</p>
