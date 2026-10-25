"""差分更新测试（1.2.0 新增）。

覆盖三块：
* ``bspatch``：补丁应用端（纯标准库）必须与 ``bsdiff4`` 的产物逐字节一致；
* ``delta``：构建 → 还原的往返、基准不符的拒绝、删除清单；
* ``payload.apply_delta``：真实安装目录上的替换 / 回滚 / 受保护目录不动。
"""

import zipfile
from pathlib import Path

import pytest

from installer.core import bspatch, delta, payload


# --------------------------------------------------------------------------- #
# bspatch
# --------------------------------------------------------------------------- #
def test_bspatch_roundtrip_shapes():
    import bsdiff4

    cases = [
        (b"", b"hello"),
        (b"abc" * 500, b"abc" * 400 + b"tail"),
        (bytes(range(256)) * 40, bytes(range(256)) * 39 + b"END"),
    ]
    for old, new in cases:
        patch = bsdiff4.diff(old, new)
        assert bspatch.apply_patch(old, patch) == new


def test_bspatch_rejects_garbage():
    with pytest.raises(ValueError):
        bspatch.apply_patch(b"abc", b"not a patch")
    # 头部声明了负长度（最高位置 1）→ 必须拒绝
    bad_header = b"BSDIFF40" + b"\xff" * 8 + b"\x00" * 8 + b"\x00" * 8
    with pytest.raises(ValueError):
        bspatch.apply_patch(b"abc", bad_header)
    # 声明的块长度大于实际数据 → 必须拒绝
    truncated = (b"BSDIFF40" + bspatch._offtout(100)
                 + bspatch._offtout(0) + bspatch._offtout(10))
    with pytest.raises(ValueError):
        bspatch.apply_patch(b"abc", truncated)


