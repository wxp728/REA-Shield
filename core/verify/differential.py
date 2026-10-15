"""差分 fuzz（NFR-03 / FR-E1）。

对**同一接口**的 baseline 与 protected 二进制注入相同随机输入，比对
退出码与输出；出现差异即定位首个不一致输入。为控制进程数，按 batch 批量
投喂参数：一批一致即通过，不一致再逐输入二分定位。
"""
from __future__ import annotations

import random
import subprocess


def _run(exe: str, args: list[str], timeout: float) -> tuple[int, str]:
    try:
        p = subprocess.run([exe, *args], capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return -999, "__timeout__"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _locate(baseline: str, protected: str, args: list[str], timeout: float):
    """逐输入定位首批不一致项（最多返回 1 条）。"""
    for a in args:
        rb, ob = _run(baseline, [a], timeout)
        rp, op = _run(protected, [a], timeout)
        if (rb, ob) != (rp, op):
            return {"arg": a, "baseline": {"rc": rb, "out": ob},
                    "protected": {"rc": rp, "out": op}}
    return None


def run(baseline_exe: str, protected_exe: str, n: int = 100000, seed: int = 1,
        batch: int = 64, low: int = -(2 ** 31), high: int = 2 ** 31 - 1,
        timeout: float = 30.0) -> dict:
    """注入 n 个随机整数（分批）并比对行为，返回差分 fuzz 报告。"""
    rnd = random.Random(seed)
    iterations = mismatches = 0
    first = None
    while iterations < n:
        k = min(batch, n - iterations)
        args = [str(rnd.randint(low, high)) for _ in range(k)]
        rb, ob = _run(baseline_exe, args, timeout)
        rp, op = _run(protected_exe, args, timeout)
        if (rb, ob) != (rp, op):
            mismatches += 1
            if first is None:
                first = _locate(baseline_exe, protected_exe, args, timeout)
        iterations += k
    return {
        "iterations": iterations,
        "mismatches": mismatches,
        "batch": batch,
        "seed": seed,
        "first_mismatch": first,
        "pass": mismatches == 0,
    }
