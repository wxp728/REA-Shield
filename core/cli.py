"""Anti-REA CLI（FR-D1，R1 MVP）。

子命令：scan / plan / protect / verify / report
设计：docs/design/ddd/dd-build-integration.md §3
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

EXIT_OK, EXIT_ERR, EXIT_VERIFY, EXIT_REFUSED = 0, 1, 2, 3


def _cmd_scan(args) -> int:
    manifest = _scan(args.path, {"allow_unknown_owner": args.allow_unknown_owner})
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
    policy = _plan(manifest, budget, seed=args.seed)
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
    policy["_run_id"] = args.run_id or ""
    sources = args.source
    if not sources:
        # 缺省：策略资产路径解析为源文件
        sources = [os.path.join(args.root, a["path"]) for a in policy.get("assets", [])
                   if a.get("strategies")]
    meta = _protect(policy, sources, args.out, root=args.root, seed=args.seed)
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
    meta = common.read_json(os.path.join(args.run, "metadata.json"))
    lines = ["# Anti-REA 保护报告", "", "run_id: %s" % meta.get("run_id", ""),
             "strategies: %s" % ",".join(meta.get("strategies", [])),
             "whitelist: %s" % ",".join(meta.get("whitelist", []))]
    md = "\n".join(lines) + "\n"
    out = os.path.join(args.run, "report.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(md)
    if args.format == "json":
        common.write_json(os.path.join(args.run, "report.json"),
                          {"run_id": meta.get("run_id", ""), "markdown": md})
    print("report -> %s" % out)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="anti-rea", description="Anti-REA Skill CLI")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="扫描工程，产出 asset_manifest.json")
    s.add_argument("path")
    s.add_argument("-o", "--out", default=".")
    s.add_argument("--json", action="store_true")
    s.add_argument("--allow-unknown-owner", action="store_true")
    s.set_defaults(func=_cmd_scan)

    s = sub.add_parser("plan", help="生成 protection_policy.yaml")
    s.add_argument("manifest")
    s.add_argument("-o", "--out", default=".")
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--max-overhead", type=float, default=0.20)
    s.add_argument("--target-overhead", type=float, default=0.10)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_plan)

    s = sub.add_parser("protect", help="执行变换，产出保护产物")
    s.add_argument("policy")
    s.add_argument("--source", action="append", default=[])
    s.add_argument("--root", default=".")
    s.add_argument("-o", "--out", default="build/run")
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--run-id", default="")
    s.set_defaults(func=_cmd_protect)

    s = sub.add_parser("verify", help="功能保持验证（差分）")
    s.add_argument("artifacts")
    s.add_argument("--test-args", nargs="*", default=[])
    s.add_argument("--max-overhead", type=float, default=5.0)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_verify)

    s = sub.add_parser("report", help="生成保护报告")
    s.add_argument("run")
    s.add_argument("--format", choices=["md", "json"], default="md")
    s.set_defaults(func=_cmd_report)
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
