# PoC 套件（M1 架构门禁去风险验证）

本目录承载 `docs/design/poc-plan.md` 定义的 4 项技术选型 PoC 的可执行代码与证据。
**任一 PoC 未通过，先调整技术方案（回写 ADR），再进入 S2。**

| 目录 | PoC | 目标 | 通过标准 | 回写位置 |
| :--- | :--- | :--- | :--- | :--- |
| `poc1-llvm-pass/` | PoC-1 | LLVM 18+ Pass 可行性（CFF） | 样例函数变换后可编译/可运行/单测全过 | `poc-plan.md §6`、`ADR-001` |
| `poc2-ghidra-headless/` | PoC-2 | Ghidra Headless 批量反编译 | 成功率 ≥ 95%，文本可喂 LLM | `poc-plan.md §6`、`ADR-006` |
| `poc3-deap/` | PoC-3 | DEAP 策略进化原型 | 跑通一轮进化；得分不劣化；可导出合规策略 | `poc-plan.md §6`、`ADR-005`/`FR-F3` |
| `poc4-wbc/` | PoC-4 | 白盒查找表编码（AES） | 加解密自洽；无明文密钥常量；性能可接受 | `poc-plan.md §6`、`ADR-003` |

## 快速运行

```bash
# 依赖工具链（见 docs/STATUS.md §7 与本目录 setup_env.sh 记录）
poc/poc1-llvm-pass/run.sh          # 需 LLVM 18+ / clang
poc/poc2-ghidra-headless/run.sh    # 需 Ghidra + JDK17+
poc/poc3-deap/evolve.py            # 需 Python 3.11+ / DEAP
poc/poc4-wbc/                      # make && make check
```

## 结论

各 PoC 结论与证据汇总见 `docs/design/poc-plan.md §6`，并已回写对应 ADR。
