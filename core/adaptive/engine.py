"""自适应策略进化引擎（FR-F3；DD-08 §4；ADR-004/005）。

DEAP 进化循环（种群→评估→交叉/变异→选择），精英保留保证**不劣化**；
最优个体导出为符合 `protection_policy.schema.json` 的策略（可复现、seed 决定）。
可选：以 DD-07 实测指标（`metrics`）回填适应度。
"""
from __future__ import annotations

import random

from . import genome

DEFAULTS = {"pop": 60, "gens": 25, "cxpb": 0.6, "mutpb": 0.3}


def _toolbox(assets: list[dict], metrics: dict | None):
    from deap import base, creator, tools

    if not hasattr(creator, "AntiReaFitnessMax"):
        creator.create("AntiReaFitnessMax", base.Fitness, weights=(1.0,))
    if not hasattr(creator, "AntiReaIndividual"):
        creator.create("AntiReaIndividual", list,
                       fitness=creator.AntiReaFitnessMax)

    tb = base.Toolbox()
    tb.register("attr", random.random)
    tb.register("individual", tools.initRepeat, creator.AntiReaIndividual,
                tb.attr, genome.genome_len(assets))
    tb.register("population", tools.initRepeat, list, tb.individual)
    if metrics:
        tb.register("evaluate", lambda ind: genome.fitness_from_metrics(ind, assets, metrics))
    else:
        tb.register("evaluate", lambda ind: genome.eval_fitness(ind, assets))
    tb.register("mate", tools.cxTwoPoint)
    tb.register("select", tools.selTournament, tournsize=3)

    def mutate(ind, indpb=0.1, sigma=0.15):
        for i in range(len(ind)):
            if random.random() < indpb:
                ind[i] = min(max(ind[i] + random.gauss(0.0, sigma), 0.0), 1.0)
        return (ind,)

    tb.register("mutate", mutate)
    return tb


def export_policy(individual, assets: list[dict], seed: int,
                  target: dict | None = None,
                  budget: dict | None = None) -> dict:
    asset_list = []
    for asset, selected, params in genome.decode(individual, assets):
        asset_list.append(dict(path=asset["path"],
                               sensitivity=asset["sensitivity"],
                               strategies=selected, params=params))
    return {
        "schema_version": "1.0",
        "seed": seed,
        "target": target or {"platform": "linux-x86_64", "language": "c",
                             "build_system": "cmake"},
        "performance_budget": budget or {"max_overhead": genome.BUDGET,
                                         "target_overhead": genome.BUDGET},
        "assets": asset_list,
        "verification": {"run_tests": True, "abort_on_failure": True},
    }


def evolve(assets: list[dict], seed: int = 20261016, pop: int | None = None,
           gens: int | None = None, metrics: dict | None = None,
           target: dict | None = None, budget: dict | None = None) -> dict:
    """跑一轮进化，返回 `{best_policy, best_fitness, initial_fitness, history, non_degrade}`。"""
    from deap import tools

    if not assets:
        raise ValueError("E_INVALID_INPUT: 无资产可供进化")
    pop = pop or DEFAULTS["pop"]
    gens = gens or DEFAULTS["gens"]
    cxpb, mutpb = DEFAULTS["cxpb"], DEFAULTS["mutpb"]

    random.seed(seed)
    tb = _toolbox(assets, metrics)

    population = tb.population(n=pop)
    for ind in population:
        ind.fitness.values = tb.evaluate(ind)

    hof = tools.HallOfFame(1)
    hof.update(population)
    history = []
    initial_best = hof[0].fitness.values[0]

    for gen in range(gens):
        offspring = list(map(tb.clone, tb.select(population, len(population))))
        for c1, c2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < cxpb:
                tb.mate(c1, c2)
                del c1.fitness.values, c2.fitness.values
        for m in offspring:
            if random.random() < mutpb:
                tb.mutate(m)
                del m.fitness.values
        for ind in offspring:
            if not ind.fitness.valid:
                ind.fitness.values = tb.evaluate(ind)
        # 精英保留
        worst = min(range(len(offspring)), key=lambda i: offspring[i].fitness.values[0])
        offspring[worst] = tb.clone(hof[0])
        population = offspring
        hof.update(population)
        history.append(round(max(i.fitness.values[0] for i in population), 6))

    best = hof[0]
    best_fit = best.fitness.values[0]
    return {
        "best_policy": export_policy(best, assets, seed, target, budget),
        "best_fitness": round(best_fit, 6),
        "initial_fitness": round(initial_best, 6),
        "history": history,
        "non_degrade": best_fit >= initial_best - 1e-9,
    }
