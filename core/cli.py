"""REA-Shield CLI（FR-D1）。

子命令：scan / plan / protect / verify / report（SRS §4.1）+
扩展：attack_sim（FR-E3）/ regress（FR-E8）/ diff（FR-G3）/ evolve（FR-F3）。
设计：docs/design/ddd/dd-build-integration.md §3 / dd-07 / dd-08。
退出码：0 成功、1 一般错误、2 验证失败、3 拒绝执行。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import common
from .scanner import scan as _scan
from .strategy import plan as _plan
from .transform import protect as _protect
from .evaluate import verify as _verify
from .evaluate import attack_sim as _attack_sim
from . import report as _report

EXIT_OK, EXIT_ERR, EXIT_VERIFY, EXIT_REFUSED = 0, 1, 2, 3


def _cmd_scan(args) -> int:
    options: dict = {"allow_unknown_owner": args.allow_unknown_owner}
    if args.include:
        options["include"] = args.include
    if args.exclude:
        options["exclude"] = args.exclude
    manifest = _scan(args.path, options)
    out = os.path.join(args.out, "asset_manifest.json")
    common.write_json(out, manifest)
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print("scan: %d assets -> %s" % (len(manifest["assets"]), out))
    return EXIT_OK


def _cmd_plan(args) -> int:
    manifest = common.read_json(args.manifest)
    budget = {"max_overhead": args.max_overhead, "target_overhead": args.target_overhead}
    scope: dict = {}
    if args.only_path:
        scope["only_path"] = args.only_path
    if args.only_func:
        scope["only_func"] = args.only_func
    policy = _plan(manifest, budget, seed=args.seed, scope=scope or None)
    policy["_run_id"] = manifest.get("run_id", "")
    out = os.path.join(args.out, "protection_policy.yaml")
    common.write_yaml(out, {k: v for k, v in policy.items() if not k.startswith("_")})
    if args.json:
        print(json.dumps(policy, ensure_ascii=False, indent=2))
    else:
        print("plan: %d assets -> %s" % (len(policy["assets"]), out))
    return EXIT_OK


def _cmd_protect(args) -> int:
    policy = common.read_yaml(args.policy)
    policy["_run_id"] = args.run_id or policy.get("run_id") or common.new_run_id(args.seed)
    sources = args.source
    if not sources:
        # 缺省：策略资产路径解析为源文件
        sources = [os.path.join(args.root, a["path"]) for a in policy.get("assets", [])
                   if a.get("strategies")]
    meta = _protect(policy, sources, args.out, root=args.root, seed=args.seed,
                    protect_all=args.protect_all)
    print("protect: artifacts -> %s (strategies=%s, whitelist=%s)" %
          (args.out, meta["strategies"], meta["whitelist"]))
    return EXIT_OK


def _cmd_verify(args) -> int:
    report = _verify(args.artifacts, args.test_args, max_overhead=args.max_overhead)
    out = os.path.join(args.artifacts, "verification_report.json")
    common.write_json(out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("verify: functional_pass=%s overall_pass=%s -> %s" %
              (report["functional_pass"], report["overall_pass"], out))
    return EXIT_OK if report["overall_pass"] else EXIT_VERIFY


def _cmd_report(args) -> int:
    out = _report.generate(args.run, args.format if args.format != "all" else "md")
    print("report -> %s" % out)
    return EXIT_OK


def _cmd_attack_sim(args) -> int:
    report = _attack_sim(args.artifacts, benchmark=args.benchmark,
                         allow_llm=args.allow_llm, mode=args.mode, db=args.db)
    out = os.path.join(args.artifacts, "eval_report.json")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("attack_sim: verdict_pass=%s -> %s" %
              (report["verdict"]["pass"], out))
    return EXIT_OK if report["verdict"]["pass"] else EXIT_VERIFY


def _cmd_diff(args) -> int:
    result = _report.diff(args.run_a, args.run_b)
    print("diff: %d 指标差异, %d 产物变更 -> %s" %
          (len(result["metrics"]), len(result["artifacts"]["changed"]),
           os.path.join(args.run_b, "diff_report.json")))
    return EXIT_OK


def _cmd_regress(args) -> int:
    from .evaluate import regression
    result = regression.regress(args.artifacts, args.db, args.benchmark,
                                mode=args.mode, allow_llm=args.allow_llm)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("regress: degraded=%s (%d 退化, %d 未达标) -> %s" %
              (result["degraded"], len(result["regressions"]),
               len(result["target_violations"]),
               os.path.join(args.artifacts, "regression_report.json")))
    return EXIT_VERIFY if result["degraded"] else EXIT_OK


def _cmd_evolve(args) -> int:
    from .adaptive import evolve as _evolve, knowledge
    manifest = common.read_json(args.manifest)
    assets = [{"path": a["path"], "type": a.get("type", "business_logic"),
               "sensitivity": a.get("sensitivity", "P3")}
              for a in manifest.get("assets", []) if not a.get("skip_transform")]
    if not assets:
        print("evolve: 无可用资产", file=sys.stderr)
        return EXIT_ERR
    res = _evolve(assets, seed=args.seed, pop=args.pop, gens=args.gens)
    policy = res["best_policy"]
    os.makedirs(args.out, exist_ok=True)
    out = os.path.join(args.out, "protection_policy.yaml")
    common.write_yaml(out, policy)
    if args.kb:
        sig = knowledge.signature(manifest.get("target", {}).get("language", ""), assets)
        knowledge.save(args.kb, {"signature": sig, "seed": args.seed,
                                 "fitness": res["best_fitness"], "policy": policy})
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("evolve: best_fitness=%.4f initial=%.4f non_degrade=%s -> %s" %
              (res["best_fitness"], res["initial_fitness"], res["non_degrade"], out))
    return EXIT_OK


def _cmd_doctor(args) -> int:
    from . import toolchain
    if args.llvm:
        os.environ["ANTI_REA_LLVM"] = args.llvm
    report = toolchain.doctor()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(toolchain.format_report(report))
    return EXIT_OK if report["ok"] else EXIT_ERR


def build_parser() -> argparse.ArgumentParser:
    from . import __version__
    p = argparse.ArgumentParser(prog="anti-rea", description="REA-Shield CLI")
    p.add_argument("--version", action="version",
                   version="anti-rea %s" % __version__)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("doctor", help="环境自检：检查 Python/LLVM/插件/工具链是否就绪")
    s.add_argument("--llvm", default=None,
                   help="指定 LLVM 前缀（等价于设置 ANTI_REA_LLVM）")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_doctor)

    s = sub.add_parser("scan", help="扫描工程，产出 asset_manifest.json")
    s.add_argument("path")
    s.add_argument("-o", "--out", default=".")
    s.add_argument("--json", action="store_true")
    s.add_argument("--allow-unknown-owner", action="store_true")
    s.add_argument("--include", action="append", default=[],
                   help="只扫描该子路径（可重复；相对 root，子串匹配）")
    s.add_argument("--exclude", action="append", default=[],
                   help="排除该子路径（可重复；相对 root，子串匹配）")
    s.set_defaults(func=_cmd_scan)

    s = sub.add_parser("plan", help="生成 protection_policy.yaml")
    s.add_argument("manifest")
    s.add_argument("-o", "--out", default=".")
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--max-overhead", type=float, default=0.20)
    s.add_argument("--target-overhead", type=float, default=0.10)
    s.add_argument("--only-path", action="append", default=[],
                   help="只保护路径匹配该 glob 的资产（可重复；收窄范围）")
    s.add_argument("--only-func", action="append", default=[],
                   help="只保护符号名匹配该正则的资产（可重复；收窄范围）")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_plan)

    s = sub.add_parser("protect", help="执行变换，产出保护产物")
    s.add_argument("policy")
    s.add_argument("--source", action="append", default=[])
    s.add_argument("--root", default=".")
    s.add_argument("-o", "--out", default="build/run")
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--run-id", default="")
    s.add_argument("--protect-all", action="store_true",
                   help="整文件保护：白名单取 scope 内文件全部函数（含内部辅助函数）")
    s.set_defaults(func=_cmd_protect)

    s = sub.add_parser("verify", help="功能保持验证（差分）")
    s.add_argument("artifacts")
    s.add_argument("--test-args", nargs="*", default=[])
    s.add_argument("--max-overhead", type=float, default=5.0)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_verify)

    s = sub.add_parser("report", help="生成保护报告（json/md/html）")
    s.add_argument("run")
    s.add_argument("--format", choices=["md", "json", "html", "all"], default="md")
    s.set_defaults(func=_cmd_report)

    s = sub.add_parser("attack_sim", help="攻击模拟，产出 eval_report.json")
    s.add_argument("artifacts")
    s.add_argument("--benchmark", default=None)
    s.add_argument("--mode", choices=["static", "dynamic", "crossver", "all"],
                   default="static")
    s.add_argument("--allow-llm", action="store_true")
    s.add_argument("--db", default=None, help="指标时间序列 SQLite 路径")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_attack_sim)

    s = sub.add_parser("diff", help="对比两次运行（FR-G3）")
    s.add_argument("run_a")
    s.add_argument("run_b")
    s.set_defaults(func=_cmd_diff)

    s = sub.add_parser("regress", help="回归检测：重跑攻击模拟并比对历史（FR-E8）")
    s.add_argument("artifacts")
    s.add_argument("--benchmark", default=None)
    s.add_argument("--db", required=True, help="指标时间序列 SQLite 路径")
    s.add_argument("--mode", choices=["static", "dynamic", "crossver", "all"],
                   default="static")
    s.add_argument("--allow-llm", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_regress)

    s = sub.add_parser("evolve", help="策略遗传进化（FR-F3），产出 protection_policy.yaml")
    s.add_argument("manifest")
    s.add_argument("-o", "--out", default=".")
    s.add_argument("--seed", type=int, default=20261016)
    s.add_argument("--pop", type=int, default=None)
    s.add_argument("--gens", type=int, default=None)
    s.add_argument("--kb", default=None, help="策略知识库 JSON 路径（FR-F4）")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_evolve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_REFUSED
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERR
    except Exception as exc:  # noqa: BLE001
        print("error: %s" % exc, file=sys.stderr)
        return EXIT_ERR


if __name__ == "__main__":
    raise SystemExit(main())
