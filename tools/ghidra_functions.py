#!/usr/bin/env python3
"""Ghidra(PyGhidra) 独立函数名枚举（供 `core/verify/independent.py` 调用）。

用法：GHIDRA_INSTALL_DIR=<ghidra> JAVA_HOME=<jdk> python3 ghidra_functions.py <binary>
输出：JSON `{"functions": [names...]}`。
非零退出/异常即视为不可用，调用方降级。
"""
import json
import os
import sys
import tempfile


def _scan_opt(prefix: str) -> str | None:
    """在 /opt 及其一级子目录下找 <prefix>* 目录（不写死任何内部路径）。"""
    root = "/opt"
    if not os.path.isdir(root):
        return None
    bases = [root] + [os.path.join(root, d) for d in sorted(os.listdir(root))
                      if os.path.isdir(os.path.join(root, d))]
    for base in bases:
        for d in sorted(os.listdir(base)):
            if d.lower().startswith(prefix):
                return os.path.join(base, d)
    return None


def _autodetect():
    if not os.environ.get("GHIDRA_INSTALL_DIR"):
        home = _scan_opt("ghidra_")
        if home:
            os.environ["GHIDRA_INSTALL_DIR"] = home
    if not os.environ.get("JAVA_HOME"):
        home = _scan_opt("jdk")
        if home:
            os.environ["JAVA_HOME"] = home


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ghidra_functions.py <binary>", file=sys.stderr)
        return 2
    _autodetect()
    import pyghidra
    pyghidra.start()  # 读取 GHIDRA_INSTALL_DIR / JAVA_HOME

    binary = sys.argv[1]
    project_dir = tempfile.mkdtemp(prefix="pyghidra_s4_")
    names = []
    with pyghidra.open_program(binary, project_location=project_dir,
                               analyze=True) as api:
        program = api.getCurrentProgram()
        fm = program.getFunctionManager()
        for func in fm.getFunctions(True):
            if func.isExternal() or func.isThunk():
                continue
            names.append(func.getName())
    print(json.dumps({"functions": sorted(names)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
