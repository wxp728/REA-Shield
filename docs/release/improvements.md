# 改进项清单（S5 试点反馈）

> 来源：`docs/release/pilot-report.md`（3 个试点：C/CMake/P0、C++/Make/P1、Python C 扩展/P2）。
> 状态：`已落地` / `待排期`。

| 编号 | 级别 | 改进项 | 来源 | 处置 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| I-01 | P2 | 将「独立工具交叉验证」纳入试点/发布验收 | 对抗结论可信度 | 已在 S4 落地（`core/verify/independent.py` + `tools/ghidra_functions.py`） | 已落地 |
| I-02 | P2 | 交叉编译仅到 IR 层，链接层多目标支持待补交叉 sysroot | 兼容性矩阵 | 记录为已知限制；后续补 sysroot 或改用 `--sysroot` 配置 | 待排期 |
| I-03 | P2 | 无 LLM 时以 `static_only` 代理指标验收，Token 倍数未测 | NFR-02 | 配置真实 LLM（CQ-05）后补测 Token 倍数 ≥ 100x | 待排期 |
| I-04 | P3 | 扫描器函数定义正则不支持 `extern "C"` 前缀（C++ 导出） | 试点 2 | 已修正 `_FUNC_RE`（容许 `extern "C"`） | 已落地 |
| I-05 | P3 | 对抗诱导变体文件名恒为 `.c`，C++ 源变体编译失败 | 试点 2 | 已改为保留源扩展名（`.cpp`） | 已落地 |
| I-06 | P3 | Python 扩展试点需「双模式」源（`ANTI_REA_EXT`）方能既做扩展又做差分验证 | 试点 3 | 已在试点与文档中固化该模式（沿用 `integrations/python/example`） | 已落地 |
