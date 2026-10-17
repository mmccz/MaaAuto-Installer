# 安装器侧回复：对主程序《MaaAuto ↔ MaaAutoInstaller 对接说明》的确认

> 对应文档：`MaaAuto-Tool-works/docs/INSTALLER_INTEGRATION.md`（主程序 v2.1.0 @ `14634d6`）
> 主程序答复：`MaaAuto-Tool-works/docs/INSTALLER_REPLY.md`（2026-10-17）
> 回复方：`MaaAuto-Installer` 1.0.0（`manifest_version = 3`）
> 日期：2026-10-17
> 结论：**边界划分同意**；§9 的 7 个开放问题已逐条回答（§3）；同时发现 13 处“文档要求 vs 当前实现”的差异（§2）。主程序已在 `INSTALLER_REPLY.md` 中对 6 个问题给出决议，本文件已按决议回填。

---

## 0. 总览

- 主程序文档把边界定义为「主程序负责发现版本 + 调起升级器 + 让位；安装器负责停进程 + 换文件 + 回滚 + 恢复启动 + 清标志」——**安装器侧完全同意**，本文不再重复论证。
- 主程序侧**不需要**写 `upgrade.py` 参考实现。`upgrade.exe` 的唯一实现已经在安装器仓库：`tools/upgrade_stub.py`（UI/参数）+ `installer/core/upgrade_engine.py`（纯逻辑）。再维护一份参考实现只会产生第二套真源。
- 英文翻译暂不需要；等协议冻结后再翻，避免反复改。
- **2026-10-17 主程序决议**（详见 `INSTALLER_REPLY.md`）：
  - Q1：主程序已实现 `upgrade_guard.py`（300s + 进程探测），安装器仍必须修自己的清标志路径；两方兜底叠加。
  - Q2：`upgrade_failed.flag` 覆盖 `run_full` **以退出码 2 结束且非用户取消**的所有终态：缺 `.maaauto.json`、升级器版本过低、检查更新失败、下载失败、无法停止主程序、`perform_upgrade` 失败、已写过标志的未捕获异常；`--check-only` / 已最新 / 用户取消不写。
  - Q3：升级 UI 保持“主程序检查 + 升级器复核”，不改成 `--check-only`。
  - Q4：版本语法与 `MaaAuto_Source.zip` 固定名冻结。
  - Q5：三个 `app_info.py` 常量冻结，安装器构建期断言（已在 `build_installer.py` 落地）。
  - Q6：接受“不可交互的进度窗口”，主程序把文案改为“自动下载并升级（免确认）”，不要求真无 UI。
- 安装器侧 P0/P1 已处理（2026-10-17）：`.upgrading` 全路径清理 + 终态重启 + 失败标志全 2 号终态（按 Q2 修订）+ 构建期契约断言；剩余 P1/P2 见 §5。


---

## 1. 边界确认

| 环节 | 主程序 | 安装器 / `upgrade.exe` |
|---|---|---|
| 发现新版本 | ✅ 自己请求 `releases/latest` | ✅ 升级器内部**再查一次**（当前设计） |
| 调起升级器 | ✅ `Popen(upgrade.exe --from-main --restart [--silent])` 后退出 | ❌ 不反向调主程序 |
| 停止主程序 | ✅ 每秒轮询 `.upgrading`，保存配置/清理子进程后退出 | ✅ 写 `.upgrading`、等待、超时强杀 |
| 下载 / 校验 / 替换 / 回滚 | ❌ 不做 | ✅ 全权负责 |
| 恢复启动 | ❌ 只提供 `last_launch_args.json` | ✅ 读取并重启 |
| 失败提示 | ✅ 下次启动读 `upgrade_failed.flag` 并删除 | ✅ 写标志 |
| 用户数据 | ✅ `config/`、`logs/` 唯一主人 | ✅ 只保护，不读写内容 |

---

## 2. 与当前实现的差异（按主程序文档章节）

> 状态说明：**已符合** = 无需改动；**待修** = 安装器侧代码需要改；**待定** = 需要双方拍板。

