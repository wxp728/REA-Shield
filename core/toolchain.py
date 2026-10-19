"""工具链探测与自检（可用性 / 去除硬编码路径）。

设计目标：让「换一台机器、换一个目录」不必改代码。所有外部程序的定位
优先级统一为：

    环境变量  >  PATH  >  常见安装目录

支持的环境变量：

    ANTI_REA_LLVM         LLVM 安装前缀（其下有 bin/、lib/cmake/llvm/）
    ANTI_REA_LLVM_BIN     LLVM bin 目录（直接覆盖）
    ANTI_REA_CLANG        clang 可执行文件
    ANTI_REA_OPT          opt 可执行文件
    ANTI_REA_LLVM_CONFIG  llvm-config 可执行文件
    ANTI_REA_PLUGIN       变换插件（anti_rea_passes.so）路径
    ANTI_REA_VM_BC        VM 解释器 bitcode（vm_interp.bc）路径
    LLVM_DIR              CMake 约定，值为 <prefix>/lib/cmake/llvm

`anti-rea doctor` 会据此给出环境自检报告。
"""
from __future__ import annotations

import glob
import os
import platform
import shutil
import sys

from . import common

# 兜底搜索目录（通配符），仅在本机确实存在时命中
_BIN_GLOBS = [
    "/opt/*/clang+llvm-*/bin",
    "/opt/clang+llvm-*/bin",
    "/opt/*/llvm*/bin",
    "/usr/lib/llvm-*/bin",
    "/usr/local/opt/llvm/bin",
    "/opt/homebrew/opt/llvm/bin",
    "/usr/local/llvm*/bin",
]

MIN_PYTHON = (3, 11)

# --------------------------------------------------------------------------
# 分级安装（provisioning）：tier 表示「什么时候才需要装」
#
# 原则：**不打包、不预装第三方工具**。最小安装只装核心；其余按「用户选定的
# 语言 / 工作流模式 / 是否需要独立验证」按需获取（详见 docs/PROVISIONING.md）。
# --------------------------------------------------------------------------
PROVISION_TIERS = {
    "T0": "核心（必装，最小）：scan / plan / doctor / report / diff / regress",
    "T1": "原生变换（按需）：要对 C/C++（或 Rust C-FFI、Python C 扩展）施加变换时才需要",
    "T2": "语言与平台扩展（按需）：按目标语言、构建体系或宿主平台选装",
    "T3": "可选增强（按需，最迟）：独立验证 / 进化搜索 / LLM 红队会话",
}


def _env_path(*names: str) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            v = os.path.expanduser(v)
            if os.path.exists(v):
                return v
    return None


def llvm_prefix() -> str | None:
    """LLVM 安装前缀（其下有 bin/）。"""
    p = _env_path("ANTI_REA_LLVM")
    if p:
        return p
    # LLVM_DIR=<prefix>/lib/cmake/llvm
    d = os.environ.get("LLVM_DIR")
    if d:
        cand = os.path.abspath(os.path.join(d, "..", ".."))
        if os.path.isdir(os.path.join(cand, "bin")):
            return cand
    cfg = shutil.which("llvm-config")
    if cfg:
        # 形如 /usr/lib/llvm-18/bin/llvm-config -> /usr/lib/llvm-18
        cand = os.path.abspath(os.path.join(os.path.dirname(cfg), ".."))
        if os.path.isdir(os.path.join(cand, "bin")):
            return cand
    return None


def llvm_bin() -> str | None:
    """LLVM bin 目录。"""
    for d in (os.environ.get("ANTI_REA_LLVM_BIN"), os.environ.get("LLVM_BIN")):
        if d and os.path.isdir(d):
            return d
    pref = llvm_prefix()
    if pref and os.path.isdir(os.path.join(pref, "bin")):
        return os.path.join(pref, "bin")
    if shutil.which("clang"):
        return None  # clang 在 PATH 上，交给 which 解析
    for g in _BIN_GLOBS:
        for d in sorted(glob.glob(g)):
            if os.path.isfile(_tool_in(d, "clang")):
                return d
    return None


