#!/usr/bin/env python3
"""
PoC-3: DEAP 策略进化原型
关联：ADR-005 / FR-F3 / docs/design/poc-plan.md §4

目标（通过标准）：
  1. 用 DEAP 表达「策略基因」并跑通一轮完整进化循环
     （种群初始化 → 评估 → 交叉/变异 → 选择）；
  2. 防护得分不劣化（相对初始种群最优非降）；
  3. 运行时间可接受；
  4. 最优个体可导出为符合 schemas/protection_policy.schema.json 的策略文件。

说明：适应度函数的防护/开销模型为**代理模型（placeholder）**，
     与 poc-plan §4「伪造的适应度函数（或少量真实评估数据）」一致；
     真实得分将由评估验证层（Ghidra+LLM，PoC-2）回填。

运行：python3 evolve.py [--seed N] [--gens N]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time

from deap import algorithms, base, creator, tools

# ---------------------------------------------------------------------------
# 资产与策略元数据（与 schemas/protection_policy.schema.json 的策略枚举一致）
# ---------------------------------------------------------------------------
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
S = {name: i for i, name in enumerate(STRATEGIES)}

# base=基础防护贡献；overhead=单位开销；applies=适用资产类型
META = {
    "code_virtualization":             dict(base=0.40, overhead=0.35, applies={"business_logic", "algorithm", "protocol"}),
    "white_box_crypto":                dict(base=0.45, overhead=0.10, applies={"crypto", "secret"}),
    "non_linear_mba":                  dict(base=0.15, overhead=0.08, applies={"algorithm", "business_logic", "license_check", "crypto", "protocol", "util"}),
    "adversarial_inducement":          dict(base=0.20, overhead=0.05, applies={"business_logic", "algorithm", "protocol", "license_check"}),
    "control_flow_flattening":         dict(base=0.18, overhead=0.12, applies={"business_logic", "algorithm", "license_check", "protocol"}),
    "mixed_boolean_arithmetic":        dict(base=0.14, overhead=0.07, applies={"algorithm", "crypto", "util", "business_logic"}),
    "opaque_predicates":               dict(base=0.10, overhead=0.05, applies={"algorithm", "business_logic", "protocol"}),
    "function_boundary_perturbation":  dict(base=0.08, overhead=0.04, applies={"business_logic", "algorithm", "protocol", "util", "ui"}),
    "data_flow_noise":                 dict(base=0.09, overhead=0.06, applies={"business_logic", "algorithm", "protocol", "util"}),
    "identifier_renaming":             dict(base=0.03, overhead=0.005, applies={"business_logic", "algorithm", "protocol", "util", "ui", "crypto", "license_check", "secret"}),
    "string_encryption":               dict(base=0.12, overhead=0.03, applies={"business_logic", "protocol", "ui", "util"}),
}

SENS_WEIGHT = {"P0": 1.0, "P1": 0.6, "P2": 0.3, "P3": 0.1}

# 样例资产清单（等价于资产清单层输出，供 PoC 使用）
ASSETS = [
    dict(path="src/crypto/keymgr.c",   type="crypto",         sensitivity="P0", size=1.0),
    dict(path="src/core/license.c",    type="license_check",  sensitivity="P0", size=1.2),
    dict(path="src/core/engine.c",     type="business_logic", sensitivity="P1", size=2.0),
    dict(path="src/net/protocol.c",    type="protocol",       sensitivity="P1", size=1.5),
    dict(path="src/util/strings.c",    type="util",           sensitivity="P2", size=0.8),
]

PER_ASSET_GENES = 11 + 4  # 11 个策略开关 + coverage/order/noise/depth
GENOME_LEN = PER_ASSET_GENES * len(ASSETS)

WEIGHT_STRATEGY = 1.0
LAMBDA_OVERHEAD = 6.0     # 超预算的二次惩罚系数（防作弊式堆叠）
MU_OVERHEAD = 1.5         # 线性开销惩罚
INVALID_PENALTY = 0.5     # 策略不适用于该资产类型时的惩罚


# ---------------------------------------------------------------------------
# 基因解码
# ---------------------------------------------------------------------------
def decode(individual):
    """把实值基因解码为按资产的策略选择与参数。"""
    plan = []
    for ai, asset in enumerate(ASSETS):
        g = individual[ai * PER_ASSET_GENES:(ai + 1) * PER_ASSET_GENES]
        selected = [STRATEGIES[i] for i in range(11) if g[i] > 0.5]
        params = dict(
            coverage=round(min(max(g[11], 0.0), 1.0), 4),
            order=1 + int(min(max(g[12], 0.0), 1.0) * 3.999),
            noise_ratio=round(min(max(g[13], 0.0), 1.0), 4),
            flatten_depth=1 + int(min(max(g[14], 0.0), 1.0) * 4.999),
        )
        plan.append((asset, selected, params))
    return plan


# ---------------------------------------------------------------------------
# 适应度：防护得分 - 开销惩罚（含去冗余、防堆叠、类型适配）
# ---------------------------------------------------------------------------
def eval_fitness(individual):
    score = 0.0
    total_overhead = 0.0

    for asset, selected, params in decode(individual):
        w = SENS_WEIGHT[asset["sensitivity"]]
        covered = 0.0  # 噪声或（noisy-OR）：叠加同类策略呈边际递减

        for name in selected:
            m = META[name]
            base = m["base"]
            # 参数调制
            if name == "code_virtualization":
                base *= (0.3 + 0.7 * params["coverage"])
            elif name == "non_linear_mba":
                base *= (0.5 + 0.15 * params["order"])
            elif name == "control_flow_flattening":
                base *= (0.5 + 0.1 * params["flatten_depth"])
            elif name == "data_flow_noise":
                base *= (0.3 + 0.7 * params["noise_ratio"])

            if asset["type"] not in m["applies"]:
                base -= INVALID_PENALTY  # 不适用 → 负贡献（阻止乱堆）
            base = max(base, -1.0)

            covered = covered + base * (1.0 - covered)
            total_overhead += m["overhead"] * asset["size"]

        score += w * covered

    total_size = sum(a["size"] for a in ASSETS)
    overhead = total_overhead / total_size
    budget = 0.20
    penalty = MU_OVERHEAD * overhead + LAMBDA_OVERHEAD * max(0.0, overhead - budget) ** 2
    return (WEIGHT_STRATEGY * score - penalty,)


# ---------------------------------------------------------------------------
# DEAP 配置
# ---------------------------------------------------------------------------
def build_toolbox():
    if not hasattr(creator, "FitnessMax"):
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMax)

    tb = base.Toolbox()
    tb.register("attr", random.random)
    tb.register("individual", tools.initRepeat, creator.Individual, tb.attr, GENOME_LEN)
    tb.register("population", tools.initRepeat, list, tb.individual)
    tb.register("evaluate", eval_fitness)
    tb.register("mate", tools.cxTwoPoint)
    tb.register("select", tools.selTournament, tournsize=3)

    def mutate(ind, indpb=0.1, sigma=0.15):
        for i in range(len(ind)):
            if random.random() < indpb:
                ind[i] = min(max(ind[i] + random.gauss(0.0, sigma), 0.0), 1.0)
        return (ind,)

    tb.register("mutate", mutate)
    return tb


def export_policy(individual, path, seed):
    asset_list = []
    for asset, selected, params in decode(individual):
        asset_list.append(dict(
            path=asset["path"],
            sensitivity=asset["sensitivity"],
            strategies=selected,
            params=params,
        ))
    return dict(
        schema_version="1.0",
        seed=seed,
        target=dict(platform="linux-x86_64", language="c", build_system="cmake"),
        performance_budget=dict(max_overhead=0.20, target_overhead=0.20),
        assets=asset_list,
        verification=dict(run_tests=True, abort_on_failure=True),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261015)
    ap.add_argument("--gens", type=int, default=25)
    ap.add_argument("--pop", type=int, default=60)
    args = ap.parse_args()

    random.seed(args.seed)
    tb = build_toolbox()

    POP, NGEN, CXPB, MUTPB = args.pop, args.gens, 0.6, 0.3

    pop = tb.population(n=POP)
    for ind in pop:
        ind.fitness.values = tb.evaluate(ind)

    hof = tools.HallOfFame(1)
    hof.update(pop)
    stats = tools.Statistics(lambda ind: ind.fitness.values[0])
    stats.register("max", max)
    stats.register("avg", lambda xs: sum(xs) / len(xs))

    initial_best = hof[0].fitness.values[0]
    print(f"== PoC-3 DEAP 策略进化 ==  seed={args.seed} pop={POP} gens={NGEN}")
    print(f"初始最优适应度: {initial_best:.4f}")

    t0 = time.time()
    for gen in range(NGEN):
        offspring = list(map(tb.clone, tb.select(pop, len(pop))))
        for c1, c2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < CXPB:
                tb.mate(c1, c2)
                del c1.fitness.values
                del c2.fitness.values
        for m in offspring:
            if random.random() < MUTPB:
                tb.mutate(m)
                del m.fitness.values
        for ind in offspring:
            if not ind.fitness.valid:
                ind.fitness.values = tb.evaluate(ind)

        # 精英保留：把上一代最优替换掉子代最差
        worst = min(range(len(offspring)), key=lambda i: offspring[i].fitness.values[0])
        offspring[worst] = tb.clone(hof[0])
        pop = offspring
        hof.update(pop)
        rec = stats.compile(pop)
        if gen % 5 == 0 or gen == NGEN - 1:
            print(f"  gen {gen:>2}: max={rec['max']:.4f} avg={rec['avg']:.4f}")
    elapsed = time.time() - t0

    best = hof[0]
    best_fit = best.fitness.values[0]
    print(f"\n进化耗时: {elapsed:.2f}s（{NGEN} 代）")
    print(f"最终最优适应度: {best_fit:.4f}（初始 {initial_best:.4f}）")
    non_degrade = best_fit >= initial_best - 1e-9
    print(f"得分不劣化: {'PASS' if non_degrade else 'FAIL'}")

    # 导出并校验策略文件
    policy = export_policy(best, "best_policy.yaml", args.seed)
    here = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(here, "..", "..", "schemas", "protection_policy.schema.json")
    valid = None
    try:
        import jsonschema
        import yaml
        schema = json.load(open(schema_path, encoding="utf-8"))
        jsonschema.validate(policy, schema)
        valid = True
        with open(os.path.join(here, "best_policy.json"), "w", encoding="utf-8") as fh:
            json.dump(policy, fh, ensure_ascii=False, indent=2)
        with open(os.path.join(here, "best_policy.yaml"), "w", encoding="utf-8") as fh:
            yaml.safe_dump(policy, fh, allow_unicode=True, sort_keys=False)
        print("策略导出: best_policy.json / best_policy.yaml（符合 protection_policy schema）")
    except Exception as exc:  # noqa: BLE001
        valid = False
        print(f"策略校验失败: {exc}")

    # 可解释性：打印最优策略概要
    print("\n最优策略概要:")
    for asset, selected, params in decode(best):
        print(f"  {asset['sensitivity']:<2} {asset['path']:<22} "
              f"strategies={selected} params={params}")

    ok = non_degrade and (valid is True)
    print(f"\n结论: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
