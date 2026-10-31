# 更新日志

本文件记录本仓库（安装器 / 升级器 / 卸载器）的变更。版本号与主程序保持一致。

发版节奏（1.4.1 起）：大更新动 `X.Y`（`1.4.x` → `1.5.0`），小更新动 `X.Y.Z`
（`1.4.0` → `1.4.1`）；两个仓库版本号始终同步。

---

## [1.4.5] - 2026-10-31

**与主程序同步发版；安装器本身无功能变化。**

- 启动项从注册表 Run 键迁移到登录计划任务（见主程序 `autostart.py`），安装/升级流程未改。
- 版本号只用于让在线包与整包对得上 1.4.5。

## [1.4.4] - 2026-10-31

**与主程序同步发版；安装器 / 升级器 / 卸载器本身无功能变化。**

本次修复在主程序侧：MAA 6.21 改版后内置 `maa_start.png` 过期（匹配度 0.74 < 0.80），
已重截；同时找图超时会给出「重新截模板」的可操作提示，窗口离屏时立即失败。

详见主程序仓库 `CHANGELOG.md`。

## [1.4.3] - 2026-10-31

**开发工具修复：Store 版 Python（MSIX）下外壳集成读写落到重定向目录。**

### 问题

Microsoft Store 版 Python 是 MSIX 打包应用，写 `%APPDATA%` 会被静默重定向到
`%LOCALAPPDATA%\Packages\...\LocalCache\Roaming`。于是：

- `repair_integration.py` 报「开始菜单 OK」，Explorer 里却什么也没有；
- `verify_release.py` 的 `restore()` 也写进重定向目录，用户开始菜单实际没被还原。

### 修复

- `shell_integration.packaged_python()` 检测 MSIX；命中时开始菜单的读、写、
  建快捷方式全部交给子进程 `powershell.exe`（子进程不继承包身份，写真实路径）；
- 新增 `start_menu_files()` / `clear_start_menu_group()`，校验工具改用真实视图；
- `restore()` 增加保护：快照无登记但现有登记指向仍在的正式安装时保留，不误删；
- `verify_release` 第 [7] 步断言开始菜单与桌面按快照还原。

测试：安装器 92 → 98。安装器/升级器运行时代码无行为变化。

## [1.4.2] - 2026-10-25

**修复：本地校验脚本会删掉用户正式安装的图标与「设置→应用」登记。**

### 现象

用户装在 `D:\MaaAuto`（自定义目录），升级到 1.4.1 后：

- 「设置 → 应用」里的 MaaAuto 显示「**系统找不到应用**」；
- 开始菜单里的 MaaAuto 文件夹没了；
- 桌面图标没了。

程序文件和数据都还在，直接跑安装目录里的 `MaaAuto.exe` 一切正常。

### 根因

Inno 的这三样东西是**按 AppId 全局共享**的，跟装在哪个目录无关：

- `HKCU\...\Uninstall\{AppId}_is1`（「设置 → 应用」那条记录）
- 开始菜单组 `%APPDATA%\...\Programs\MaaAuto`
- 桌面 `MaaAuto.lnk`

`tools/verify_release.py` / `tools/smoke_install.py` 会「装一份 → 跑断言 → 卸载」，
而且默认装在 `%LOCALAPPDATA%\Programs\MaaAuto` —— 与用户的正式安装**同一个 AppId**。
于是校验脚本的卸载把用户那份的登记一起删了（卸载还带 `/PURGEDATA`）。

### 修复

- 新增 `installer/core/shell_integration.py`：读/写/删卸载注册表项、
  `snapshot()` / `restore()` 备份还原（注册表值 + 快捷方式原始字节）、
  `foreign_install()` 检测「本机另有一份安装」、`repair_integration()` 重建登记；
- `verify_release.py`：改装到 `%LOCALAPPDATA%\Programs\MaaAuto_verify`，开跑前
  `snapshot()`、结束时 `restore()`，并断言用户那份登记已还原；
- `smoke_install.py`：同样装到 `MaaAuto_verify`，**拒绝**在 `Programs\MaaAuto`
  这个正式目录上运行，跑完还原登记；
- 新增 `tools/repair_integration.py`：给已经被误删的机器一键重建（不动程序文件/配置）；
- 测试：83 → 92（`test_shell_integration.py` 9 项，含 AppId 与 `installer.iss` 一致性校验）。

## [1.4.1] - 2026-10-25

**随主程序 1.4.1 发布**：安装器 / 升级器代码无改动，仅同步版本号
（`VERSION`、`installer.__version__`）。差分链路沿用 1.4.0，1.4.0 用户升级时
走 `MaaAuto_delta_v1.4.0_to_1.4.1.zip`。

## [1.4.0] - 2026-10-25

**跳版本差分**：升级器新增串行差分链。

- `find_delta_chain()`：从 Release 列表里收集所有 `MaaAuto_delta_v{A}_to_{B}.zip`，
  BFS 找 `当前版本 → 最新版` 的最短链（最多 4 跳）；
- `apply_delta_chain()`：把安装目录复制成工作副本，在副本上逐级打补丁，最后一次性
  覆盖安装目录——整条链只有一次提交/回滚，中间失败不会留下半新半旧的安装；
- `check_update` 在找不到直达差分包时自动挂上链；升级器按步下载并逐个校验 digest；
- 测试：78 → 83。

## [1.3.0] - 2026-10-25

**随主程序 1.3.0 发布**：安装器 / 升级器代码无改动，仅同步版本号（含 `installer_version`）。
差分更新链路沿用 1.2.0，1.2.0 用户升级时走差分（约 0.5 MB）。

## [1.2.0] - 2026-10-25

**差分更新**：升级下载量从整包 ~61 MB 降到 ~0.6 MB。

- 新增 `installer/core/bspatch.py`：BSDIFF40 补丁应用端，**纯标准库**
  （升级器仍只依赖 stdlib + psutil，体积不涨）；构建端用 `bsdiff4`。
- 新增 `installer/core/delta.py`：`build_delta()` 生成差分包（文件级 + 按需 bsdiff），
  `materialize()` 还原并逐文件校验 sha256。
- 升级器：`check_update` 会找 `MaaAuto_delta_v{current}_to_{latest}.zip`；
  优先差分，基准不符/补丁损坏/没有该资产时自动回退整包。
- `apply_payload` 的替换/回滚逻辑抽成 `_commit_tree()`，整包与差分共用；
  差分额外支持「删除清单」（上一版有、这一版删掉的文件）并纳入回滚。
- `build_release.py`：新增 `--delta-from` / `--delta-base-version` / `--delta-auto`；
  差分包写入 `SHA256SUMS.txt`。
- `fake_release_server.py`：支持 `--delta`，离线可验差分链路。
- 契约：`installer/contract.py` 新增 `delta_asset_prefix`。
- 测试：69 → 78。

## [1.1.1] - 2026-10-25

**随主程序 1.1.1 发布的小修版**。安装/升级链路本身无变化，只多做了一道发布前保险。

- 主程序侧修复了两个「点击校验谎报成功」的问题与假开关；
- **新增发布前安装/卸载 smoke**（`tools/smoke_install.py`）：CI 在构建完成后、发布 Release
  之前，真的静默安装一遍 → 校验 `MaaAuto.exe` / `upgrade.exe` / `.maaauto.json`
  （版本与 `contract.py` 契约）→ 静默卸载并确认目录清空；任一项失败即中止发布；
- 安装包、payload、升级链路均无变化，1.1.0 用户可正常自动升级到 1.1.1。

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