# --------------------------------------------------------------------------- #
# delta 构建 / 还原
# --------------------------------------------------------------------------- #
def _write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def make_pair(tmp_path: Path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    # 不变
    _write(old / "_internal/stable.dll", b"S" * 4096)
    _write(new / "_internal/stable.dll", b"S" * 4096)
    # 小改（适合补丁）
    _write(old / "MaaAuto.exe", b"M" * 20000)
    _write(new / "MaaAuto.exe", b"M" * 19000 + b"CHANGED" * 100)
    # 新增
    _write(new / "_internal/new.dll", b"N" * 1024)
    # 删除
    _write(old / "_internal/gone.dll", b"G" * 1024)
    return old, new


def test_build_and_materialize_roundtrip(tmp_path):
    old, new = make_pair(tmp_path)
    out = tmp_path / "delta.zip"
    stat = delta.build_delta(new, old, out, "1.2.0", "1.1.1")

    assert out.exists()
    assert stat["patch_files"] >= 1          # MaaAuto.exe 应走补丁
    assert stat["deleted"] == 1              # gone.dll 在删除清单里

    stage = tmp_path / "stage"
    count, deletes = delta.materialize(out, old, stage)
    assert count == stat["patch_files"] + stat["full_files"]
    assert deletes == ["_internal/gone.dll"]

    # 还原出来的文件必须和目标完全一致
    for rel in ("MaaAuto.exe", "_internal/new.dll"):
        assert (stage / rel).read_bytes() == (new / rel).read_bytes()
    # 内容没变的文件不该进包
    assert not (stage / "_internal/stable.dll").exists()


def test_base_mismatch_is_detected(tmp_path):
    old, new = make_pair(tmp_path)
    out = tmp_path / "delta.zip"
    delta.build_delta(new, old, out, "1.2.0", "1.1.1")

    # 篡改本地基准文件（模拟用户手动替换过文件）
    _write(old / "MaaAuto.exe", b"X" * 20000)
    with pytest.raises(delta.BaseMismatch):
        delta.materialize(out, old, tmp_path / "stage")


def test_delta_delete_list_is_applied_by_apply_delta(tmp_path):
    """apply_delta 在真实安装目录上：替换 + 删除 + 保护 config。"""
    install = tmp_path / "app"
    old, new = make_pair(tmp_path)
    # 让 install 目录起点等于 old
    for src in old.rglob("*"):
        if src.is_file():
            _write(install / src.relative_to(old), src.read_bytes())
    _write(install / "config" / "config.json", b'{"keep": true}')
    _write(install / "_internal/gone.dll", b"G" * 1024)

    out = tmp_path / "delta.zip"
    delta.build_delta(new, old, out, "1.2.0", "1.1.1")

    result = payload.apply_delta(install, out)
    assert result.success and result.via_delta

    assert (install / "MaaAuto.exe").read_bytes() == (new / "MaaAuto.exe").read_bytes()
    assert (install / "_internal/new.dll").exists()
    assert not (install / "_internal/gone.dll").exists()      # 删除清单生效
    assert (install / "config" / "config.json").exists()      # 用户数据不动


def test_apply_delta_reports_base_mismatch(tmp_path):
    install = tmp_path / "app"
    old, new = make_pair(tmp_path)
    for src in old.rglob("*"):
        if src.is_file():
            _write(install / src.relative_to(old), src.read_bytes())
    out = tmp_path / "delta.zip"
    delta.build_delta(new, old, out, "1.2.0", "1.1.1")

    _write(install / "MaaAuto.exe", b"tampered")

    result = payload.apply_delta(install, out)
    assert not result.success
    assert result.base_mismatch          # 调用方据此回退整包
    # 失败时不能留下垃圾目录
    leftovers = list(tmp_path.glob(".MaaAuto_new_*")) + list(tmp_path.glob(".MaaAuto_bak_*"))
    assert leftovers == []


# --------------------------------------------------------------------------- #
# 资产选择
# --------------------------------------------------------------------------- #
def _release(assets):
    return {"tag_name": "v1.2.0", "assets": assets}


def test_pick_delta_asset_matches_exact_pair():
    assets = [
        {"name": "MaaAuto_payload_v1.2.0.zip", "browser_download_url": "u"},
        {"name": "MaaAuto_delta_v1.1.1_to_1.2.0.zip", "browser_download_url": "d"},
    ]
    got = payload.pick_delta_asset(_release(assets), "1.1.1", "1.2.0")
    assert got and got["browser_download_url"] == "d"
    # 版本对不上就没有
    assert payload.pick_delta_asset(_release(assets), "1.0.0", "1.2.0") is None
    assert payload.pick_delta_asset(_release(assets), "0.0.0", "1.2.0") is None


def test_check_update_exposes_delta(monkeypatch):
    assets = [
        {"name": "MaaAuto_payload_v1.2.0.zip", "browser_download_url": "p",
         "size": 100, "digest": "sha256:" + "a" * 64},
        {"name": "MaaAuto_delta_v1.1.1_to_1.2.0.zip", "browser_download_url": "d",
         "size": 10, "digest": "sha256:" + "b" * 64},
    ]
    monkeypatch.setattr(payload, "fetch_release", lambda *a, **k: _release(assets))

    class M:
        version = "1.1.1"

    info = payload.check_update(M(), "http://x", "MaaAuto_payload_v")
    assert info.has_update
    assert info.delta_url == "d"
    assert info.delta_size == 10
    assert info.delta_sha == "b" * 64


def test_check_update_without_delta_still_works(monkeypatch):
    assets = [{"name": "MaaAuto_payload_v1.2.0.zip", "browser_download_url": "p",
               "size": 100, "digest": "sha256:" + "a" * 64}]
    monkeypatch.setattr(payload, "fetch_release", lambda *a, **k: _release(assets))

    class M:
        version = "0.9.0"

    info = payload.check_update(M(), "http://x", "MaaAuto_payload_v")
    assert info.has_update
    assert info.delta_url == ""
