"""兼容性矩阵（NFR-05 / NFR-10）。

实测本机可覆盖的组合，并做**跨目标 IR 探针**（编译到非 x86_64 目标三元组，
验证变换插件在 IR 层目标无关）；未实测组合显式标注「未验证」，不含糊声称支持。
"""
from __future__ import annotations

import os
import platform
import subprocess

from ..transform import _clang, _find_plugin

# 目标三元组探针（仅编译到汇编，避免交叉链接器依赖）
_CROSS = ["aarch64-linux-gnu", "riscv64-linux-gnu", "wasm32-unknown-unknown",
          "x86_64-pc-windows-gnu"]


def toolchain() -> dict:
    clang = _clang()
    p = subprocess.run([clang, "--version"], capture_output=True, text=True)
    line = (p.stdout or "").splitlines()[0] if p.stdout else "unknown"
    return {"system": platform.system(), "machine": platform.machine(),
            "clang": line.strip()}


_PROBE_C = """/* freestanding 探针：不依赖 libc，纯 IR 变换，用于跨目标验证 */
int probe_mix(int x)
{
    int y = x ^ 0x5a;
    if (x > 0) {
        y = y * 3 + 1;
    } else {
        y = y - 7;
    }
    return y;
}
"""


def _opt_bin() -> str:
    import shutil
    o = shutil.which("opt")
    if o:
        return o
    return os.path.join(os.path.dirname(_clang()), "opt")


def cross_target_probe(source: str, workdir: str) -> list[dict]:
    """对若干目标三元组生成 IR 并跑变换，验证 IR 层目标无关（FR-C 变换不依赖具体后端）。

    `source` 参数保留用于签名一致；探针使用内置 freestanding 源，避免交叉编译
    头文件缺失干扰对「变换是否目标无关」的判定。
    """
    clang, opt, plugin = _clang(), _opt_bin(), _find_plugin()
    probe_c = os.path.join(workdir, "probe_freestanding.c")
    with open(probe_c, "w", encoding="utf-8") as fh:
        fh.write(_PROBE_C)

    env = dict(os.environ)
    env.update({"ANTI_REA_WHITELIST": "*", "ANTI_REA_STRATEGIES": "cff,mba",
                "ANTI_REA_SEED": "1"})
    rows = []
    for triple in _CROSS:
        ir = os.path.join(workdir, "probe-%s.ll" % triple)
        out = os.path.join(workdir, "probe-%s.prot.ll" % triple)
        c = subprocess.run([clang, "-target", triple, "-O1", "-emit-llvm", "-S",
                            "-ffreestanding", "-nostdlib", probe_c, "-o", ir],
                           capture_output=True, text=True)
        if c.returncode != 0:
            rows.append({"triple": triple, "ok": False,
                         "err": "emit-ir: " + (c.stderr or "").strip().splitlines()[-1][:90]})
            continue
        o = subprocess.run([opt, "-load-pass-plugin=" + plugin,
                            "-passes=reg2mem,anti-rea", ir, "-S", "-o", out],
                           capture_output=True, text=True, env=env)
        if o.returncode != 0:
            rows.append({"triple": triple, "ok": False,
                         "err": "opt: " + (o.stderr or "").strip().splitlines()[-1][:90]})
            continue
        with open(out, encoding="utf-8") as fh:
            text = fh.read()
        applied = ("mba." in text) or ("cff." in text)
        rows.append({"triple": triple, "ok": applied,
                     "err": "" if applied else "no-transform-marker"})
    return rows


def matrix(source: str, workdir: str) -> dict:
    """返回兼容性矩阵（含实测/未验证标注）。"""
    tk = toolchain()
    cross = cross_target_probe(source, workdir)
    rows = [
        {"platform": "linux-x86_64", "language": "c", "build_system": "direct",
         "status": "tested"},
        {"platform": "linux-x86_64", "language": "c", "build_system": "cmake",
         "status": "tested"},
        {"platform": "linux-x86_64", "language": "c", "build_system": "npm",
         "status": "tested"},
        {"platform": "linux-x86_64", "language": "c", "build_system": "python-build_ext",
         "status": "tested"},
        {"platform": "linux-x86_64", "language": "rust(c/ffi)", "build_system": "cargo",
         "status": "tested"},
    ]
    for c in cross:
        rows.append({"platform": c["triple"], "language": "c",
                     "build_system": "ir-only",
                     "status": "tested" if c["ok"] else "unsupported"})
    for plat in ("windows-x64", "macos-arm64", "android", "wasm"):
        rows.append({"platform": plat, "language": "-", "build_system": "-",
                     "status": "unverified"})
    return {"toolchain": tk, "cross_probes": cross, "rows": rows,
            "supported_here": sum(1 for r in rows if r["status"] == "tested")}