| ID | 主程序文档要求 | 当前安装器实现 | 状态 / 处理 |
|---|---|---|---|
| D1 | §2.2 等待主程序退出，建议超时 **15s** | `DEFAULT_EXIT_TIMEOUT = 5.0`，0.1s 轮询 | **待修（P1）**：改为 15s；主程序最坏情况（任务线程 3s + 杀 MAA/模拟器）留余量 |
| D2 | §2.2 成功 / 失败 / 取消 / 异常**所有路径**都删除 `.upgrading` | `perform_upgrade` 的 `finally` 会清；但“停不掉主程序”路径直接 `return 2`，**残留标志** | **已修（2026-10-17）**：`request_main_exit` 失败路径清标志；`run_full` 停止失败路径再兜一次；`progress.py` 安装/覆盖安装开始时清理残留 |
| D3 | §3.2 步骤 2：部署前确保 `.upgrading` 存在，封住“退出到替换之间用户又启动”的窗口 | 只在 `is_main_running()` 为真时写；主程序已退出则不写 | **待修（P1）**：停止阶段结束后、部署开始前**无条件**写一次标志 |
| D4 | §2.5 替换文件遇 `ERROR_SHARING_VIOLATION` 建议退避重试 3 次 | `copy_dist_to_install` 直接 `copytree` / `copy2`，无重试 | **待修（P1）**：加 0.5s / 1s / 2s 重试；失败再走回滚 |
| D5 | §3.1 `--silent` 要求**无 UI、无交互** | `--silent` = 有进度窗但不可交互；`--silent --check-only` 才完全无 UI | **已决议（主程序 Q6）**：接受不可交互进度窗，主程序文案改为“免确认”；安装器无需实现真无窗口模式 |
| D6 | §3.2 步骤 0：无 `--from-main` 时也可先停主程序 | 无 `--from-main` 直接弹提示并 `return 0`，不执行任何升级 | **建议保持拒绝**（防用户双击误升级）。若将来要“手动升级”，新增显式 `--manual` 参数，而不是放开 `--from-main` |
| D7 | §3.2 步骤 6：失败就回滚 + 写 `upgrade_failed.flag` | 原先只有 `perform_upgrade` 内部失败才写；检查失败、下载失败、无法停止主程序都不写 | **已修（2026-10-17，按 Q2 修订）**：`run_full` 所有以 2 结束且非取消的终态都写（含缺 manifest / 版本过低 / 检查失败）；`--check-only`/已最新/取消不写 |
| D8 | §3.4 示例 `log_path` 指向 `<安装目录>/logs/upgrade_*.log` | 失败时 `log_path` 指向 `%TEMP%\MaaAuto_upgrade_*.log`；仅成功时复制到 `logs/upgrade/` | **待修（P2）**：失败也先复制到 `logs/upgrade/`，再写标志 |
| D9 | §5.2 卸载器应无条件删除 `HKCU\...\Run\MaaAuto` | `uninstall_stub.remove_registry()` 只删 Uninstall / App Paths / AppCompat，**漏了 Run** | **待修（P1）**：补删 Run 值 |
| D10 | §7.1 卸载先走 `.upgrading` 优雅停止 | 卸载器直接写 VBS，2.5s 后 `taskkill /F /IM MaaAuto.exe` | **待修（P1）**：先写标志 + 等待，超时才强杀；与升级共用同一套停止逻辑 |
| D11 | §7.6 询问是否保留 `config/`、`logs/`、`.maaauto.json`，**默认建议保留** | 询问保留 `config/`、`logs/`，默认按钮是“否”；保留时只保留这两个目录，`.maaauto.json` 会被删 | **待定**：主程序文档建议默认保留，安装器 README 建议默认删除；见 §6-Q3 |
| D12 | §7.8 用户取消卸载时删除已写入的 `.upgrading` | 当前卸载器根本不写 `.upgrading` | 随 D10 一起实现；实现后必须覆盖取消路径 |
| D13 | §9-Q7 需要明确 `uninstall.exe` 的参数（如 `/S`） | 注册表写了 `QuietUninstallString = "uninstall.exe" /S`，但 stub **完全不解析 argv**，`/S` 仍会弹两个 MessageBox | **待修（P1）**：要么实现 `/S`，要么删掉 `QuietUninstallString`，不能继续“宣传支持但不支持” |
| D14 | §1.3 若新版本自带新版 `upgrade.exe`，需延迟替换 | 升级流程**从不重建/更新** stub，旧版 `upgrade.exe` 会一直沿用 | **待定（P2）**：要么接受“升级器只随完整安装包更新”，要么增加延迟替换逻辑 |
| D15 | §4.5 `APP_MIN_INSTALLER_VERSION` 主程序尚未校验 | 升级器**会**读 `manifest.extra.min_installer_version` 并校验 | **已确认**：主程序不校验；校验点在升级器。文档补注即可，无需改代码 |
| D16 | §1.4 安装器可预创建 `config/`、`logs/` 并授权 | 安装器只创建安装目录，`config/`、`logs/` 由主程序首次启动创建 | **可选（P3）**：若担心标准用户写权限，可在部署后预创建空目录 |
| D17 | （文档未写）主程序 `Popen` 后立即退出；升级器“无更新 / 检查失败 / 下载失败”时不会重启主程序 | `run_full` 在这些路径返回 0/1/2，只有 `perform_upgrade` 成功才 `restart_main` | **已修（2026-10-17）**：新增 `_restart_if_needed()`；检查失败、无更新、下载失败、用户取消、升级失败、升级成功都走同一入口（`--restart` 且主程序不在运行时重启） |

