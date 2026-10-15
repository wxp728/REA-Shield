"""静态特征提取（dd-07 §5 的后端之一）。

无 LLM 时（static_only）用于计算可复现的静态代理指标：
函数名恢复（符号存活）、结构相似度、功能判断（以结构相似度近似）。
仅依赖 binutils（`nm`/`strings`）与文件系统，确定性、可复现。
"""
from __future__ import annotations

import os
import shutil
import subprocess


def _run(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout or ""


def _nm() -> str | None:
    return shutil.which("nm")


def _strings() -> str | None:
    return shutil.which("strings")


def symbols(exe: str) -> set[str]:
    """定义符号名集合（去地址/类型，仅取已定义文本符号）。"""
    nm = _nm()
    if not nm:
        return set()
    out = _run([nm, exe])
    syms: set[str] = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        typ, name = parts[-2], parts[-1]
        if typ.upper() in {"T", "W"}:  # 文本/弱符号（已定义）
            syms.add(name.split("@@")[0].split("@")[0])
    return syms


# 常见 C 运行时/库函数与编译器插入的桩（不反映工程自身的可复用性）
_CRT_NAMES = {"main", "printf", "puts", "putchar", "scanf", "exit", "abort",
              "malloc", "calloc", "realloc", "free", "memcpy", "memset",
              "memmove", "strlen", "strcmp", "strcpy", "strncpy", "fprintf",
              "snprintf", "PyInit_app", "data_start"}
_CRT_RE = None


def _is_crt(name: str) -> bool:
    import re
    global _CRT_RE
    if _CRT_RE is None:
        _CRT_RE = re.compile(r"^(__|_[A-Za-z])|tm_clones|frame_dummy|"
                             r"global_.*|__do_global")
    return name in _CRT_NAMES or bool(_CRT_RE.search(name))


def user_symbols(exe: str) -> set[str]:
    """工程自身函数符号（剔除 CRT/加载器/编译器桩，如 `_start`、`frame_dummy`）。"""
    return {s for s in symbols(exe) if not _is_crt(s)}


def string_literals(exe: str, min_len: int = 4) -> set[str]:
    s = _strings()
    if not s:
        return set()
    out = _run([s, "-n", str(min_len), exe])
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def features(exe: str) -> dict:
    """提取一份二进制的静态特征。"""
    return {
        "size": os.path.getsize(exe) if os.path.exists(exe) else 0,
        "symbols": symbols(exe),
        "user_symbols": user_symbols(exe),
        "strings": string_literals(exe),
    }


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 1.0
    return len(a & b) / len(u)


def name_recovery_accuracy(targets: list[str], protected_syms: set[str]) -> float:
    """ground truth 目标名在保护产物中的存活比例（越低越好；目标 ≤ 0.20）。"""
    if not targets:
        return 0.0
    hit = sum(1 for t in targets if t in protected_syms)
    return round(hit / len(targets), 4)


def bin_similarity(fb: dict, fp: dict) -> float:
    """结构相似度代理：**工程函数** Jaccard(0.5) + 字符串 Jaccard(0.3) + 体积接近度(0.2)。

    越低越好（目标 ≤ 0.55）。这是一个**确定性静态代理**，非 BinDiff/Asm2Vec；
    无独有工具时作为可复现替代，理由写入 `verdict.reasons`。
    仅统计工程自身函数符号（剔除 CRT/库函数），避免共性符号虚高相似度。
    """
    sym = _jaccard(fb.get("user_symbols", set()), fp.get("user_symbols", set()))
    st = _jaccard(fb["strings"], fp["strings"])
    sb, sp = fb["size"], fp["size"]
    size_close = (min(sb, sp) / max(sb, sp)) if max(sb, sp) else 1.0
    return round(0.5 * sym + 0.3 * st + 0.2 * size_close, 4)
