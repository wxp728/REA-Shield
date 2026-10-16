"""REA-Shield 变换执行层（Transform v0.1，R1 MVP）。

设计：docs/design/ddd/dd-03-llvm-transforms.md
覆盖：FR-C1（CFF）、FR-C2（MBA）、FR-C3（不透明谓词）、FR-C6（选择性/白名单）。
编译经 clang + engine/build/anti_rea_passes.so 插件；白名单来自策略资产涉及的符号。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess

from . import common
from . import toolchain
from .scanner import scanner
from . import wbc
from . import adversarial


def _input_fingerprint(sources: list[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(sources):
        h.update(os.path.basename(p).encode())
        if os.path.exists(p):
            with open(p, "rb") as fh:
                h.update(hashlib.sha256(fh.read()).hexdigest().encode())
    return h.hexdigest()


def _policy_hash(policy: dict) -> str:
    clean = {k: v for k, v in policy.items() if not k.startswith("_")}
    return hashlib.sha256(
        json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

# policy 策略名 -> 引擎插件策略名
STRAT_MAP = {
    "control_flow_flattening": "cff",
    "mixed_boolean_arithmetic": "mba",
    "non_linear_mba": "mba",
    "opaque_predicates": "opaque",
    "code_virtualization": "virtualize",
    "function_boundary_perturbation": "func_split",
    "data_flow_noise": "noise",
    "identifier_renaming": "rename",
    "string_encryption": "string_encrypt",
}
# 走 IR 白名单的策略（虚拟化走独立白名单）
_IR_STRATEGIES = {"control_flow_flattening", "mixed_boolean_arithmetic",
                  "non_linear_mba", "opaque_predicates",
                  "function_boundary_perturbation", "data_flow_noise",
                  "identifier_renaming", "string_encryption"}
# 策略名 -> 覆盖需求，供 transform.log 记录
SUPPORTED_REQ = {"cff": "FR-C1", "mba": "FR-C2", "opaque": "FR-C3",
                 "virtualize": "FR-C7", "func_split": "FR-C4", "noise": "FR-C5",
                 "rename": "dd-03§7", "string_encrypt": "dd-03§7"}

def _find_plugin() -> str:
    cand = toolchain.find_plugin()
    if not cand:
        raise FileNotFoundError(
            "E_TRANSFORM_FAILED: 未找到变换插件 anti_rea_passes.so。\n"
            "请先构建引擎：make build（或 cmake -S engine -B engine/build "
            "-DLLVM_DIR=$(llvm-config --cmakedir) && cmake --build engine/build）。\n"
            "也可用环境变量 ANTI_REA_PLUGIN 直接指定插件路径。\n"
            "自检：anti-rea doctor")
    return cand


def _find_vm_bc() -> str:
    cand = toolchain.find_vm_bc()
    if not cand:
        raise FileNotFoundError(
            "E_TRANSFORM_FAILED: 未找到 VM 解释器 vm_interp.bc（随引擎一同构建）。\n"
            "请先构建引擎：make build。也可用 ANTI_REA_VM_BC 指定路径。")
    return cand


def _clang() -> str:
    c = toolchain.find_clang()
    if c:
        return c
    raise FileNotFoundError(
        "E_BUILD_FAILED: 未找到 clang。\n"
        "protect 需要 LLVM/clang >= 18。请安装后设置 ANTI_REA_LLVM=<LLVM 前缀>"
        "（或用 ANTI_REA_CLANG 指定可执行文件），或把 clang 放进 PATH。\n"
        "自检：anti-rea doctor")


def _whitelist_symbols(policy: dict, root: str, only: str,
                       protect_all: bool = False) -> list[str]:
    """按策略类型收集白名单符号。

    only="vm"  -> 含 code_virtualization 的资产；
    only="ir"  -> 含任一 IR 策略的资产。
    protect_all=True 时取**文件内全部函数**（整文件保护），否则仅取名称命中
    扫描规则者——后者会漏掉 `sm4_key_expand` 这类内部辅助函数（经验记录 gap#7）。
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
            if protect_all:
                syms.update(n for n in scanner.all_function_names(p) if n)
            else:
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


