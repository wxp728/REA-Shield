"""策略基因编码与适应度（FR-F3；DD-08 §3/§5，源自 PoC-3）。

- 表型：对每资产 `{selected_strategies, params}`；
- 基因型：每资产 11（策略开关，>0.5 选中）+ 4（coverage/order/noise_ratio/flatten_depth）= 15 位；
- 适应度：防护得分（噪声或叠加）× 敏感权重 − 开销惩罚 − 不适用惩罚；
- 可选：由**实测指标**（DD-07 反馈）替代代理模型（`fitness_from_metrics`）。
"""
from __future__ import annotations

STRATEGIES = [
    "code_virtualization",
    "white_box_crypto",
    "non_linear_mba",
    "adversarial_inducement",
    "control_flow_flattening",
    "mixed_boolean_arithmetic",
    "opaque_predicates",
    "function_boundary_perturbation",
    "data_flow_noise",
    "identifier_renaming",
    "string_encryption",
]

# base=基础防护贡献；overhead=单位开销；applies=适用资产类型
META = {
    "code_virtualization": dict(base=0.40, overhead=0.35, applies={"business_logic", "algorithm", "protocol"}),
    "white_box_crypto": dict(base=0.45, overhead=0.10, applies={"crypto", "secret"}),
    "non_linear_mba": dict(base=0.15, overhead=0.08, applies={"algorithm", "business_logic", "license_check", "crypto", "protocol", "util"}),
    "adversarial_inducement": dict(base=0.20, overhead=0.05, applies={"business_logic", "algorithm", "protocol", "license_check"}),
    "control_flow_flattening": dict(base=0.18, overhead=0.12, applies={"business_logic", "algorithm", "license_check", "protocol"}),
    "mixed_boolean_arithmetic": dict(base=0.14, overhead=0.07, applies={"algorithm", "crypto", "util", "business_logic"}),
    "opaque_predicates": dict(base=0.10, overhead=0.05, applies={"algorithm", "business_logic", "protocol"}),
    "function_boundary_perturbation": dict(base=0.08, overhead=0.04, applies={"business_logic", "algorithm", "protocol", "util", "ui"}),
    "data_flow_noise": dict(base=0.09, overhead=0.06, applies={"business_logic", "algorithm", "protocol", "util"}),
    "identifier_renaming": dict(base=0.03, overhead=0.005, applies={"business_logic", "algorithm", "protocol", "util", "ui", "crypto", "license_check", "secret"}),
    "string_encryption": dict(base=0.12, overhead=0.03, applies={"business_logic", "protocol", "ui", "util"}),
}

SENS_WEIGHT = {"P0": 1.0, "P1": 0.6, "P2": 0.3, "P3": 0.1}

PER_ASSET_GENES = 11 + 4

WEIGHT_STRATEGY = 1.0
LAMBDA_OVERHEAD = 6.0   # 超预算二次惩罚（防作弊式堆叠）
MU_OVERHEAD = 1.5       # 线性开销惩罚
INVALID_PENALTY = 0.5   # 策略不适用于该资产类型时的惩罚
BUDGET = 0.20


def genome_len(assets: list[dict]) -> int:
    return PER_ASSET_GENES * len(assets)


def decode(individual, assets: list[dict]) -> list[tuple]:
    """把实值基因解码为 [(asset, selected, params)]。"""
    out = []
    for ai, asset in enumerate(assets):
        g = individual[ai * PER_ASSET_GENES:(ai + 1) * PER_ASSET_GENES]
        selected = [STRATEGIES[i] for i in range(11) if g[i] > 0.5]
        params = dict(
            coverage=round(min(max(g[11], 0.0), 1.0), 4),
            order=1 + int(min(max(g[12], 0.0), 1.0) * 3.999),
            noise_ratio=round(min(max(g[13], 0.0), 1.0), 4),
            flatten_depth=1 + int(min(max(g[14], 0.0), 1.0) * 4.999),
        )
        out.append((asset, selected, params))
    return out


def eval_fitness(individual, assets: list[dict]) -> tuple:
    """代理适应度（无实测数据时）。`assets` 每项含 type/sensitivity/size。"""
    score = 0.0
    total_overhead = 0.0
    for asset, selected, params in decode(individual, assets):
        w = SENS_WEIGHT[asset["sensitivity"]]
        covered = 0.0
        for name in selected:
            m = META[name]
            base = m["base"]
            if name == "code_virtualization":
                base *= (0.3 + 0.7 * params["coverage"])
            elif name == "non_linear_mba":
                base *= (0.5 + 0.15 * params["order"])
            elif name == "control_flow_flattening":
                base *= (0.5 + 0.1 * params["flatten_depth"])
            elif name == "data_flow_noise":
                base *= (0.3 + 0.7 * params["noise_ratio"])
            if asset["type"] not in m["applies"]:
                base -= INVALID_PENALTY
            base = max(base, -1.0)
            covered = covered + base * (1.0 - covered)
            total_overhead += m["overhead"] * asset.get("size", 1.0)
        score += w * covered
    total_size = sum(a.get("size", 1.0) for a in assets) or 1.0
    overhead = total_overhead / total_size
    penalty = MU_OVERHEAD * overhead + LAMBDA_OVERHEAD * max(0.0, overhead - BUDGET) ** 2
    return (WEIGHT_STRATEGY * score - penalty,)


def fitness_from_metrics(individual, assets: list[dict], metrics: dict) -> tuple:
    """由**实测指标**（DD-07 eval_report.metrics）构造适应度（FR-F3 回填）。

    防护得分 = 期望目标达成度：越低越好的指标（相似度/恢复率）取反归一；
    token/time 倍数取对数放大。开销惩罚沿用代理模型。
    """
    m = metrics or {}
    def _inv(v, target):
        if v is None:
            return 0.0
        return max(0.0, min(1.0, (target - v) / target)) if target else 0.0

    prot = (_inv(m.get("name_recovery_accuracy"), 0.20)
            + _inv(m.get("function_judgement_accuracy"), 0.30)
            + _inv(m.get("bin_similarity"), 0.55)
            + _inv(m.get("vuln_discovery_rate"), 0.10)) / 4.0
    tok = m.get("token_ratio")
    if tok:
        import math
        prot = min(1.0, prot + 0.1 * math.log10(max(tok, 1.0)) / 2.0)
    # 复用代理开销惩罚
    _score, = eval_fitness(individual, assets)
    return (prot, _score)
