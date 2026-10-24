"""本地假 Release 服务器（离线升级测试工具）的单元测试。

它把升级链路从「必须等发版」变成可复现的本地流程，所以它自己的行为也要被钉住：
JSON 形状不对 / digest 形状不对，会让离线测试得出错误的结论。
"""

import json
import os
import sys

import pytest

TOOLS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "MaaAutoInstaller", "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import fake_release_server as frs  # noqa: E402


def test_guess_version_from_filename(tmp_path):
    p = tmp_path / "MaaAuto_payload_v1.0.2.zip"
    assert frs.guess_version(p) == "1.0.2"
    assert frs.guess_version(tmp_path / "other.zip") == "0.0.0"


def test_build_release_shape(tmp_path):
    payload = tmp_path / "MaaAuto_payload_v1.0.2.zip"
    payload.write_bytes(b"x" * 10)
    rel = frs.build_release("http://127.0.0.1:8765", "1.0.2", "v1.0.2",
                            payload, "ab" * 32, 10, "notes")

    assert rel["tag_name"] == "v1.0.2"
    assert rel["draft"] is False
    assert rel["prerelease"] is False
    asset = rel["assets"][0]
    assert asset["name"] == payload.name
    assert asset["browser_download_url"] == \
        "http://127.0.0.1:8765/download/MaaAuto_payload_v1.0.2.zip"
    assert asset["digest"] == "sha256:" + "ab" * 32
    assert asset["size"] == 10
    json.dumps(rel)          # 必须可序列化


def test_build_release_marks_prerelease(tmp_path):
    payload = tmp_path / "MaaAuto_payload_v1.0.2b1.zip"
    rel = frs.build_release("http://x", "1.0.2b1", "v1.0.2b1", payload,
                            "00" * 32, 1, "")
    assert rel["prerelease"] is True


def test_sha256_of_matches_hashlib(tmp_path):
    import hashlib

    p = tmp_path / "f.bin"
    p.write_bytes(b"hello")
    assert frs.sha256_of(p) == hashlib.sha256(b"hello").hexdigest()


def test_patch_manifest_sets_api_and_downgrades_version(tmp_path):
    install = tmp_path / "app"
    install.mkdir()
    manifest = install / ".maaauto.json"
    manifest.write_text(json.dumps({
        "version": "1.0.2",
        "extra": {"update_api": "https://api.github.com/x", "keep": 1},
    }), encoding="utf-8")

    assert frs.patch_manifest(install, "http://127.0.0.1:8765/releases/latest") is True

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["version"] == "1.0.0"
    assert data["extra"]["update_api"] == "http://127.0.0.1:8765/releases/latest"
    assert data["extra"]["keep"] == 1        # 其它字段不能丢


def test_patch_manifest_creates_extra(tmp_path):
    install = tmp_path / "app"
    install.mkdir()
    (install / ".maaauto.json").write_text(
        json.dumps({"version": "1.0.2"}), encoding="utf-8")

    assert frs.patch_manifest(install, "http://127.0.0.1:9/releases/latest") is True
    data = json.loads((install / ".maaauto.json").read_text(encoding="utf-8"))
    assert data["extra"]["update_api"] == "http://127.0.0.1:9/releases/latest"


def test_patch_manifest_missing_file(tmp_path):
    assert frs.patch_manifest(tmp_path, "http://x") is False
