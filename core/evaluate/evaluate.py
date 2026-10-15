"""Anti-REA 评估验证层（Evaluation v0.1，R1 MVP）。

设计：docs/design/ddd/dd-07-evaluation.md
覆盖：FR-E1（功能保持，差分验证）、FR-E2（性能基准，粗测）。
攻击模拟（FR-E3…E8）留待 R3。
"""
from __future__ import annotations

import os
import subprocess
import time

from .. import common


def _run(exe: str, args: list[str]) -> tuple[int, str, float]:
    t0 = time.perf_counter()
    p = subprocess.run([exe, *args], capture_output=True, text=True)
    dt = time.perf_counter() - t0
    return p.returncode, (p.stdout or "") + (p.stderr or ""), dt


def verify(artifacts_dir: str, args: list[str] | None = None,
           max_overhead: float = 5.0) -> dict:
    """差分验证 baseline vs protected，产出 verification_report（dict）。"""
    args = args or []
    meta = common.read_json(os.path.join(artifacts_dir, "metadata.json"))
    run_id = meta.get("run_id", "run-unknown")
    baseline = meta.get("baseline_exe")
    protected = meta.get("protected_exe")
    if not baseline or not protected or not os.path.exists(baseline) or \
       not os.path.exists(protected):
        raise ValueError("E_INVALID_INPUT: 缺少 baseline/protected 可执行产物")

    rc_b, out_b, t_b = _run(baseline, args)
    rc_p, out_p, t_p = _run(protected, args)
    functional_pass = (rc_b == rc_p) and (out_b == out_p)
    overhead = (t_p / t_b) if t_b > 0 else 0.0
    performance_pass = overhead <= max_overhead

    if functional_pass:
        detail = ["输出一致: rc=%d" % rc_p]
    else:
        detail = ["输出不一致: baseline rc=%d protected rc=%d" % (rc_b, rc_p)]

    report = {
        "schema_version": common.SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": common.now_iso(),
        "functional_pass": functional_pass,
        "test_suite": {"total": 1, "passed": 1 if functional_pass else 0,
                       "failed": 0 if functional_pass else 1, "skipped": 0,
                       "command": "differential: baseline vs protected"},
        "performance_pass": performance_pass,
        "overhead": round(overhead, 4),
        "detail": detail,
        "overall_pass": functional_pass and performance_pass,
    }
    common.validate(report, "verification_report.schema.json")
    return report
