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
    "/opt/anti-rea-toolchain/clang+llvm-*/bin",
    "/opt/anti-rea-toolchain/llvm*/bin",
    "/usr/lib/llvm-*/bin",
    "/usr/local/opt/llvm/bin",
    "/opt/homebrew/opt/llvm/bin",
    "/usr/local/llvm*/bin",
]

MIN_PYTHON = (3, 11)


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
        "required": True,
        "ok": python_ok(),
        "detail": "Python %s (%s)" % (py, sys.executable),
        "hint": "需要 Python >= %d.%d" % MIN_PYTHON,
    })

    for mod, req in (("jsonschema", True), ("yaml", True), ("deap", False)):
        rows.append({
            "name": "py:%s" % mod,
            "required": req,
            "ok": _mod_ok(mod),
            "detail": "import %s" % mod,
            "hint": "pip install -r requirements.txt",
        })

    clang = find_clang()
    rows.append({
        "name": "clang",
        "required": False,  # scan/plan 不需要；protect 需要
        "ok": bool(clang),
        "detail": clang or "未找到",
        "hint": ("protect 需要 clang >= 18。安装 LLVM 18 并设置 "
                 "ANTI_REA_LLVM=<prefix>，或把 clang 放进 PATH"),
    })

    opt = find_opt()
    rows.append({
        "name": "opt",
        "required": False,
        "ok": bool(opt),
        "detail": opt or "未找到",
        "hint": "随 LLVM 一同安装（与 clang 同源）",
    })

    plugin = find_plugin()
    rows.append({
        "name": "engine-plugin",
        "required": False,
        "ok": bool(plugin),
        "detail": plugin or "未构建",
        "hint": ("运行 `make build`（或 cmake -S engine -B engine/build）"
                 "构建 LLVM 变换插件"),
    })

    cmake = find_cmake()
    rows.append({
        "name": "cmake",
        "required": False,
        "ok": bool(cmake),
        "detail": cmake or "未找到",
        "hint": "构建引擎插件需要 cmake >= 3.16",
    })

    for tool in ("nm", "objdump", "strings"):
        w = shutil.which(tool)
        rows.append({
            "name": "binutils:%s" % tool,
            "required": False,
            "ok": bool(w),
            "detail": w or "未找到",
            "hint": "verify 的独立核验依赖 binutils",
        })

    rows.append({
        "name": "platform",
        "required": False,
        "ok": platform_info.is_supported(),
        "detail": "%s (%s %s)" % (platform_info.host_platform(),
                                  platform.system(), platform.machine()),
        "hint": ("v1.0 实测支持 linux-x86_64；其他平台可运行 scan/plan，"
                 "protect 需自行验证（见 docs/release/compatibility-matrix.md）"),
    })
    return rows


def doctor() -> dict:
    """环境自检报告（dict）。`ok` 表示必需项是否齐备。"""
    rows = checks()
    hard_fails = [r for r in rows if r["required"] and not r["ok"]]
    # protect 关键项缺失时给出 warning（非致命，scan/plan 仍可用）
    warns = [r for r in rows if not r["required"] and not r["ok"]]
    return {
        "ok": not hard_fails,
        "toolchain_ready": not warns,
        "checks": rows,
        "failed": hard_fails,
        "warnings": warns,
    }


def format_report(report: dict) -> str:
    lines = ["REA-Shield 环境自检 (doctor)", "=" * 40]
    for r in report["checks"]:
        tag = "OK  " if r["ok"] else ("MISS" if r["required"] else "warn")
        lines.append("[%s] %-16s %s" % (tag, r["name"], r["detail"]))
    lines.append("-" * 40)
    if report["ok"] and report["toolchain_ready"]:
        lines.append("结果：环境就绪，scan/plan/protect 全流程可用。")
    elif report["ok"]:
        lines.append("结果：核心依赖就绪（scan/plan 可用）。")
        lines.append("以下可选组件缺失，protect/verify 可能不可用：")
        for r in report["warnings"]:
            lines.append("  - %s: %s" % (r["name"], r["hint"]))
    else:
        lines.append("结果：缺少必需依赖，请先修复：")
        for r in report["failed"] + report["warnings"]:
            lines.append("  - %s: %s" % (r["name"], r["hint"]))
    return "\n".join(lines)
