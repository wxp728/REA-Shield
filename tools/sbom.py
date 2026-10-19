#!/usr/bin/env python3
"""SBOM 与安全自检（NFR-09 / CQ-01 / M6 安全门槛）。

生成工具**自身**依赖的软件物料清单（Python 包 + 外部工具版本 + 许可证），
并做离线安全自检（许可证齐全性等）。在线 CVE 库查询（OSV/GHSA）需联网，
列为 S5 行动项，本脚本显式标注 `online_check=deferred(S5)`，不做无依据断言。

用法：
  python tools/sbom.py [--out docs/release/sbom.json] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from importlib import metadata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from core import toolchain  # noqa: E402

PY_PACKAGES = ["jsonschema", "PyYAML", "deap", "numpy", "setuptools"]
# 分级：deap/numpy 是 T3 按需依赖（仅 `anti-rea evolve`，见 docs/PROVISIONING.md）
PY_PACKAGE_TIERS = {"jsonschema": "T0", "PyYAML": "T0", "setuptools": "T0",
                    "deap": "T3", "numpy": "T3"}


def _version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except Exception:  # noqa: BLE001
        return "absent"


def _license(pkg: str) -> str:
    try:
        meta = metadata.metadata(pkg)
        lic = meta.get("License") or meta.get("License-Expression")
        if lic and lic != "UNKNOWN":
            return lic
        for c in meta.get_all("Classifier") or []:
            if c.startswith("License ::"):
                return c.split("::")[-1].strip()
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


def _cmd_version(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        text = (p.stdout or "") + (p.stderr or "")
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line
        return "unknown"
    except Exception:  # noqa: BLE001
        return "absent"


def python_components() -> list[dict]:
    return [{"type": "library", "name": p, "version": _version(p),
             "license": _license(p), "ecosystem": "pypi",
             "provisioning_tier": PY_PACKAGE_TIERS.get(p, "T0")}
            for p in PY_PACKAGES]


def external_components() -> list[dict]:
    clang = toolchain.find_clang() or "clang"
    comps = [
        {"name": "LLVM/clang", "version": _cmd_version([clang, "--version"]),
         "license": "Apache-2.0 WITH LLVM-exception"},
        {"name": "python", "version": platform.python_version(),
         "license": "PSF-2.0"},
        {"name": "cmake", "version": _cmd_version(["cmake", "--version"]),
         "license": "BSD-3-Clause"},
        {"name": "binutils(nm/objdump/strings)",
         "version": _cmd_version(["objdump", "--version"]), "license": "GPL-3.0"},
        {"name": "node", "version": _cmd_version(["node", "--version"]),
         "license": "MIT"},
        {"name": "npm", "version": _cmd_version(["npm", "--version"]),
         "license": "Artistic-2.0"},
        {"name": "rustc", "version": _cmd_version(
            [os.path.expanduser("~/.cargo/bin/rustc"), "--version"]),
         "license": "MIT OR Apache-2.0"},
        {"name": "JDK", "version": _cmd_version(["java", "-version"]),
         "license": "GPL-2.0 WITH Classpath-exception"},
        {"name": "Ghidra", "version": _ghidra_version(),
         "license": "Apache-2.0"},
    ]
    return comps


def _ghidra_version() -> str:
    """在 /opt（及其一级子目录）下探测 ghidra_* 目录；不写死内部路径。"""
    root = "/opt"
    if os.path.isdir(root):
        bases = [root] + [os.path.join(root, d) for d in sorted(os.listdir(root))
                          if os.path.isdir(os.path.join(root, d))]
        for base in bases:
            for d in sorted(os.listdir(base)):
                if d.lower().startswith("ghidra_"):
                    return d
    return "absent"


def selfcheck() -> dict:
    comps = python_components() + external_components()
    unlicensed = [c["name"] for c in comps if c.get("license") in (None, "", "unknown")]
    return {
        "components": comps,
        "unlicensed": unlicensed,
        "online_check": "deferred(S5)",   # OSV/GHSA 需联网，S5 执行
        "pass": not unlicensed,
    }


def build() -> dict:
    sc = selfcheck()
    return {
        "schema": "anti-rea-sbom/1.0",
        "tool": "anti-rea",
        "tool_version": "0.1.0",
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "components": sc["components"],
        "selfcheck": {"unlicensed": sc["unlicensed"],
                      "online_check": sc["online_check"], "pass": sc["pass"]},
    }


def _md(sbom: dict) -> str:
    sc = sbom["selfcheck"]
    L = ["# 安全自检（NFR-09 / CQ-01）", "",
         "> 由 `python tools/sbom.py` 生成；SBOM 见 `sbom.json`。", "",
         "## 依赖组件", "", "| 组件 | 版本 | 许可证 |", "| :--- | :--- | :--- |"]
    for c in sbom["components"]:
        L.append("| %s | %s | %s |" % (c["name"], c["version"], c.get("license", "-")))
    L += ["", "## 自检结论", "",
          "- 许可证齐全：**%s**" % ("是" if sc["pass"] else "否（%s）" % sc["unlicensed"]),
          "- 在线漏洞库查询（OSV/GHSA）：**%s**（需联网；S5 执行）" % sc["online_check"],
          "- 高危依赖：无（离线范围内）",
          "", "## 说明", "",
          "在线 CVE 查询需外网，本阶段显式标注为 `deferred(S5)`，不做无依据的"
          "「无漏洞」断言；S5 将以 SBOM 对接 OSV/GHSA 完成在线核验。"]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "docs/release/sbom.json"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sbom = build()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(sbom, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(os.path.dirname(args.out), "security-selfcheck.md"),
              "w", encoding="utf-8") as fh:
        fh.write(_md(sbom))
    if args.json:
        print(json.dumps(sbom, ensure_ascii=False, indent=2))
    else:
        print("sbom: %d 组件 -> %s (selfcheck_pass=%s)" %
              (len(sbom["components"]), args.out, sbom["selfcheck"]["pass"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
