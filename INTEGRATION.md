# MaaAuto 安装器 ↔ 主程序 对接说明

> 面向仓库：`mmccz/MaaAuto-Tool-works`（主程序，当前 `APP_VERSION = 2.1.0`）
> 本文对应：`MaaAuto-Installer` 安装器 `1.0.0`（`manifest_version = 3`）
> 状态：主程序已答复（2026-10-17）；本文件已按答复回填决议
> 目的：把两边已经耦合、但分散在代码里的约定集中成一份可核对的清单，避免升级链路各自演进后对不上。
> 对应主程序侧文档：[`INSTALLER_INTEGRATION.md`](../MaaAuto-Tool-works/docs/INSTALLER_INTEGRATION.md)；主程序答复：[`INSTALLER_REPLY.md`](../MaaAuto-Tool-works/docs/INSTALLER_REPLY.md)；安装器侧逐条回复见 [`docs/INSTALLER_RESPONSE.md`](docs/INSTALLER_RESPONSE.md)。

---

## 0. 结论先行（TL;DR）

1. **安装器只把主程序仓库当“源码输入”**：需要 `app_info.py`、`main.py`、`build.py`、`requirements.txt` 和资源目录，不 import 主程序任何代码。
2. **主程序运行时只依赖 `MaaAuto.exe`（onedir，含 `_internal/`）和安装器写入的 `RUNASADMIN` 兼容标志**；升级链路依赖同目录的 `upgrade.exe`；`.maaauto.json` 是“安装器 ↔ 升级器”的契约，主程序**不读也不写**。
3. **升级靠“文件 + 进程”握手**：`config/.upgrading`（升级器写、主程序读并退出）、`config/upgrade_failed.flag`（升级器写、主程序下次启动提示）、`config/last_launch_args.json`（主程序写、升级器重启时读取）。
4. **当前有 1 个 P0 联调风险**：升级器“停不掉主程序”时会残留 `.upgrading`，而主程序启动时看到它就立即 `sys.exit(0)`，用户会表现为“主程序打不开”。
5. **需要主程序确认的 6 件事**见 §12，主要集中在：遗留 `.upgrading` 的处理、失败标志覆盖范围、版本号/Asset 规则、`app_info.py` 常量同步机制。

---

## 1. 角色与边界

| 能力 | 安装器（本仓库） | 主程序（MaaAuto-Tool-works） |
|---|---|---|
| 安装 Python 运行时 | ✅ 下载 embeddable 3.11.9 到临时目录，装完删除 | ❌ 不感知 |
| 安装依赖 / 本地打包 | ✅ `pip install` + 调 `build.py` + PyInstaller | ✅ 提供 `requirements.txt` 和 `build.py` |
| 生成主程序产物 | ✅ 复制 `dist/MaaAuto/` 到安装目录 | ✅ 产物结构由 `build.py` 决定 |
| 卸载器 / 升级器 | ✅ 用户端现场打包并部署 | ❌ 不生成、不修改 |
| 快捷方式 / 注册表 / 元数据 | ✅ 安装时写入 | ❌ 不读、不写 `.maaauto.json` |
| 用户配置 / 日志 | ❌ 只保护，不读写内容 | ✅ `config/`、`logs/` 的唯一主人 |
| 检查更新 | ✅ 升级器内部再检查一次 | ✅ 自己检查并决定是否提示 |
| 下载 / 替换程序 | ✅ `upgrade.exe` 全权负责 | ❌ 只调起 `upgrade.exe` |
| 处理升级中状态 | ✅ 写 `.upgrading`、备份、回滚 | ✅ 轮询 `.upgrading` 并优雅退出 |

**边界原则**：主程序永远不下载、不替换、不打包；安装器永远不解析、不修改 `config.json`。

---

## 2. 安装目录布局

```text
<install_dir>/                     默认 D:\MaaAuto（无 D 盘时 E:，再退 C:）
├── MaaAuto.exe                    ← 主程序入口（名字固定，不可改）
├── _internal/                     ← PyInstaller onedir 运行时
├── resources/                     ← 主程序资源（build.py add-data）
├── themes/                        ← 主题 QSS
├── i18n/                          ← 语言包
├── requirements.txt               ← 主程序依赖清单（build.py 附带）
├── README.md / LICENSE / CHANGELOG.md
├── _version_info.txt
├── uninstall.exe                  ← 安装器部署，独立 exe
├── upgrade.exe                    ← 安装器部署，独立 exe
├── .maaauto.json                  ← 唯一安装元数据（安装器/升级器维护）
├── config/                        ← 主程序用户数据（安装/升级必须保留）
│   ├── config.json
│   ├── .upgrading                 ← 升级中标志（临时）
│   ├── upgrade_failed.flag        ← 升级失败标志（临时）
│   ├── last_launch_args.json      ← 上次启动参数
│   └── ...
└── logs/                          ← 主程序日志（安装/升级必须保留）
    ├── upgrading.log              ← --upgrading 退出日志
    └── upgrade/                   ← 升级成功后复制的升级日志
```

