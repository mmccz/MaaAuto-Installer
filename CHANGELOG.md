# 更新日志

本文件记录本仓库（安装器 / 升级器 / 卸载器）的变更。版本号与主程序保持一致。

---

## [1.1.0] - 2026-10-24

**首个正式版**，随主程序 1.1.0 发布。本版把 1.0.2 ~ 1.0.7 的改动合并发布：

### 核心变化

- **升级器体积从 43 MB 降到 7.5 MB**：去掉 PySide6 依赖，进度界面改成纯 Win32
  （`installer/core/native_ui.py`），只依赖标准库 + psutil。
- **升级链路**：查版本 → 下载 → sha256 校验 → 停主程序 → 解压替换 → 失败回滚 →
  更新 manifest → 重启；校验失败写 `config\upgrade_failed.flag`，下次启动提示。
- **卸载先让主程序自己退出**（`config\.upgrading` 握手，最多等 12 秒），同权限
  `taskkill` 兜底；用户数据可选保留；开始菜单组兜底清理，不留残留。
- **安装向导**：开始菜单快捷方式改为「选择附加任务」里的可选项（默认勾选），
  桌面图标仍为可选。
- **离线验证工具**：`tools/fake_release_server.py` 用本地 HTTP 模拟 GitHub Releases
  （含 `sha256:` digest 校验分支），不联网就能跑完整升级/回滚链路。

### 修复

- 升级器 GUI 依赖导致体积过大与启动慢；原生窗口不再需要 Qt。
- 卸载时主程序仍在运行 → 文件删不干净、开始菜单快捷方式残留。
- `min_installer_version` 门槛从 3.0.0 修正为 1.0.0。

---

## [1.0.7] - 2026-10-24

配合主程序 1.0.7（在线公告 / 背景模糊滑杆 / 教程不再重复弹）。
安装器 / 升级器本身无逻辑变化，仅同步版本号。

---

## [1.0.6] - 2026-10-24

配合主程序 1.0.6（升级弹窗重做 / 公告 / 新手教程 / 重启不杀进程）。

### 新增

- **开始菜单快捷方式改为安装时可选项**。安装向导「选择附加任务」页新增
  「创建开始菜单快捷方式」（默认勾选）；不想被塞开始菜单条目的用户可取消，
  `[Icons]` 的两条 `{group}` 项都挂上了 `Tasks: startmenuicon`。
  卸载时的 `[UninstallDelete]` 兜底仍然保留，取消勾选也不会残留目录。

---

## [1.0.5] - 2026-10-24

配合主程序 1.0.5（界面缩放即时生效 + 「重启程序」入口 + 定时时间被重置的修复）。

### 修复

- **卸载后开始菜单残留**. 卸载器删掉了「卸载 MaaAuto」快捷方式，却经常把
  `MaaAuto.lnk` 和 `{group}` 目录留下（先升级再卸载、或外壳正持有目录句柄时
  更容易复现；本机实测残留能存在数分钟）。新增
  `[UninstallDelete] Type: filesandordirs; Name: "{group}"`，直接清掉整个
  开始菜单组——这个目录只属于本程序。

---

## [1.0.4] - 2026-10-24

配合主程序 1.0.4（修「模拟器启动失败被误报成任务成功」）。安装器 / 升级器
本身无逻辑变化，仅同步版本号。

---

## [1.0.3] - 2026-10-24

配合主程序 1.0.3。修「主程序在运行时卸载不干净」。

### 修复

- **卸载时主程序还在跑，残留一大堆文件**。根因是权限不对等：安装包默认 per-user、
  卸载器**不提权**，而主程序 exe 清单要求管理员——低完整性进程 `taskkill` 不掉
  高完整性进程（返回「拒绝访问」），Inno 随后删文件自然失败。
  现在卸载流程改为：
  1. 写 `config\.upgrading` 让主程序**自己**保存配置后退出（复用升级握手，
     不需要 UAC，也不会留下半截状态），最多等 12 秒；
  2. 还在跑才退回 `taskkill`（同权限场景有效）；
  3. 保留用户数据时会删掉这个握手标志，避免重装后主程序一启动就退出；
  4. 进程真的退不掉时明确弹窗告知，而不是留下半截目录。
- `VERSION` / `installer.__version__` 改为 `1.0.3`。

---

