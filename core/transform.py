"""Anti-REA 变换执行层（Transform v0.1，R1 MVP）。

设计：docs/design/ddd/dd-03-llvm-transforms.md
覆盖：FR-C1（CFF）、FR-C2（MBA）、FR-C3（不透明谓词）、FR-C6（选择性/白名单）。
编译经 clang + engine/build/anti_rea_passes.so 插件；白名单来自策略资产涉及的符号。
"""
from __future__ import annotations

import os
import shutil
import subprocess

from . import common
from .scanner import scanner

# policy 策略名 -> 引擎插件策略名
STRAT_MAP = {
    "control_flow_flattening": "cff",
    "mixed_boolean_arithmetic": "mba",
    "non_linear_mba": "mba",
    "opaque_predicates": "opaque",
    "code_virtualization": "virtualize",
}
# 走 IR 白名单的策略（虚拟化走独立白名单）
_IR_STRATEGIES = {"control_flow_flattening", "mixed_boolean_arithmetic",
                  "non_linear_mba", "opaque_predicates"}
# 策略名 -> 覆盖需求，供 transform.log 记录
SUPPORTED_REQ = {"cff": "FR-C1", "mba": "FR-C2", "opaque": "FR-C3",
                 "virtualize": "FR-C7"}

_DEFAULT_LLVM_BIN = "/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04/bin"


def _find_plugin() -> str:
    cand = os.path.join(common.REPO_ROOT, "engine", "build", "anti_rea_passes.so")
    if not os.path.exists(cand):
        raise FileNotFoundError(
            "E_TRANSFORM_FAILED: 未找到插件 %s，请先构建 engine/" % cand)
    return cand


def _find_vm_bc() -> str:
    cand = os.path.join(common.REPO_ROOT, "engine", "build", "vm_interp.bc")
    if not os.path.exists(cand):
        raise FileNotFoundError(
            "E_TRANSFORM_FAILED: 未找到 VM 解释器 %s，请先构建 engine/" % cand)
    return cand


def _clang() -> str:
    if os.environ.get("ANTI_REA_CLANG"):
        return os.environ["ANTI_REA_CLANG"]
    c = shutil.which("clang")
    if c:
        return c
    c = os.path.join(_DEFAULT_LLVM_BIN, "clang")
    if os.path.exists(c):
        return c
    raise FileNotFoundError("E_BUILD_FAILED: 未找到 clang")


def _whitelist_symbols(policy: dict, root: str, only: str) -> list[str]:
    """按策略类型收集白名单符号。

    only="vm"  -> 含 code_virtualization 的资产；
    only="ir"  -> 含任一 IR 策略的资产。
    """
    syms: set[str] = set()
    for a in policy.get("assets", []):
        strat = set(a.get("strategies", []))
        if only == "vm":
            if "code_virtualization" not in strat:
                continue
        else:
            if not (strat & _IR_STRATEGIES):
                continue
        p = os.path.join(root, a["path"])
        if os.path.isfile(p) and os.path.splitext(p)[1] in scanner._LANG_EXT_SOURCES:
            for cand in scanner._scan_file(p):
                if cand.get("symbol"):
                    syms.add(cand["symbol"])
    return sorted(syms)


def _plugin_strategies(policy: dict) -> list[str]:
    out: set[str] = set()
    for a in policy.get("assets", []):
        for s in a.get("strategies", []):
            if s in STRAT_MAP:
                out.add(STRAT_MAP[s])
    return sorted(out)


def protect(policy: dict, sources: list[str], out_dir: str, root: str = ".",
            seed: int | None = None, offline: bool = True) -> dict:
    """对 sources 施加策略保护的变换，产出 artifacts + transform.log + metadata。"""
    os.makedirs(out_dir, exist_ok=True)
    art_dir = os.path.join(out_dir, "artifacts")
    os.makedirs(art_dir, exist_ok=True)
    seed = int(seed if seed is not None else policy.get("seed", 0))

    clang = _clang()
    plugin = _find_plugin()
    whitelist = _whitelist_symbols(policy, root, "ir")
    vmp_whitelist = _whitelist_symbols(policy, root, "vm")
    strategies = _plugin_strategies(policy)
    extra_inputs: list[str] = []
    if "virtualize" in strategies:
        extra_inputs.append(_find_vm_bc())

    baseline_exe = os.path.join(art_dir, "baseline")
    protected_exe = os.path.join(art_dir, "protected")

    # 基线（未保护）
    subprocess.run([clang, "-O0", *sources, "-o", baseline_exe],
                   check=True, capture_output=True, text=True)

    env = dict(os.environ)
    env["ANTI_REA_WHITELIST"] = ",".join(whitelist)
    env["ANTI_REA_VMP_WHITELIST"] = ",".join(vmp_whitelist)
    env["ANTI_REA_STRATEGIES"] = ",".join(strategies) if strategies else ""
    env["ANTI_REA_SEED"] = str(seed)
    cmd = [clang, "-O1", "-fpass-plugin=" + plugin,
           *sources, *extra_inputs, "-o", protected_exe]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError("E_BUILD_FAILED: 保护构建失败:\n" + (p.stderr or ""))

    log_lines = [
        "# Anti-REA transform.log",
        "run_id: %s" % policy.get("_run_id", ""),
        "seed: %d" % seed,
        "plugin: %s" % plugin,
        "whitelist: %s" % ",".join(whitelist),
        "vmp_whitelist: %s" % ",".join(vmp_whitelist),
        "strategies: %s" % ",".join(strategies),
        "requirements: %s" % ",".join(SUPPORTED_REQ.get(s, "?") for s in strategies),
    ]
    for a in policy.get("assets", []):
        log_lines.append("asset %s sens=%s strategies=%s" %
                         (a["path"], a["sensitivity"], ",".join(a.get("strategies", []))))
    with open(os.path.join(out_dir, "transform.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")

    metadata = {
        "run_id": policy.get("_run_id", ""),
        "seed": seed,
        "engine_version": "0.1.0",
        "toolchain": {"clang": clang},
        "strategies": strategies,
        "whitelist": whitelist,
        "vmp_whitelist": vmp_whitelist,
        "baseline_exe": os.path.abspath(baseline_exe),
        "protected_exe": os.path.abspath(protected_exe),
        "offline": offline,
    }
    common.write_json(os.path.join(out_dir, "metadata.json"), metadata)
    return metadata
