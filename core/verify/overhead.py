"""性能基准（NFR-01 / FR-E2）。

多次运行取中位耗时，计算 protected/baseline 开销倍数，并与预算比对。
"""
from __future__ import annotations

import statistics
import subprocess
import time

# NFR-01 预算（SRS：P2 ≤ 5%、P1 ≤ 15%、P0 组合策略 ≤ 40%；开销 = 增量/基线）
BUDGET = {"P0": 0.40, "P1": 0.15, "P2": 0.05, "P3": 0.05}


def _time_once(exe: str, args: list[str]) -> float:
    t0 = time.perf_counter()
    subprocess.run([exe, *args], capture_output=True)
    return time.perf_counter() - t0


def measure(baseline_exe: str, protected_exe: str, args: list[str] | None = None,
            reps: int = 15, warmup: int = 3) -> dict:
    """返回中位耗时与开销倍数（开销按增量/基线计，与预算同口径）。"""
    args = args or []
    for _ in range(warmup):
        _time_once(baseline_exe, args)
        _time_once(protected_exe, args)
    tb = [ _time_once(baseline_exe, args) for _ in range(reps)]
    tp = [ _time_once(protected_exe, args) for _ in range(reps)]
    mb, mp = statistics.median(tb), statistics.median(tp)
    overhead = (mp - mb) / mb if mb > 0 else 0.0
    return {"baseline_ms": round(mb * 1000, 3), "protected_ms": round(mp * 1000, 3),
            "overhead": round(overhead, 4), "reps": reps}


def baseline_data(entries: list[dict], seed: int | None = None) -> dict:
    """聚合逐资产基准。`entries` 每项：{asset, sensitivity, baseline_exe,
    protected_exe, args?}。返回带预算判定的数据（供 STR / 性能基线文档）。"""
    rows = []
    for e in entries:
        m = measure(e["baseline_exe"], e["protected_exe"], e.get("args"))
        budget = BUDGET.get(e.get("sensitivity", "P3"), 0.02)
        m.update({"asset": e["asset"], "sensitivity": e.get("sensitivity", "P3"),
                  "budget": budget, "within_budget": m["overhead"] <= budget})
        rows.append(m)
    worst = max((r["overhead"] for r in rows), default=0.0)
    return {"rows": rows, "worst_overhead": round(worst, 4), "seed": seed,
            "pass": all(r["within_budget"] for r in rows)}