约定：

- `MaaAuto.exe` 必须位于安装目录**顶层**。主程序用 `sys.executable` 的父目录作为 `BASE_DIR`，`config/`、`logs/` 都在这里。
- 升级覆盖安装目录时，安装器**保护**顶层 `config/`、`logs/`、`.maaauto.json`，其余按产物覆盖。
- `uninstall.exe`、`upgrade.exe` 不属于主程序打包产物；升级时**不会**被重新生成（见 §11-R3）。
- 安装目录允许非空，但安装器只会覆盖自己的产物，不会清空整目录。

---

## 3. `.maaauto.json` 契约（v3）

位置：`<install_dir>/.maaauto.json`，UTF-8 无 BOM，缩进 2。

### 3.1 示例

```json
{
  "version": "2.1.0",
  "installer_version": "1.0.0",
  "manifest_version": 3,
  "install_dir": "D:\\MaaAuto",
  "app_exe": "D:\\MaaAuto\\MaaAuto.exe",
  "uninstall_exe": "D:\\MaaAuto\\uninstall.exe",
  "upgrade_exe": "D:\\MaaAuto\\upgrade.exe",
  "requirements_hash": "a3f2...",
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

### 3.2 字段

| 字段 | 写入方 | 含义 / 注意事项 |
|---|---|---|
| `version` | 安装器 / 升级器 | 主程序版本，来自源码 `app_info.py` 的 `APP_VERSION`；升级后来自新源码 |
| `installer_version` | 安装器 / 升级器 | 产生当前安装（或当前 `upgrade.exe`）的安装器版本。**不是**“最新可用安装器版本” |
| `manifest_version` | 安装器 / 升级器 | 当前固定 `3`；读取方需按此判断兼容性 |
| `install_dir` / `app_exe` / `uninstall_exe` / `upgrade_exe` | 安装器 | 绝对路径；升级后 `app_exe` 等不变 |
| `requirements_hash` | 安装器 / 升级器 | `requirements.txt` 的 sha256；**目前仅记录，升级不做增量判断** |
| `mirror` | 安装器 | 用户选择的 **PyPI 镜像 key**（`auto/tuna/aliyun/ustc/pypi`），不是 Python 下载源 |
| `installed_at` / `updated_at` | 安装器 / 升级器 | ISO 8601（秒精度）；首次写 manifest 时补 `installed_at` |
| `release_channel` | 安装器 | 当前恒为 `stable`；`--channel` 参数尚未生效 |
| `last_checked_at` | 升级器 | 升级检查成功时写入 |
| `last_upgrade_from` | 升级器 | 升级前版本 |
| `source_hash` | 升级器 | 本次升级所用的 `MaaAuto_Source.zip` sha256 |
| `extra.update_api` | 安装器（硬编码） | GitHub Release API；升级器读它 |
| `extra.source_asset_name` | 安装器（硬编码） | 升级器只认这个名字的 asset |
| `extra.min_installer_version` | 安装器（硬编码） | 低于此版本的升级器拒绝升级 |
| `extra.github_url` | 安装器（硬编码） | 仅展示用途 |
| `extra.online_asset_pattern` | 安装器（硬编码） | 命名约定，代码未使用 |
| `extra.launch_args` | 安装器（硬编码 `[]`） | 预留，代码未使用（启动参数实际走 `last_launch_args.json`） |
| `extra.release_channel` | 安装器（硬编码） | 与顶层字段重复，预留 |

> ⚠️ `extra` 里的 4 个关键值（`update_api`、`source_asset_name`、`min_installer_version`、`github_url`）目前是**安装器侧硬编码**，与主程序 `app_info.py` 的 `APP_UPDATE_API`、`APP_SOURCE_ASSET`、`APP_MIN_INSTALLER_VERSION` 重复。主程序改这些常量时，**必须同步通知安装器**，否则新装用户拿到的 manifest 仍指向旧地址/旧约束。

### 3.3 读写规则

- **主程序运行时不读也不写**（当前实现确实如此）；不要为了“记录版本”新增对它的依赖，也不要改它。真正读它的是 `upgrade.exe`。
- 安装器/升级器写；反序列化时会**丢弃未知顶层字段**，所以不要往顶层加自定义键。
- 卸载器不依赖它：`uninstall.exe` 以自身所在目录为安装目录；manifest 只用于显示版本。
- 升级器在找不到 `.maaauto.json` 时直接报错退出（退出码 2），不会尝试修复。

---

## 4. 升级时序（主程序视角）

```text
主程序启动
  └─ 5s 后（auto_check_update=true）后台检查 GitHub
       ├─ 无更新 → 结束
       ├─ 有更新 + 未开自动下载 → 托盘提示（主程序不退出）
       └─ 有更新 + 开启自动下载
            ├─ 任务运行中 → 挂起，任务结束后再触发
            └─ 空闲 → apply_update(silent=True)