def _tool_in(bindir: str, name: str) -> str:
    exe = name + (".exe" if os.name == "nt" else "")
    return os.path.join(bindir, exe)


def find_tool(name: str, env_var: str | None = None) -> str | None:
    """定位一个 LLVM 工具：环境变量 > PATH > LLVM bin > 常见目录。"""
    if env_var:
        p = _env_path(env_var)
        if p:
            return p
    w = shutil.which(name)
    if w:
        return w
    b = llvm_bin()
    if b:
        cand = _tool_in(b, name)
        if os.path.isfile(cand):
            return cand
    for g in _BIN_GLOBS:
        for d in sorted(glob.glob(g)):
            cand = _tool_in(d, name)
            if os.path.isfile(cand):
                return cand
    return None


def find_clang() -> str | None:
    return find_tool("clang", "ANTI_REA_CLANG")


def find_opt() -> str | None:
    return find_tool("opt", "ANTI_REA_OPT")


def find_llvm_config() -> str | None:
    return find_tool("llvm-config", "ANTI_REA_LLVM_CONFIG")


def find_cmake() -> str | None:
    return shutil.which("cmake")


def find_plugin() -> str | None:
    """变换插件（anti_rea_passes.so）路径。"""
    for cand in (_env_path("ANTI_REA_PLUGIN"),):
        if cand:
            return cand
    pats = [
        os.path.join(common.REPO_ROOT, "engine", "build", "anti_rea_passes.so"),
        os.path.join(common.REPO_ROOT, "engine", "build", "anti_rea_passes.dylib"),
        os.path.join(common.REPO_ROOT, "engine", "build", "anti_rea_passes.dll"),
        os.path.join(common.REPO_ROOT, "build", "anti_rea_passes.so"),
    ]
    for p in pats:
        if os.path.exists(p):
            return p
    return None


def find_vm_bc() -> str | None:
    if _env_path("ANTI_REA_VM_BC"):
        return _env_path("ANTI_REA_VM_BC")
    p = os.path.join(common.REPO_ROOT, "engine", "build", "vm_interp.bc")
    return p if os.path.exists(p) else None


def python_ok() -> bool:
    return sys.version_info >= MIN_PYTHON


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------

