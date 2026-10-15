"""Anti-REA 策略决策层（Strategy Engine v0.1，R1 MVP）。

设计：docs/design/ddd/dd-02-strategy.md
覆盖：FR-B1（模板库）、FR-B2（按敏感度匹配）、FR-B6（Schema 校验）。
FR-B3/B4/B5 留待后续迭代。
"""
from __future__ import annotations

import os

from .. import common


def _load_templates() -> tuple[dict, list[dict], str]:
    tpl = common.read_yaml(os.path.join(common.POLICY_DIR, "strategy_templates.yaml"))
    rules_doc = common.read_yaml(os.path.join(common.POLICY_DIR, "match_rules.yaml"))
    templates = {t["id"]: t for t in tpl.get("templates", [])}
    return templates, rules_doc.get("rules", []), rules_doc.get("default", "P3-none")


def _match(asset: dict, project: dict, rules: list[dict], default: str) -> str:
    ctx = {
        "sensitivity": asset.get("sensitivity"),
        "type": asset.get("type"),
        "skip_transform": asset.get("skip_transform", False),
        "language": project.get("language"),
    }
    for rule in rules:
        when = rule.get("when", {})
        if all(ctx.get(k) == v for k, v in when.items()):
            return rule["use"]
    return default


def plan(manifest: dict, budget: dict | None = None, seed: int | None = None) -> dict:
    """依据资产清单与预算生成 protection_policy（dict）。"""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("assets"), list):
        raise ValueError("E_INVALID_INPUT: manifest.assets 缺失或非数组")
    budget = budget or {}
    templates, rules, default = _load_templates()
    project = manifest.get("project", {})

    assets_out: list[dict] = []
    for a in manifest.get("assets", []):
        tpl_id = _match(a, project, rules, default)
        tpl = templates.get(tpl_id, {"strategies": []})
        entry = {
            "path": a["path"],
            "sensitivity": a["sensitivity"],
            "strategies": list(tpl.get("strategies", [])),
        }
        if tpl.get("params"):
            entry["params"] = dict(tpl["params"])
        if tpl.get("mtd"):
            entry["mtd"] = dict(tpl["mtd"])
        assets_out.append(entry)

    policy = {
        "schema_version": common.SCHEMA_VERSION,
        "seed": int(seed) if seed is not None else 0,
        "target": {
            "platform": project.get("target_platform", "unknown"),
            "language": project.get("language", "unknown"),
            "build_system": project.get("build_system", "unknown"),
        },
        "performance_budget": {
            "max_overhead": float(budget.get("max_overhead", 0.20)),
            "target_overhead": float(budget.get("target_overhead", 0.10)),
        },
        "assets": assets_out,
        "verification": {"run_tests": True, "abort_on_failure": True},
    }
    common.validate(policy, "protection_policy.schema.json")
    return policy