用户手动升级（关于页/提示）
  └─ apply_update(silent=False)

apply_update()
  └─ Popen(<install>\upgrade.exe --from-main --restart [--silent])
       └─ 返回 True → 主程序保存配置、清理子进程、退出

upgrade.exe
  1. 读 .maaauto.json
  2. GitHub Release API → 版本比较（PEP 440 简化版）
  3. 下载 MaaAuto_Source.zip → 可选 sha256 校验
  4. 写 config/.upgrading
  5. 主程序每秒轮询到标志 → 保存配置/清理子进程 → 退出
  6. 最多等 5s；仍未退出 → taskkill /F /IM MaaAuto.exe
  7. 备份安装目录 → %TEMP%\MaaAuto_backup_*.zip
  8. 重跑安装流水线（下载 Python、装依赖、PyInstaller 打包）
  9. 覆盖安装目录（保留 config/、logs/、.maaauto.json）
 10. 更新 .maaauto.json（version/last_upgrade_from/source_hash/...）
 11. 清 config/.upgrading、清理临时目录
 12. 读 config/last_launch_args.json → 重启 MaaAuto.exe

失败/无更新/取消路径
  └─ 尽量回滚 → 写 config/upgrade_failed.flag（取消不写）→ 清 .upgrading
     → 若主程序已退出且带 --restart：同样重启主程序，避免用户被搁在关闭状态
```

时间参数（当前实现）：

| 项 | 值 | 位置 |
|---|---|---|
| 主程序自动检查延迟 | 5s | `ui/main_window.py` |
| 主程序轮询 `.upgrading` | 1000ms | `ui/main_window.py` |
| 升级器等待主程序退出 | 5s（0.1s 轮询） | `installer/core/upgrade_engine.py` |
| 超时后强制结束 | `taskkill /F /IM MaaAuto.exe` | 同上 |
| 升级成功后重启前等待 | 1s | `tools/upgrade_stub.py` |
| 失败标志检查延迟 | 启动后 300ms | `main.py` |

---

## 5. 文件 / 进程握手

| 文件 | 写入方 | 读取方 | 格式 | 生命周期 |
|---|---|---|---|---|
| `config/.upgrading` | `upgrade.exe` | 主程序（启动时 + 每秒轮询） | 纯文本 `upgrading`（**不是 JSON**） | 升级器 `finally` 删除；正常情况下重启主程序前已删 |
| `config/upgrade_failed.flag` | `upgrade.exe` | 主程序（启动 300ms 后） | JSON（见下） | 主程序读取并弹窗后删除 |
| `config/last_launch_args.json` | 主程序（每次启动） | `upgrade.exe`（重启时） | `{"args": [...], "written_at": "..."}` | 每次启动覆盖；升级器只读 `args` |
| `logs/upgrading.log` | 主程序（`--upgrading` 模式） | 人工排查 | 文本日志 | 追加 |
| `logs/upgrade/<ts>.log` | `upgrade.exe`（成功后复制） | 人工排查 | 文本日志 | 保留 |
| `%TEMP%\MaaAuto_upgrade_<ts>.log` | `upgrade.exe` | 人工排查 | 文本日志 | 升级器主日志，成功/失败都保留 |

### 5.1 `upgrade_failed.flag` 结构

```json
{
  "failed_at": "2026-10-17T20:15:00",
  "from_version": "2.1.0",
  "to_version": "2.2.0",
  "reason": "pip 退出码 1",
  "log_path": "C:\\Users\\xxx\\AppData\\Local\\Temp\\MaaAuto_upgrade_20261017_201000.log"
}
```

主程序当前行为：读取 → `QMessageBox.warning` 展示 → 删除文件。字段缺失时用 `?`/“未知”兜底。

### 5.2 主程序启动时的 `.upgrading` 判断

```python
# main.py 当前实现
if os.path.exists(os.path.join(CONFIG_DIR, ".upgrading")):
    sys.exit(0)
