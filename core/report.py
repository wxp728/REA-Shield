"""报告与产物管理（FR-G1 统一目录 / FR-G2 可复现元数据 / FR-G3 变更对比）。

设计：`docs/design/ddd/dd-build-integration.md §7/§8/§9`。
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import platform
import subprocess

from . import common


# ------------------------- FR-G2 可复现元数据 -------------------------
def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def input_fingerprint(sources: list[str]) -> str:
    """对输入源文件集合的确定性指纹（路径+内容，排序后）。"""
    h = hashlib.sha256()
    for p in sorted(sources):
        h.update(os.path.relpath(p, os.path.dirname(os.path.abspath(p))).encode())
        if os.path.exists(p):
            h.update(_sha256_file(p).encode())
    return h.hexdigest()


def _canonical_hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def toolchain_versions() -> dict:
    versions: dict[str, str] = {"python": platform.python_version()}
    try:
        from .transform import _clang
        p = subprocess.run([_clang(), "--version"], capture_output=True, text=True)
        versions["clang"] = (p.stdout or "").splitlines()[0] if p.stdout else "unknown"
    except Exception:  # noqa: BLE001
        versions["clang"] = "unknown"
    return versions


# ------------------------- FR-G1 统一产物目录 -------------------------
ARTIFACTS = ("asset_manifest.json", "protection_policy.yaml", "artifacts",
             "transform.log", "verification_report.json", "eval_report.json",
             "metadata.json")


def layout_ok(run_dir: str) -> dict:
    """检查统一产物目录结构（存在性），返回定位映射。"""
    found = {}
    for name in ARTIFACTS:
        found[name] = os.path.exists(os.path.join(run_dir, name))
    return found


# ------------------------- 报告生成（FR-E7：json/md/html 一致）-------------------------
def _report_model(run_dir: str) -> dict:
    meta = common.read_json(os.path.join(run_dir, "metadata.json"))
    model = {
        "run_id": meta.get("run_id", ""),
        "seed": meta.get("seed"),
        "strategies": meta.get("strategies", []),
        "whitelist": meta.get("whitelist", []),
        "vmp_whitelist": meta.get("vmp_whitelist", []),
        "engine_version": meta.get("engine_version", ""),
        "input_fingerprint": meta.get("input_fingerprint", ""),
        "policy_hash": meta.get("policy_hash", ""),
        "generated_at": meta.get("generated_at", ""),
    }
    vr = os.path.join(run_dir, "verification_report.json")
    if os.path.exists(vr):
        v = common.read_json(vr)
        model["verification"] = {
            "functional_pass": v.get("functional_pass"),
            "performance_pass": v.get("performance_pass"),
            "overhead": v.get("overhead"),
            "overall_pass": v.get("overall_pass"),
            "detail": v.get("detail", []),
        }
    er = os.path.join(run_dir, "eval_report.json")
    if os.path.exists(er):
        e = common.read_json(er)
        model["evaluation"] = {"metrics": e.get("metrics", {}),
                               "verdict": e.get("verdict", {})}
    return model


def _to_markdown(m: dict) -> str:
    L = ["# REA-Shield 保护报告", "",
         "- run_id: `%s`" % m.get("run_id", ""),
         "- engine: `%s`" % m.get("engine_version", ""),
         "- seed: `%s`" % m.get("seed"),
         "- input_fingerprint: `%s`" % m.get("input_fingerprint", ""),
         "- policy_hash: `%s`" % m.get("policy_hash", ""),
         "- generated_at: `%s`" % m.get("generated_at", ""),
         "",
         "## 策略", "", "`%s`" % ", ".join(m.get("strategies", [])),
         "", "白名单: `%s`" % ", ".join(m.get("whitelist", []))]
    v = m.get("verification")
    if v:
        L += ["", "## 功能/性能验证", "",
              "- functional_pass: **%s**" % v.get("functional_pass"),
              "- performance_pass: **%s**（overhead=%s）" % (v.get("performance_pass"), v.get("overhead")),
              "- overall_pass: **%s**" % v.get("overall_pass")]
        for d in v.get("detail", []):
            L.append("  - %s" % d)
    e = m.get("evaluation")
    if e:
        L += ["", "## 攻击模拟（FR-E6 指标）", ""]
        for k, val in e.get("metrics", {}).items():
            L.append("- `%s`: %s" % (k, val))
        L += ["", "判定: **%s**" % e.get("verdict", {}).get("pass")]
        for r in e.get("verdict", {}).get("reasons", []):
            L.append("  - %s" % r)
    return "\n".join(L) + "\n"


def _to_html(m: dict, md: str) -> str:
    body = "<pre>%s</pre>" % html.escape(md)
    return ("<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
            "<title>REA-Shield 保护报告 %s</title></head><body>%s</body></html>\n"
            % (html.escape(m.get("run_id", "")), body))


def generate(run_dir: str, fmt: str = "md") -> str:
    """生成报告；`fmt` ∈ {json, md, html}；同时写出三种格式以保证一致（FR-E7）。"""
    m = _report_model(run_dir)
    md = _to_markdown(m)
    common.write_json(os.path.join(run_dir, "report.json"),
                      {"run_id": m.get("run_id", ""), "model": m, "markdown": md})
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    with open(os.path.join(run_dir, "report.html"), "w", encoding="utf-8") as fh:
        fh.write(_to_html(m, md))
    return os.path.join(run_dir, {"json": "report.json", "md": "report.md",
                                  "html": "report.html"}[fmt])


# ------------------------- FR-G3 变更对比 -------------------------
def _hash_dir(d: str) -> dict:
    out = {}
    if not os.path.isdir(d):
        return out
    for root, _dirs, files in os.walk(d):
        for fn in files:
            p = os.path.join(root, fn)
            out[os.path.relpath(p, d)] = _sha256_file(p)
    return out


def diff(run_a: str, run_b: str) -> dict:
    """对比两次运行：策略差异、指标差异、产物差异（FR-G3）。"""
    a, b = _report_model(run_a), _report_model(run_b)

    def _set_diff(x, y):
        sx, sy = set(x or []), set(y or [])
        return {"only_in_a": sorted(sx - sy), "only_in_b": sorted(sy - sx),
                "common": sorted(sx & sy)}

    result = {
        "run_a": a.get("run_id", ""), "run_b": b.get("run_id", ""),
        "strategies": _set_diff(a.get("strategies"), b.get("strategies")),
        "whitelist": _set_diff(a.get("whitelist"), b.get("whitelist")),
        "metrics": {},
        "artifacts": {},
    }
    ma = (a.get("evaluation") or {}).get("metrics", {})
    mb = (b.get("evaluation") or {}).get("metrics", {})
    for k in sorted(set(ma) | set(mb)):
        va, vb = ma.get(k), mb.get(k)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            result["metrics"][k] = {"a": va, "b": vb, "delta": round(vb - va, 6)}
        else:
            result["metrics"][k] = {"a": va, "b": vb}

    ha = _hash_dir(os.path.join(run_a, "artifacts"))
    hb = _hash_dir(os.path.join(run_b, "artifacts"))
    keys = sorted(set(ha) | set(hb))
    changed = [k for k in keys if ha.get(k) != hb.get(k)]
    result["artifacts"] = {"changed": changed,
                           "added": sorted(set(hb) - set(ha)),
                           "removed": sorted(set(ha) - set(hb))}

    common.write_json(os.path.join(run_b, "diff_report.json"), result)
    lines = ["# REA-Shield 变更对比", "",
             "- run_a: `%s`" % result["run_a"],
             "- run_b: `%s`" % result["run_b"], "",
             "## 策略差异", "```json",
             json.dumps(result["strategies"], ensure_ascii=False, indent=2), "```",
             "## 指标差异", "```json",
             json.dumps(result["metrics"], ensure_ascii=False, indent=2), "```",
             "## 产物差异", "```json",
             json.dumps(result["artifacts"], ensure_ascii=False, indent=2), "```"]
    with open(os.path.join(run_b, "diff.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return result
