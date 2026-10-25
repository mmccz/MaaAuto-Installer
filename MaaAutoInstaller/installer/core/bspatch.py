"""BSDIFF40 补丁的应用端（纯标准库，不引入第三方依赖）。

为什么自己写：``upgrade.exe`` 目前只依赖标准库 + psutil（7.5 MB），加一个
bsdiff 的二进制依赖会把它撑大、还要处理架构/杀软问题。补丁**生成**在构建机
上用 ``bsdiff4`` 完成（只影响 CI/本机打包），**应用**在这里用 ``bz2`` 完成。

文件格式（Colin Percival 的 bsdiff，行内常称 BSDIFF40）::

    "BSDIFF40" | ctrl_len:int64 | diff_len:int64 | new_size:int64
    ctrl_block  = bz2( control triples:  (x, y, z) * n )
    diff_block  = bz2( x 段逐字节相加的差值 )
    extra_block = bz2( y 段逐字节新内容 )

    new = 0
    old = 0
    逐个三元组：
        new[new:new+x] = old[old:old+x] + diff[x 段]      # 逐字节相加
        new[new+x:new+x+y] = extra[y 段]
        old += x + z;  new += x + y

int64 采用「最高位当符号位」的写法（详见 ``_offtin``），和 bsdiff 原实现一致。
"""

import bz2
from typing import Callable, Optional

MAGIC = b"BSDIFF40"


def _offtin(buf: bytes) -> int:
    """bsdiff 的 8 字节整数：小端绝对值 + 最高位符号。"""
    if len(buf) != 8:
        raise ValueError("int64 长度必须为 8")
    y = buf[7] & 0x7F
    for i in range(6, -1, -1):
        y = y * 256 + buf[i]
    return -y if buf[7] & 0x80 else y


def _offtout(value: int) -> bytes:
    """``_offtin`` 的逆操作（测试/自检用）。"""
    if value < 0:
        y = -value
        sign = 0x80
    else:
        y = value
        sign = 0
    out = bytearray(8)
    for i in range(8):
        out[i] = y & 0xFF
        y >>= 8
    out[7] |= sign
    return bytes(out)


def _read_exact(f, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise ValueError(f"补丁被截断：期望 {n} 字节，实际 {len(data)}")
    return data


def apply_patch(old: bytes, patch: bytes,
                progress: Optional[Callable[[int, int], None]] = None) -> bytes:
    """把 ``patch`` 应用到 ``old``，返回新内容（不合法时抛 ``ValueError``）。"""
    if len(patch) < 32 or patch[:8] != MAGIC:
        raise ValueError("不是 BSDIFF40 补丁")
    ctrl_len = _offtin(patch[8:16])
    diff_len = _offtin(patch[16:24])
    new_size = _offtin(patch[24:32])
    if ctrl_len < 0 or diff_len < 0 or new_size < 0:
        raise ValueError("补丁头损坏（长度为负）")

    pos = 32
    ctrl_end = pos + ctrl_len
    diff_end = ctrl_end + diff_len
    if diff_end > len(patch):
        raise ValueError("补丁长度与声明不符")

    ctrl = bz2.decompress(patch[pos:ctrl_end])
    diff = bz2.decompress(patch[ctrl_end:diff_end])
    extra = bz2.decompress(patch[diff_end:])

    out = bytearray(new_size)
    oldpos = 0
    newpos = 0
    cpos = dpos = epos = 0
    old_len = len(old)

    def _byte(i: int) -> int:
        return old[i] if 0 <= i < old_len else 0

    while newpos < new_size:
        if cpos + 24 > len(ctrl):
            raise ValueError("控制块提前结束")
        x = _offtin(ctrl[cpos:cpos + 8])
        y = _offtin(ctrl[cpos + 8:cpos + 16])
        z = _offtin(ctrl[cpos + 16:cpos + 24])
        cpos += 24
        if x < 0 or y < 0 or newpos + x + y > new_size:
            raise ValueError("控制块数值越界")

        for i in range(x):
            out[newpos + i] = (_byte(oldpos + i) + diff[dpos + i]) & 0xFF
        dpos += x
        oldpos += x
        newpos += x

        out[newpos:newpos + y] = extra[epos:epos + y]
        epos += y
        newpos += y

        oldpos += z
        if progress:
            progress(newpos, new_size)

    return bytes(out)


def apply_patch_file(old_path, patch_path, out_path,
                     progress: Optional[Callable[[int, int], None]] = None) -> int:
    """文件版：读旧文件 + 补丁，写出新文件，返回新文件字节数。"""
    with open(patch_path, "rb") as f:
        patch = f.read()
    with open(old_path, "rb") as f:
        old = f.read()
    new = apply_patch(old, patch, progress=progress)
    with open(out_path, "wb") as f:
        f.write(new)
    return len(new)