```

没有时间戳、没有检查 `upgrade.exe` 是否仍在运行。**这是 P0 风险的一半**，见 §11-R1。

### 5.3 `--upgrading` 命令行参数

主程序 `main.py` 支持 `--upgrading`，但**当前没有任何一方传它**：升级器走的是标志文件，不是命令行。该参数保留为“外部要求主程序立即优雅退出”的入口，不建议删除。

---

## 6. `upgrade.exe` 命令行契约

主程序当前调用：

```text
<install>\upgrade.exe --from-main --restart [--silent]
```

| 参数 | 语义 | 现状备注 |
|---|---|---|
| `--from-main` | 必须；缺失时弹提示并退出 | 防用户直接双击；实际返回码是 `0`，不是错误码 2 |
| `--silent` | 有 UI 但不可交互（无取消、不可关） | `--silent --check-only` 时完全无 UI。主程序已确认接受“不可交互进度窗”，文案改为“免确认”；真无窗口留待 `--no-ui` |
| `--check-only` | 只检查；交互模式展示 UI + “立即升级” | 主程序目前**不传**，因为它自己先检查过 |
| `--restart` | 升级成功后重启主程序 | 参数已解析但**未使用**：当前实现成功后总是重启（主程序总是带此参数，故无实际影响） |
| `--downgrade` | 允许降级 | 主程序不传 |
| `--channel stable\|beta` | 更新通道 | 已解析但**未使用**：始终取 `releases/latest` |

### 6.1 退出码

| 退出码 | 文档语义 | 实际行为 |
|---|---|---|
| `0` | 成功 / 有新版 | 升级成功；`--check-only` 且发现新版；非 `--check-only` 且已是最新 |
| `1` | 已是最新 | **仅 `--check-only` 模式**返回 1；完整升级模式下“已是最新”返回 0 |
| `2` | 错误 | 检查失败、下载失败、无法停止主程序、升级失败等 |

> 主程序目前用 `subprocess.Popen` 调起后不等待、不读退出码。若将来需要根据结果做 UI，建议不要依赖退出码，改为读 `upgrade_failed.flag` 或让升级器通过退出码以外的方式回传。

---

## 7. 主程序必须保持的输入契约

### 7.1 `app_info.py`

安装器在打包时和升级时都用正则读取：

```python
re.search(r'^APP_VERSION\s*=\s*["\']([^"\']*)["\']', text, re.M)
```

要求：

- `APP_VERSION = "2.1.0"` 必须**单独一行、从行首开始**。
- 不要改成 `APP_VERSION: str = "2.1.0"`、`APP_VERSION = str(2.1)`、多行拼接或从环境变量读取；否则安装器读到 `0.0.0`，导致 manifest 版本、产物文件名全部错误。
- `APP_UPDATE_API`、`APP_MIN_INSTALLER_VERSION`、`APP_SOURCE_ASSET` 目前与安装器硬编码值重复，改动需同步（见 §12-Q5）。

### 7.2 `build.py`

安装器执行：

```text
python build.py        # cwd = 解压后的源码根；不传任何参数
```

要求：

- **无参数、无交互**即可完成 onedir 打包。
- 产物固定为 `dist/MaaAuto/MaaAuto.exe`（目录名、exe 名不可变）。
- 安装器会在调用前删除 `dist/` 和 `build/`；`build.py` 不要依赖旧产物。
- 安装器允许 `build.py` 返回非 0，只要 `dist/MaaAuto/MaaAuto.exe` 存在（对 PyInstaller 的 warning 较宽容）；但请尽量保持 0。
- 不要要求管理员权限、不要写安装目录、不要弹窗。
- 安装器为子进程设置了 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`，日志按 UTF-8 读取；仍建议输出以 ASCII 为主（历史上有 GBK 控制台 emoji 崩溃问题）。

### 7.3 `requirements.txt`

- 必须能被 Python 3.11 embeddable 安装（有对应 wheel）。
- **必须包含 PySide6**：升级器的进度 UI 是安装时用这份依赖现打的；主程序若移除 PySide6，升级器会失去 UI（会降级为错误提示，功能不完整）。
- 建议保留 `packaging`（主程序 `update_checker` 使用）。
- 安装器会把 `#` 注释剥掉、丢弃含非 ASCII 的行后交给 pip；不要在依赖行里写中文或本地路径。

### 7.4 源码包 / 源码目录结构

`MaaAuto_Source.zip`（以及传给 `build_installer.py --source-dir` 的目录）要求：