## [1.0.2] - 2026-10-24

配合主程序 1.0.2。`upgrade.exe` 体积从 43 MB 降到 7.5 MB。

### 变更

- **`upgrade.exe` 不再自带 PySide6**：进度窗改为纯 `ctypes`/Win32 实现
  （`installer/core/native_ui.py`：`msctls_progress32` 进度条 + 只读日志框 +
  取消按钮）。实测 45,537,671 B → 7,900,764 B（-82.6%），payload 少约 37 MB。
  - 工作线程只 `PostMessageW(WM_APP+n)` 投递状态，控件操作全部在窗口线程的
    消息循环里串行执行——跨线程直接 `SetWindowTextW` 会 0xC0000005。
  - 保留原有语义：`--silent` 窗口不可关、按钮禁用；`--no-ui` 完全无窗口；
    取消按钮写 `threading.Event`；结束仍按 800ms / 2500ms 延迟关闭。
- `VERSION` / `installer.__version__` 改为 `1.0.2`。

### 修复

- `payload.DEFAULT_MIN_INSTALLER_VERSION` 从 `3.0.0` 改为 `1.0.0`：
  版本号重置后，`.maaauto.json` 里没有 `extra.min_installer_version` 的老安装
  会被这个兜底值判定成「升级器版本过低」，从而永远无法自动升级。

### 测试

- 新增 `tests/`（pytest，69 项）：版本解析/比较、payload 资产匹配与频道选择、
  `.maaauto.json` 读写契约、payload 替换/保护/回滚/路径穿越、假 Release 服务器
  本身、以及「upgrade.exe 不许再引入 PySide6/PyQt/tkinter」的回归测试。
- 新增 `tools/fake_release_server.py`：本地模拟 GitHub Releases API，
  **不用发版**就能把「查版本 → 下载 → sha256 校验 → 替换 → 更新 manifest」
  整条链路跑一遍；`--corrupt-digest` 可验证校验失败 → 回滚。测完把
  `extra.update_api` 改回 GitHub 地址（或重装）即可。

---

## [1.0.1b1] - 2026-10-24

测试版，配合主程序 1.0.1b1 验证 beta 渠道升级。

### 变更

- `VERSION` / `__init__` 改为 `1.0.1b1`。
- `build_release.py` 生成 Inno 需要的纯数字版本（`1.0.1.0`），预发布不再导致编译失败。
- CI 对 `b` / `rc` tag 自动发布为 prerelease（草稿只用于正式版）。

---

## [1.0.0] - 2026-10-24

首个「预构建 + payload」版本。删除了整条用户机编译链路。

### 新增

- `build_release.py`：契约校验 → 主程序打包 → 裁剪 → `upgrade.exe` → payload zip → Inno 完整包 / 在线包 → `SHA256SUMS.txt`。
- `packaging/`：`installer.iss`（完整包）、`online.iss`（约 2 MB 引导包）、`trim_payload.py`、官方中文语言包。
- `installer/core/payload.py`：下载 / sha256 校验 / 解压 / 备份替换 / 回滚 / 重启。
- `tools/upgrade_stub.py` 重写为 payload 模式，保留 2.x 的 CLI；新增 `--no-ui`（完全无界面，供自动化）。
- 更新渠道：`--channel stable|beta`，beta 走 `/releases` 列表并包含 prerelease。
- GitHub Actions：推 `v*` tag 自动构建并创建草稿 Release（含 prerelease 标记）。

### 安装包行为

- 默认 per-user 安装（免 UAC），可选「为所有用户安装」。
- 安装完成页「立即启动」使用 ShellExecute，不再报错误 740。
- 卸载：先 `taskkill` 主程序，再删除文件；默认保留 `config/`、`logs/`，`/PURGEDATA` 彻底删除；同时清理卸载项、开机自启项与旧 `RUNASADMIN` 标志。

### 删除

- 用户机编译链路：`pages/`、`app.py`、`wizard.py`、`state.py`、`i18n/`、`python_env.py`、`pip_installer.py`、`pyinstaller_builder.py`、`source_deployer.py`、`stub_builder.py`、`uninstall_stub.py`、`build_stubs.py`、`build_installer.py`。
- 2.x 过渡逻辑：不再产出/校验 `MaaAuto_Source.zip`。

---

更早的版本历史已随版本号重置移除。
