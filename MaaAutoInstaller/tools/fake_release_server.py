#!/usr/bin/env python
"""本地假 Release 服务器：**不联网**也能把升级链路从头到尾跑一遍。

为什么需要它
------------
真实升级要等 GitHub 上有 Release 才能测，而升级链路（查版本 → 下载 → sha256
校验 → 停主程序 → 解压替换 → 回滚 → 更新 manifest → 重启）恰恰是最容易出错的
一段。这个脚本用 `http.server` 模拟 GitHub Releases API 的形状，把本地构建出来的
`MaaAuto_payload_v{ver}.zip` 当作「远端资产」提供出去，于是升级器会完全按真实
流程跑，只是 URL 指向 127.0.0.1。

用法（两步）
------------
1. 起服务（会打印注入命令）：

    python tools/fake_release_server.py --payload ..\\dist\\MaaAuto_payload_v1.0.2.zip

2. 让目标安装目录指向本地服务，然后跑升级器：

    # 该脚本可以直接帮你改 .maaauto.json（只改 extra.update_api）
    python tools/fake_release_server.py --payload ..\\dist\\MaaAuto_payload_v1.0.2.zip ^
        --patch-manifest C:\\MaaAutoTest\\app

    C:\\MaaAutoTest\\app\\upgrade.exe --from-main --check-only --no-ui
    C:\\MaaAutoTest\\app\\upgrade.exe --from-main --no-ui

注意
----
* 只用于本地测试。`--patch-manifest` 会把 `extra.update_api` 改成
  `http://127.0.0.1:<port>/releases/latest`；测试完记得用完整安装包重装，
  或把该字段改回 GitHub 地址，否则程序会一直查本地地址。
* 服务按 GitHub 的形状返回 `digest: "sha256:..."`，所以升级器的**校验分支**
  同样会被真实执行（校验失败 → 回滚 + 写 upgrade_failed.flag）。
* 想让校验失败（测试回滚），加 `--corrupt-digest`。
"""

import argparse
import hashlib
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_PORT = 8765


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_version(payload: Path) -> str:
    m = re.search(r"payload_v(.+)\.zip$", payload.name)
    return m.group(1) if m else "0.0.0"


def build_release(base_url: str, version: str, tag: str, payload: Path,
                  sha: str, size: int, notes: str) -> dict:
    return {
        "tag_name": tag,
        "name": f"MaaAuto {tag}",
        "body": notes,
        "html_url": f"{base_url}/releases/{tag}",
        "draft": False,
        "prerelease": bool(re.search(r"(?:a|b|rc)\d+$", version)),
        "published_at": "2026-01-01T00:00:00Z",
        "assets": [
            {
                "name": payload.name,
                "browser_download_url": f"{base_url}/download/{payload.name}",
                "size": size,
                "content_type": "application/zip",
                "digest": f"sha256:{sha}",
            }
        ],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MaaAutoFakeRelease/1.0"

    # ---- 由 main() 注入 ----
    release: dict = None
    payload_path: Path = None

    def log_message(self, fmt, *args):        # 默认会刷屏，简化
        print(f"  [http] {self.address_string()} {fmt % args}")

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):                          # noqa: N802 (http.server 约定)
        path = self.path.split("?")[0]

        if path in ("/releases/latest", "/releases/latest/"):
            return self._send_json(self.release)

        if path.rstrip("/") == "/releases":
            return self._send_json([self.release])

        if path.startswith("/download/"):
            name = path[len("/download/"):]
            if name != self.payload_path.name:
                return self._send_json({"message": "not found"}, 404)
            size = self.payload_path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with open(self.payload_path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return

        if path == "/health":
            return self._send_json({"ok": True, "payload": self.payload_path.name})

        return self._send_json({"message": "not found"}, 404)


def patch_manifest(install_dir: Path, api: str) -> bool:
    """把测试安装目录的 extra.update_api 指向本地假服务。"""
    path = install_dir / ".maaauto.json"
    if not path.exists():
        print(f"[!] 找不到 {path}，先跑一次完整安装包")
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    extra = data.setdefault("extra", {})
    old = extra.get("update_api")
    extra["update_api"] = api
    # 让升级器认为「当前版本更旧」，否则同一版本不会触发升级
    data["version"] = "1.0.0"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] 已把 {path} 的 version 改成 1.0.0，update_api 改为本地：")
    print(f"     旧值: {old}")
    print(f"     新值: {api}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="本地假 Release 服务器（升级链路离线测试）")
    ap.add_argument("--payload", required=True, help="本地 payload zip 路径")
    ap.add_argument("--version", default="", help="版本号，默认从文件名推断")
    ap.add_argument("--tag", default="", help="tag 名，默认 v{version}")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--base-url", default="", help="对外地址，默认 http://host:port")
    ap.add_argument("--notes", default="本地假 Release，用于离线验证升级链路")
    ap.add_argument("--corrupt-digest", action="store_true",
                    help="故意返回错误 sha256（测校验失败 → 回滚）")
    ap.add_argument("--patch-manifest", default="",
                    help="顺手把这个安装目录的 extra.update_api 指向本服务")
    args = ap.parse_args()

    payload = Path(args.payload).resolve()
    if not payload.exists():
        print(f"[!] payload 不存在: {payload}")
        return 2

    version = args.version or guess_version(payload)
    tag = args.tag or f"v{version}"
    base_url = args.base_url or f"http://{args.host}:{args.port}"
    api = f"{base_url}/releases/latest"

    sha = sha256_of(payload)
    if args.corrupt_digest:
        sha = "0" * 64
        print("[!] --corrupt-digest：返回的 sha256 是假的，升级应在校验阶段失败并回滚")

    release = build_release(base_url, version, tag, payload, sha,
                            payload.stat().st_size, args.notes)
    Handler.release = release
    Handler.payload_path = payload

    print("=" * 68)
    print(f"假 Release 已就绪：{tag}（payload {payload.name}，"
          f"{payload.stat().st_size / 1048576:.1f} MB）")
    print(f"  更新接口: {api}")
    print(f"  channel : stable → /releases/latest ；beta → /releases")
    print("=" * 68)

    if args.patch_manifest:
        patch_manifest(Path(args.patch_manifest), api)

    print("\n接下来在另一个终端执行：")
    print(f"  # 只检查（应报「发现新版本」）")
    print(f"  upgrade.exe --from-main --check-only --no-ui")
    print(f"  # 真正升级（下载→校验→替换→更新 manifest）")
    print(f"  upgrade.exe --from-main --no-ui")
    print(f"  # 想验证回滚：加 --corrupt-digest 重启本服务后重跑上面两条\n")

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"监听 http://{args.host}:{args.port} … Ctrl+C 结束")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ok] 已停止")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
