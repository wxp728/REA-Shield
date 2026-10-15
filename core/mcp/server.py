"""Anti-REA MCP Server（FR-D6；SRS §4.2；dd-build-integration §5）。

JSON-RPC 2.0 over stdio；7 个工具（`anti_rea.scan/plan/protect/verify/attack_sim/report/evolve`），
每个工具暴露 JSON Schema 供 Agent 发现。出站控制：`attack_sim` 需显式 `allow_llm=true`（CQ-05）。

用法：`python -m core.mcp`（或控制台脚本 `anti-rea-mcp`）。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

from .. import common
from ..scanner import scan as _scan
from ..strategy import plan as _plan
from ..transform import protect as _protect
from ..evaluate import verify as _verify
from ..evaluate import attack_sim as _attack_sim
from .. import report as _report
from ..adaptive import evolve as _evolve

SERVER_NAME = "anti-rea-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"

_OBJECT = {"type": "object"}


def _tool_scan(args: dict) -> dict:
    return _scan(args["path"], args.get("options", {}))


def _tool_plan(args: dict) -> dict:
    budget = args.get("budget") or {}
    return _plan(args["manifest"], budget, seed=args.get("seed", 0))


def _tool_protect(args: dict) -> dict:
    out = args["out"]
    os.makedirs(out, exist_ok=True)
    policy = args["policy"]
    policy = dict(policy)
    policy["_run_id"] = args.get("run_id") or common.new_run_id(args.get("seed"))
    common.write_yaml(os.path.join(out, "protection_policy.yaml"),
                      {k: v for k, v in policy.items() if not k.startswith("_")})
    sources = args.get("sources") or [
        os.path.join(args.get("root", "."), a["path"])
        for a in policy.get("assets", []) if a.get("strategies")]
    meta = _protect(policy, sources, out, root=args.get("root", "."),
                    seed=args.get("seed"))
    return {"metadata": meta, "out": out,
            "transform_log": os.path.join(out, "transform.log")}


def _tool_verify(args: dict) -> dict:
    report = _verify(args["artifacts"], args.get("test_args", []),
                     max_overhead=args.get("max_overhead", 5.0))
    common.write_json(os.path.join(args["artifacts"], "verification_report.json"), report)
    return report


def _tool_attack_sim(args: dict) -> dict:
    return _attack_sim(args["artifacts"], benchmark=args.get("benchmark"),
                       allow_llm=bool(args.get("allow_llm", False)),
                       mode=args.get("mode", "static"), db=args.get("db"))


def _tool_report(args: dict) -> dict:
    path = _report.generate(args["run"], args.get("format", "md"))
    return {"path": path, "layout": _report.layout_ok(args["run"])}


def _tool_evolve(args: dict) -> dict:
    assets = args.get("assets")
    if not assets and args.get("manifest"):
        manifest = args["manifest"]
        assets = [{"path": a["path"], "type": a.get("type", "business_logic"),
                   "sensitivity": a.get("sensitivity", "P3")}
                  for a in manifest.get("assets", []) if not a.get("skip_transform")]
    if not assets:
        raise ValueError("E_INVALID_INPUT: evolve 需要 assets 或 manifest")
    res = _evolve(assets, seed=args.get("seed", 20261016),
                  pop=args.get("pop"), gens=args.get("gens"),
                  metrics=args.get("metrics"))
    return {"best_policy": res["best_policy"], "best_fitness": res["best_fitness"],
            "initial_fitness": res["initial_fitness"], "non_degrade": res["non_degrade"]}


TOOLS = [
    {
        "name": "anti_rea.scan",
        "description": "扫描工程，产出符合 asset_manifest schema 的资产清单（只读幂等）。",
        "inputSchema": {"type": "object", "required": ["path"],
                        "properties": {"path": {"type": "string"},
                                       "options": _OBJECT}},
        "handler": _tool_scan,
    },
    {
        "name": "anti_rea.plan",
        "description": "由资产清单生成保护策略（protection_policy）。",
        "inputSchema": {"type": "object", "required": ["manifest"],
                        "properties": {"manifest": _OBJECT, "budget": _OBJECT,
                                       "seed": {"type": "integer"}}},
        "handler": _tool_plan,
    },
    {
        "name": "anti_rea.protect",
        "description": "按策略执行变换，产出保护产物 + 变换日志（同 seed 确定性）。",
        "inputSchema": {"type": "object", "required": ["policy", "out"],
                        "properties": {"policy": _OBJECT, "root": {"type": "string"},
                                       "sources": {"type": "array", "items": {"type": "string"}},
                                       "out": {"type": "string"},
                                       "seed": {"type": "integer"},
                                       "run_id": {"type": "string"}}},
        "handler": _tool_protect,
    },
    {
        "name": "anti_rea.verify",
        "description": "功能保持 + 性能基准验证（差分），产出 verification_report（只读幂等）。",
        "inputSchema": {"type": "object", "required": ["artifacts"],
                        "properties": {"artifacts": {"type": "string"},
                                       "test_args": {"type": "array", "items": {"type": "string"}},
                                       "max_overhead": {"type": "number"}}},
        "handler": _tool_verify,
    },
    {
        "name": "anti_rea.attack_sim",
        "description": "攻击模拟（静态/动态/跨版本），产出 eval_report（只读幂等；LLM 出站需 allow_llm）。",
        "inputSchema": {"type": "object", "required": ["artifacts"],
                        "properties": {"artifacts": {"type": "string"},
                                       "benchmark": {"type": "string"},
                                       "mode": {"type": "string",
                                                "enum": ["static", "dynamic", "crossver", "all"]},
                                       "allow_llm": {"type": "boolean"},
                                       "db": {"type": "string"}}},
        "handler": _tool_attack_sim,
    },
    {
        "name": "anti_rea.report",
        "description": "生成保护报告（json/md/html）并返回统一产物目录定位。",
        "inputSchema": {"type": "object", "required": ["run"],
                        "properties": {"run": {"type": "string"},
                                       "format": {"type": "string",
                                                  "enum": ["json", "md", "html"]}}},
        "handler": _tool_report,
    },
    {
        "name": "anti_rea.evolve",
        "description": "策略遗传进化（有状态），返回最优策略与适应度。",
        "inputSchema": {"type": "object",
                        "properties": {"assets": {"type": "array", "items": _OBJECT},
                                       "manifest": _OBJECT,
                                       "seed": {"type": "integer"},
                                       "pop": {"type": "integer"},
                                       "gens": {"type": "integer"},
                                       "metrics": _OBJECT}},
        "handler": _tool_evolve,
    },
]


def _ok(req_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str, data=None) -> dict:
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": e}


def handle(request: dict) -> dict | None:
    """处理单条 JSON-RPC 请求；通知（无 id）返回 None。"""
    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        return _ok(req_id, {"protocolVersion": PROTOCOL_VERSION,
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": SERVER_NAME,
                                           "version": SERVER_VERSION}})
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return _ok(req_id, {})
    if method == "tools/list":
        return _ok(req_id, {"tools": [{"name": t["name"],
                                       "description": t["description"],
                                       "inputSchema": t["inputSchema"]}
                                      for t in TOOLS]})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if not tool:
            return _err(req_id, -32602, "未知工具: %s" % name)
        try:
            result = tool["handler"](arguments)
        except Exception as exc:  # noqa: BLE001
            return _ok(req_id, {"content": [{"type": "text",
                                             "text": "error: %s" % exc}],
                                "isError": True})
        return _ok(req_id, {"content": [{"type": "text",
                                         "text": json.dumps(result, ensure_ascii=False)}],
                            "isError": False})
    if req_id is None:
        return None
    return _err(req_id, -32601, "未实现的方法: %s" % method)


def serve(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        try:
            resp = handle(request)
        except Exception:  # noqa: BLE001
            resp = _err(request.get("id"), -32603, "internal error",
                        traceback.format_exc())
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()


def main() -> int:
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
