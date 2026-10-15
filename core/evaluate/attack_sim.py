"""攻击模拟（FR-E3 静态 / FR-E4 动态 / FR-E5 跨版本）与 eval_report 产出。

设计：`docs/design/ddd/dd-07-evaluation.md §2/§5`；判定口径：`decisions/OI-07-*.md`。
无 LLM（未配置或未授权出站）时降级 `static_only`（OI-07 §D5），并在 `verdict.reasons` 标注。
"""
from __future__ import annotations

import os
import shutil
import subprocess

from .. import common
from . import static_features
from . import metrics as M
from . import llm
from . import timeseries


def _load_benchmark(path: str | None) -> dict:
    if not path:
        return {"id": "default", "targets": []}
    if path.endswith((".yaml", ".yml")):
        bm = common.read_yaml(path)
    else:
        bm = common.read_json(path)
    common.validate(bm, "benchmark.schema.json")
    return bm


def _targets(bm: dict) -> list[str]:
    return [t["name"] for t in bm.get("targets", [])]


def _secrets(bm: dict) -> list[str]:
    out = []
    for t in bm.get("targets", []):
        if t.get("secret"):
            out.append(t["secret"])
    return out


# ------------------------- 动态攻击（FR-E4，best-effort）-------------------------
def dynamic_sim(protected_exe: str, secrets: list[str], workdir: str) -> dict:
    """在受控调试会话中转储进程内存并搜索 ground truth 秘密（S4）。

    工具缺失或无法中断时返回 `measured=False`（不计入判定）。
    """
    gdb = shutil.which("gdb")
    if not gdb or not secrets:
        return {"measured": False, "reason": "无 gdb 或缺 ground truth 秘密",
                "secret_hits": []}
    core = os.path.join(workdir, "mem.core")
    script = ("set pagination off\n"
              "starti\n"
              "gcore %s\n"
              "kill\n" % core)
    try:
        subprocess.run([gdb, "--batch", "-ex", script, "--args", protected_exe],
                       capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"measured": False, "reason": "gdb 执行失败: %s" % exc,
                "secret_hits": []}
    if not os.path.exists(core):
        return {"measured": False, "reason": "gcore 未产出转储", "secret_hits": []}
    with open(core, "rb") as fh:
        blob = fh.read()
    hits = [s for s in secrets if s.encode() in blob]
    return {"measured": True, "secret_hits": hits}


# ------------------------- 跨版本复用攻击（FR-E5）-------------------------
def crossver_sim(baseline_exe: str, protected_exe: str,
                 prev_protected: str | None) -> dict:
    """用上一版本的受保护产物衡量结构复用可行性（低相似度=复用攻击无效）。"""
    if not prev_protected or not os.path.exists(prev_protected):
        return {"measured": False, "reason": "无上一版本产物"}
    fp = static_features.features(protected_exe)
    fo = static_features.features(prev_protected)
    sim = static_features.bin_similarity(fo, fp)
    return {"measured": True, "crossver_similarity": sim}


# ------------------------- 主入口 -------------------------
def attack_sim(artifacts_dir: str, *, benchmark: str | None = None,
               allow_llm: bool = False, mode: str = "static",
               db: str | None = None, prev_protected: str | None = None,
               budget: dict | None = None) -> dict:
    """执行攻击模拟，产出符合 `eval_report.schema.json` 的报告（dict）。

    mode: "static"（默认）/ "dynamic" / "crossver" / "all"。
    """
    meta = common.read_json(os.path.join(artifacts_dir, "metadata.json"))
    run_id = meta.get("run_id", "run-unknown")
    baseline = meta.get("baseline_exe")
    protected = meta.get("protected_exe")
    if not baseline or not protected or not os.path.exists(protected):
        raise ValueError("E_INVALID_INPUT: 缺少 baseline/protected 可执行产物")

    bm = _load_benchmark(benchmark)
    targets = _targets(bm)
    secrets = _secrets(bm)

    reasons: list[str] = []
    llm_meta: dict = {}
    baseline_m: dict = {}
    protected_m: dict = {}

    use_llm = llm.available(allow_llm)
    if use_llm:
        reasons.append("LLM 会话判定已启用")
        # 会话编排（FR-E3）由 provider 实现；此处预留接口，未配置输出则视为未测量
        reasons.append("LLM 已配置，但会话编排为 v0.1 预留（见 dd-07 §11 后续动作）")

    # 静态代理指标
    met = M.compute_static(baseline, protected, targets)
    ratio = None
    rea_success = None
    static_only = not use_llm

    # 动态攻击（可选）
    if mode in ("dynamic", "all"):
        dyn = dynamic_sim(protected, secrets, artifacts_dir)
        if dyn.get("measured"):
            protected_m["analysis_time_sec"] = 0.0
            if dyn["secret_hits"]:
                rea_success = True  # S4
                reasons.append("动态攻击命中 S4：内存中发现秘密")
            else:
                reasons.append("动态攻击未命中秘密（S4 未达成）")
        else:
            reasons.append("动态攻击未执行（%s）" % dyn.get("reason", "未测量"))

    # 跨版本攻击（可选，FR-E5）
    if mode in ("crossver", "all"):
        cv = crossver_sim(baseline, protected, prev_protected)
        if cv.get("measured"):
            reasons.append("跨版本结构相似度=%.3f" % cv["crossver_similarity"])
        else:
            reasons.append("跨版本攻击未执行（%s）" % cv.get("reason", "未测量"))

    if use_llm:
        verdict = M.judge(met, ratio=ratio, rea_success=(rea_success is True))
    else:
        reasons.append("静态代理指标（无 LLM；见 dd-07 §5）")
        verdict = M.judge(met, static_only=True)

    report = {
        "schema_version": common.SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": common.now_iso(),
        "metrics": met,
        "verdict": {"pass": bool(verdict["pass"]),
                    "reasons": reasons + list(verdict["reasons"])},
    }
    if use_llm:
        report["llm"] = {
            "provider": llm_meta.get("provider", os.environ.get("ANTI_REA_LLM_PROVIDER", "env")),
            "model": llm_meta.get("model", os.environ.get("ANTI_REA_LLM_MODEL", "default")),
            "session_context_window": llm.context_window(),
        }
    if baseline_m:
        report["baseline"] = baseline_m
    if protected_m:
        report["protected"] = protected_m

    # 逐资产开销（来自 verification_report）与敏感级（来自 policy）
    vr = os.path.join(artifacts_dir, "verification_report.json")
    pol = os.path.join(artifacts_dir, "protection_policy.yaml")
    per_asset = []
    if os.path.exists(pol):
        policy = common.read_yaml(pol)
        for a in policy.get("assets", []):
            if a.get("strategies"):
                per_asset.append({"path": a.get("path", ""),
                                  "sensitivity": a.get("sensitivity", "P3")})
    if per_asset:
        if os.path.exists(vr):
            v = common.read_json(vr)
            per_asset[0]["overhead"] = v.get("overhead", 0.0)
        report["per_asset"] = per_asset

    common.validate(report, "eval_report.schema.json")

    # 落库（FR-E6）
    if db:
        timeseries.record(db, run_id, report["generated_at"],
                          {k: v for k, v in met.items()
                           if isinstance(v, (int, float)) and not isinstance(v, bool)})

    common.write_json(os.path.join(artifacts_dir, "eval_report.json"), report)
    return report
