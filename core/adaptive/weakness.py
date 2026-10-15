"""弱点记录与策略调整建议（FR-F2；DD-08 §6）。

当实测指标未达目标时记录弱点，并给出可一键执行的调整建议（强化相应策略）。
"""
from __future__ import annotations

import json
import os

# 指标 -> 未达目标时应强化的策略（dd-07 §5 目标的映射）
_REMEDY = {
    "name_recovery_accuracy": ["identifier_renaming"],
    "function_judgement_accuracy": ["control_flow_flattening", "non_linear_mba",
                                    "opaque_predicates"],
    "vuln_discovery_rate": ["control_flow_flattening", "data_flow_noise"],
    "bin_similarity": ["code_virtualization", "function_boundary_perturbation",
                       "adversarial_inducement"],
}

THRESHOLD = {
    "name_recovery_accuracy": ("<=", 0.20),
    "function_judgement_accuracy": ("<=", 0.30),
    "vuln_discovery_rate": ("<=", 0.10),
    "bin_similarity": ("<=", 0.55),
}


def detect(metrics: dict) -> list[dict]:
    """返回未达目标的弱点列表 `[{metric, value, target, remedy}]`。"""
    out = []
    for k, (op, th) in THRESHOLD.items():
        v = metrics.get(k)
        if v is None:
            continue
        bad = (v > th) if op == "<=" else (v < th)
        if bad:
            out.append({"metric": k, "value": v, "target": th,
                        "remedy": _REMEDY.get(k, [])})
    return out


def adjust(policy: dict, weaknesses: list[dict]) -> dict:
    """按弱点为相应资产追加补救策略（不改动已选策略），返回新策略。"""
    add = sorted({s for w in weaknesses for s in w.get("remedy", [])})
    if not add:
        return policy
    new = json.loads(json.dumps(policy))
    W = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}
    for a in new.get("assets", []):
        if W.get(a.get("sensitivity"), 0) >= 2:  # 仅 P0/P1 强化
            a["strategies"] = sorted(set(a.get("strategies", [])) | set(add))
    return new


def record(path: str, run_id: str, weaknesses: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = {"records": []}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    for w in weaknesses:
        w = dict(w)
        w["run_id"] = run_id
        data["records"].append(w)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