**已符合、无需改动**的项：`.upgrading` 存在性判断、`--upgrading` 作为清理工具、`last_launch_args.json` 格式与 `--autostart` 恢复、`upgrade_failed.flag` 四个字段、`RUNASADMIN` 写法、`config.json` 不读不写、日志目录不删、Source.zip 顶层为源码根、四版本号一致要求。

---

## 3. §9 开放问题逐条回答

### Q1. `upgrade.exe` 如何消费 `MaaAuto_Source.zip`？

**不是文件级替换，也不是自带 Python；是完整的本地重打包。** 当前流程：

1. 下载 `MaaAuto_Source.zip` 到 `%TEMP%\MaaAuto_upgrade_dl_*`；
2. 下载 embeddable Python 3.11.9 到 `<install_parent>\.MaaAuto_upgrade_<ts>\python`；
3. 解压源码到 `<work>\source`（**校验 `main.py`、`build.py` 必须存在**）；
4. `pip install -r requirements.txt`，再装 PyInstaller；
5. 执行 `python build.py`（无参数），产出 `dist/MaaAuto/`；
6. 复制到安装目录，保护 `config/`、`logs/`、`.maaauto.json`；
7. 更新 `.maaauto.json`，清 `.upgrading`，重启主程序。

因此 `MaaAuto_Source.zip` 里 **`build.py`、`main.py`、`requirements.txt`、`resources/`、`themes/`、`i18n/` 以及全部运行时代码都是必需的**；`publish.py`、`deploy_dev.py`、`diagnose.py`、`_version_info.txt`、`.spec`、`__pycache__` 可以没有（`_version_info.txt` 由 `build.py` 重新生成）。当前 `publish.py` 的排除列表是正确的。

升级耗时主要来自“下载 Python + 装依赖 + PyInstaller 打包”，通常几分钟；这也是为什么升级器必须有进度 UI（见 Q5）。

### Q2. `.maaauto.json` 的 schema 是什么？

已冻结为 **v3**，完整定义见安装器 `installer/core/manifest.py`。主程序不读不写；升级器读写。

