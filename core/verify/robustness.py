"""稳健性验证（NFR-07）：异常输入 / 超时 / 大工程。

不改动被测逻辑；只观察其**防御性行为**（抛受控异常、超时受控、规模可扩展）。
"""
from __future__ import annotations

import os
import stat
import time

from .. import common
from ..scanner import scan as _scan
from ..strategy import plan as _plan
from ..transform import protect as _protect
from ..evaluate import verify as _verify, attack_sim as _attack_sim
from . import differential


def _capture(fn, *a, **kw) -> dict:
    try:
        fn(*a, **kw)
        return {"raised": False, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"raised": True, "error": type(exc).__name__, "msg": str(exc)[:120]}


def abnormal_inputs(root: str, workdir: str) -> list[dict]:
    """一组异常输入，均应「受控失败」而非崩溃/静默通过。"""
    bad_policy = os.path.join(workdir, "bad_policy.yaml")
    common.write_yaml(bad_policy, {"schema_version": "1.0"})  # 缺必填
    cases = [
        ("scan_nonexistent", _capture, (_scan, os.path.join(workdir, "no-such-dir"))),
        ("plan_malformed_manifest", _capture, (_plan, {"assets": "not-a-list"})),
        ("protect_malformed_policy", _capture, (_protect, common.read_yaml(bad_policy),
                                                [], os.path.join(workdir, "o1"))),
        ("verify_missing_metadata", _capture, (_verify, os.path.join(workdir, "o2"))),
        ("attack_sim_missing_metadata", _capture, (_attack_sim,
                                                   os.path.join(workdir, "o3"))),
    ]
    out = []
    for name, fn, args in cases:
        r = fn(*args)
        r["case"] = name
        r["controlled"] = bool(r["raised"])   # 受控失败 = 抛异常而非崩溃
        out.append(r)
    return out


def timeout_probe(workdir: str, timeout: float = 0.5) -> dict:
    """超时受控：挂起进程应在超时后返回哨兵值而不阻塞。"""
    sleeper = os.path.join(workdir, "sleeper.sh")
    with open(sleeper, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\nsleep 5\n")
    os.chmod(sleeper, os.stat(sleeper).st_mode | stat.S_IEXEC)
    rc, out = differential._run(sleeper, [], timeout=timeout)
    return {"timed_out": rc == -999 and out == "__timeout__", "rc": rc}


def large_project(workdir: str, n: int = 200) -> dict:
    """大工程可扩展：生成 n 个源文件，扫描应完成并产出合规清单。"""
    proj = os.path.join(workdir, "large")
    os.makedirs(proj, exist_ok=True)
    with open(os.path.join(proj, "LICENSE"), "w", encoding="utf-8") as fh:
        fh.write("MIT\n")
    for i in range(n):
        with open(os.path.join(proj, "m%03d.c" % i), "w", encoding="utf-8") as fh:
            fh.write("int fn_%03d(int x){return x+%d;}\n" % (i, i))
    t0 = time.perf_counter()
    manifest = _scan(proj)
    dt = time.perf_counter() - t0
    ok = True
    try:
        common.validate(manifest, "asset_manifest.schema.json")
    except Exception:  # noqa: BLE001
        ok = False
    return {"files": n, "assets": len(manifest.get("assets", [])),
            "elapsed_sec": round(dt, 3), "schema_ok": ok, "pass": ok}