```text
main.py
app_info.py
build.py
requirements.txt
ui/ themes/ i18n/ resources/
...
```

- **顶层直接是源码根，不含 `MaaAutoProject/` 这一层**。
- 必须包含 `main.py`、`build.py`（安装器会校验）；否则解压阶段直接失败。
- 资源目录需与 `build.py` 的 `add-data` 配置一致。
- 不要把 `config/`、`logs/`、`dist/`、`build/`、`release/` 打进源码包。
  - `publish.py` 生成的 `MaaAuto_Source.zip` 已排除它们；
  - 但 `build_installer.py --source-dir` 直接指向开发目录时，安装器只排除 `config/logs/dist/build`，**不排除 `release/`**，构建前请清理。
- 不要把 `.maaauto.json` 放进源码。

### 7.5 运行时假设

- 产物是 **onedir**，主程序通过 `sys._MEIPASS`（即 `_internal/`）找 `resources/themes/i18n`。
- 安装目录含空格、中文路径时也应正常工作（安装器只保证自身路径处理；主程序资源加载建议用 `sys._MEIPASS`，不要拼 `sys.argv[0]`）。
- 主程序进程名固定为 `MaaAuto.exe`（升级器/卸载器/taskkill 都按这个名字找）。

---

## 8. Release / 版本契约

### 8.1 Tag

必须使用 PEP 440 格式，安装器与主程序的解析器都能接受：

| Tag | 是否可用 |
|---|---|
| `v2.1.0` / `2.1.0` | ✅ |
| `v2.1.0b1` / `v2.1.0rc2` | ✅ |
| `v2.1.0.post1` | ✅（安装器正则支持） |
| `v2.1.0-beta` / `2.1.0-beta.1` | ❌ |
| `v2.1.0.dev1` / `2.1.0+local` | ❌ 安装器解析器不接受（主程序 `packaging` 接受，会出现“主程序说有新版、升级器说无法解析”） |

建议：CI 用 `^v?\d+\.\d+\.\d+((a|b|rc)\d+)?(\.post\d+)?$` 校验 tag。

### 8.2 Asset

同一个 Release 必须同时上传：

| Asset | 用途 | 命名要求 |
|---|---|---|
| `MaaAuto_Online_v{APP_VERSION}-Windows-x64.exe` | 新用户安装 | 约定；安装器不读此名字 |
| `MaaAuto_Source.zip` | 已装用户升级 | **必须精确等于** `MaaAuto_Source.zip` |

注意：

- 主程序 `update_checker` 找 asset 的顺序是：精确名 → 含 `win` 的 zip → 任意 zip；**但升级器只认精确名**（`extra.source_asset_name`）。如果 Release 里只有 `MaaAuto_Source-v2.2.0.zip`，主程序会提示有更新，调起升级器后升级器却报“Release 里没有找到 asset”。**请只用固定名。**
- GitHub asset 若带 `digest`（`sha256:...`），升级器会校验；没有则跳过校验（不阻塞）。
- `APP_VERSION` 必须与 tag 去掉 `v` 后一致；安装器用 `APP_VERSION` 生成安装包文件名。

### 8.3 版本比较器差异

| 场景 | 主程序（`packaging.version`） | 安装器（自研正则） |
|---|---|---|
| `2.1.0` / `v2.1.0` | ✅ | ✅ |
| `2.1.0b1` / `rc` / `post` | ✅ | ✅ |
| `.devN`、`+local`、`-beta` | 部分接受 | ❌ |
| 非法版本 | 检查失败 | 检查失败/不升级 |

结论：**只用两套解析器都支持的子集**。升级链路的最终判断在升级器，主程序的提示不能超出升级器能处理的范围。

---

## 9. 权限与注册表

### 9.1 权限模型（2026-09-20 起）

- 安装器以 `--uac-admin` 打包，安装全过程需要管理员权限（要写 HKLM）。
- 安装器为 `MaaAuto.exe` 写入 `RUNASADMIN` 兼容标志：

  ```text
  HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers
      值名：<install_dir>\MaaAuto.exe
      值：  "~ RUNASADMIN"
  ```

- 主程序 **v2.1.0 已移除自我提权**，依赖上述标志；因此正常安装后主程序每次启动都会弹 UAC，`is_admin()` 恒为 True。
- ⚠️ 如果主程序重新加入 `ShellExecuteW("runas")` 自我提权，会与 `RUNASADMIN` 形成二次 UAC；如果安装器将来不再写该标志，主程序将失去管理员权限。**这条契约变更必须双方同步。**
- `uninstall.exe` 以 `--uac-admin` 打包（删 HKLM）；`upgrade.exe` **不提权**，但由已提权的主程序调起时会继承管理员令牌。

