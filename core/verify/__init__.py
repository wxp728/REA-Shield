"""S4 系统集成与验证工具集（M6）。

- `differential`：差分 fuzz（同接口注入随机输入，比对原版/保护版行为）；
- `overhead`：逐资产性能基准；
- `independent`：独立工具交叉验证（objdump / 可选 Ghidra）；
- `reproducibility`：同输入 + 同种子 -> 产物逐位一致；
- `robustness`：异常输入 / 超时 / 大工程；
- `matrix`：兼容性矩阵（平台 / 语言 / 构建系统 / LLVM 版本）。
"""
from . import (differential, overhead, independent, reproducibility,  # noqa: F401
               robustness, matrix)
