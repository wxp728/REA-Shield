"""回归检测（FR-E8；dd-07 §8）。

策略变更后在基准上重跑攻击模拟，并与历史指标比对：指标退化（相对上一次）
或未达目标阈值即告警。触发式为「同签名有新运行」或「策略哈希变化」。
"""
from __future__ import annotations

import os

from .. import common
from . import metrics as M
from . import timeseries
from .attack_sim import attack_sim as _attack_sim

# 方向：True=越大越好；False=越小越好
_DIRECTION = {
    "token_ratio": True,
    "time_ratio": True,
    "name_recovery_accuracy": False,
    "function_judgement_accuracy": False,
    "vuln_discovery_rate": False,
    "bin_similarity": False,
    "session_context_used_ratio": True,
}


def _worse(metric: str, prev: float, curr: float) -> bool:
    higher_better = _DIRECTION.get(metric)
    if higher_better is None:
        return False
    return curr < prev if higher_better else curr > prev


def compare(current: dict, previous: dict) -> dict:
    """比对两组指标；返回 `{regressions, target_violations, degraded}`。"""
    regressions, violations = [], []
    for k, curr in current.items():
        if not isinstance(curr, (int, float)) or isinstance(curr, bool):
            continue
        prev = previous.get(k)
        if isinstance(prev, (int, float)) and _worse(k, float(prev), float(curr)):
            regressions.append({"metric": k, "prev": prev, "curr": curr,
                                "delta": round(curr - prev, 6)})
        th = M.TH.get({"name_recovery_accuracy": "name_recovery_max",
                       "function_judgement_accuracy": "function_judgement_max",
                       "vuln_discovery_rate": "vuln_discovery_max",
                       "bin_similarity": "bin_similarity_max"}.get(k, ""), None)
        if th is not None and curr > th:
            violations.append({"metric": k, "value": curr, "target_max": th})
    return {"regressions": regressions, "target_violations": violations,
            "degraded": bool(regressions or violations)}


def previous_metrics(db: str, run_id: str) -> dict:
    """取时间序列库中最近一次**其它**运行的指标（用于回归基线）。"""
    import sqlite3
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT run_id FROM metrics WHERE run_id != ? ORDER BY ts DESC LIMIT 1",
        (run_id,)).fetchone()
    if not row:
        con.close()
        return {}
    prev_run = row[0]
    rows = con.execute(
        "SELECT metric, value FROM metrics WHERE run_id = ?", (prev_run,)).fetchall()
    con.close()
    return {m: v for m, v in rows}


def regress(artifacts_dir: str, db: str, benchmark: str | None = None,
            *, mode: str = "static", allow_llm: bool = False) -> dict:
    """跑一次攻击模拟并与历史比对，产出回归报告（写 `regression_report.json`）。"""
    rep = _attack_sim(artifacts_dir, benchmark=benchmark, mode=mode,
                      allow_llm=allow_llm, db=db)
    run_id = rep["run_id"]
    prev = previous_metrics(db, run_id)
    result = compare(rep["metrics"], prev)
    result.update({"run_id": run_id, "generated_at": common.now_iso(),
                   "benchmark": benchmark or "",
                   "policy_hash": common.read_json(
                       os.path.join(artifacts_dir, "metadata.json")).get("policy_hash", "")})
    common.write_json(os.path.join(artifacts_dir, "regression_report.json"), result)
    return result