def _mod_ok(name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def checks() -> list[dict]:
    """返回自检项列表（每项含 name/required/ok/detail/hint）。"""
    from . import platform_info
    rows: list[dict] = []

    py = "%d.%d.%d" % sys.version_info[:3]
    rows.append({
        "name": "python",
        "tier": "T0",
        "when": "始终",
        "required": True,
        "ok": python_ok(),
        "detail": "Python %s (%s)" % (py, sys.executable),
        "hint": "需要 Python >= %d.%d" % MIN_PYTHON,
    })

    for mod, req, tier, when in (
            ("jsonschema", True, "T0", "始终（清单/策略校验）"),
            ("yaml", True, "T0", "始终（策略与基准读写）"),
            ("deap", False, "T3", "只在运行 `anti-rea evolve`（进化式策略搜索）时"),
    ):
        rows.append({
            "name": "py:%s" % mod,
            "tier": tier,
            "when": when,
            "required": req,
            "ok": _mod_ok(mod),
            "detail": "import %s" % mod,
            "hint": ("pip install -r requirements.txt" if req
                     else "按需安装：pip install -r requirements-optional.txt"),
        })

    clang = find_clang()
    rows.append({
        "name": "clang",
        "tier": "T1",
        "when": "选定工作流模式 A/B 且要对原生代码施加变换（protect）时",
        "required": False,  # scan/plan 不需要；protect 需要
        "ok": bool(clang),
        "detail": clang or "未找到",
        "hint": ("protect 需要 clang >= 18。安装 LLVM 18 并设置 "
                 "ANTI_REA_LLVM=<prefix>，或把 clang 放进 PATH"),
    })

    opt = find_opt()
    rows.append({
        "name": "opt",
        "tier": "T1",
        "when": "同上（protect 的变换流水线）",
        "required": False,
        "ok": bool(opt),
        "detail": opt or "未找到",
        "hint": "随 LLVM 一同安装（与 clang 同源）",
    })

    plugin = find_plugin()
    rows.append({
        "name": "engine-plugin",
        "tier": "T1",
        "when": "同上（protect 前构建本仓库插件，不随包分发预编译产物）",
        "required": False,
        "ok": bool(plugin),
        "detail": plugin or "未构建",
        "hint": ("运行 `make build`（或 cmake -S engine -B engine/build）"
                 "构建 LLVM 变换插件"),
    })

    cmake = find_cmake()
    rows.append({
        "name": "cmake",
        "tier": "T1",
        "when": "同上（构建引擎插件）",
        "required": False,
        "ok": bool(cmake),
        "detail": cmake or "未找到",
        "hint": "构建引擎插件需要 cmake >= 3.16",
    })

    for tool in ("nm", "objdump", "strings"):
        w = shutil.which(tool)
        rows.append({
            "name": "binutils:%s" % tool,
            "tier": "T1",
            "when": "同上（verify / attack_sim 的产物静态核验）",
            "required": False,
            "ok": bool(w),
            "detail": w or "未找到",
            "hint": "verify 的独立核验依赖 binutils",
        })

    rows.append({
        "name": "platform",
        "tier": "T2",
        "when": "宿主不是 linux-x86_64 时（改用容器镜像或自行验证）",
        "required": False,
        "ok": platform_info.is_supported(),
        "detail": "%s (%s %s)" % (platform_info.host_platform(),
                                  platform.system(), platform.machine()),
        "hint": ("v1.0 实测支持 linux-x86_64；其他平台可运行 scan/plan，"
                 "protect 需自行验证（见 docs/release/compatibility-matrix.md）"),
    })

    # ---- 语言扩展（按目标语言选装；本技能不代装）----
    for name, exe, when in (
            ("rust-cargo", "cargo", "目标含 Rust C/FFI 源（经 Cargo 集成）时"),
            ("node-npm", "npm", "目标含 JS/TS（仅扫描/识别）时"),
    ):
        w = shutil.which(exe)
        rows.append({
            "name": name,
            "tier": "T2",
            "when": when,
            "required": False,
            "ok": bool(w),
            "detail": w or "未找到",
            "hint": "按需安装（由目标项目的语言工具链提供；本技能不代装）",
        })

    dh = shutil.which("docker") or shutil.which("podman")
    rows.append({
        "name": "container-runtime",
        "tier": "T2",
        "when": "不想在宿主安装 LLVM 18、或宿主平台与插件不匹配时（改用镜像）",
        "required": False,
        "ok": bool(dh),
        "detail": dh or "未找到",
        "hint": "可选：用本仓库 Dockerfile 自建镜像（镜像构建期会联网获取 LLVM）",
    })

    # ---- 可选增强（最迟按需）----
    ghidra = os.environ.get("ANTI_REA_GHIDRA", "")
    rows.append({
        "name": "ghidra",
        "tier": "T3",
        "when": "需要独立（第三方引擎）交叉验证时，例如跑 `verify --ghidra`",
        "required": False,
        "ok": bool(ghidra and ghidra != "0"),
        "detail": "ANTI_REA_GHIDRA=%s" % (ghidra or "未设置"),
        "hint": ("按需自备 Ghidra + PyGhidra（不随本技能分发）：从官方发布页获取，"
                 "装好后设 ANTI_REA_GHIDRA=1"),
    })

    llm = bool(os.environ.get("ANTI_REA_LLM_ENDPOINT")
               or os.environ.get("ANTI_REA_LLM_CMD"))
    rows.append({
        "name": "llm-egress",
        "tier": "T3",
        "when": "要跑真实 LLM 红队会话（`attack_sim --allow-llm`）时",
        "required": False,
        "ok": llm,
        "detail": "已配置" if llm else "未配置（默认纯静态评估可用）",
        "hint": ("按需自备模型/网关：设 ANTI_REA_LLM_ENDPOINT（或 "
                 "ANTI_REA_LLM_CMD 钩子）；凭据与配额由用户自管"),
    })

    return rows


def doctor(only_tier: str | None = None) -> dict:
    """环境自检报告（dict）。`ok` 表示必需项是否齐备。

    `only_tier` 只保留某个分级（T0/T1/T2/T3）的自检项——用于「按需安装」：
    只看当前工作流模式/语言真正需要的部分。
    """
    rows = checks()
    if only_tier:
        rows = [r for r in rows if r.get("tier") == only_tier]
    hard_fails = [r for r in rows if r["required"] and not r["ok"]]
    # protect 关键项缺失时给出 warning（非致命，scan/plan 仍可用）
    warns = [r for r in rows if not r["required"] and not r["ok"]]
    by_tier: dict[str, dict] = {}
    for r in rows:
        t = r.get("tier", "T0")
        slot = by_tier.setdefault(t, {"desc": PROVISION_TIERS.get(t, ""),
                                      "missing": []})
        if not r["ok"]:
            slot["missing"].append(r["name"])
    return {
        "ok": not hard_fails,
        "toolchain_ready": not warns,
        "tier": only_tier,
        "tiers": by_tier,
        "checks": rows,
        "failed": hard_fails,
        "warnings": warns,
    }


def format_report(report: dict) -> str:
    lines = ["REA-Shield 环境自检 (doctor)", "=" * 40]
    if report.get("tier"):
        lines.append("（只显示分级 %s：%s）"
                     % (report["tier"], PROVISION_TIERS.get(report["tier"], "")))
    rows = report["checks"]
    t0 = [r for r in rows if r.get("tier", "T0") == "T0"]
    later = [r for r in rows if r.get("tier", "T0") != "T0"]

    def _line(r: dict) -> str:
        tag = "OK  " if r["ok"] else ("MISS" if r["required"] else "warn")
        return "[%s] %-18s %s" % (tag, r["name"], r["detail"])

    for r in t0:
        lines.append(_line(r))
    if later:
        lines.append("-" * 40)
        lines.append("按需组件（未选到对应语言 / 模式 / 可选功能时，无需安装）：")
        for tier in sorted({r.get("tier", "T0") for r in later}):
            lines.append("  %s · %s" % (tier, PROVISION_TIERS.get(tier, "")))
            for r in [x for x in later if x.get("tier") == tier]:
                lines.append("    %s" % _line(r))
                if not r["ok"]:
                    lines.append("        何时需要：%s" % r.get("when", "-"))
                    lines.append("        怎么装：  %s" % r["hint"])
    lines.append("-" * 40)
    if report["ok"] and report["toolchain_ready"]:
        lines.append("结果：环境就绪，scan/plan/protect 全流程可用。")
    elif report["ok"]:
        lines.append("结果：核心依赖就绪（scan/plan 可用）。")
        lines.append("以下按需组件尚未安装（选到对应功能时再装即可，详见 docs/PROVISIONING.md）：")
        for r in report["warnings"]:
            lines.append("  - %s [%s]：%s" % (r["name"], r.get("tier", "-"),
                                             r.get("when", r["hint"])))
    else:
        lines.append("结果：缺少必需依赖，请先修复：")
        for r in report["failed"] + report["warnings"]:
            lines.append("  - %s: %s" % (r["name"], r["hint"]))
    return "\n".join(lines)
