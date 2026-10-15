"""量化指标与判定（FR-E6 / OI-07）。

- `compute_static`：由静态特征计算可复现的代理指标（无 LLM）；
- `judge`：按 `decisions/OI-07-rea-success-criteria.md` 的 D3/D5 判定；
- `aggregate`：多模型保守聚合（D4）。

指标口径见 `docs/design/ddd/dd-07-evaluation.md §5`；成功信号 S1–S4 见 OI-07 §3。
"""
from __future__ import annotations

from . import static_features

# 阈值（SRS §3.5.2 / dd-07 §5）
TH = {
    "name_recovery_max": 0.20,
    "function_judgement_max": 0.30,
    "vuln_discovery_max": 0.10,
    "bin_similarity_max": 0.55,
    "context_min": 0.90,
    "token_target": 100.0,
    "time_target": 10.0,
}


def compute_static(baseline_exe: str, protected_exe: str,
                   targets: list[str]) -> dict:
    """计算无 LLM 时可用的一组静态指标（含代理说明）。

    - `name_recovery_accuracy`：ground truth 名在保护产物中的存活比例；
    - `bin_similarity`：结构相似度代理（静态特征）；
    - `function_judgement_accuracy`：无 LLM 时以 `bin_similarity` 近似（代理）；
    - `vuln_discovery_rate`：无漏洞 ground truth 时记为 0。
    """
    fb = static_features.features(baseline_exe)
    fp = static_features.features(protected_exe)
    nm = static_features.name_recovery_accuracy(targets, fp["symbols"])
    bs = static_features.bin_similarity(fb, fp)
    return {
        "name_recovery_accuracy": nm,
        # 无 LLM 时：功能判断以名称/符号线索为上界近似（代理）
        "function_judgement_accuracy": nm,
        "vuln_discovery_rate": 0.0,
        "bin_similarity": bs,
    }


def judge(metrics: dict, *, ratio: float | None = None,
          rea_success: bool | None = None, static_only: bool = False) -> dict:
    """按 OI-07 §6/§8 判定，返回 `{pass, reasons}`。"""
    reasons: list[str] = []

    if static_only or rea_success is None:
        ok = (metrics.get("name_recovery_accuracy", 1.0) <= TH["name_recovery_max"]
              and metrics.get("function_judgement_accuracy", 1.0) <= TH["function_judgement_max"]
              and metrics.get("bin_similarity", 1.0) <= TH["bin_similarity_max"])
        reasons.append("未执行 LLM 会话判定（static_only）")
        if not ok:
            reasons.append("静态指标未达目标（name/function/similarity）")
        return {"pass": bool(ok), "reasons": reasons}

    if rea_success:
        reasons.append("REA 成功：出现 S1–S4 成功信号")
        return {"pass": False, "reasons": reasons}

    if ratio is not None and ratio >= TH["context_min"]:
        reasons.append("上下文消耗 >= 90% 仍未成功")
    else:
        reasons.append("会话提前结束且未成功（未出现 S1–S4）")
    return {"pass": True, "reasons": reasons}


def signals_from(session_output: dict, ground_truth: dict) -> dict:
    """由会话产物计算 S1–S4（判分器）。ground_truth 见 `schemas/benchmark.schema.json`。"""
    targets = ground_truth.get("targets", [])
    tnames = [t["name"] for t in targets]
    recovered = session_output.get("recovered_names", {})
    judged = session_output.get("judged_category", {})
    s3_hits = session_output.get("equivalence_hits", [])
    s4_hits = session_output.get("secret_hits", [])

    nr = (sum(1 for t in targets
              if recovered.get(t["symbol"], "").strip().lower() == t["name"].lower())
          / len(targets)) if targets else 0.0
    fj = (sum(1 for t in targets
              if judged.get(t["symbol"]) == t.get("category"))
          / len(targets)) if targets else 0.0
    return {
        "name_recovery_accuracy": round(nr, 4),
        "function_judgement_accuracy": round(fj, 4),
        "S1": fj > TH["function_judgement_max"],
        "S2": nr > TH["name_recovery_max"],
        "S3": len(s3_hits) >= 1,
        "S4": len(s4_hits) >= 1,
        "rea_success": (fj > TH["function_judgement_max"]) or (nr > TH["name_recovery_max"])
                       or len(s3_hits) >= 1 or len(s4_hits) >= 1,
        "targets": tnames,
    }


def aggregate(per_model: list[dict]) -> dict:
    """多模型保守聚合（D4）：任一模型成功即整体不通过。"""
    if not per_model:
        return {"pass": True, "reasons": ["无模型判定"]}
    reasons: list[str] = []
    ok = True
    for i, m in enumerate(per_model):
        if not m.get("pass", True):
            ok = False
            reasons.append("model[%d] 不通过: %s" % (i, "; ".join(m.get("reasons", []))))
    return {"pass": ok, "reasons": reasons or ["全部模型均未成功"]}
