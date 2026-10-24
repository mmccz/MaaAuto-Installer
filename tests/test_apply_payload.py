"""apply_payload 的替换 / 保护 / 回滚 / 路径穿越测试。

这是升级最危险的一段代码：它直接往安装目录里覆盖文件。
测试用临时目录 + 手工构造的 zip，不联网、不碰真实安装。
"""

import zipfile
from pathlib import Path

import pytest

from installer.core import payload


def make_zip(path: Path, files: dict):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return path


def make_install(tmp_path: Path):
    install = tmp_path / "MaaAuto"
    install.mkdir()
    (install / payload.MAIN_EXE_NAME).write_text("OLD-EXE", encoding="utf-8")
    (install / "old_only.dll").write_text("OLD-DLL", encoding="utf-8")
    (install / "config").mkdir()
    (install / "config" / "config.json").write_text('{"keep": true}', encoding="utf-8")
    (install / "logs").mkdir()
    (install / "logs" / "task.log").write_text("old log", encoding="utf-8")
    return install


def test_apply_replaces_files_and_keeps_user_data(tmp_path):
    install = make_install(tmp_path)
    zpath = make_zip(tmp_path / "p.zip", {
        payload.MAIN_EXE_NAME: "NEW-EXE",
        "new_lib.dll": "NEW-LIB",
        # payload 里混进用户数据也不能覆盖用户的
        "config/config.json": '{"keep": false}',
        "logs/task.log": "payload log",
    })

    result = payload.apply_payload(install, zpath)

    assert result.success is True
    assert result.rolled_back is False
    assert result.replaced == 2
    assert (install / payload.MAIN_EXE_NAME).read_text(encoding="utf-8") == "NEW-EXE"
    assert (install / "new_lib.dll").read_text(encoding="utf-8") == "NEW-LIB"
    assert (install / "config" / "config.json").read_text(encoding="utf-8") == '{"keep": true}'
    assert (install / "logs" / "task.log").read_text(encoding="utf-8") == "old log"


def test_old_files_are_not_deleted(tmp_path):
    """payload 里没有的文件（比如用户自己放的）不该被动。"""
    install = make_install(tmp_path)
    zpath = make_zip(tmp_path / "p.zip", {payload.MAIN_EXE_NAME: "NEW"})

    assert payload.apply_payload(install, zpath).success is True
    assert (install / "old_only.dll").exists()


def test_missing_main_exe_is_rejected(tmp_path):
    install = make_install(tmp_path)
    zpath = make_zip(tmp_path / "p.zip", {"lib.dll": "x"})

    result = payload.apply_payload(install, zpath)
    assert result.success is False
    assert "缺少" in result.error


def test_path_traversal_is_rejected(tmp_path):
    install = make_install(tmp_path)
    zpath = make_zip(tmp_path / "p.zip", {
        payload.MAIN_EXE_NAME: "NEW",
        "../../evil.txt": "pwned",
    })

    result = payload.apply_payload(install, zpath)
    assert result.success is False
    assert "非法路径" in result.error or "解压失败" in result.error
    assert not (tmp_path / "evil.txt").exists()


def test_failure_midway_rolls_back(tmp_path, monkeypatch):
    """替换到一半失败时，已替换的文件必须恢复原内容。"""
    install = make_install(tmp_path)
    zpath = make_zip(tmp_path / "p.zip", {
        payload.MAIN_EXE_NAME: "NEW-EXE",
        "boom.dll": "NEW-BOOM",
    })
    (install / "boom.dll").write_text("OLD-BOOM", encoding="utf-8")

    real = payload._remove_running_exe_conflict

    def fake(target):
        if target.name == "boom.dll":
            raise PermissionError("模拟被占用")
        return real(target)

    monkeypatch.setattr(payload, "_remove_running_exe_conflict", fake)

    result = payload.apply_payload(install, zpath)

    assert result.success is False
    assert result.rolled_back is True
    assert (install / payload.MAIN_EXE_NAME).read_text(encoding="utf-8") == "OLD-EXE"
    assert (install / "boom.dll").read_text(encoding="utf-8") == "OLD-BOOM"


def test_cancel_before_start(tmp_path):
    install = make_install(tmp_path)
    zpath = make_zip(tmp_path / "p.zip", {payload.MAIN_EXE_NAME: "NEW"})

    result = payload.apply_payload(install, zpath, cancel_check=lambda: True)
    assert result.success is False
    assert "取消" in result.error
    assert (install / payload.MAIN_EXE_NAME).read_text(encoding="utf-8") == "OLD-EXE"


def test_temp_dirs_cleaned_up(tmp_path):
    install = make_install(tmp_path)
    zpath = make_zip(tmp_path / "p.zip", {payload.MAIN_EXE_NAME: "NEW"})

    payload.apply_payload(install, zpath)
    leftovers = [p.name for p in tmp_path.iterdir()
                 if p.name.startswith(".MaaAuto_")]
    assert leftovers == []


def test_failure_flag_write_and_clear(tmp_path):
    payload.write_failure_flag(tmp_path, "1.0.0", "1.0.1", reason="boom",
                               log_path="C:/x.log")
    flag = tmp_path / "config" / payload.FAILURE_FLAG_NAME
    assert flag.exists()
    text = flag.read_text(encoding="utf-8")
    assert "1.0.0" in text and "boom" in text

    payload.clear_failure_flag(tmp_path)
    assert not flag.exists()


def test_read_launch_args_filters_upgrading(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "last_launch_args.json").write_text(
        '{"args": ["--autostart", "--upgrading", 42]}', encoding="utf-8")
    assert payload.read_launch_args(tmp_path) == ["--autostart"]


def test_read_launch_args_tolerates_missing(tmp_path):
    assert payload.read_launch_args(tmp_path) == []
