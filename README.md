<div align="center">

<img src="docs/images/logo.png" width="96" alt="MaaAuto logo">

# MaaAuto Installer

**MaaAuto 的打包与升级仓库** —— Inno Setup 安装包 + payload 升级器

[![Version](https://img.shields.io/badge/version-1.0.0-2f81f7.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011%20x64-0078D4.svg)](https://github.com/mmccz/MaaAuto-Installer/releases)
[![Main App](https://img.shields.io/badge/main%20app-MaaAuto--Tool--works-6f42c1.svg)](https://github.com/mmccz/MaaAuto-Tool-works)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

---

## 这是什么

**3.0.0 起，程序在 CI 预构建，用户机器上不再有 Python / pip / PyInstaller。**

本仓库负责两件事：

1. **打包**：把主程序的 onedir 产物裁剪、压缩成 payload，再用 Inno Setup 生成安装包；
2. **升级**：`upgrade.exe` 下载 payload、校验、替换程序文件，失败回滚。

主程序本身（界面、调度、找图、推送）在 [MaaAuto-Tool-works](https://github.com/mmccz/MaaAuto-Tool-works)。

### 产物

| 文件 | 大小 | 用途 |
| --- | --- | --- |
| `MaaAuto_Setup_v{ver}-Windows-x64.exe` | ~94 MB | 完整安装包，内嵌 payload，断网可装 |
| `MaaAuto_Online_v{ver}-Windows-x64.exe` | ~2 MB | 在线引导包，安装时才下载完整包 |
| `MaaAuto_payload_v{ver}.zip` | ~100 MB | 升级器下载的预构建程序包 |
| `SHA256SUMS.txt` | — | 上述三个文件的校验和 |

---

## 安装包行为

| 项 | 说明 |
| --- | --- |
| 默认目录 | `%LOCALAPPDATA%\Programs\MaaAuto`（per-user，免 UAC） |
| 可选模式 | 向导中选「为所有用户安装」→ `Program Files\MaaAuto`（需要提权） |
| 需要联网 | **否**（完整包） |
| 需要 Python | **否** |
| 安装耗时 | 约 30 秒 |
| 快捷方式 | 开始菜单固定创建；桌面可选 |
| 卸载 | Inno 生成的 `unins000.exe`（开始菜单也有「卸载 MaaAuto」入口）：先停主程序，再删文件/快捷方式/注册表/自启项；默认保留 `config` 与 `logs`，加 `/PURGEDATA` 彻底删除 |

主程序 exe 内嵌 `requireAdministrator` 清单，**每次启动弹一次 UAC**（它需要点击游戏的提权窗口）；安装本身不再写 `RUNASADMIN` 兼容标志，安装时还会清理 2.x 留下的旧标志。

---

## 升级流程

```
主程序（5 秒后或手动）：查 releases/latest，比对版本
        │  有新版 → 写 config/.upgrading 并调起 upgrade.exe
        ▼
upgrade.exe：读 .maaauto.json → 重新查询 Release
        │  找到 MaaAuto_payload_v{ver}.zip
        ▼
   下载到 %TEMP% → 校验 sha256 → 等主程序退出（15s，超时强杀）
        ▼
   解压到 <parent>/.MaaAuto_new_<ts>
        ▼
   逐文件：旧文件移到 .MaaAuto_bak_<ts>，新文件替换进去
        │  任一步失败 → 反向恢复 → 写 upgrade_failed.flag
        ▼
   更新 .maaauto.json（version / installer_version / source_hash）
        ▼
   清 .upgrading → 按 last_launch_args.json 重启主程序
```

- `config/`、`logs/`、`.maaauto.json` **永远不参与替换**。
- 正在运行的 `upgrade.exe` 会被改名让位（`.old`），下次启动时清理，因此**升级器自身可以随 payload 更新**。
- 用户取消、已是最新、检查失败等终态都会回到主程序（`--restart` 且主程序未运行时）。

命令行（与旧版保持一致，主程序无需改动）：

```text
upgrade.exe --from-main [--restart] [--silent] [--check-only] [--no-ui] [--channel stable|beta] [--downgrade]
```

- `--silent`：显示不可交互的进度窗；
- `--no-ui`：完全无窗口，只写日志，供自动化 / CI 使用；
- `--channel beta`：同时接受预发布（`bN` / `rcN`），稳定版只看 `releases/latest`。

退出码：`0` 成功/有新版本，`1` 仅 `--check-only` 且已最新，`2` 错误。

---

## 构建

### 环境

```powershell
cd MaaAutoInstaller
pip install -r requirements.txt      # PySide6 + psutil
pip install pyinstaller
winget install JRSoftware.InnoSetup  # 提供 ISCC.exe
```

还需要主程序源码目录（默认自动探测同级仓库，或 `--source-dir` 指定）。

### 一条命令

```powershell
cd MaaAutoInstaller
python build_release.py                    # 完整构建
python build_release.py --keep-build       # 保留中间产物
python build_release.py --skip-main-build  # 复用主程序 dist/
python build_release.py --skip-stub        # 复用 _build/stub/upgrade.exe
python build_release.py --no-trim          # 不裁剪
python build_release.py --debug            # upgrade.exe 保留控制台
python build_release.py --source-dir ..\..\MaaAuto-Tool-works\MaaAutoProject
```

流程：**契约校验** → 主程序 `build.py` → 复制并裁剪 payload（约 −67 MB）→ PyInstaller 打包 `upgrade.exe` → 压缩 payload（LZMA）→ Inno 编译完整包 → 计算 sha256 → Inno 编译在线包 → 写 `dist/SHA256SUMS.txt`。

产物在 `dist/`。

### CI

`.github/workflows/release.yml` **位于主程序仓库**（Release 与 tag 都在那边）：推 `v*` tag 后检出本仓库、装依赖与 Inno、跑 `build_release.py`，把三个资产 + `SHA256SUMS.txt` 挂到草稿 Release；tag 含 `b` / `rc` 时自动标记为 prerelease。

---

## 关键契约

| 文件 | 写入方 | 读取方 | 语义 |
| --- | --- | --- | --- |
| `config/.upgrading` | 升级器 | 主程序（启动 + 每秒轮询） | 存在即退出；**必须由升级器删除**，残留 5 分钟后主程序兜底清理 |
| `config/upgrade_failed.flag` | 升级器 | 主程序（启动 300ms 后） | JSON；弹窗提示后由主程序删除 |
| `config/last_launch_args.json` | 主程序 | 升级器 | 重启时恢复 `--autostart` 等参数 |

`.maaauto.json`（`manifest_version = 3`）由安装包写入、升级器更新，主程序从不读写。

**冻结常量**（改动 = 协议变更，两仓库必须同时发版）：

```text
APP_UPDATE_API               ↔ extra.update_api
APP_SOURCE_ASSET             ↔ extra.source_asset_name      （过渡期）
APP_MIN_INSTALLER_VERSION    ↔ extra.min_installer_version
APP_PAYLOAD_ASSET_PREFIX     ↔ extra.payload_asset_prefix
```

`extra` 只在安装时写入、升级不刷新——改了地址等于老用户永远读旧值。

---

## 目录结构

```text
MaaAuto-Installer/
├─ CHANGELOG.md
├─ docs/images/logo.png
├─ .github/workflows/release.yml   ← tag 触发构建
└─ MaaAutoInstaller/
   ├─ VERSION                      ← 安装器/升级器版本
   ├─ build_release.py             ← 一键构建
   ├─ packaging/
   │  ├─ installer.iss             ← 完整安装包
   │  ├─ online.iss                ← 在线引导包
   │  ├─ trim_payload.py           ← 裁剪规则
   │  └─ languages/ChineseSimplified.isl
   ├─ installer/
   │  ├─ contract.py               ← 冻结常量与 manifest.extra
   │  └─ core/
   │     ├─ payload.py             ← 升级核心：下载/校验/替换/回滚
   │     ├─ manifest.py            ← .maaauto.json
   │     └─ downloader.py          ← 带进度的下载
   ├─ tools/upgrade_stub.py        ← upgrade.exe 源码
   └─ resources/
```

---

## 已知限制

| 限制 | 说明 |
| --- | --- |
| 未签名 | SmartScreen 会提示「未知发布者」；构建脚本预留了签名步骤，拿到证书后接入即可 |
| 不做差分升级 | 每次升级下载全量 payload（约 100 MB）；文件级差分留待后续 |
| 安装包变大 | 从 ~50 MB 变成 ~94 MB，换来免编译与可复现 |
| 升级器版本门槛 | `min_installer_version = 1.0.0`；低于它的旧安装包需要重装一次 |

---

## 许可证

[MIT](LICENSE)。本项目为第三方工具，与 MAA / MaaEnd 官方无关联。
