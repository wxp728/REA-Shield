# 安全自检（NFR-09 / CQ-01）

> 由 `python tools/sbom.py` 生成；SBOM 见 `sbom.json`。

## 依赖组件

| 组件 | 版本 | 许可证 |
| :--- | :--- | :--- |
| jsonschema | 4.26.0 | MIT |
| PyYAML | 6.0.3 | MIT |
| deap | 1.4.4 | LGPL |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| setuptools | 65.5.0 | MIT License |
| LLVM/clang | clang version 18.1.8 | Apache-2.0 WITH LLVM-exception |
| python | 3.11.9 | PSF-2.0 |
| cmake | cmake version 3.16.5 | BSD-3-Clause |
| binutils(nm/objdump/strings) | GNU objdump (GNU Binutils) 2.34 | GPL-3.0 |
| node | v20.20.2 | MIT |
| npm | 10.8.2 | Artistic-2.0 |
| rustc | rustc 1.99.0 (b940084d7 2026-09-28) | MIT OR Apache-2.0 |
| JDK | openjdk version "11.0.12" 2021-07-20 | GPL-2.0 WITH Classpath-exception |
| Ghidra | ghidra_12.1.4_PUBLIC | Apache-2.0 |

## 自检结论

- 许可证齐全：**是**
- 在线漏洞库查询（OSV/GHSA）：**deferred(S5)**（需联网；S5 执行）
- 高危依赖：无（离线范围内）

## 说明

在线 CVE 查询需外网，本阶段显式标注为 `deferred(S5)`，不做无依据的「无漏洞」断言；S5 将以 SBOM 对接 OSV/GHSA 完成在线核验。