### 9.2 注册表项

| 位置 | 内容 | 写入/删除 |
|---|---|---|
| `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MaaAuto` | `DisplayName` / `DisplayVersion` / `Publisher` / `InstallLocation` / `InstallDate` / `DisplayIcon` / `UninstallString` / `QuietUninstallString` / `EstimatedSize` / `NoModify` / `NoRepair` | 安装器写；`uninstall.exe` 删 |
| `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\MaaAuto.exe` | 默认值 = exe 路径；`Path` = 安装目录 | 同上 |
| `HKCU\...\AppCompatFlags\Layers` | `RUNASADMIN` 标志 | 安装器写；`uninstall.exe` 删 |

已知缺口：**升级器不会刷新 `DisplayVersion` / `EstimatedSize`**，所以升级后“设置 → 应用”里仍显示旧版本。属于展示问题，不影响主程序运行。

---

## 10. 双方 Do / Don't

### 安装器侧（本仓库）

| Do | Don't |
|---|---|
| 覆盖时保护 `config/`、`logs/`、`.maaauto.json` | 不读写 `config.json` 的内容 |
| 升级成功后清 `.upgrading`、失败时写 `upgrade_failed.flag` | 不在主程序运行时直接改 `MaaAuto.exe` |
| 用 `last_launch_args.json` 恢复启动参数 | 不自己决定“是否重启”（目前总是重启） |
| 保证 `MaaAuto.exe`、`uninstall.exe`、`upgrade.exe` 在顶层 | 不删除安装目录里的其他用户文件 |

### 主程序侧

| Do | Don't |
|---|---|
| 只用 `sys.executable` 的目录作为 `BASE_DIR` | 不把 `config/`、`logs/` 写到 CWD 或用户目录 |
| 升级前保存配置、清理子进程 | 不自己下载/替换 `MaaAuto.exe` |
| 调起 `upgrade.exe` 后退出 | 不等待/不依赖升级器退出码 |
| 保持 `APP_VERSION` 可被行首正则读取 | 不读、不写 `.maaauto.json`（不要新增依赖） |
| 启动时处理 `.upgrading`（建议加“陈旧判断”） | 不删除安装目录里的 `uninstall.exe`/`upgrade.exe` |
| 保持 `MaaAuto.exe` 进程名不变 | 不把 `upgrade.exe` 加入“退出时强杀”名单 |

---

## 11. 已知风险（影响主程序）

| ID | 级别 | 现象 | 归属 | 建议 |
|---|---|---|---|---|
| R1 | **P0** | 升级器“停不掉主程序”时（`request_main_exit` 返回 False）直接 `return 2`，**未删除刚写的 `config/.upgrading`**。主程序下次启动看到文件立即 `sys.exit(0)`，表现为双击无反应/闪退 | 安装器（主因）+ 主程序（兜底） | **双方均已修（2026-10-17）**：安装器在 `request_main_exit` 失败、`run_full` 停止失败、安装/覆盖安装开始时清标志；主程序新增 `upgrade_guard.py`（300s + 进程探测）处理“升级器被强杀”等安装器无法覆盖的残留 |
| R2 | P1 | `--silent` 升级仍会显示一个不可交互的进度窗口，并非完全静默 | 双方认知 | **已决议（主程序 Q6）**：接受该窗口；主程序文案改为“自动下载并升级（免确认）”。真无窗口另设 `--no-ui`，不改 `--silent` 语义 |
| R3 | P1 | 升级**不会重新打包/更新** `uninstall.exe`、`upgrade.exe`，也不会刷新注册表；旧版升级器会一直沿用 | 安装器 | 主程序不要假设“升级后 `upgrade.exe` 是最新版”；如需强制更新升级器，需要安装器增补逻辑（或让用户重装完整包） |
| R4 | P1 | 原先只有 `perform_upgrade` 内部失败才写 `upgrade_failed.flag` | 安装器 | **已修（2026-10-17，按主程序 Q2 修订版）**：`run_full` 以退出码 2 结束且非用户取消都写——缺 `.maaauto.json`、升级器版本过低、检查更新失败、下载失败、无法停止主程序、升级失败、未捕获异常；`--check-only`、已是最新、用户取消不写 |
| R5 | P2 | 退出码语义与 README 不一致（非 `--check-only` 时“已是最新”返回 0） | 安装器 | 主程序不要依赖退出码；安装器统一语义 |
| R6 | P2 | 主程序与升级器使用不同版本解析器，`.dev`/`+local` tag 会出现“主程序说有新版、升级器不升级” | 双方 | 发布流程限制 tag 语法（§8.1） |
| R7 | P2 | `app_info.py` 的 `APP_UPDATE_API` / `APP_MIN_INSTALLER_VERSION` / `APP_SOURCE_ASSET` 与安装器硬编码值重复 | 双方 | **已冻结（主程序 Q5）**：三常量视为协议常量；安装器新增 `installer/contract.py`，`build_installer.py` 构建期强校验，不一致直接失败 |
| R8 | P2 | 升级超时走 `taskkill /F` 时，主程序可能来不及保存配置（优雅退出路径会保存） | 双方 | 主程序尽量把配置落盘提前；升级器可提示用户手动关闭 |
| R9 | P2 | 安装过程在“复制产物之后、写 manifest 之前”被中止时，已部署的主程序缺少 `.maaauto.json`；若中止发生在“部署 stub”之前，还会缺 `uninstall.exe`/`upgrade.exe` | 安装器 | 本地打包耗时长，建议提前写临时 manifest 或失败回滚；主程序侧无感知 |
| R10 | P3 | `upgrade.exe` 的参数 `--restart` 未使用（总是重启） | 安装器 | **已修（2026-10-17）**：终态重启改为受 `--restart` 控制（主程序恒传，行为不变） |
| R11 | P3 | 安装器“清理临时文件”会清空用户全局 pip 缓存（`%LOCALAPPDATA%\pip\cache`），与其他 Python 项目互相影响 | 安装器 | 选项文案需明确，或只清本次缓存 |