def scope_env(policy: dict, root: str = ".", protect_all: bool = False,
              seed: int | None = None, plugin: str | None = None) -> dict:
    """构建注入所需的环境变量（把插件挂进真实构建，而非独立编译）。

    供 `anti-rea buildenv` 与 `integrations/cc-wrapper` 使用：CI/构建系统先
    `source scope.env`，再以包装器作 `CC` 编译，即可对**真实产物**（如 .so）逐 TU
    施加变换，而链接步骤保持不变。
    """
    seed = int(seed if seed is not None else policy.get("seed", 0))
    whitelist = _whitelist_symbols(policy, root, "ir", protect_all)
    vmp = _whitelist_symbols(policy, root, "vm", protect_all)
    strategies = _plugin_strategies(policy)
    env = {
        "ANTI_REA_WHITELIST": ",".join(whitelist),
        "ANTI_REA_VMP_WHITELIST": ",".join(vmp),
        "ANTI_REA_STRATEGIES": ",".join(strategies),
        "ANTI_REA_SEED": str(seed),
        # 真实构建（多 TU）：默认不改外部名，避免他 TU 按原名引用而断链。
        "ANTI_REA_RENAME_EXTERNAL": os.environ.get("ANTI_REA_RENAME_EXTERNAL", "0"),
    }
    if plugin:
        env["ANTI_REA_PLUGIN"] = plugin
    else:
        try:
            env["ANTI_REA_PLUGIN"] = _find_plugin()
        except Exception:  # noqa: BLE001 - 未构建引擎时留空，由包装器报错
            pass
    if "virtualize" in strategies:
        try:
            env["ANTI_REA_VM_BC"] = _find_vm_bc()
        except Exception:  # noqa: BLE001
            pass
    return env


# 头文件里的函数声明（用于生成导出白名单）。仅扫 .h/.hpp，避免 .c 中 `return foo(x);`
# 之类的误报。函数指针/嵌套括号声明可能漏匹配，属可接受范围。
_DECL_RE = re.compile(
    r"^[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\([^;{)]*\)\s*;", re.M)
_C_KEYWORDS = {
    "if", "for", "while", "switch", "return", "sizeof", "do", "else", "case",
    "typedef", "struct", "union", "enum", "static", "inline", "extern", "void",
    "int", "char", "long", "short", "unsigned", "signed", "float", "double",
}


def export_map(paths: list[str], out_path: str) -> dict:
    """由公共头文件生成链接版本脚本，只导出公共 API（其余符号本地化）。

    产物形如 `{ global: foo; bar; local: *; };`。用法：链接时 `-Wl,--version-script`。
    非 API 符号本地化后，`.dynsym`/`.dynstr` 不再携带内部名（配合 strip 效果更佳）。
    仅扫 `.h/.hpp`（声明）；给目录则递归。
    """
    files: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for dp, _, fns in os.walk(p):
                for fn in fns:
                    if os.path.splitext(fn)[1].lower() in (".h", ".hpp"):
                        files.append(os.path.join(dp, fn))
        elif os.path.splitext(p)[1].lower() in (".h", ".hpp"):
            files.append(p)
    syms: set[str] = set()
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        for m in _DECL_RE.finditer(text):
            name = m.group(1)
            if name not in _C_KEYWORDS:
                syms.add(name)
    lines = ["{", "  global:"]
    lines += ["    %s;" % s for s in sorted(syms)]
    lines += ["  local:", "    *;", "};", ""]
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return {"out": out_path, "count": len(syms), "symbols": sorted(syms)}