```json
{
  "version": "2.1.0",
  "installer_version": "1.0.0",
  "manifest_version": 3,
  "install_dir": "D:\\MaaAuto",
  "app_exe": "D:\\MaaAuto\\MaaAuto.exe",
  "uninstall_exe": "D:\\MaaAuto\\uninstall.exe",
  "upgrade_exe": "D:\\MaaAuto\\upgrade.exe",
  "requirements_hash": "…",
  "mirror": "auto",
  "installed_at": "2026-10-17T20:00:00",
  "updated_at": "2026-10-17T20:00:00",
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

要点：

- `manifest_version` 固定 `3`；升级器遇到未知顶层字段会**丢弃**，主程序不要往里加字段。
- `version` 来自源码 `app_info.py / APP_VERSION`；升级后来自新源码。
- `installer_version` 表示“产生当前安装/当前 upgrade.exe 的安装器版本”，不是“最新可用版本”。
- `last_upgrade_from` / `source_hash` / `last_checked_at` 只由升级器写。
- 建议主程序继续保持“不读不写”，避免形成第二份真源。

### Q3. 是否需要主程序把目标版本 / 下载 URL 传给 `upgrade.exe`？

**当前不需要**。现状是主程序只传 `--from-main --restart [--silent]`，升级器自己查 `releases/latest`。这样协议最简单，主程序也不需要理解 asset 结构。

代价是“检查两次”：主程序先查一次，升级器再查一次；两次之间如果 Release 变了，升级器可能得出不同结论。当前可以接受。

如果将来要支持以下场景，建议以 **协议 v1.1** 增加可选参数，而不是改默认行为：

- `--target-version X.Y.Z`：主程序已确定要升到哪个版本，避免二次判断；
- `--source-url <url>`：内网/镜像下载，或预发布版本；
- `--channel beta`：当前 `--channel` 已解析但**未使用**，且 `releases/latest` 不返回 prerelease，beta 需要改用 `/releases` 列表或显式 URL。

在这些参数落地前，主程序**不要**传它们（当前会忽略未知参数，无副作用）。

### Q4. 从 `< v2.1.0` 升级怎么办？

**只能手动覆盖安装，不能自动升级。** 原因：

- 旧版主程序不认 `.upgrading`，也没有 `last_launch_args.json`/`upgrade_failed.flag` 这套东西；
- 旧版 `upgrade.exe`（占位版）不实现本协议；
- 新安装器无法“从旧主程序内部”被调起。

可行路径：让用户下载新版 `MaaAuto_Online_v*-Windows-x64.exe`，安装到**同一目录**。当前安装器会覆盖程序文件、保留 `config/`、`logs/`，并重新写 `.maaauto.json`，可以平滑迁移。建议在主程序 Release Notes 和安装器 README 都写明这一步。

### Q5. `--silent` 失败时是否需要 UI？

**已决议（主程序 Q6，2026-10-17）**：接受一个**不可交互、成功/失败都会自动关闭**的进度窗口，不要求真无 UI。理由：升级要重新下载 Python + 依赖 + PyInstaller 打包，持续数分钟；完全无窗口时用户会以为程序卡死/被杀。主程序会把设置文案从“自动下载并升级（静默）”改为“**自动下载并升级（免确认）**”。

安装器侧保持 `run_ui(mode="silent")`，只需保证：

- 无按钮可点、无确认弹窗、关闭按钮无效；
- 成功/失败都自动关闭；
- 不设置 `AlwaysOnTop` 长时间抢占焦点；
- 失败信息写 `upgrade_failed.flag`（按 Q2 的范围）。

若将来确实需要“真无窗口”，新加 `--no-ui` 参数，**不要**改 `--silent` 的语义。

无论哪种模式，**失败/无更新/取消都必须重启主程序**（前提是调用方传了 `--restart`），这是比“是否弹窗”更重要的体验底线。

### Q6. 是否要求主程序做单实例锁？

**不需要为安装器增加单实例锁。** 理由：

- 升级器停止主程序靠 `.upgrading`，不依赖“只有一个实例”；
- 部署前会无条件写 `.upgrading`（D3 修复后），升级期间用户再启动主程序也会在 1s 内退出；
- 升级器超时兜底是 `taskkill /IM MaaAuto.exe`，会结束所有实例。

如果主程序出于其他产品原因想做单实例，可以另议，但**不要把它作为安装器协议的前置条件**。

### Q7. `uninstall.exe` 的参数与注册表约定？

当前实现与文档存在明确不一致，建议按下面收敛：

| 项 | 建议 |
|---|---|
| 无参数 | 交互式卸载：确认 → 询问是否保留用户数据 → 优雅停止主程序 → 删文件/注册表/快捷方式 |
| `/S` | 静默卸载：不弹任何框；默认**保留** `config/`、`logs/`（与升级不清数据的承诺一致），可用 `/REMOVE_DATA` 覆盖 |
| `/KEEP_DATA` | 显式保留用户数据 |
| `/REMOVE_DATA` | 显式删除用户数据 |
| `UninstallString` | `"<install>\uninstall.exe"`（交互） |
| `QuietUninstallString` | `"<install>\uninstall.exe" /S` —— **只有在 `/S` 真正实现后才写**；当前先删掉这个值，避免“设置 → 应用”里静默卸载仍弹窗 |

同时卸载器需要补齐：优雅停止（D10）、删除 `HKCU\...\Run\MaaAuto`（D9）、删除 `AppCompatFlags` 值、删除快捷方式、`upgrade.exe`/`uninstall.exe` 自删除。

---

## 4. 建议的协议修订（v1.1 草案）

1. **`--silent` 定义**：已确认“不可交互（允许进度窗）”；真无窗口另设 `--no-ui`，不改语义。
2. **停止超时**：统一为 15s（安装器改常量）；主程序轮询保持 1000ms。
3. **标志生命周期**：升级器在“停止阶段结束 → 部署开始前”无条件写 `.upgrading`；所有终止路径（成功/失败/取消/异常）都删除。
4. **终态重启**：只要主程序已退出，升级器在**成功、无更新、失败、用户取消**四种终态都重启主程序（前提是调用方传了 `--restart`）。
5. **失败标志覆盖**：按主程序 Q2 修订版，`run_full` 以退出码 2 结束且非用户取消都写——缺 manifest、版本过低、检查失败、下载失败、停止失败、升级失败、异常；`--check-only`/已最新/取消不写。
6. **卸载契约**：优雅停止 + 删除 Run 键 + `/S` 真正实现；`QuietUninstallString` 与实现保持一致。
7. **`.maaauto.json`**：冻结为 v3，主程序不读不写（与主程序文档 §1.2 一致）。
8. **stub 更新策略**：明确“`upgrade.exe`/`uninstall.exe` 只随完整安装包更新，升级不更新”，并在主程序文档 §1.3 去掉“若新版本自带新版 upgrade.exe”一段，避免误解。
9. **版本/常量冻结**：tag 语法 `X.Y.Z[(a|b|rc)N][.postN]`、`MaaAuto_Source.zip` 固定名、`APP_UPDATE_API` / `APP_SOURCE_ASSET` / `APP_MIN_INSTALLER_VERSION` 三常量冻结；安装器构建期断言（已落地）。

---

## 5. 安装器侧修复清单

### P0（发版前必须）

- [x] `upgrade_stub.run_full`：`request_main_exit` 失败 / 提前返回路径清 `.upgrading`（引擎 + stub + 安装流程三处兜底）。
- [x] 升级器终态统一处理：检查失败、无更新、下载失败、用户取消、升级失败、升级成功都走 `_restart_if_needed()`；`--restart` 且主程序不在运行时重启。
- [x] `run_full` 所有以 2 结束且非取消的终态写 `upgrade_failed.flag`（主程序 Q2 修订）；`--check-only`/已最新/取消不写。
- [x] 与主程序确认 `--silent`：接受不可交互进度窗，文案改“免确认”；无需无窗口分支。
- [x] 构建期断言 `app_info.py` 三常量与 `installer/contract.py` 一致。

**P0/P1 实施记录（2026-10-17）**

| 文件 | 改动 |
|---|---|
| `installer/core/upgrade_engine.py` | `request_main_exit()` 的 taskkill 失败/异常路径调用 `clear_upgrading_flag()` |
| `installer/contract.py` | 新增：冻结的 `manifest.extra` 默认值与 `APP_INFO_CONSTANTS` 映射 |
| `installer/pages/progress.py` | 安装/覆盖安装开始时清理残留的 `config/.upgrading`；manifest 改用 `default_manifest_extra()` |
| `tools/upgrade_stub.py` | 新增 `_restart_if_needed()` 与 `_write_failure()`；停止/下载/异常失败写标志并清标志；终态统一重启；取消不写失败标志 |
| `build_installer.py` | 新增 `check_app_info_contract()`：构建期校验 `APP_VERSION` 格式与三常量，不一致直接失败 |

已用独立冒烟测试验证：主程序在跑时不重复启动；主程序已退出时先清标志再重启；`request_main_exit` 停不掉时标志被删除；`run_full` 七条路径（检查失败/无更新/下载失败/停止失败/成功/失败/取消）均走预期分支。`python -m compileall MaaAutoInstaller` 通过。

### P1

- [ ] 停止阶段结束后、部署开始前**无条件**写 `.upgrading`。
- [ ] `copy_dist_to_install` 增加占用重试（0.5s/1s/2s）。
- [ ] `uninstall.exe`：先写 `.upgrading` 优雅停止，再删文件；删除 `HKCU\...\Run\MaaAuto`；实现 `/S`（或删除 `QuietUninstallString`）。
- [ ] 等待超时从 5s 改为 15s。

### P2

- [ ] 失败时把升级日志复制到 `<install>/logs/upgrade/`，再写 `log_path`。
- [ ] 明确卸载“默认保留数据”还是“默认删除”，与主程序文档统一。
- [ ] 决定 stub 是否随升级更新（当前不更新）。
- [ ] 可选：部署后预创建 `config/`、`logs/` 空目录（权限兜底）。
- [x] `--silent` 窗口：无交互、成功/失败自动关闭、未设置 `AlwaysOnTop`（Q6 已满足）。

---

## 6. 主程序答复回填（2026-10-17）

| 问题 | 主程序答复 | 状态 |
|---|---|---|
| 1. `.upgrading` 兜底 | 已实现 `upgrade_guard.py`：300s + 进程探测，保守优先 | 已解决；安装器侧清标志也已修，双方兜底叠加 |
| 2. 失败标志范围 | Q2（修订）：`run_full` 以 2 结束且非取消都写；`--check-only`/已最新/取消不写 | 已解决；安装器已按此实现 |
| 3. 升级 UI 归属 | Q3：保持“主程序检查 + 升级器复核”，不改 `--check-only` | 已解决 |
| 4. 版本语法 / Asset 名 | Q4：`X.Y.Z[(a\|b\|rc)N][.postN]`，`MaaAuto_Source.zip` 固定名 | 已冻结 |
| 5. 常量同步 | Q5：三常量冻结 + 安装器构建期断言 | 已解决；`check_app_info_contract()` 已落地 |
| 6. `--silent` 语义 | Q6：接受不可交互进度窗，文案改“免确认”；真无窗口另设 `--no-ui` | 已解决 |
| 7. 终态重启 | 主程序未直接表态；安装器已实现“成功/无更新/失败/取消都重启” | **待主程序确认**是否接受（尤其失败时是否希望保持关闭） |
| 8. 卸载默认值 | 主程序答复未涉及 | **待确认**：默认保留还是默认删除（安装器建议默认保留） |
| 9. 预发布版本 | Q4 明确 `releases/latest` 不返回 prerelease | 已明确：短期只支持 stable，beta 走完整包手动安装 |

---

## 7. 明确不需要的东西

| 提议 | 结论 |
|---|---|
| 主程序仓库再写一份 `upgrade.py` 参考实现 | **不需要**。真源是 `tools/upgrade_stub.py` + `installer/core/upgrade_engine.py`，两份实现必然漂移 |
| 主程序传目标版本 / 下载 URL | 当前不需要；作为 v1.1 可选项，等 beta/镜像需求明确再加 |
| 单实例锁 | 不需要作为安装器协议前置条件（见 Q6） |
| 英文翻译 | 暂不需要；协议冻结后再翻 |
| 安装器读取 `config.json` | 不需要，也不会做（主程序文档 §6.2 已正确） |
