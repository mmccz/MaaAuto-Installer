# 更新日志

本文件记录安装器 / 升级器 / 卸载器的变更。版本号遵循 `X.Y.Z`。

---

## [3.0.0] - 2026-10-24

**架构重构**：安装与升级都不再在用户机上编译。

### 变更

- **安装包改用 Inno Setup**：新增 `packaging/installer.iss`（完整包）与 `packaging/online.iss`（在线引导包）。
  - 默认 per-user 安装（`%LOCALAPPDATA%\Programs\MaaAuto`，免 UAC），向导可选「为所有用户安装」到 `Program Files`。
  - 卸载、快捷方式、卸载项、旧 `RUNASADMIN` 标志清理全部由安装包完成；卸载时询问是否保留 `config`/`logs`。
- **主程序改为预构建**：构建脚本不再内嵌源码在用户机打包，改为 `build_release.py` 在 CI/开发机完成，产物是 payload。
- **升级器重写为 payload 替换**（`installer/core/payload.py`）：下载 → sha256 校验 → 解压 → 逐文件备份替换 → 失败回滚 → 更新 manifest → 重启。
- **`upgrade.exe` 随 payload 分发并更新**：运行中的旧 exe 改名 `.old` 让位，下次启动清理——消除了「升级器修复对存量用户不生效」的限制。
- **在线引导包**：约 2 MB，下载完整安装包并校验 sha256 后交给它安装。
- 删除整条旧链路：`pages/`、`wizard.py`、`app.py`、`state.py`、`python_env.py`、`pip_installer.py`、`pyinstaller_builder.py`、`source_deployer.py`、`stub_builder.py`、`uninstall_stub.py`、`build_stubs.py`、`mirror.py`（不再需要下载 Python / 装依赖）。
- **新增 CI**：`.github/workflows/release.yml`，推 `v*` tag 自动构建并挂草稿 Release。

### 体积

- 裁剪规则（`packaging/trim_payload.py`）：移除 Qt Quick/QML、Qt PDF/SVG、软件 OpenGL、cv2 视频后端，实测 −67 MB；payload 205 MB，安装包约 100 MB。

### 契约

- `installer/contract.py` 新增 `payload_asset_prefix`，`min_installer_version` 提升到 `3.0.0`；`APP_INFO_CONSTANTS` 增加 `APP_PAYLOAD_ASSET_PREFIX`，构建期强校验。

### 兼容

- 2.x 用户首次升级仍由旧 `upgrade.exe` 走 Source.zip 重编译，成功后进入 payload 模式（3.0.0 的 Release 同时上传 `MaaAuto_Source.zip`）。

---

## [1.0.1] - 2026-10-24

配合主程序 2.1.1 发布。重点是**升级链路的可靠性**。

### 修复

- **停不掉主程序时残留 `.upgrading`** —— `request_main_exit()` 在 `taskkill` 失败或抛异常时未清标志，主程序下次启动直接退出、表现为「双击没反应」。现在三条路径都会清理：停止失败、`run_full` 停止失败、安装/覆盖安装开始前。
- **终态不重启主程序** —— 原先只有升级成功才重启。现在「缺少安装信息 / 检查失败 / 已是最新 / 下载失败 / 停止失败 / 升级失败 / 取消 / 成功」都走统一入口 `_restart_if_needed()`，仅在 `--restart` 且主程序确实未运行时重启（避免双开）。
- **失败标志覆盖不全** —— 按主程序 Q2 修订口径，`run_full` 所有以退出码 2 结束且非用户取消的终态都写 `upgrade_failed.flag`，补上「缺少 `.maaauto.json`」「升级器版本过低」「检查更新失败」三条路径；`--check-only`、已是最新、用户取消不写。
- **复制产物因占用失败** —— 杀软实时扫描常让刚写入的 exe/dll 短暂不可覆盖，原先一次失败就整轮回滚。现在每个文件/目录重试 3 次（0.4 秒间隔）。
- **源码包混入上次的产物** —— `source.zip` 的排除清单缺 `release/`，用 `--source-dir` 指向开发目录时会把旧的 `MaaAuto_Source.zip` 打进去形成「包中包」。现已排除 `release/` 与 `_version_info.txt`。
- **国内选镜像仍回落官方站** —— `resolve_python_mirror()` 遇到 PyPI 的镜像 key（tuna/aliyun/ustc/pypi）时回落到 `python.org`。现在未知 key 按 `auto` 处理（国内 → 华为云）。

### 变更

- 停止主程序的默认超时 **5s → 15s**：覆盖主程序「等任务线程 3s + 杀子进程 + Qt 退出」的最坏耗时，减少强杀丢配置。
- 移除无效的 `PYI_DISABLE_UPX` 环境变量（PyInstaller 不认），改由主程序 `build.py` 传 `--noupx`。
- 构建期契约断言保留不变：`APP_VERSION` 语法 + 三个冻结常量必须与主程序 `app_info.py` 一致，否则构建失败。
- 清理了 10 个文件中的未使用导入；`upgrade_engine.read_manifest` 保留为对 `upgrade_stub` 的显式再导出。

### 文档

- README 完全重写为「安装器专属」，不再复用主程序说明。
- 新增本文件。
- 协议要点并入 README「关键契约」，不再维护单独的对接口文档。

---

## [1.0.0] - 2026-10-17

首次发布。安装向导 5 页、用户端现场打包主程序与 stub、`.maaauto.json` v3、注册表与环境配置。
