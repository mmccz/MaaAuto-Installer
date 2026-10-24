<div align="center">

<img src="docs/images/logo.png" width="96" alt="MaaAuto logo">

# MaaAuto Installer

**MaaAuto 的安装器 · 升级器 · 卸载器**

[![Version](https://img.shields.io/badge/version-1.0.1-2f81f7.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011%20x64-0078D4.svg)](https://github.com/mmccz/MaaAuto-Installer/releases)
[![Main App](https://img.shields.io/badge/main%20app-MaaAuto--Tool--works-6f42c1.svg)](https://github.com/mmccz/MaaAuto-Tool-works)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

---

## 这是什么

本仓库只负责**把 MaaAuto 装到用户机器上**，以及**让它能升级、能卸载**。主程序本身（界面、调度、找图、推送）在 [MaaAuto-Tool-works](https://github.com/mmccz/MaaAuto-Tool-works)。

三个可执行文件的职责：

| 程序 | 谁生成 | 干什么 |
| --- | --- | --- |
| `MaaAuto_Online_v{ver}-Windows-x64.exe` | 本仓库构建时 | 安装向导：下载 Python → 装依赖 → **现场打包主程序** → 部署 |
| `upgrade.exe` | 安装时在用户机现场打包 | 升级：查 GitHub → 下载源码包 → 停主程序 → 备份 → 重装 → 覆盖 → 重启 / 回滚 |
| `uninstall.exe` | 安装时在用户机现场打包 | 卸载：确认 → 删快捷方式与注册表 → 延迟强删目录（可保留用户数据） |

**一句话**：安装包只有几十 MB，因为它不预置主程序产物，只预置**源码**，把编译和打包放到用户机器上完成。

---

## 它是怎么工作的

```
① 安装                     ② 升级                          ③ 卸载
─────────────────────      ──────────────────────────      ───────────────────
下载 embeddable Python      主程序发现新版，调起 upgrade.exe   双击 uninstall.exe
解压 source.zip             升级器下 MaaAuto_Source.zip      两次确认
pip install 依赖            写 config/.upgrading             删快捷方式 / 注册表
PyInstaller 打包主程序      等主程序退出（15s，超时强杀）     VBS 延迟 2.5s
现场打包两个 stub           备份 → 重装 → 覆盖               强删安装目录
部署 + 快捷方式 + manifest  清标志 → 按 last_launch_args 重启   （可选保留 config/logs）
```

升级时**只覆盖程序文件**，`config/`、`logs/`、`.maaauto.json` 永远保留；失败会从备份回滚。

---

## 用户指南

### 系统要求

| 项 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11（x64） |
| 磁盘 | 约 1 GB（安装峰值约 1.5 GB） |
| 网络 | **必须联网**（首次安装需下载 Python 与约 200 MB 依赖） |
| 权限 | **需要管理员**（要写 HKLM 并给主程序打 `RUNASADMIN` 兼容标志） |

### 安装

从 [Releases](https://github.com/mmccz/MaaAuto-Tool-works/releases) 下载 `MaaAuto_Online_v2.1.1-Windows-x64.exe`，双击后：

| 步骤 | 内容 |
| --- | --- |
| ① 欢迎 | 选语言（简体中文 / English） |
| ② 目录 | 默认 `D:\MaaAuto`，建议非系统盘、纯英文路径 |
| ③ 选项 | 镜像源、桌面 / 开始菜单快捷方式、安装后清理、安装后启动 |
| ④ 进度 | 自动执行，实时日志 |
| ⑤ 完成 | 打开目录 / 立即启动 |

安装阶段（括号内为进度权重）：准备（2）→ 下载 Python（8）→ 解压源码（2）→ 装依赖（28）→ 装 PyInstaller（5）→ 打包主程序（28）→ 打包 stub（15）→ 部署 stub（2）→ 快捷方式（2）→ 写 manifest（2）→ 写注册表（2）→ 清理（3）→ 完成（1）。

> 打包阶段 CPU 占用高属正常现象，**不要中途关窗口**。

### 安装后目录

```
D:\MaaAuto\
├─ MaaAuto.exe            ← 主程序
├─ _internal/             ← PyInstaller 运行时
├─ resources/ themes/ i18n/
├─ upgrade.exe            ← 升级器
├─ uninstall.exe          ← 卸载器
├─ .maaauto.json          ← 安装元数据（主程序不读不写）
├─ config/                ← 用户配置（首次启动生成，升级保留）
└─ logs/                  ← 运行日志（升级保留）
```

### 升级

主程序启动 5 秒后自动检查更新（可关闭），或在「关于 → 检查更新」手动触发：

- **手动升级**：弹窗确认 → 调起 `upgrade.exe --from-main --restart`
- **自动升级**：`--silent`，有不可交互的进度窗；任务运行中会等任务结束
- 升级完成后自动重启主程序，恢复 `--autostart` 等原启动参数

> `upgrade.exe` 由主程序传参：`--from-main`（恒传）、`--restart`（恒传）、`--silent`（仅自动升级）。**不传版本号、不传下载地址**——升级器自己去 GitHub 查。

### 卸载

双击安装目录里的 `uninstall.exe`：

1. 确认卸载；
2. 选择是否保留 `config/` 与 `logs/`（**建议保留**）；
3. 程序删除快捷方式、HKLM 卸载项、App Paths、`RUNASADMIN` 标志，然后由 VBS 延迟强制删除目录。

---

## 开发者指南

### 环境

```powershell
cd MaaAutoInstaller
pip install -r requirements.txt   # PySide6, pywin32
pip install pyinstaller
```

还需要主程序源码目录。默认按以下顺序自动探测，也可 `--source-dir` 指定：

1. `<ROOT>/../../MaaAuto-Tool-works/MaaAutoProject`
2. `<ROOT>/../MaaAuto-Tool-works/MaaAutoProject`
3. `<ROOT>/../MaaAutoProject`
4. `<ROOT>/MaaAutoProject`

### 构建安装器

```powershell
python build_installer.py                                  # 正式构建
python build_installer.py --debug                          # 控制台 + 保留中间产物
python build_installer.py --keep-build                     # 不清理
python build_installer.py --source-dir "..\..\MaaAuto-Tool-works\MaaAutoProject"
```

流程：

1. **契约校验**（`check_app_info_contract`）——读主程序 `app_info.py`，比对 `APP_VERSION` 语法与三个冻结常量；不一致直接 `exit 1`；
2. 生成 `_embedded/source.zip`（主程序源码，排除 `config/`、`logs/`、`build/`、`dist/`、`release/`、`__pycache__`…）；
3. 生成 `_embedded/stubs_source.zip`（`upgrade_stub.py`、`uninstall_stub.py` 及其依赖的 `core/` 模块白名单）；
4. PyInstaller onefile 打包：`--uac-admin --windowed`，两个 zip 内嵌为 `_embedded`；
5. 改名 `dist/MaaAuto_Online_v{主程序版本}-Windows-x64.exe`；
6. 清理 `build/`、`_embedded/`、`*.spec` 与两边 `__pycache__`。

> 产物名用的是**主程序版本**，不是安装器版本。

### 开发期单独打 stub

```powershell
python tools/build_stubs.py                 # upgrade.exe + uninstall.exe
python tools/build_stubs.py --only upgrade  # 只打升级器（含 PySide6，较慢）
```

产物在 `tools/_out/`。**发布流程不调用它**——stub 由用户在安装时现场打包。

---

## 关键契约

与主程序之间的协议见 [INTEGRATION.md](INTEGRATION.md)，逐条回复见 [docs/INSTALLER_RESPONSE.md](docs/INSTALLER_RESPONSE.md)。核心是三个握手文件：

| 文件 | 写入方 | 读取方 | 语义 |
| --- | --- | --- | --- |
| `config/.upgrading` | 升级器 | 主程序（启动 + 每秒轮询） | 存在即退出；**正常路径必须由升级器删除**，否则主程序「双击没反应」 |
| `config/upgrade_failed.flag` | 升级器 | 主程序（启动 300ms 后） | JSON；弹窗提示后由主程序删除 |
| `config/last_launch_args.json` | 主程序 | 升级器 | 重启时恢复 `--autostart` 等参数 |

`.maaauto.json`（`manifest_version = 3`）由安装器写入、升级器更新，**主程序从不读写**。

**冻结常量**（改动等于协议变更，需两仓库同时发版）：

```text
APP_UPDATE_API               ↔ extra.update_api
APP_SOURCE_ASSET             ↔ extra.source_asset_name
APP_MIN_INSTALLER_VERSION    ↔ extra.min_installer_version
```

`extra` 只在安装时写入、升级不刷新——所以改了地址等于老用户永远读旧值。

---

## 已知限制

| 限制 | 说明 |
| --- | --- |
| 升级不更新 stub | `upgrade.exe` / `uninstall.exe` 只在完整安装时生成；升级链路本身的修复对存量用户不生效，需重装完整包 |
| 不刷新注册表版本 | 升级后「设置 → 应用」里的 `DisplayVersion` 仍是旧值（主程序「关于」页读编译期版本，不受影响） |
| 卸载不清理开机自启 | `HKCU\...\Run\MaaAuto` 目前不会被删除（待修）；卸载后可手动删除该值 |
| `--silent` 仍有窗口 | 有不可交互进度窗，不是完全静默；失败时必定写 `upgrade_failed.flag` |
| 升级 = 完整重跑 | 每次升级都会重新下载 Python、装依赖、打包，耗时几分钟，不是增量替换 |

---

## 目录结构

```text
MaaAuto-Installer/
├─ INTEGRATION.md              ← 与主程序的契约
├─ CHANGELOG.md
├─ docs/
│  ├─ INSTALLER_RESPONSE.md    ← 对契约的逐条回复
│  └─ images/logo.png
└─ MaaAutoInstaller/
   ├─ VERSION                  ← 安装器版本
   ├─ build_installer.py       ← 一键构建
   ├─ installer/
   │  ├─ __main__.py app.py wizard.py state.py
   │  ├─ contract.py           ← 冻结常量与 manifest.extra
   │  ├─ core/                 ← 纯逻辑：manifest/下载/打包/升级引擎/注册表/清理
   │  ├─ pages/                ← 向导 5 页
   │  └─ i18n/
   ├─ tools/
   │  ├─ upgrade_stub.py       ← 升级器源码（用户机打包）
   │  ├─ uninstall_stub.py     ← 卸载器源码（用户机打包）
   │  └─ build_stubs.py        ← 开发期单独打 stub
   └─ resources/
```

---

## 常见问题

**Q1 安装器报「契约常量校验失败」？** 主程序 `app_info.py` 的三个常量与本仓库 `installer/contract.py` 不一致。同步两处，或确认这是不是一次协议变更。

**Q2 下载 Python 很慢？** 镜像解析会跟着系统语言走（国内 → 华为云）。仍失败可换网络或代理。

**Q3 覆盖文件时提示被占用？** 已内置 3 次重试；仍失败多半是杀软实时扫描，临时加白名单。

**Q4 安装中途失败留下半个目录？** 删除安装目录后重装；若只是缺 `.maaauto.json`，升级器会提示「找不到安装信息」并要求重装。

**Q5 升级后主程序没自动回来？** 看 `%TEMP%\MaaAuto_upgrade_*.log`；同时确认主程序当时确实已退出（`--restart` 只在主程序未运行时重启）。

**Q6 主程序双击没反应？** 检查 `<安装目录>\config\.upgrading` 是否残留：主程序会在 5 分钟后自行判定陈旧并清理；急用可手动删除该文件。

---

## 许可证

[MIT](LICENSE)。本项目为第三方工具，与 MAA / MaaEnd 官方无关联。
