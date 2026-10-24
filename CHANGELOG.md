# 更新日志

本文件记录本仓库（安装器 / 升级器 / 卸载器）的变更。版本号与主程序保持一致。

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
