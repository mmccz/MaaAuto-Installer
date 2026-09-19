# MaaAuto Tool Works

> MaaAuto 的官方工作区：主程序 + 在线轻便版安装器。

![Python](https://img.shields.io/badge/Python-3.11-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6+-green)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11%20x64-lightgrey)
![Size](https://img.shields.io/badge/Download-~95%20MB-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📖 目录

- [一、项目总览](#一项目总览)
- [二、用户指南](#二用户指南)
  - [2.1 系统要求](#21-系统要求)
  - [2.2 安装](#22-安装)
  - [2.3 安装后目录](#23-安装后目录)
  - [2.4 卸载](#24-卸载)
  - [2.5 升级](#25-升级)
- [三、开发者指南](#三开发者指南)
  - [3.1 环境要求](#31-环境要求)
  - [3.2 目录结构](#32-目录结构)
  - [3.3 主程序开发](#33-主程序开发)
  - [3.4 安装器构建](#34-安装器构建)
  - [3.5 发布流程](#35-发布流程)
- [四、架构与设计](#四架构与设计)
  - [4.1 工作流程](#41-工作流程)
  - [4.2 关键设计决策](#42-关键设计决策)
  - [4.3 元数据契约](#43-元数据契约)
  - [4.4 升级机制](#44-升级机制)
- [五、模块参考](#五模块参考)
  - [5.1 主程序模块](#51-主程序模块)
  - [5.2 安装器模块](#52-安装器模块)
  - [5.3 数据流](#53-数据流)
- [六、常见问题](#六常见问题)
  - [6.1 用户侧](#61-用户侧)
  - [6.2 开发者侧](#62-开发者侧)
- [七、版本号约定](#七版本号约定)
- [八、许可证与联系](#八许可证与联系)

---

## 一、项目总览

**MaaAuto** 是一款面向 MAA（MaaAssistantArknights）的图形化自动化助手。

本工作区包含两部分：

| 目录 | 说明 |
|---|---|
| `MaaAutoProject/` | MaaAuto 主程序源码（PySide6 桌面应用） |
| `MaaAuto-Installer/`（**独立仓库**） | MaaAuto 的在线轻便版安装器 |

### 核心特性

**主程序**：
- 🎮 **一键启动**：自动检测并启动 MAA / 模拟器
- ⏰ **定时任务**：设定时间自动执行日常任务
- 📊 **任务日志**：记录每次执行的详细日志
- 🔔 **通知推送**：任务完成后通过 Server 酱推送
- 🌏 **多语言**：简体中文 / English
- 🎨 **主题**：浅色 / 深色 / 跟随系统
- 🔄 **自动更新**：内置升级器，一键更新

**安装器**：
- 📦 **单文件分发**：约 95 MB 的独立 exe，双击即用
- 🔧 **无预装 Python**：安装时下载 embeddable Python 3.11.9
- 🧹 **无残留**：安装完自动清理临时工作目录
- 🎨 **深浅色主题**：跟随系统
- 📊 **分阶段进度条**：精确反映每个安装阶段
- 🚀 **自动更新**：内置升级器

### 分发形态

```
MaaAuto_Online_vX.X.X-Windows-x64.exe      ← 单文件，约 95 MB
```

内嵌 3 个资源：
- `MaaAuto_Source.zip`（主程序源码，~100 KB）
- `uninstall.exe`（卸载器，~7 MB）
- `upgrade.exe`（升级器，~43 MB，含 PySide6 进度 UI）

---

## 二、用户指南

### 2.1 系统要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10 / 11（64 位） |
| 磁盘空间 | 约 1 GB（安装过程中峰值 ~1.5 GB） |
| 网络 | **必须联网**（首次安装需下载约 200 MB 依赖） |
| CPU / 内存 | 无特殊要求，打包阶段建议 4 核 + 8 GB |
| 管理员权限 | **不需要** |

### 2.2 安装

#### 下载

从 [GitHub Releases](https://github.com/mmccz/MaaAuto-Tool-works/releases) 下载最新的：

```
MaaAuto_Online_vX.X.X-Windows-x64.exe
```

#### 运行

**双击该 exe**，按向导操作：

| 步骤 | 操作 |
|---|---|
| **① 欢迎页** | 选语言（简体中文 / English） |
| **② 选择目录** | 默认 `D:\MaaAuto`，推荐非系统盘、纯英文路径 |
| **③ 安装选项** | 选镜像源、是否创建快捷方式 |
| **④ 进度页** | 自动执行（见下方流程） |
| **⑤ 完成页** | 打开目录 / 立即启动 |

#### 安装流程

安装过程**通常只需几分钟**，取决于网速和 CPU。进度页会实时显示日志：

```
准备中...
下载独立 Python 3.11.9...        ← ~10 MB
解压程序源码...
安装 pip...
安装程序依赖（约 200 MB）...      ← 最耗时
安装打包工具 PyInstaller...
在本地打包主程序...              ← CPU 占用高
释放卸载器 / 升级器...
创建快捷方式...
写入元数据...
清理临时文件...
安装完成！
```

> 💡 **提示**：打包阶段 CPU 占用较高，属正常现象，请勿关闭窗口。

#### 完成

从桌面快捷方式启动 MaaAuto。

### 2.3 安装后目录

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
├── upgrade.exe             ← 升级程序
├── .maaauto.json           ← 安装元数据
├── config/                 ← 用户配置（首次启动生成）
└── logs/                   ← 运行日志（首次启动生成）
```

### 2.4 卸载

双击 `D:\MaaAuto\uninstall.exe`：

1. 确认卸载 → 点"是"
2. 是否保留 `config/` 和 `logs/` → 推荐"否"
3. 弹窗提示后，几秒内目录被清理

### 2.5 升级

MaaAuto 内置**自动升级**功能：

- 主程序启动后会自动检查更新（可在**设置**中调整检查时机）
- 发现新版本时：
  - **手动升级**：弹提示，用户确认后由 `upgrade.exe` 完成
  - **自动升级**：若用户在设置中开启"自动更新"，检测到新版后会**静默执行升级**

升级过程会：

1. 校验版本 + 下载新版源码包
2. 优雅停止主程序
3. 备份现有安装（可回滚）
4. 重新下载 Python + 依赖 + 本地打包
5. 覆盖安装目录（**保留 `config/` 和 `logs/`**）
6. 重启主程序

升级**失败会自动回滚**到升级前的版本，并在下次启动主程序时提示用户。

---

## 三、开发者指南

### 3.1 环境要求

- Windows 10 / 11
- Python 3.11.9
- PyInstaller

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

### 3.2 目录结构

```
MaaAuto-Tool-works/                    ← 主程序仓库
├── README.md                          ← 本文件
├── LICENSE
├── .gitignore
│
├── MaaAutoProject/                    ← 主程序源码
│   ├── main.py                        ← 入口
│   ├── app_info.py                    ← 版本号 + 升级常量
│   ├── config_manager.py              ← 配置读写
│   ├── update_checker.py              ← 更新检查
│   ├── process_utils.py               ← 进程管理
│   ├── automation.py                  ← 自动化逻辑
│   ├── notifier.py                    ← 通知推送
│   ├── build.py                       ← PyInstaller 打包脚本
│   ├── publish.py                     ← 发布脚本
│   ├── ui/                            ← 界面
│   │   ├── main_window.py
│   │   ├── home_page.py
│   │   ├── settings_page.py
│   │   ├── about_page.py
│   │   └── widgets/
│   ├── themes/                        ← 主题 QSS
│   ├── i18n/                          ← 语言包
│   ├── resources/                     ← 图标 / 素材
│   └── requirements.txt
│
└── image/                             ← 仓库展示图片

MaaAuto-Installer/                     ← 安装器仓库（独立）
└── MaaAutoInstaller/
    ├── build_installer.py             ← 一键构建脚本
    ├── VERSION                        ← 安装器版本号
    ├── requirements.txt
    ├── README.md
    │
    ├── installer/                     ← 安装器源码
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── app.py
    │   ├── wizard.py
    │   ├── state.py
    │   ├── core/                      ← 核心逻辑（无 GUI）
    │   │   ├── manifest.py
    │   │   ├── mirror.py
    │   │   ├── downloader.py
    │   │   ├── python_env.py
    │   │   ├── pip_installer.py
    │   │   ├── pyinstaller_builder.py
    │   │   ├── source_deployer.py
    │   │   ├── uninstall.py
    │   │   ├── upgrade.py
    │   │   ├── upgrade_engine.py
    │   │   ├── shortcut.py
    │   │   └── cleanup.py
    │   ├── pages/                     ← 向导页
    │   │   ├── base.py
    │   │   ├── welcome.py
    │   │   ├── choose_dir.py
    │   │   ├── options.py
    │   │   ├── progress.py
    │   │   └── finish.py
    │   └── i18n/
    │       ├── zh_CN.json
    │       └── en_US.json
    │
    ├── tools/                         ← 独立小工具
    │   ├── uninstall_stub.py
    │   ├── upgrade_stub.py
    │   ├── build_stubs.py
    │   └── _out/                      ← 产物（构建后自动清理）
    │
    └── resources/
        └── icon.ico
```

### 3.3 主程序开发

#### 从源码运行

```powershell
cd MaaAutoProject
pip install -r requirements.txt
python main.py
```

#### 打包

```powershell
python build.py
# 产物：dist/MaaAuto/
```

#### 发布（生成 Source.zip）

```powershell
python publish.py
# 产物：
#   release/MaaAuto_Source.zip                    ← 升级器需要
#   release/MaaAuto_Online_vX.X.X-Windows-x64.zip ← 备用交付包
```

**`MaaAuto_Source.zip` 目录结构**：

```
main.py
app_info.py
requirements.txt
build.py
publish.py
ui/
themes/
i18n/
resources/
...
```

> ⚠️ 顶层直接是源码根，**不含 `MaaAutoProject/` 这一层**。
> 升级器读取 `requirements.txt` 时依赖此约定。

#### 主程序配置

配置文件位置：`<install>/config/config.json`

| 项 | 默认 | 说明 |
|---|---|---|
| `language` | `zh_CN` | 界面语言 |
| `theme` | `system` | 主题（system / light / dark） |
| `auto_check_update` | `true` | 启动后自动检查更新 |
| `auto_download_update` | `false` | 检测到新版后自动下载并升级 |

### 3.4 安装器构建

```powershell
cd MaaAuto-Installer/MaaAutoInstaller
python build_installer.py
```

#### 构建流程

1. 打包 `MaaAutoProject/` 为 `_embedded/source.zip`（排除 `__pycache__` / `build` / `dist` / `config` / `logs`）
2. 打包 `tools/uninstall_stub.py` → `tools/_out/uninstall.exe`（约 7 MB）
3. 打包 `tools/upgrade_stub.py` → `tools/_out/upgrade.exe`（约 43 MB，含 PySide6）
4. 打包 `installer/` → `dist/MaaAuto_Setup.exe`（**onefile**，内嵌上面 3 个资源 + `resources/`）
5. 重命名为最终产物 + **清理所有中间产物**

#### 产物

```
dist/MaaAuto_Online_vX.X.X-Windows-x64.exe      ← 单文件，约 95 MB
```

#### 参数

| 参数 | 说明 |
|---|---|
| `--debug` | 保留控制台（自动等于 `--keep-build`） |
| `--no-stub-rebuild` | 复用已有 stubs（加快迭代） |
| `--keep-build` | 不清理中间产物（用于调试） |
| `--source-dir PATH` | 指定主程序源码路径（默认自动探测） |

#### 源码路径自动探测顺序

1. `<ROOT>/../../MaaAuto-Tool-works/MaaAutoProject`
2. `<ROOT>/../MaaAuto-Tool-works/MaaAutoProject`
3. `<ROOT>/../MaaAutoProject`
4. `<ROOT>/MaaAutoProject`

找到含 `app_info.py` 的目录即采用。

#### 单独更新 stub

改完 `tools/uninstall_stub.py` 或 `tools/upgrade_stub.py` 后：

```powershell
# 全量：重打两个 stub + 重打安装器
python build_installer.py

# 只重打 upgrade stub + 复用另一个 stub
python tools\build_stubs.py --only upgrade
python build_installer.py --no-stub-rebuild
```

#### 手动清理

```powershell
# 正常构建会自动清理
Remove-Item -Recurse -Force build, dist, _embedded, tools\_out -ErrorAction SilentlyContinue
Remove-Item -Force MaaAuto_Setup.spec, _installer_version_info.txt -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

### 3.5 发布流程

**两个独立仓库，需协同发布**：

#### 步骤 1：主程序侧

```powershell
cd MaaAutoProject

# 1. 修改 app_info.py 里的 APP_VERSION
#    例如从 2.0.1 → 2.0.2

# 2. 打包 + 生成发布资源
python publish.py
# 产物：
#   release/MaaAuto_Source.zip                    ← 升级器需要
#   release/MaaAuto_Online_v2.0.2-Windows-x64.zip ← （若无安装器 exe 时备用）
```

#### 步骤 2：安装器侧

```powershell
cd MaaAuto-Installer/MaaAutoInstaller

# 1. 确认 ../MaaAutoProject/app_info.py 的版本已更新
# 2. 全量构建
python build_installer.py
# 产物：
#   dist/MaaAuto_Online_v2.0.2-Windows-x64.exe    ← 最终交付
```

#### 步骤 3：上传 GitHub Release

到 [Releases](https://github.com/mmccz/MaaAuto-Tool-works/releases/new)：

- **Tag**：`v2.0.2`（**必须** PEP 440 格式，不能是 `v2.0.2-beta`）
- **Asset 1**：`MaaAuto_Online_v2.0.2-Windows-x64.exe` ← 安装器（普通用户下载）
- **Asset 2**：`MaaAuto_Source.zip` ← 源码包（升级器自动下载）

> ⚠️ **两个 asset 缺一不可**：
> - 普通用户从 `MaaAuto_Online_*.exe` 安装
> - 已装用户通过 `upgrade.exe` 从 `MaaAuto_Source.zip` 升级

**Tag 格式（PEP 440）**：

| Tag | 是否合法 |
|---|---|
| `v2.0.2` | ✅ |
| `2.0.2` | ✅ |
| `v2.0.2b1` | ✅（beta 1） |
| `v2.0.2rc1` | ✅（release candidate 1） |
| `v2.0.2-beta` | ❌ 连字符会被拒绝 |
| `2.0.2-beta.1` | ❌ 同上 |

---

## 四、架构与设计

### 4.1 工作流程

```
┌────────────────────────────────────────────────────────────┐
│ 开发者本地                                                  │
│                                                            │
│  MaaAutoProject/  ──publish.py──>  MaaAuto_Source.zip      │
│         │                                                  │
│         └─build.py─> dist/MaaAuto/（PyInstaller onedir）   │
│                                                            │
│  MaaAutoInstaller/  ──build_installer.py──>  单文件 exe    │
│         ↑                                                  │
│         └── 内嵌 MaaAuto_Source.zip + 2 stubs               │
└────────────────────────────────────────────────────────────┘
                      ↓ 上传 GitHub Release
┌────────────────────────────────────────────────────────────┐
│ 用户端                                                      │
│                                                            │
│  双击 MaaAuto_Online_*.exe → 安装向导                       │
│    1. 下载 embeddable Python                                │
│    2. 解压内嵌 source.zip                                    │
│    3. pip install 依赖 + PyInstaller                        │
│    4. 本地重打包主程序                                       │
│    5. 部署到 <install>                                       │
│    6. 写 .maaauto.json（供升级器读）                         │
│    7. 清理临时目录                                           │
│                                                            │
│  启动主程序                                                  │
│    ├─ 检查更新（GitHub API）                                 │
│    ├─ 发现新版 → 调 upgrade.exe                              │
│    └─ upgrade.exe → 完整重跑安装流程 → 覆盖 → 重启            │
└────────────────────────────────────────────────────────────┘
```

### 4.2 关键设计决策

| 决策 | 原因 |
|---|---|
| **不在安装包内预置 PyInstaller 产物** | 否则安装包会膨胀到 250 MB+ |
| **用户端本地打包** | 安装包仅 ~95 MB，便于分发 |
| **下载 embeddable Python** | 用户机器无需预装 Python |
| **不保留 Python 环境** | 安装目录保持干净（~200 MB） |
| **单文件 exe + 内嵌 3 资源** | 用户不会因"文件缺失"而失败 |
| **VBS 后端卸载** | 避免 bat 的编码/管道坑，`wscript.exe` 从 XP 起就有 |
| **4 级兜底删除** | rmtree → 重试 → cmd rmdir → VBS 延迟删除 |
| **镜像源自动选择** | 中文系统 → 清华/阿里云；其他 → 官方 PyPI |
| **`core/` 无 GUI 依赖** | 升级器直接复用升级引擎 |
| **深浅色主题跟随系统** | 读注册表 `AppsUseLightTheme` |
| **升级 = 完整重跑安装** | 简单、可靠、不会因残留导致奇怪问题 |

### 4.3 元数据契约

**`.maaauto.json`**（安装根目录）是安装器 / 升级器 / 主程序之间的**唯一契约文件**。

`MANIFEST_VERSION = 3`。

```json
{
  "version": "2.0.2",
  "installer_version": "1.0.0",
  "manifest_version": 3,
  "install_dir": "D:\\MaaAuto",
  "app_exe": "D:\\MaaAuto\\MaaAuto.exe",
  "uninstall_exe": "D:\\MaaAuto\\uninstall.exe",
  "upgrade_exe": "D:\\MaaAuto\\upgrade.exe",
  "requirements_hash": "a3f2b1c4d5e6f7...",
  "mirror": "auto",
  "installed_at": "2026-09-19T15:30:00",
  "updated_at": "2026-09-19T15:30:00",
  "release_channel": "stable",
  "last_checked_at": "",
  "last_upgrade_from": "",
  "source_hash": "",
  "extra": {
    "github_url": "https://github.com/mmccz/MaaAuto-Tool-works",
    "update_api": "https://api.github.com/repos/mmccz/MaaAuto-Tool-works/releases/latest",
    "release_channel": "stable",
    "launch_args": [],
    "source_asset_name": "MaaAuto_Source.zip",
    "online_asset_pattern": "MaaAuto_Online_*-Windows-x64.exe",
    "min_installer_version": "1.0.0"
  }
}
```

| 字段 | 用途 |
|---|---|
| `version` | 主程序版本 |
| `manifest_version` | 契约版本（当前 = 3） |
| `requirements_hash` | 依赖清单 sha256，升级时判断依赖是否变化 |
| `mirror` | 记录用户选择的镜像源 |
| `installed_at` / `updated_at` | 安装时间 |
| `release_channel` | 更新通道（stable / beta） |
| `last_checked_at` | 上次检查更新时间 |
| `last_upgrade_from` | 上次升级前版本 |
| `source_hash` | 当前版本对应的源包 sha256 |
| `extra.*` | 升级相关配置（GitHub URL、asset 命名约定等） |

**主程序侧不读写此文件**，只由安装器 / 升级器维护。

### 4.4 升级机制

`upgrade.exe` 是**独立进程**，由主程序调起（必须带 `--from-main`）。

#### 命令行参数

| 参数 | 行为 |
|---|---|
| `--from-main` | 必须（防用户直接双击） |
| `--silent` | 有 UI 但不可交互（无取消、不可关） |
| `--check-only` | 交互模式下弹完整 UI + 一键升级；`--silent` 时纯静默 |
| `--restart` | 升级成功后自动重启主程序 |
| `--downgrade` | 允许降级 |
| `--channel` | stable / beta |

#### 退出码

- `0` 成功 / 有新版
- `1` 已是最新
- `2` 错误

#### 升级流程

```
1. 读 <install>/.maaauto.json → 拿当前版本 + extra 配置
2. 请求 GitHub Release API → 拿最新 tag
3. 版本比较（PEP 440）：
   - 非法版本号 → 判"无法比较" → 不升级
   - 无新版 → 退出码 1
4. 下载 MaaAuto_Source.zip + 校验 sha256
5. 停止主程序：
   a. 写 <install>/config/.upgrading 标志文件
   b. 等 5 秒（主程序轮询该文件并优雅退出）
   c. 未退出 → taskkill /F
6. 备份现有安装（zip 到 %TEMP%，可回滚）
7. 完整重跑安装流程（下载 Python + 依赖 + 打包）
8. 覆盖安装目录（保护 config/ logs/ .maaauto.json）
9. 更新 .maaauto.json（version / last_upgrade_from / source_hash）
10. 清理临时目录 + 备份
11. 重启主程序（读 config/last_launch_args.json 恢复启动参数）

失败 → 从备份回滚 → 写 config/upgrade_failed.flag → 下次启动主程序时提示
```

#### 主程序侧职责

- ✅ 检查是否有新版本（调用 GitHub API）
- ✅ 展示更新提示
- ✅ 调起 `upgrade.exe`
- ✅ 优雅退出以让升级器接管
- ❌ **不做**下载 / 替换 / 打包

#### 用户看到的流程

```
主程序启动
   ↓
5 秒后自动检查更新（若 auto_check_update）
   ↓
有新版？
   ├─ 是 + 用户开自动更新
   │    ├─ 任务运行中 → 挂起，任务结束后触发
   │    └─ 空闲 → 静默触发 upgrade.exe → 主程序退出 → 弹升级窗口 → 完成 → 重启
   └─ 是 + 用户未开自动更新
        └─ 关于页提示"发现新版本"
             ↓
           用户点"检查更新" → 弹升级器 UI → 用户点"立即升级"
```

#### 关键文件

| 文件 | 作用 |
|---|---|
| `<install>/config/.upgrading` | 升级中标志（升级器写、主程序读并退出） |
| `<install>/config/upgrade_failed.flag` | 升级失败标志（升级器写、主程序读并提示） |
| `<install>/config/last_launch_args.json` | 上次启动参数（用于升级后恢复启动） |
| `<install>/logs/upgrading.log` | `--upgrading` 退出日志 |
| `<install>/logs/upgrade/*.log` | 升级器日志副本 |

#### 升级契约（2026-09 冻结）

1. **`MaaAuto_Source.zip` 顶层直接是源码根**
   （`main.py` / `app_info.py` / `requirements.txt` / ...）
   **不含 `MaaAutoProject/` 这一层**

2. **`.maaauto.json` 是唯一契约文件**（`MANIFEST_VERSION = 3`）
   主程序只读不写，安装器 / 升级器读写

3. **`upgrade.exe` 必须由主程序调起**（参数 `--from-main`）
   用户直接双击会被拒绝

4. **`<install>/config/` 和 `<install>/logs/` 是用户数据**
   升级时**必须保留**

5. **`<install>/config/.upgrading`** 是"升级中"标志
   升级器写、主程序读并退出

6. **`<install>/config/upgrade_failed.flag`** 是升级失败标志
   升级器写、主程序读并提示

---

## 五、模块参考

### 5.1 主程序模块

| 文件 | 职责 |
|---|---|
| `main.py` | 入口（含 `--upgrading` 处理） |
| `app_info.py` | 版本号 + 升级常量 |
| `config_manager.py` | 配置读写（`config/config.json`） |
| `update_checker.py` | 更新检查 + `apply_update` |
| `process_utils.py` | 进程检测 / 清理 |
| `automation.py` | 自动化流程 |
| `notifier.py` | 通知推送（Server 酱） |
| `build.py` | PyInstaller 打包脚本 |
| `publish.py` | 发布脚本（生成 `Source.zip`） |
| `ui/main_window.py` | 主窗口（含 `.upgrading` 轮询） |
| `ui/home_page.py` | 首页 |
| `ui/settings_page.py` | 设置页 |
| `ui/about_page.py` | 关于页 |

### 5.2 安装器模块

**`installer/core/` 各模块职责**：

| 模块 | 职责 |
|---|---|
| `manifest.py` | 读写 `.maaauto.json`（v3，兼容 v1/v2） |
| `mirror.py` | PyPI / Python 镜像源解析（自动检测中文系统） |
| `downloader.py` | 通用 HTTP 下载（带进度回调） |
| `python_env.py` | 下载解压 embeddable Python + 修改 `._pth` |
| `pip_installer.py` | 安装 pip + 升级到最新 + 装依赖/PyInstaller |
| `pyinstaller_builder.py` | 调 `build.py` 打包主程序 + 拷贝产物（保护用户数据） |
| `source_deployer.py` | 解压 `source.zip` |
| `uninstall.py` | 释放 `uninstall.exe` |
| `upgrade.py` | 释放 `upgrade.exe` |
| `upgrade_engine.py` | 升级引擎（版本比较、下载、备份、覆盖、回滚） |
| `shortcut.py` | 创建/删除桌面和开始菜单快捷方式（pywin32） |
| `cleanup.py` | 删工作目录、pip 缓存、系统临时文件（4 级兜底） |

**`installer/pages/` 向导页**：

| 页面 | 职责 |
|---|---|
| `welcome.py` | 欢迎 + 语言选择 |
| `choose_dir.py` | 选择安装目录（路径规范化） |
| `options.py` | 安装选项（镜像源 / 快捷方式） |
| `progress.py` | 进度 + 后台 `InstallWorker`（分阶段加权进度） |
| `finish.py` | 完成页 |

### 5.3 数据流

**安装流程**：

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

**升级流程**：

```
主程序 → apply_update() → subprocess → upgrade.exe
    ↓
tools/upgrade_stub.py（含 PySide6 进度 UI）
    ↓ 调用
installer/core/upgrade_engine.py（纯逻辑）
    ↓ 输出
日志信号 / 进度信号 → 升级窗口 UI
```

---

## 六、常见问题

### 6.1 用户侧

#### Q1：双击安装器后启动很慢

**原因**：PyInstaller onefile 需要把内嵌的 PySide6（~80 MB）解压到 `%TEMP%`。

**解决**：正常现象（3~8 秒），第二次启动会快一些。

#### Q2：pip 阶段很慢

**原因**：默认镜像源可能是官方 PyPI。

**解决**：安装向导第 3 步选"清华大学镜像"或"阿里云镜像"。

#### Q3：PyInstaller 打包阶段特别久

**正常现象**：打包 PySide6 项目耗时几分钟，CPU 占用高。

**解决**：耐心等待，不要关窗口。

#### Q4：主程序报 `ModuleNotFoundError`

**原因**：依赖没装全（`requirements.txt` 缺失某包）。

**解决**：

1. 检查安装目录下的 `requirements.txt` 是否完整
2. 重装，**不要**中断 pip 阶段
3. 若是升级后出错，检查 `<install>/config/upgrade_failed.flag` 和 `%TEMP%\MaaAuto_upgrade_*.log`

#### Q5：卸载程序双击无反应

**原因**：可能被杀毒软件拦截，或 VBS 执行失败。

**解决**：

1. 检查 `%TEMP%\MaaAuto_uninstall_*.vbs` 是否生成
2. 手动执行 `wscript <vbs路径>` 看是否报错
3. 若无法自动卸载，手动删除安装目录

#### Q6：升级失败后主程序打不开

**原因**：升级失败但回滚也失败了。

**解决**：

1. 看 `<install>/config/upgrade_failed.flag` 里的 `log_path` 指向的日志
2. 手动下载最新完整安装包，覆盖安装到同一目录

#### Q7：升级时提示"无法停止主程序"

**原因**：主程序在升级信号发出后 5 秒内未退出（可能卡在某个任务）。

**解决**：

1. 手动关闭主程序
2. 重新触发升级

#### Q8：为什么安装包只有 ~95 MB，主程序却有 ~200 MB？

**原因**：安装包内**不预置**主程序产物，用户端本地下载依赖 + PyInstaller 打包。

**好处**：分发小。
**缺点**：首次安装需联网 + 耗时几分钟。

#### Q9：升级为什么这么慢？

**原因**：升级 = **完整重跑一次安装流程**（重新下载 Python + 依赖 + 打包）。

**设计取舍**：牺牲速度换取可靠性——没有"增量"带来的残留风险。

#### Q10：主程序运行时能升级吗？

**答**：

- **手动升级**：主程序会提示用户关闭并升级
- **自动升级**：若用户开启"自动更新"，主程序会在当前**任务结束后**再触发升级，避免打断自动化流程

### 6.2 开发者侧

#### Q11：`build_installer.py` 报 `UnboundLocalError: 'count'`

**解决**：检查 `build_source_zip()` 函数体开头有没有 `count = 0`。

#### Q12：主程序 `build.py` 报 `UnicodeEncodeError: 'gbk' codec`

**原因**：`build.py` 里有 emoji print（如 `print("打包成功 ✅")`），GBK 控制台编不出来。

**解决**：把 emoji 换成 ASCII（如 `[OK]`）。

#### Q13：`pip install` 报 `UnicodeDecodeError: 'gbk' codec`

**原因**：`requirements.txt` 含中文注释，pip 用系统编码读取。

**解决**：`pip_installer._sanitize_requirements()` 会自动剥离非 ASCII 字符后重写，**无需手动处理**。

#### Q14：安装后 `upgrade.exe` 大小是 7 MB 而不是 43 MB

**原因**：`tools/_out/upgrade.exe` 是旧版（占位版）。

**解决**：

```powershell
# 强制重打 stub
python tools\build_stubs.py --only upgrade
# 检查产物大小
Get-Item tools\_out\upgrade.exe | Select Length
# 期望：约 45140355 字节（43 MB）

# 再全量构建
python build_installer.py
```

#### Q15：想改 `source.zip` 里包含什么

**解决**：编辑 `build_installer.py`：

```python
SOURCE_EXCLUDE_DIRS = {
    "__pycache__", ".git", "build", "dist",
    "config", "logs", "venv", ".venv",
    # 加你想排除的
}
SOURCE_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".log", ".spec")
```

#### Q16：想改 `uninstall.exe` / `upgrade.exe` 的行为

**解决**：编辑 `tools/uninstall_stub.py` 或 `tools/upgrade_stub.py`，改完跑：

```powershell
python tools\build_stubs.py
python build_installer.py
```

#### Q17：`upgrade.exe --from-main --check-only --silent` 退出码不可靠

**原因**：`--windowed` 打包的 exe 在 PowerShell 里 `$LASTEXITCODE` 经常拿到 0（不等待）。

**解决**：用 `Start-Process -Wait -PassThru`：

```powershell
$p = Start-Process -FilePath ".\upgrade.exe" `
    -ArgumentList "--from-main","--check-only","--silent" `
    -Wait -PassThru
"真实退出码: $($p.ExitCode)"
```

#### Q18：升级日志在哪

| 类型 | 位置 |
|---|---|
| 升级器主日志 | `%TEMP%\MaaAuto_upgrade_*.log` |
| 升级成功后备份 | `<install>/logs/upgrade/upgrade_*.log` |
| 主程序 `--upgrading` 退出日志 | `<install>/logs/upgrading.log` |
| 升级失败标记 | `<install>/config/upgrade_failed.flag` |

#### Q19：升级时备份文件残留

**原因**：通常是被占用未删除（本次构建已加双保险：`engine finally` + `stub 成功后`）。

**解决**：

```powershell
Remove-Item $env:TEMP\MaaAuto_backup_*.zip -Force -ErrorAction SilentlyContinue
```

#### Q20：`upgrade.exe` 完成后窗口不关

**原因**：已在最新版修复（成功后 2~2.5 秒自动关闭）。

**解决**：确保使用最新版 `upgrade.exe`（大小 ~43 MB，SHA256 `34540C12...`）。

---

## 七、版本号约定

本项目有**两个独立版本号**：

| 版本号 | 位置 | 含义 |
|---|---|---|
| **主程序版本** | `MaaAutoProject/app_info.py` → `APP_VERSION` | 用户最终运行的软件版本 |
| **安装器版本** | `MaaAuto-Installer/MaaAutoInstaller/VERSION` | 安装器工具本身的版本 |

**规则**：

- 改主程序 → `APP_VERSION` +1，`VERSION` **不变**
- 改安装器逻辑 → `VERSION` +1，`APP_VERSION` **不变**
- 两个都改 → 都 +1

**文件名**：使用**主程序版本号**（因为用户关心的是装完得到什么版本）：

```
MaaAuto_Online_v{APP_VERSION}-Windows-x64.exe
```

**Tag 格式（PEP 440）**：

| Tag | 是否合法 |
|---|---|
| `v2.0.2` | ✅ |
| `2.0.2` | ✅ |
| `v2.0.2b1` | ✅ |
| `v2.0.2rc1` | ✅ |
| `v2.0.2-beta` | ❌ |
| `2.0.2-beta.1` | ❌ |

---

## 八、许可证与联系

### 许可证

[MIT License](LICENSE) © 2024-2026 MaaAuto

### 联系

- **GitHub**：https://github.com/mmccz/MaaAuto-Tool-works
- **Issues**：https://github.com/mmccz/MaaAuto-Tool-works/issues
- **邮箱**：Frank010700@outlook.com

---

<p align="center">
  <sub>MaaAuto Tool Works · Made with ❤️ by MaaAuto Team</sub>
</p>