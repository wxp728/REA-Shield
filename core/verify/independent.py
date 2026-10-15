"""独立工具交叉验证（M6 出口「外部独立验证不矛盾」的工程化近似）。

内置评估（`core/evaluate/static_features.py`）用 `nm`/`strings`；本模块改用
**独立工具路径**复核同一结论，避免单一工具误判：

- `objdump`（binutils，独立于 nm/strings 的实现）：枚举函数符号、转储只读段；
- `Ghidra`（可选，`ANTI_REA_GHIDRA=1` 时）：独立反汇编器恢复的函数名。

两者都应得到与内置一致的结论（目标名不泄漏、关键明文串消失）。
这是**工具无关性交叉检查**，不等同于第三方红队结论（后者见 STR 说明）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess


def _objdump() -> str | None:
    return shutil.which("objdump")


def symbol_names(exe: str) -> set[str]:
    """经 `objdump -t` 枚举已定义函数符号（独立于 nm）。"""
    objdump = _objdump()
    if not objdump:
        return set()
    p = subprocess.run([objdump, "-t", exe], capture_output=True, text=True)
    names: set[str] = set()
    for line in p.stdout.splitlines():
        parts = line.split()
        # 例: "0000000000001149 l  F .text  0000000000000017 secret_mix"
        if len(parts) >= 6 and parts[2] == "F" and parts[3].startswith(".text"):
            names.add(parts[-1].split("@@")[0])
    return names


def string_present(exe: str, needle: str) -> bool:
    """经 `objdump -s` 段转储判定字符串是否存在（独立于 strings）。"""
    objdump = _objdump()
    if not objdump:
        return False
    p = subprocess.run([objdump, "-s", exe], capture_output=True, text=True)
    return needle in p.stdout


def ghidra_available() -> bool:
    if os.environ.get("ANTI_REA_GHIDRA") != "1":
        return False
    try:
        import pyghidra  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return bool(_ghidra_home())


def _ghidra_home() -> str | None:
    if os.environ.get("GHIDRA_INSTALL_DIR"):
        return os.environ["GHIDRA_INSTALL_DIR"]
    for root in ("/opt/anti-rea-toolchain", "/opt"):
        if os.path.isdir(root):
            for d in sorted(os.listdir(root)):
                if d.lower().startswith("ghidra_"):
                    return os.path.join(root, d)
    return None


def ghidra_symbols(exe: str, timeout: float = 600.0) -> set[str]:
    """经 Ghidra(PyGhidra) 独立恢复函数名（可选路径；失败返回空集）。"""
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "tools", "ghidra_functions.py")
    if not os.path.exists(script):
        return set()
    env = dict(os.environ)
    home = _ghidra_home()
    if home:
        env["GHIDRA_INSTALL_DIR"] = home
    try:
        p = subprocess.run([os.environ.get("ANTI_REA_PYTHON", "python3"), script, exe],
                           capture_output=True, text=True, timeout=timeout, env=env)
        if p.returncode != 0:
            return set()
        return set(json.loads(p.stdout).get("functions", []))
    except Exception:  # noqa: BLE001
        return set()


def verify(baseline_exe: str, protected_exe: str, targets: list[str],
           needles: list[str]) -> dict:
    """独立复核**与内置相同的判据**：受保护目标函数名是否泄漏。

    说明：保护为**选择性**（FR-C6），非目标函数（如 `main`）中的字符串
    不受保护，故 `leaked_strings` 仅作信息项，不计入独立结论，以免与内置
    `static_only` 判据口径不一致。
    """
    base_names = symbol_names(baseline_exe)
    prot_names = symbol_names(protected_exe)
    leaked_names = sorted(t for t in targets if t in prot_names)
    leaked_strings = sorted(n for n in needles if string_present(protected_exe, n))

    tool = "objdump"
    ghidra_names = None
    if ghidra_available():
        tool = "objdump+ghidra"
        ghidra_names = ghidra_symbols(protected_exe)
        leaked_names = sorted(set(leaked_names) |
                              {t for t in targets if t in (ghidra_names or set())})

    # 独立判据：目标名不泄漏（与内置 name_recovery ≤ 20% 同向）
    independent_pass = not leaked_names
    return {
        "tool": tool,
        "baseline_functions": len(base_names),
        "protected_functions": len(prot_names),
        "leaked_names": leaked_names,
        "leaked_strings": leaked_strings,
        "ghidra_ran": ghidra_names is not None,
        "independent_pass": independent_pass,
    }


def agrees_with_builtin(builtin_pass: bool, independent: dict) -> bool:
    """「不矛盾」：独立结论与内置结论方向一致。"""
    return bool(builtin_pass) == bool(independent.get("independent_pass"))
