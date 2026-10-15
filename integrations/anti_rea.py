#!/usr/bin/env python3
"""Anti-REA 构建集成共享驱动（FR-D2…D5）。

CMake / Cargo / npm / Python 插件统一调用本入口：**不内嵌引擎**，只走
scan → plan → protect → verify 链路（`docs/design/ddd/dd-build-integration.md §4`）。
验证失败时可返回非零以中止构建（FR-D7）。
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from core import common  # noqa: E402
from core.scanner import scan  # noqa: E402
from core.strategy import plan  # noqa: E402
from core.transform import protect  # noqa: E402
from core.evaluate import verify  # noqa: E402


def pipeline(root: str, sources: list[str], out: str, seed: int,
             max_overhead: float, abort_on_failure: bool) -> int:
    os.makedirs(out, exist_ok=True)
    manifest = scan(root)
    common.validate(manifest, "asset_manifest.schema.json")
    policy = plan(manifest, {"max_overhead": max_overhead,
                             "target_overhead": max_overhead / 2.0}, seed=seed)
    policy["_run_id"] = manifest.get("run_id", "")
    common.write_yaml(os.path.join(out, "protection_policy.yaml"),
                      {k: v for k, v in policy.items() if not k.startswith("_")})

    if not sources:
        sources = [os.path.join(root, a["path"]) for a in policy.get("assets", [])
                   if a.get("strategies")]
    protect(policy, sources, out, root=root, seed=seed)
    report = verify(out, [], max_overhead=5.0)
    common.write_json(os.path.join(out, "verification_report.json"), report)

    ok = bool(report.get("functional_pass") and report.get("overall_pass"))
    print("anti-rea pipeline: functional_pass=%s overall_pass=%s -> %s"
          % (report.get("functional_pass"), report.get("overall_pass"), out))
    if not ok and abort_on_failure:
        print("anti-rea: 验证失败，构建中止（abort_on_failure=true）", file=sys.stderr)
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="anti-rea-integration")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("pipeline", help="scan→plan→protect→verify")
    s.add_argument("--root", default=".")
    s.add_argument("--source", action="append", default=[])
    s.add_argument("--out", required=True)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--max-overhead", type=float, default=0.20)
    s.add_argument("--abort-on-failure", action="store_true")
    s.set_defaults(func=lambda a: pipeline(a.root, a.source, a.out, a.seed,
                                           a.max_overhead, a.abort_on_failure))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
