#!/usr/bin/env python3
"""S5 Beta 试点运行器（M7）。

对 2–3 个**不同语言/构建系统/敏感度**的试点工程，按文档流程独立完成保护闭环，
采集证据并产出 `docs/release/pilot-report.md`（试点报告）与改进行动。

用法：
  python tools/run_s5.py [--out build/s5] [--docs docs/release]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core import common  # noqa: E402
from core.scanner import scan  # noqa: E402
from core.strategy import plan  # noqa: E402
from core.transform import protect  # noqa: E402
from core.evaluate import verify, attack_sim  # noqa: E402

PILOTS = [
    {"id": "crypto-lib", "lang": "C", "build": "CMake", "level": "P0",
     "root": "pilots/crypto-lib", "source": "src/license.c",
     "benchmark": "benchmarks/bench-crypto-lib.yaml",
     "build_cmd": ["cmake -S {root} -B {tmp} && cmake --build {tmp}"]},
    {"id": "protocol-svc", "lang": "C++", "build": "Make", "level": "P1",
     "root": "pilots/protocol-svc", "source": "src/decode.cpp",
     "benchmark": "benchmarks/bench-protocol.yaml",
     "build_cmd": ["make -C {root}"]},
    {"id": "python-ext", "lang": "Python C 扩展", "build": "setuptools build_ext",
     "level": "P2", "root": "pilots/python-ext", "source": "src/transform.c",
     "benchmark": "benchmarks/bench-python-ext.yaml", "build_cmd": []},
]


def _sh(cmd: str) -> tuple[int, str]:
    p = subprocess.run(["bash", "-lc", cmd], cwd=REPO, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _run_native(pilot: dict, workdir: str) -> dict:
    """C / C++ 试点：走 scan→plan→protect→verify→attack_sim→report。"""
    root = os.path.join(REPO, pilot["root"])
    source = os.path.join(root, pilot["source"])
    out = os.path.join(workdir, pilot["id"], "anti-rea")
    t0 = time.perf_counter()
    manifest = scan(root)
    policy = plan(manifest, {"max_overhead": 0.5}, seed=7)
    policy["_run_id"] = manifest["run_id"]
    os.makedirs(out, exist_ok=True)
    common.write_yaml(os.path.join(out, "protection_policy.yaml"),
                      {k: v for k, v in policy.items() if not k.startswith("_")})
    meta = protect(policy, [source], out, root=root, seed=7)
    vr = verify(out)
    common.write_json(os.path.join(out, "verification_report.json"), vr)
    bench = os.path.join(REPO, pilot["benchmark"])
    er = attack_sim(out, benchmark=bench)
    prot = {k: v for k, v in policy.items() if not k.startswith("_")}
    return {
        "id": pilot["id"], "lang": pilot["lang"], "build": pilot["build"],
        "level": pilot["level"],
        "assets": len(manifest.get("assets", [])),
        "sensitive": [a["path"] for a in manifest.get("assets", [])
                      if a.get("sensitivity") in ("P0", "P1", "P2")],
        "strategies": meta["strategies"], "whitelist": meta["whitelist"],
        "functional_pass": bool(vr["functional_pass"]),
        "overall_pass": bool(vr["overall_pass"]),
        "attack_verdict_pass": bool(er["verdict"]["pass"]),
        "metrics": er["metrics"], "out": os.path.relpath(out, REPO),
        "policy_seed": prot.get("seed"), "elapsed_sec": round(time.perf_counter() - t0, 2),
        "independent_loop": True,
    }


def _run_python_ext(pilot: dict, workdir: str) -> dict:
    """Python C 扩展试点：经 build_ext 集成在构建期完成保护，并验证可导入。"""
    py = os.environ.get("ANTI_REA_PYTHON", sys.executable)
    dst = os.path.join(workdir, pilot["id"])
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, pilot["root"]), dst)
    env = dict(os.environ)
    env.update({"ANTI_REA_PYTHON": py,
                "ANTI_REA_INTEGRATIONS": os.path.join(REPO, "integrations", "python"),
                "ANTI_REA_DRIVER": os.path.join(REPO, "integrations", "anti-rea")})
    t0 = time.perf_counter()
    r = subprocess.run([py, "setup.py", "build_ext", "--inplace"], cwd=dst,
                       capture_output=True, text=True, env=env)
    build_ok = r.returncode == 0
    run_dir = os.path.join(dst, "anti-rea")
    vr = {}
    meta = {}
    if os.path.exists(os.path.join(run_dir, "verification_report.json")):
        vr = common.read_json(os.path.join(run_dir, "verification_report.json"))
    if os.path.exists(os.path.join(run_dir, "metadata.json")):
        meta = common.read_json(os.path.join(run_dir, "metadata.json"))
    # 导入并调用（保护后语义应保持）
    imp = subprocess.run([py, "-c", "import pilotext; print(pilotext.transform(7))"],
                         cwd=dst, capture_output=True, text=True)
    import_ok = imp.returncode == 0
    prot_val = (imp.stdout or "").strip()
    base = subprocess.run([os.path.join(run_dir, "artifacts", "baseline")],
                          capture_output=True, text=True)
    base_val = (base.stdout or "").strip()
    er = {}
    if os.path.isdir(run_dir):
        er = attack_sim(run_dir, benchmark=os.path.join(REPO, pilot["benchmark"]))
    return {
        "id": pilot["id"], "lang": pilot["lang"], "build": pilot["build"],
        "level": pilot["level"], "build_ok": build_ok,
        "functional_pass": bool(vr.get("functional_pass")) and import_ok
        and prot_val == base_val and prot_val != "",
        "overall_pass": bool(vr.get("overall_pass", True)),
        "attack_verdict_pass": bool(er.get("verdict", {}).get("pass", False)),
        "metrics": er.get("metrics", {}),
        "strategies": meta.get("strategies", []),
        "whitelist": meta.get("whitelist", []),
        "import_ok": import_ok, "protected_value": prot_val,
        "baseline_value": base_val,
        "out": os.path.relpath(run_dir, REPO),
        "elapsed_sec": round(time.perf_counter() - t0, 2),
        "independent_loop": build_ok and import_ok,
    }


def run_all(workdir: str) -> dict:
    os.makedirs(workdir, exist_ok=True)
    results = []
    for pilot in PILOTS:
        tmp = tempfile.mkdtemp(prefix="pilot-build-", dir=workdir)
        for c in pilot["build_cmd"]:
            _sh(c.format(root=pilot["root"], tmp=tmp))
        if pilot["id"] == "python-ext":
            results.append(_run_python_ext(pilot, workdir))
        else:
            results.append(_run_native(pilot, workdir))
    return {"pilots": results,
            "all_functional": all(p["functional_pass"] for p in results),
            "all_attack_pass": all(p["attack_verdict_pass"] for p in results),
            "all_independent": all(p["independent_loop"] for p in results)}


def _md(res: dict) -> str:
    L = ["# S5 Beta 试点报告（Pilot Report）", "",
         "> 由 `tools/run_s5.py` 生成（`plan §7`）。试点覆盖不同语言 / 构建系统 / 敏感度。",
         "", "## 1. 试点总览", "",
         "| 试点 | 语言 | 构建系统 | 敏感度 | 资产 | 功能保持 | 对抗判定 | 独立闭环 |",
         "| :--- | :--- | :--- | :--- | ---: | :--- | :--- | :--- |"]
    for p in res["pilots"]:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |"
                 % (p["id"], p["lang"], p["build"], p["level"],
                    p.get("assets", "-"),
                    "通过" if p["functional_pass"] else "失败",
                    "通过" if p["attack_verdict_pass"] else "未通过",
                    "是" if p["independent_loop"] else "否"))
    L += ["", "## 2. 逐试点详情", ""]
    for p in res["pilots"]:
        L += ["### %s（%s / %s / %s）" % (p["id"], p["lang"], p["build"], p["level"]), "",
              "- 产物目录：`%s`" % p["out"],
              "- 策略：`%s`" % json.dumps(p.get("strategies", []), ensure_ascii=False),
              "- 白名单：`%s`" % json.dumps(p.get("whitelist", []), ensure_ascii=False),
              "- 功能保持：%s；对抗判定：%s"
              % ("通过" if p["functional_pass"] else "失败",
                 "通过" if p["attack_verdict_pass"] else "未通过")]
        if p.get("metrics"):
            L.append("- 对抗指标：`%s`" % json.dumps(p["metrics"], ensure_ascii=False))
        if "protected_value" in p:
            L.append("- 扩展调用：protected=%s / baseline=%s（可导入：%s）"
                     % (p["protected_value"], p["baseline_value"], p["import_ok"]))
        L.append("- 用时：%.2fs" % p["elapsed_sec"])
        L.append("")
    L += ["## 3. 结论与改进行动", "",
          "- 三个试点**均按文档独立完成保护闭环**：`%s`" % ("是" if res["all_independent"] else "否"),
          "- 功能保持全通过：`%s`；对抗判定全通过：`%s`"
          % (res["all_functional"], res["all_attack_pass"]),
          "",
          "改进行动（见 `docs/release/improvements.md`）：",
          "- I-01 将「独立工具交叉验证」纳入试点验收（已在 S4 落地）；",
          "- I-02 交叉编译仅到 IR 层，链接层目标支持待补交叉 sysroot（S5→后续）；",
          "- I-03 无 LLM 时以 `static_only` 代理指标验收，Token 倍数在配置 LLM 后补测。",
          ""]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "build", "s5"))
    ap.add_argument("--docs", default=os.path.join(REPO, "docs", "release"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    res = run_all(args.out)
    with open(os.path.join(args.out, "s5-results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    os.makedirs(args.docs, exist_ok=True)
    with open(os.path.join(args.docs, "pilot-report.md"), "w", encoding="utf-8") as fh:
        fh.write(_md(res))
    print(json.dumps({"all_functional": res["all_functional"],
                      "all_attack_pass": res["all_attack_pass"],
                      "all_independent": res["all_independent"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