> 注：R1 的盲区是 `perform_upgrade()` **之前**的停止失败路径；`perform_upgrade()` 内部失败的清理由其 `finally` 覆盖，本来就正常。

### 安装器内部待修（不阻塞主程序，供知悉）

- ~~选择 `tuna/aliyun/ustc/pypi` 镜像时，Python embeddable 下载实际回落到 `python.org`（镜像 key 映射错误），国内安装可能变慢/失败。~~ **已修（2026-10-17）**：`resolve_python_mirror()` 对未知 key（含 PyPI 镜像 key）改按 `auto` 处理（国内→华为云），不再回落官方站。
- 进度页重复创建了两个提示标签，静态提示会一直显示。
- 中止安装后可能留下半安装目录（见 R9）。

---

## 12. 主程序答复与遗留问题（2026-10-17）

| 问题 | 主程序答复 | 状态 |
|---|---|---|
| `.upgrading` 兜底 | `upgrade_guard.py`：300s + 进程探测 | 已解决（双方兜底） |
| 失败提示范围 | `run_full` 以退出码 2 结束且非用户取消都写（含缺 manifest、版本过低、检查失败）；`--check-only`/已最新/取消不写 | 已解决（安装器已按此实现） |
| 升级 UI 归属 | 保持“主程序检查 + 升级器复核”，不改 `--check-only` | 已解决 |
| 版本 / Asset 冻结 | `X.Y.Z[(a\|b\|rc)N][.postN]`，`MaaAuto_Source.zip` 固定名 | 已冻结 |
| 常量同步 | 三常量冻结 + 安装器构建期断言 | 已解决（`installer/contract.py` + `check_app_info_contract()`） |
| “静默升级”定义 | 接受不可交互进度窗，文案改“免确认”；真无窗口另设 `--no-ui` | 已解决 |
| 终态重启 | 主程序未直接表态；安装器已实现失败/无更新/取消都重启 | **待主程序确认** |
| 卸载默认值 | 主程序答复未涉及 | **待确认**：默认保留还是删除用户数据 |

---

## 13. 联调 Checklist

### 13.1 构建前

- [ ] `MaaAutoProject/app_info.py` 的 `APP_VERSION` 行首可被正则匹配
- [ ] `main.py`、`build.py`、`requirements.txt` 在源码根
- [ ] `requirements.txt` 含 PySide6、packaging
- [ ] `python build.py` 无参数可产出 `dist/MaaAuto/MaaAuto.exe`
- [ ] 源码目录不含 `release/*.zip`、`config/`、`logs/`、`dist/`
- [ ] Release 两个 asset 命名正确

### 13.2 安装后

- [ ] `MaaAuto.exe`、`uninstall.exe`、`upgrade.exe`、`.maaauto.json` 都在安装目录顶层
- [ ] `.maaauto.json.version` == `APP_VERSION`，`manifest_version` == 3
- [ ] `HKLM\...\Uninstall\MaaAuto\DisplayVersion` == `APP_VERSION`
- [ ] `HKCU\...\AppCompatFlags\Layers` 存在 `MaaAuto.exe` → `~ RUNASADMIN`
- [ ] 启动主程序弹 UAC，`is_admin()` 为 True
- [ ] `config/`、`logs/` 由主程序创建，位置在安装目录

