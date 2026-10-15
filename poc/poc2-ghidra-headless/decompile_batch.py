#!/usr/bin/env python3
"""
decompile_batch.py — Ghidra Headless 批量反编译（PyGhidra / CPython）
关联：ADR-006 / FR-E3 / docs/design/poc-plan.md §3

Ghidra 12 起不再内置 Jython，官方推荐 PyGhidra（CPython）。本脚本作为
「外部工具适配层」的原型：对单个二进制自动分析并逐函数反编译，输出：
  - <out_dir>/<addr>_<name>.c  供 LLM 消费的函数级伪代码；
  - <json_out> 汇总（total/ok/rate）。

用法：
  GHIDRA_INSTALL_DIR=<ghidra> python3 decompile_batch.py <binary> <out_dir> <json_out>
"""
import json
import os
import sys
import tempfile

import pyghidra

pyghidra.start()  # 读取 GHIDRA_INSTALL_DIR / JAVA_HOME

from ghidra.app.decompiler import DecompInterface  # noqa: E402
from ghidra.util.task import ConsoleTaskMonitor  # noqa: E402


def decompile(binary, out_dir, json_out, timeout_sec=60):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    results = []
    ok = 0
    # Ghidra 项目落在临时目录，避免污染样例目录
    project_dir = tempfile.mkdtemp(prefix="pyghidra_proj_")
    with pyghidra.open_program(binary, project_location=project_dir,
                               analyze=True) as api:
        program = api.getCurrentProgram()
        decomp = DecompInterface()
        decomp.openProgram(program)
        monitor = ConsoleTaskMonitor()
        fm = program.getFunctionManager()
        for func in fm.getFunctions(True):
            if func.isExternal() or func.isThunk():
                continue
            entry = {"name": func.getName(), "addr": str(func.getEntryPoint())}
            try:
                res = decomp.decompileFunction(func, timeout_sec, monitor)
            except Exception as exc:  # noqa: BLE001
                res = None
                entry["error"] = str(exc)
            if res is not None and res.decompileCompleted():
                code = res.getDecompiledFunction().getC()
                entry["ok"] = True
                entry["chars"] = len(code)
                safe = "%s_%s.c" % (entry["addr"], func.getName())
                with open(os.path.join(out_dir, safe), "w", encoding="utf-8") as fh:
                    fh.write("// %s @ %s\n" % (func.getName(), entry["addr"]))
                    fh.write(code)
                ok += 1
            else:
                entry["ok"] = False
                if res is not None:
                    entry["error_msg"] = res.getErrorMessage()
            results.append(entry)
        program_name = program.getName()

    total = len(results)
    rate = (float(ok) / total) if total else 0.0
    summary = {
        "program": program_name,
        "total": total,
        "ok": ok,
        "rate": rate,
        "functions": results,
    }
    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print("DECOMP_RESULT program=%s total=%d ok=%d rate=%.4f"
          % (program_name, total, ok, rate))
    return summary

def main():
    if len(sys.argv) != 4:
        print("用法: decompile_batch.py <binary> <out_dir> <json_out>", file=sys.stderr)
        return 2
    decompile(sys.argv[1], sys.argv[2], sys.argv[3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