def build_vm_object(out_path: str) -> str:
    """把 VM 解释器 IR（vm_interp.bc）预编译为 PIC 目标文件。

    构建注入时，被虚拟化的函数会调用 `anti_rea_vm_run`；独立编译流程由引擎把
    `vm_interp.bc` 一起链接，真实构建则需在**链接步骤**并入该运行期对象。
    """
    clang = _clang()
    bc = _find_vm_bc()
    d = os.path.dirname(os.path.abspath(out_path))
    if d:
        os.makedirs(d, exist_ok=True)
    subprocess.run([clang, "-O2", "-fPIC", "-c", bc, "-o", out_path],
                   check=True, capture_output=True, text=True)
    return out_path


def protect(policy: dict, sources: list[str], out_dir: str, root: str = ".",
            seed: int | None = None, offline: bool = True,
            protect_all: bool = False) -> dict:
    """对 sources 施加策略保护的变换，产出 artifacts + transform.log + metadata。

    protect_all=True：白名单取 scope 内文件**全部函数**（整文件保护）。
    """
    os.makedirs(out_dir, exist_ok=True)
    art_dir = os.path.join(out_dir, "artifacts")
    os.makedirs(art_dir, exist_ok=True)
    seed = int(seed if seed is not None else policy.get("seed", 0))

    clang = _clang()
    plugin = _find_plugin()
    whitelist = _whitelist_symbols(policy, root, "ir", protect_all)
    vmp_whitelist = _whitelist_symbols(policy, root, "vm", protect_all)
    strategies = _plugin_strategies(policy)
    # 外部 SPI 插件（FR-C11）：策略名由 ANTI_REA_EXTRA_STRATEGIES 追加，
    # 插件路径由 ANTI_REA_EXTRA_PLUGINS 经环境继承给引擎宿主。
    extra_strats = [s for s in os.environ.get("ANTI_REA_EXTRA_STRATEGIES", "").split(",") if s]
    if extra_strats:
        strategies = sorted(set(strategies) | set(extra_strats))
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
    # 多编译单元（多 source）：外部链接符号可能被其它 TU 按原名引用，重命名会破坏链接。
    # 自动降级为「只改名内部链接函数」；用户显式设置 ANTI_REA_RENAME_EXTERNAL 时以其为准。
    if len(sources) > 1 and "ANTI_REA_RENAME_EXTERNAL" not in os.environ:
        env["ANTI_REA_RENAME_EXTERNAL"] = "0"
    cmd = [clang, "-O1", "-fpass-plugin=" + plugin,
           *sources, *extra_inputs, "-o", protected_exe]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError("E_BUILD_FAILED: 保护构建失败:\n" + (p.stderr or ""))

    log_lines = [
        "# REA-Shield transform.log",
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
        "extra_plugins": os.environ.get("ANTI_REA_EXTRA_PLUGINS", ""),
        "offline": offline,
        # FR-G2 可复现元数据
        "input_fingerprint": _input_fingerprint(sources),
        "policy_hash": _policy_hash(policy),
        # 全部源文件（绝对路径）：供 verify 的对抗诱导变体与其它多-TU 步骤复用
        "sources": [os.path.abspath(s) for s in sources],
        "generated_at": common.now_iso(),
    }

    # 组合防护：白盒密码（FR-C10）与对抗诱导（FR-C9）产物
    strat_set = {s for a in policy.get("assets", []) for s in a.get("strategies", [])}
    if "white_box_crypto" in strat_set:
        metadata["wbc"] = wbc.generate(os.path.join(out_dir, "wbc"), seed=seed)
        log_lines.append("white_box_crypto: alg=aes-128 seed=%d" % seed)
    if "adversarial_inducement" in strat_set:
        syms = sorted({a.get("symbol") for a in policy.get("assets", []) if a.get("symbol")})
        vc = int(policy.get("variant_count") or 3)
        metadata["adversarial"] = adversarial.generate_variants(
            sources[0], os.path.join(out_dir, "adversarial"), syms,
            count=max(1, min(vc, 64)), seed=seed)
        log_lines.append("adversarial_inducement: variants=%d seed=%d" % (vc, seed))

    with open(os.path.join(out_dir, "transform.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    common.write_json(os.path.join(out_dir, "metadata.json"), metadata)
    return metadata