### 13.3 升级

- [ ] 主程序退出后 `.upgrading` 被删除
- [ ] 升级后 `config/config.json`、`logs/` 内容保留
- [ ] 升级后 `MaaAuto.exe` 版本 == 新 tag
- [ ] 升级后主程序按 `last_launch_args.json` 的参数重启（包括 `--autostart`）
- [ ] 升级失败时 `upgrade_failed.flag` 字段完整，主程序下次启动能提示并删除
- [ ] 手动结束 `upgrade.exe` 模拟崩溃后，主程序仍能启动（R1 兜底；**修复前此项预期失败**）
- [ ] 断网/错误 tag 场景下，升级器不会破坏现有安装

### 13.4 命令示例（PowerShell）

```powershell
# 退出码（windowed exe 必须 -Wait -PassThru）
$p = Start-Process -FilePath "D:\MaaAuto\upgrade.exe" `
     -ArgumentList "--from-main","--check-only","--silent" `
     -Wait -PassThru
"exit code: $($p.ExitCode)"

# 查看 manifest
Get-Content "D:\MaaAuto\.maaauto.json" -Raw | ConvertFrom-Json | Format-List

# 查看注册表版本
Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MaaAuto"
```

---

## 附录 A. 主程序侧对照代码位置

| 主程序文件 | 与本契约相关的内容 |
|---|---|
| `MaaAutoProject/app_info.py` | `APP_VERSION`（安装器正则读取）、`APP_UPDATE_API`、`APP_MIN_INSTALLER_VERSION`、`APP_SOURCE_ASSET`（需与安装器同步） |
| `MaaAutoProject/update_checker.py` | `check_update()` 自行检查；`apply_update()` 调起 `upgrade.exe` 的唯一入口；asset 选择顺序 |
| `MaaAutoProject/main.py` | `.upgrading` 启动兜底、`upgrade_failed.flag` 提示并删除、`last_launch_args.json` 写入、`--upgrading` 模式 |
| `MaaAutoProject/ui/main_window.py` | 每秒轮询 `.upgrading`、启动 5s 后自动检查、自动升级挂起/触发、退出前保存配置与清理 |
| `MaaAutoProject/config_manager.py` | `BASE_DIR = exe 目录`，`CONFIG_DIR` / `LOG_DIR` 的定义 |
| `MaaAutoProject/process_utils.py` | `WHITE_LIST` 已包含 `upgrade.exe` / `uninstall.exe`，避免被“前台程序清理”误杀 |
| `MaaAutoProject/build.py` | onedir 产物 `dist/MaaAuto/MaaAuto.exe`、`_internal/`、顶层附带文件 |
| `MaaAutoProject/publish.py` | `MaaAuto_Source.zip` 顶层为源码根、PEP 440 tag 提示 |
| `MaaAutoProject/deploy_dev.py` | 开发部署时保留 `config/logs/.maaauto.json/upgrade.exe/uninstall.exe`，与安装器覆盖策略一致 |

---

## 14. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09 | 升级契约冻结：`manifest_version = 3`、`MaaAuto_Source.zip` 顶层为源码根、主程序只检查不替换 |
| 2026-09-20 | 主程序 v2.1.0 移除自我提权，改为依赖安装器写入的 `RUNASADMIN` 标志 |
| 2026-09-20 | 安装器 1.0.0：改为内嵌 `stubs_source.zip`，卸载器/升级器在用户端现场打包；升级不再重建 stub |
| 2026-10-17 | 本文档整理，用于与主程序侧对齐；列出 R1–R11 与 6 个待确认问题 |
| 2026-10-17 | 主程序答复（`INSTALLER_REPLY.md`）：`upgrade_guard.py` 300s 兜底、Q2 失败标志范围、Q3 保持复核、Q4 版本/Asset 冻结、Q5 常量冻结、Q6 接受不可交互窗口 |
| 2026-10-17 | 安装器修复：`.upgrading` 全路径清理、终态重启、停止/下载/异常失败标志、`installer/contract.py` 构建期断言 |
| 2026-10-17 | Q2 口径修正：失败标志扩大为「`run_full` 以 2 结束且非取消」（补缺 manifest / 版本过低 / 检查失败三条路径），与主程序 `INSTALLER_REPLY.md` §2 修订表一致；`resolve_python_mirror()` 未知 key 改按 `auto` 处理 |
