# 缺陷清单（Defect List）

> S4 缺陷管理（`plan §6.2`）。分级：P0 阻塞 / P1 严重 / P2 一般 / P3 轻微。
> 处理原则：无未修复 P0/P1；P2 修复率 ≥ 90%；P3 记录待排期。

## 未修复缺陷

_（无未修复 P0/P1/P2）_

## 已修复缺陷

| 编号 | 级别 | 描述 | 修复 | 回归用例 |
| :--- | :--- | :--- | :--- | :--- |
| D-001 | P1 | 锚点移除初版密钥流为编译期常量，易被常量折叠/提取 | 改为运行期从可变全局派生（volatile 载入） | `test_anchor_removal` |
| D-002 | P2 | `ident-rename` 后调试信息仍可能泄漏原名 | rename 末尾剥离逐函数调试信息并清除 `llvm.dbg.cu` | `test_anchor_removal` |
| D-003 | P2 | Cargo 集成无 rust 环境时被跳过，未实测 | 经 rsproxy 安装 rust 工具链，样例实测通过 | `test_integrations.py` |
| D-004 | P2 | 跨目标三元组探针误判「不支持」（实为目标头文件缺失） | 改为 freestanding IR 探针（`matrix.cross_target_probe`） | `test_verify_s4.py` |

## 额外工程改进（非缺陷）

| 编号 | 描述 | 处置 |
| :--- | :--- | :--- |
| I-001 | 函数级 `main`（非白名单）字符串不加密 | 设计使然（选择性变换 FR-C6）；独立复核仅以目标名为判据 |
| I-002 | 无 LLM 时 `token_ratio` 不可测 | `static_only` 降级（OI-07 D5）；Token 倍数留待 S5 |
