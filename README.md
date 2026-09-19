# MaaAuto 完整项目文档

> 基于 PySide6 的 Windows 桌面自动化调度工具，用于管理 **MAA**（明日方舟）与 **MaaEnd**（终末地）。

![Python](https://img.shields.io/badge/Python-3.11-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6+-green)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📑 目录

- [一、项目简介](#一项目简介)
- [二、项目结构](#二项目结构)
- [三、用户指南](#三用户指南)
- [四、开发者指南](#四开发者指南)
- [五、架构说明](#五架构说明)
- [六、常见问题](#六常见问题)
- [七、版本历史](#七版本历史)
- [八、许可证与联系](#八许可证与联系)

---

## 一、项目简介

### 1.1 是什么

MaaAuto 是一个为 MAA / MaaEnd 提供 **自动化调度** 的 Windows 桌面工具。

### 1.2 核心功能

| 功能 | 说明 |
|---|---|
| 🕐 **定时启动** | 到点自动开始任务，跑完自动关闭 |
| 🖱️ **图像识别** | 自动点击"Link Start!"等按钮，无需人工干预 |
| 📊 **状态监控** | 等待模拟器/游戏启动、等待退出，全程可视化 |
| 📬 **推送通知** | 任务完成后通过 Server酱 / Webhook 推送结果 |
| 🎨 **主题美化** | 深浅主题、背景图片、强调色自定义 |
| 🌐 **多语言** | 简体中文 / English |
| 📦 **轻量安装** | 安装包仅 ~45 MB，用户本地构建主程序 |

### 1.3 核心设计理念

传统方案把主程序（PyInstaller 打包后约 300 MB）直接塞进安装包，导致：
- ❌ 下载慢
- ❌ 每次更新都要重新下载 300 MB
- ❌ GitHub Release 上传慢

**MaaAuto 的方案**：
- ✅ 安装器本体只 **45 MB**（含 Qt 运行时 + 卸载/升级工具）
- ✅ 用户端 **本地下载 Python + 依赖 + PyInstaller 打包**
- ✅ 首次安装耗时 6~20 分钟，但之后只有源码更新（~100 KB）

---

## 二、项目结构

### 2.1 仓库总结构

```
MaaAuto-Tool-works/
├── MaaAutoProject/         ← 主程序源码（用户最终运行的软件）
├── MaaAutoInstaller/       ← 安装器项目（用户下载后用来安装主程序）
├── image/                  ← README 截图
│   └── README/
│       ├── main.png
│       ├── settings.png
│       └── about.png
├── requirements.txt        ← 主程序依赖清单
├── CHANGELOG.md            ← 更新日志
├── LICENSE                 ← MIT 许可证
├── README.md               ← 本文件
└── .gitignore
```

### 2.2 `MaaAutoProject/` —— 主程序

```
MaaAutoProject/
├── main.py                 # 入口：DPI / QApplication / i18n / 主题 / 主窗口
├── app_info.py             # 应用元信息（版本、作者、GitHub）
├── config_manager.py       # 配置读写 + 日志系统
├── automation.py           # 自动化流程（MAA / MaaEnd 阶段）
├── process_utils.py        # 进程检测、窗口控制、中断响应
├── notifier.py             # Server酱 / Webhook 推送
├── utils.py                # 通用工具
├── serverchan_sdk.py       # Server酱 SDK
├── build.py                # 打包脚本
├── requirements.txt        # 依赖清单
│
├── i18n/                   # 语言包
│   ├── __init__.py
│   ├── zh_CN.json
│   └── en_US.json
│
├── themes/                 # 主题 QSS
│   ├── __init__.py
│   ├── light.qss
│   └── dark.qss
│
├── resources/              # 图标 / 图像识别素材
│   ├── icon.ico
│   ├── maa_start.png
│   └── maaend_start.png
│
└── ui/                     # 界面层
    ├── __init__.py
    ├── main_window.py      # 主窗口 + Worker(QThread)
    ├── sidebar.py          # 侧边导航
    ├── components.py       # 通用组件（Card/Switch/SegmentedControl/AccentColorPicker）
    ├── background.py       # 背景图（透明度/模糊/4 种缩放模式）
    ├── animations.py       # 动画（fade_in / theme_transition）
    ├── sliding_stack.py    # 页面滑动容器
    ├── wheel_time_picker.py# 滚轮时间选择器
    ├── no_wheel.py         # 无滚轮控件（避免误触）
    ├── update_checker.py   # 更新检测
    └── pages/
        ├── __init__.py
        ├── home_page.py    # 首页（状态卡 + 立即执行/结束 + 日志）
        ├── settings_page.py# 设置页（单页滚动 + chips 跳转）
        ├── about_page.py   # 关于页（版本 + 打开目录 + 导出日志 + 检查更新）
        └── process_picker.py# 进程选择对话框
```

### 2.3 `MaaAutoInstaller/` —— 安装器

```
MaaAutoInstaller/
├── build_installer.py      # 一键构建脚本
├── VERSION                 # 安装器版本号
├── requirements.txt        # 安装器依赖（PySide6 + pywin32）
├── README.md               # 安装器子项目说明
│
├── installer/              # 安装器源码
│   ├── __init__.py
│   ├── __main__.py         # PyInstaller 入口
│   ├── app.py              # QApplication 启动
│   ├── wizard.py           # 向导窗口
│   ├── state.py            # 安装状态
│   │
│   ├── core/               # 核心逻辑（无 GUI 依赖，可复用）
│   │   ├── __init__.py
│   │   ├── manifest.py     # .maaauto.json 读写
│   │   ├── mirror.py       # 镜像源选择
│   │   ├── downloader.py   # urllib 下载工具
│   │   ├── python_env.py   # embeddable Python 部署
│   │   ├── pip_installer.py# pip 安装 + 升级
│   │   ├── pyinstaller_builder.py # 本地打包主程序
│   │   ├── source_deployer.py     # 源码解压
│   │   ├── uninstall.py    # 卸载器部署
│   │   ├── upgrade.py      # 升级器部署
│   │   ├── shortcut.py     # 快捷方式创建（pywin32）
│   │   └── cleanup.py      # 临时文件清理
│   │
│   ├── pages/              # 向导页
│   │   ├── __init__.py
│   │   ├── base.py         # 页基类
│   │   ├── welcome.py      # 欢迎 + 语言选择
│   │   ├── choose_dir.py   # 选择安装目录
│   │   ├── options.py      # 安装选项
│   │   ├── progress.py     # 安装进度 + 后台 Worker
│   │   └── finish.py       # 完成
│   │
│   └── i18n/               # 语言包
│       ├── __init__.py
│       ├── zh_CN.json
│       └── en_US.json
│
├── tools/                  # 独立的小工具
│   ├── uninstall_stub.py   # 卸载器源码（VBS 后端）
│   ├── upgrade_stub.py     # 升级器源码（占位）
│   ├── build_stubs.py      # 把上面两个打包成 exe
│   └── _out/               # 产物
│       ├── uninstall.exe
│       └── upgrade.exe
│
└── resources/
    └── icon.ico
```

---

## 三、用户指南

### 3.1 系统要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10 / 11（64 位） |
| 磁盘空间 | 约 1 GB（安装过程中峰值 ~1.5 GB） |
| 网络 | 需要联网（首次安装需下载约 200 MB 依赖） |
| CPU / 内存 | 无特殊要求，打包阶段建议 4 核 + 8 GB |
| 管理员权限 | **不需要** |

### 3.2 安装步骤

#### Step 1 · 下载

从 [GitHub Releases](https://github.com/mmccz/MaaAuto-Tool-works/releases) 下载最新的 `MaaAuto_vX.X.X.zip`。

#### Step 2 · 解压

解压到任意目录，**保持三个文件在同一文件夹**：

```
MaaAuto_Setup.exe      ← 安装器（~45 MB）
MaaAuto_Source.zip     ← 主程序源码（~100 KB）
README.txt             ← 使用说明
```

> ⚠️ 不要单独移动 `MaaAuto_Setup.exe`，它需要读取同级的 `MaaAuto_Source.zip`。

#### Step 3 · 运行安装器

双击 `MaaAuto_Setup.exe`，按向导操作：

1. **欢迎页** —— 选语言（简中 / 英文）
2. **选择目录** —— 默认 `D:\MaaAuto`（推荐非系统盘，路径不含中文）
3. **安装选项** —— 选镜像源、是否创建快捷方式
4. **进度页** —— 自动执行：
   - 下载 embeddable Python 3.11.9（~10 MB）
   - 解压源码
   - 安装 pip
   - 安装依赖（~200 MB，3~10 分钟）
   - 安装 PyInstaller
   - **本地打包主程序**（2~5 分钟）
   - 释放卸载/升级工具
   - 创建快捷方式
5. **完成页** —— 打开目录 / 立即启动

整个流程约 **6~20 分钟**，取决于网速和 CPU。

#### Step 4 · 启动

从桌面快捷方式启动 MaaAuto。

### 3.3 安装后目录结构

```
D:\MaaAuto\
├── MaaAuto.exe             ← 主程序
├── _internal/              ← PyInstaller 运行时依赖
├── resources/              ← 图标 / 图像识别素材
├── themes/                 ← 主题 QSS
├── i18n/                   ← 语言包
├── requirements.txt        ← 依赖清单（供参考）
├── README.md
├── LICENSE
├── CHANGELOG.md
├── _version_info.txt       ← 版本信息
├── uninstall.exe           ← 卸载程序（~3 MB）
├── upgrade.exe             ← 升级程序（占位）
├── .maaauto.json           ← 安装元数据
├── config/                 ← 用户配置（首次启动生成）
│   └── config.json
└── logs/                   ← 运行日志（首次启动生成）
    └── 2026/09/19/run_N_xxx/task.log
```

### 3.4 卸载

双击 `D:\MaaAuto\uninstall.exe`：

1. 确认卸载 → 点"是"
2. 是否保留 `config/` 和 `logs/` → 推荐"否"
3. 弹窗提示后，几秒内目录被清理

**如果卸载失败**：
- 检查 `%TEMP%\MaaAuto_uninstall_*.vbs` 是否生成
- 手动执行 `wscript <vbs路径>` 看报错
- 实在不行手动删除安装目录

### 3.5 升级

> 🚧 升级功能开发中，当前 `upgrade.exe` 会弹提示引导手动升级。

**当前手动升级方式**：下载新版安装包，安装到**同一目录**（覆盖旧文件）。

### 3.6 界面说明

#### 首页
- 4 张状态卡片：当前状态 / 上次运行 / 下次运行 / 运行次数
- 立即执行 / 结束任务 按钮
- 实时日志（带颜色高亮：ERROR 红、WARNING 黄、成功绿、分隔线蓝）

#### 设置页
分为 6 个分组（顶部 chips 可快速跳转）：

| 分组 | 内容 |
|---|---|
| **路径设置** | MAA / MaaEnd 启动器路径 |
| **进程与超时** | 模拟器进程名、游戏进程名、各种超时、重试次数/间隔 |
| **前台处理** | 三选一：不处理 / 关闭所有前台 / 按黑名单关闭 |
| **定时与推送** | 定时开关、执行时间、系统通知、Server酱 / Webhook |
| **外观** | 主题（浅色/深色/跟随系统）、强调色、语言、背景图 |
| **常规** | 开机自启、最小化到托盘、退出时清理进程 |

#### 关于页
- 版本号 / 许可证 / GitHub / 邮箱
- Python / PySide6 / Qt / 系统 版本信息
- 打开配置目录 / 打开日志目录 / 导出日志（zip）
- **检查更新**（手动触发）

### 3.7 配置文件

配置保存在 `<安装目录>/config/config.json`。

| 字段 | 说明 | 默认值 |
|---|---|---|
| `maa_path` | MAA 启动器路径 | `""` |
| `maaend_path` | MaaEnd 启动器路径 | `""` |
| `emulator_proc` | 模拟器进程名 | `"MuMuPlayer.exe"` |
| `pc_game_proc` | PC 游戏进程名 | `"Endfield.exe"` |
| `execute_time` | 定时执行时间 | `"08:00"` |
| `enable_schedule` | 启用定时 | `false` |
| `wait_timeout` | 找图超时（秒） | `60` |
| `game_start_timeout` | 游戏启动超时（秒） | `120` |
| `game_exit_timeout` | 游戏退出超时（秒） | `7200` |
| `retry_times` | 重试次数 | `3` |
| `retry_interval` | 重试间隔（秒） | `30` |
| `foreground_action` | 前台处理策略 | `none` / `kill_all` / `blacklist` |
| `blacklist_apps` | 黑名单进程（逗号分隔） | `""` |
| `enable_system_notify` | 系统托盘通知 | `true` |
| `serverchan_key` | Server酱 SendKey | `""` |
| `webhook_url` | Webhook URL | `""` |
| `theme` | 主题 | `system` / `light` / `dark` |
| `accent_color` | 强调色（hex） | `"#3b82f6"` |
| `language` | 语言 | `zh_CN` / `en_US` |
| `background_image` | 背景图路径 | `""` |
| `background_opacity` | 背景透明度 | `0.3` |
| `background_blur` | 背景模糊度 | `0` |
| `background_mode` | 缩放模式 | `cover` / `contain` / `stretch` / `tile` |
| `show_animation` | 页面切换动画 | `true` |
| `auto_check_update` | 启动时检查更新 | `true` |
| `auto_start` | 开机自启 | `false` |
| `minimize_to_tray` | 最小化到托盘 | `true` |
| `kill_on_exit` | 退出时清理残留进程 | `true` |

---

## 四、开发者指南

### 4.1 环境准备

#### 要求
- Windows 10 / 11
- **Python 3.11.9**（推荐 3.11.x）
- Git
- （可选）VS Code

#### 首次准备

```powershell
# 1. 克隆仓库
git clone https://github.com/mmccz/MaaAuto-Tool-works.git
cd MaaAuto-Tool-works

# 2. 安装主程序依赖
pip install -r requirements.txt

# 3. 安装开发工具
pip install pyinstaller

# 4. 直接运行主程序（开发模式）
cd MaaAutoProject
python main.py
```

### 4.2 本地运行主程序

```powershell
cd MaaAutoProject
python main.py
```

或带控制台输出（方便看崩溃）：

```powershell
pythonw main.py 2> error.log  # 无控制台
python main.py                # 有控制台
```

### 4.3 打包主程序

```powershell
cd MaaAutoProject
python build.py
```

**产物**：
```
MaaAutoProject/dist/MaaAuto/
├── MaaAuto.exe
├── _internal/
├── resources/
├── themes/
├── i18n/
├── requirements.txt
├── README.md
├── LICENSE
├── CHANGELOG.md
└── _version_info.txt
```

**参数**：

| 参数 | 说明 |
|---|---|
| `--debug` | 保留控制台窗口，方便调试 |
| `--onefile` | 单文件模式（启动慢，不推荐） |
| `--keep-build` | 不清理 `build/` 和 `dist/` |
| `--no-clean` | 跳过 `pyinstaller --clean`（增量构建更快） |
| `--no-version` | 不生成 exe 版本信息 |

### 4.4 构建安装器

```powershell
cd MaaAutoInstaller
python build_installer.py
```

**构建流程**：
1. 打包 `../MaaAutoProject/` 为 `_embedded/source.zip`（排除 `__pycache__` / `build` / `dist` / `config` / `logs`）
2. 打包 `tools/uninstall_stub.py` → `tools/_out/uninstall.exe`
3. 打包 `tools/upgrade_stub.py` → `tools/_out/upgrade.exe`
4. 打包 `installer/` → `dist/MaaAuto_Setup.exe`（**onefile**，内嵌两个 stubs）
5. 组合最终 zip：`dist/MaaAuto_vX.X.X.zip`

**产物**：
```
MaaAutoInstaller/dist/MaaAuto_vX.X.X.zip
├── MaaAuto_Setup.exe      ← 安装器（~45 MB）
├── MaaAuto_Source.zip     ← 主程序源码（~100 KB）
└── README.txt             ← 使用说明
```

**参数**：

| 参数 | 说明 |
|---|---|
| `--debug` | 安装器保留控制台；stubs 也保留 |
| `--no-stub-rebuild` | 复用已有 stubs（加快迭代） |
| `--keep-build` | 保留 `build/` `dist/` `_embedded/` 中间产物 |
| `--source-dir PATH` | 指定主程序源码路径（默认 `../MaaAutoProject`） |

### 4.5 发布流程

#### Step 1 · 改版本号

编辑 `MaaAutoProject/app_info.py`：

```python
APP_VERSION = "2.0.2"   # ← 改这里
```

#### Step 2 · 更新日志

在 `CHANGELOG.md` 顶部追加新版本条目。

#### Step 3 · 构建

```powershell
# 打包主程序（本地验证）
cd MaaAutoProject
python build.py

# 构建安装器
cd ..\MaaAutoInstaller
python build_installer.py
```

#### Step 4 · GitHub Release

1. 打开 `https://github.com/mmccz/MaaAuto-Tool-works/releases/new`
2. **Tag**：`v2.0.2`（**必须与 `APP_VERSION` 去掉 v 后一致**）
3. **Title**：`v2.0.2` 或 `MaaAuto v2.0.2`
4. **描述**：从 `CHANGELOG.md` 复制对应版本条目
5. **Attach**：拖入 `dist/MaaAuto_v2.0.2.zip`
6. 点 **Publish release**

#### Tag 与 APP_VERSION 对应关系

| GitHub Tag | APP_VERSION |
|---|---|
| `v2.0.0` | `2.0.0` ✅ |
| `2.0.0` | `2.0.0` ✅ |
| `v2.0.0-Beta1` | `2.0.0-Beta1` ✅ |

### 4.6 日常迭代

```powershell
# 1. 改 MaaAutoProject 源码

# 2. 本地测主程序
cd MaaAutoProject
python build.py
.\dist\MaaAuto\MaaAuto.exe

# 3. 构建安装器（复用 stubs 快速迭代）
cd ..\MaaAutoInstaller
python build_installer.py --no-stub-rebuild

# 4. 拿 dist\MaaAuto_vX.X.X.zip 端到端测试
```

### 4.7 单独更新 stub

改完 `tools/uninstall_stub.py` 或 `tools/upgrade_stub.py` 后：

```powershell
cd MaaAutoInstaller
python tools\build_stubs.py          # 重打两个 stub
python build_installer.py --no-stub-rebuild   # 安装器复用新 stub
```

### 4.8 清理临时文件

```powershell
cd MaaAutoInstaller

# 删构建产物
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Remove-Item -Force MaaAuto_Setup.spec -ErrorAction SilentlyContinue

# 清 __pycache__
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force

# 清 PyInstaller 临时目录
Remove-Item -Recurse -Force tools\_work_uninstall, tools\_work_upgrade -ErrorAction SilentlyContinue
```

---

## 五、架构说明

### 5.1 安装器工作流程

```
┌─────────────────────────────────────────────────────────┐
│ 开发者本地（一次性）：                                    │
│                                                          │
│  MaaAutoProject/                                         │
│    ↓ python build.py                                     │
│  dist/MaaAuto/  （完整的 PyInstaller onedir 产物）        │
│                                                          │
│  MaaAutoInstaller/                                       │
│    ↓ python build_installer.py                           │
│  dist/MaaAuto_vX.X.X.zip                                 │
│    ├── MaaAuto_Setup.exe     （45 MB，内嵌 2 stubs）     │
│    ├── MaaAuto_Source.zip    （100 KB，主程序源码）      │
│    └── README.txt                                        │
│                                                          │
│  上传到 GitHub Release                                    │
└─────────────────────────────────────────────────────────┘
                         ↓ 用户下载 ~45 MB
┌─────────────────────────────────────────────────────────┐
│ 用户端（双击 MaaAuto_Setup.exe）：                        │
│                                                          │
│  1. 选安装目录                                            │
│  2. 下载 embeddable Python 3.11.9（10 MB，走镜像）        │
│  3. 解压 source.zip 到临时目录                             │
│  4. 安装 pip → 升级到最新                                 │
│  5. pip install 主程序依赖（~200 MB，走镜像）              │
│  6. pip install pyinstaller                              │
│  7. 调 build.py，本地打包主程序                            │
│  8. 拷贝 dist/MaaAuto/ 到安装目录                          │
│  9. 释放 uninstall.exe / upgrade.exe                     │
│  10. 创建快捷方式                                          │
│  11. 写 .maaauto.json                                    │
│  12. 删除临时工作目录（含 Python 环境）                     │
└─────────────────────────────────────────────────────────┘
                         ↓
             D:\MaaAuto\（像图片那样）
```

### 5.2 关键设计决策

| 决策 | 原因 |
|---|---|
| **不在安装包内预置 PyInstaller 产物** | 否则安装包会膨胀到 300 MB+ |
| **用户端本地打包** | 安装包仅 45 MB，便于分发 |
| **下载 embeddable Python** | 用户机器无需预装 Python |
| **不保留 Python 环境** | 安装目录保持干净（约 200 MB） |
| **升级器复用安装流程** | `installer/core/` 模块完全解耦 GUI，升级器直接复用 |
| **VBS 后端卸载** | 避免 bat 的编码/管道坑，wscript.exe 从 XP 起就有 |
| **镜像源自动选择** | 中文系统 → 清华/阿里云；其他 → 官方 PyPI |

### 5.3 `.maaauto.json` 元数据

安装完成后在安装根目录生成，供未来升级器读取：

```json
{
  "version": "2.0.1",
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

**字段说明**：

| 字段 | 用途 |
|---|---|
| `version` | 主程序版本 |
| `requirements_hash` | 依赖清单 sha256，升级时判断依赖是否变化 |
| `mirror` | 记录用户选择的镜像源 |
| `installed_at` / `updated_at` | 安装时间，供展示和比较 |

### 5.4 更新机制（预留）

未来升级器 `upgrade.exe` 的计划流程：

```
1. 读 .maaauto.json → 拿到当前版本 + requirements_hash
2. 请求 GitHub Release API → 拿最新版本
3. 对比版本号：
   - 相同 → 提示"已是最新"
   - 更新 → 继续
4. 下载新版 MaaAuto_Source.zip
5. 比对 requirements_hash：
   - 变了 → 重新走完整安装流程（重建 Python + 依赖）
   - 没变 → 只覆盖源码，跳过依赖安装（快）
6. 更新 .maaauto.json
7. 重启主程序
```

**为什么现在不做**：先跑通首次安装，让基础稳固。

### 5.5 主题系统

主程序主题由 `MaaAutoProject/themes/` 管理：

- `light.qss` / `dark.qss` —— 使用 **占位符**（`{accent}` / `{accent_rgb}` / `{accent_hover}` 等）
- `ThemeManager.apply_theme()` —— 替换占位符后注入 QSS
- 强调色通过 **HSL 明暗微调** 自动派生（浅色/深色主题下自动适配）
- 用户切换强调色时用 `apply_accent()` 只重刷样式，**不走淡入淡出**

### 5.6 i18n 机制

两套独立的 i18n：

| 项目 | 位置 | 用途 |
|---|---|---|
| 主程序 | `MaaAutoProject/i18n/` | 主界面 |
| 安装器 | `MaaAutoInstaller/installer/i18n/` | 安装向导 |

**key 命名规则**：
- 点号分隔层级：`page.settings.theme.label`
- 支持占位符：`"home.next_run.in": "还有 {hours} 小时 {minutes} 分钟"`
- 使用 `i18n.t("key", hours=1)` 填充

---

## 六、常见问题

### 6.1 用户侧

#### Q1：安装时提示"找不到 MaaAuto_Source.zip"

**原因**：三个文件没放在一起。

**解决**：解压时确保在同一目录，**不要单独移动** `MaaAuto_Setup.exe`。

#### Q2：安装过程中 pip 很慢

**原因**：默认镜像源可能是官方 PyPI。

**解决**：安装向导第 3 步选"清华大学镜像"或"阿里云镜像"。

#### Q3：安装过程中 PyInstaller 阶段特别久

**正常现象**：PyInstaller 打包 PySide6 项目耗时 2~5 分钟，CPU 占用高。

**解决**：耐心等待，不要关窗口。

#### Q4：安装完成后主程序报 `ModuleNotFoundError`

**原因**：依赖没装全。

**解决**：
1. 检查安装目录下的 `requirements.txt` 是否完整
2. 重装，**不要**中断 pip 阶段
3. 若用系统 Python 依赖，尝试清理后重新安装

#### Q5：卸载程序双击无反应

**原因**：可能被杀毒软件拦截，或 VBS 执行失败。

**解决**：
1. 检查 `%TEMP%\MaaAuto_uninstall_*.vbs` 是否生成
2. 手动执行 `wscript <vbs路径>` 看是否报错
3. 若无法自动卸载，手动删除安装目录

#### Q6：主程序窗口没有图标

**原因**：打包时 `resources/icon.ico` 未正确进入产物。

**解决**：检查 `build.py` 的 `DATA_DIRS` 是否包含 `("resources", "resources")`。

#### Q7：主程序启动后立即闪退

**解决**：用 `python build.py --debug` 重新打包，双击后看控制台报错。

#### Q8：安装目录路径能不能含中文？

**理论上可以**，但不推荐。推荐纯英文路径（如 `D:\MaaAuto`）。

### 6.2 开发者侧

#### Q9：`python build.py` 报 `UnicodeEncodeError: 'gbk' codec`

**原因**：`build.py` 里有 emoji print（如 `print("打包成功 ✅")`），GBK 控制台编不出来。

**解决**：把 emoji 换成 ASCII（`[OK]`）。

#### Q10：`build_installer.py` 报 `UnboundLocalError: 'count'`

**原因**：`build_source_zip` 函数里 `count = 0` 初始化丢了。

**解决**：检查函数体开头有没有 `count = 0`。

#### Q11：安装器窗口左上角没图标

**原因**：`build_installer.py` 里没把 `resources/` 目录通过 `--add-data` 打进安装器。

**解决**：在 PyInstaller 命令里加：
```python
"--add-data", f"{ROOT / 'resources'}{os.pathsep}resources",
```

#### Q12：卸载程序弹窗后卡住

**原因**：旧版用 bat 的 `tasklist | find` 循环，某些系统会卡。

**解决**：改用 VBS 后端（`tools/uninstall_stub.py`），已修复。

#### Q13：`tools/build_stubs.py` 打包报错

**原因**：可能 Python 版本不兼容。

**解决**：用 Python 3.11 打包。

#### Q14：安装器打包后启动慢（首次）

**原因**：PyInstaller onefile 需要在 `%TEMP%` 解压 PySide6（~3~8 秒）。

**解决**：正常现象，第二次启动就快了。若无法接受，改回 `--onedir`。

#### Q15：想改 `MaaAuto_Source.zip` 里包含什么

**解决**：编辑 `MaaAutoInstaller/build_installer.py`：

```python
SOURCE_EXCLUDE_DIRS = {
    "__pycache__", ".git", "build", "dist",
    "config", "logs", "venv", ".venv",
    # 加你想排除的
}
SOURCE_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".log", ".spec")
```

#### Q16：想改 `MaaAutoProject/dist/MaaAuto/` 里附带的文件

**解决**：编辑 `MaaAutoProject/build.py`：

```python
EXTRA_DIST_FILES = [
    "requirements.txt",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "_version_info.txt",
    # 加你想附带的
]
```

---

## 七、版本历史

完整的版本历史见 [CHANGELOG.md](CHANGELOG.md)。摘要：

| 版本 | 日期 | 主要变更 |
|---|---|---|
| 2.0.1 | 2026-09-19 | 修复 requirements.txt 打包；卸载器改 VBS |
| 2.0.0 | 2026-09-18 | 全新安装器架构；本地打包；卸载/升级工具 |
| 1.x | 2026 早期 | UI 重构；主题系统；i18n；轮式时间选择器 |

### 2.0.1

**修复**
- `MaaAutoProject/build.py` 里的 emoji print 在 GBK 控制台崩溃
- `build_installer.py` 里 `count` 未初始化的笔误
- `requirements.txt` 未打进 `source.zip`
- pip 20.x 无法解析 UTF-8 `requirements.txt`（加编码预处理 + pip 升级）
- 卸载器改用 VBS 后端，解决 bat 卡死问题
- 安装器窗口图标未设置

**优化**
- pip 装完后自动升级到最新版
- 卸载器先杀主程序进程，避免文件占用

### 2.0.0

**新增**
- 独立安装器项目 `MaaAutoInstaller/`
- 用户端本地打包主程序（安装包体积从 300 MB 降到 45 MB）
- 镜像源自动选择（清华 / 阿里云 / 中科大 / 官方）
- `uninstall.exe` / `upgrade.exe`
- `.maaauto.json` 元数据（供未来升级器读取）
- 中英文双语安装向导

**改动**
- 主程序不再用 PyInstaller 预打包上传
- 安装器首次使用仍需下载依赖（~200 MB）

---

## 八、许可证与联系

### 许可证

[MIT License](LICENSE) © 2024-2026 MaaAuto

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

### 联系方式

| 渠道 | 地址 |
|---|---|
| **GitHub** | https://github.com/mmccz/MaaAuto-Tool-works |
| **Issues** | https://github.com/mmccz/MaaAuto-Tool-works/issues |
| **邮箱** | Frank010700@outlook.com |

### 贡献指南

欢迎提交 Issue 和 PR：

1. Fork 本仓库
2. 新建分支 `git checkout -b feature/xxx`
3. 提交改动 `git commit -m "feat: xxx"`
4. 推送分支 `git push origin feature/xxx`
5. 提交 Pull Request

**Commit 规范**（参考 Conventional Commits）：

| 前缀 | 用途 |
|---|---|
| `feat:` | 新功能 |
| `fix:` | Bug 修复 |
| `docs:` | 文档更新 |
| `refactor:` | 重构 |
| `chore:` | 构建/工具变更 |
| `perf:` | 性能优化 |

---

<p align="center">
  <sub>Made with ❤️ by MaaAuto Team · 2024-2026</sub>
</p>