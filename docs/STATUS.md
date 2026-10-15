# 项目状态与交接（Handoff）

> **新会话请从这里开始。** 本文件描述 Anti-REA Skill 项目的当前进度、已完成的交付物、已决 / 待决事项，以及**下一步该做什么**。

## 0. 快照

| 项 | 值 |
| :--- | :--- |
| 日期 | 2026-10-15 |
| 分支 | `master` |
| 基线 tag | `m0-baseline`（M0 需求基线） |
| 远端 | `git@gitee.com:wxp728/anti-rea.git` |
| 最近提交 | 见 `git log -1`（本文件随该提交一并推送） |
| 工作区 | 干净（无未提交改动） |

## 1. 一句话现状

**规划与设计已完成到 S1；尚未开始编码。** 下一步是执行 4 项技术选型 PoC，以通过 M1 架构门禁。

## 2. 里程碑状态（对照 `plan/anti-rea-project-plan.md` §1.2）

| 里程碑 | 状态 | 说明 |
| :--- | :--- | :--- |
| **M0 需求基线** | ✅ 已通过 | tag `m0-baseline`；47 FR + 11 NFR + 5 CQ 已基线 |
| **M1 架构基线** | 🟡 进行中 | HLD / 接口 / ADR / Schema 已产出；**PoC-1…4 未执行**，故未过门 |
| M2 设计基线 | ⬜ 未开始 | S2 详细设计 |
| M3–M5 编码迭代 | ⬜ 未开始 | R1 / R2 / R3 |
| M6–M8 验证 / 试点 / 发布 | ⬜ 未开始 | — |

## 3. 已完成交付物清单

| 阶段 | 文档 | 路径 | 版本 |
| :--- | :--- | :--- | :--- |
| 计划 | 技术方案 | `plan/anti-rea-plan.md` | v1.0 |
| 计划 | 全生命周期项目计划 | `plan/anti-rea-project-plan.md` | v1.1 |
| S0 | 需求规格说明书 | `docs/requirements/SRS.md` | v1.2（已基线） |
| S0 | 用例文档 | `docs/requirements/use-cases.md` | v1.1 |
| S0 | 需求追踪矩阵 | `docs/requirements/rtm.md` | v1.2 |
| S0 | 合规与边界需求 | `docs/requirements/compliance.md` | v1.1 |
| S1 | 概要设计说明书 | `docs/design/HLD.md` | v1.0 |
| S1 | 接口契约 | `docs/design/interfaces.md` | v1.0 |
| S1 | 架构决策记录 | `docs/design/ADR.md` | v1.0 |
| S1 | PoC 方案 | `docs/design/poc-plan.md` | v1.0 |
| S1 | 数据契约 Schema ×4 | `schemas/*.schema.json` | — |

## 4. 已决决策（**不要重新讨论**）

| 编号 | 决策 | 落点 |
| :--- | :--- | :--- |
| OI-01 | 产物目标平台含 Windows x64 = Must；工具自身原生 Windows = Should（优先 Linux/WSL2） | SRS NFR-05、ADR-007 |
| OI-02 | 白盒密码 v1.0 走**自研查找表编码**；Chow 留作增强；由 PoC-4 复核 | SRS §8.2、ADR-003 |
| OI-03 | 评估 LLM **不绑定供应商**，用运行环境 LLM；判定 = 独立会话**上下文消耗 ≥ 90% 仍未成功 REA 即通过**；同时保留 Token 倍数指标 | SRS NFR-02/FR-E3/FR-F1、ADR-004 |

架构侧另见 `docs/design/ADR.md`（ADR-001…007）。

## 5. 待决问题（后续阶段处理，当前不阻塞）

| 编号 | 问题 | 处置阶段 |
| :--- | :--- | :--- |
| OI-04 | 出口管制目标市场清单与加密强度分级 | S5 |
| OI-05 | MTD 变体上限与制品签名 / 分发方式 | S2 |
| OI-06 | 是否引入 RISC-V 后端 | 后续版本 |
| OI-07 | 「REA 成功」的判定标准 + 独立会话上下文窗口口径 | **S2 详细设计**（重要：NFR-02 判定依赖它） |

## 6. 下一步：执行 PoC（新环境的第一要务）

依据 `docs/design/poc-plan.md`，在新环境逐项执行并把结论**回写**：

| PoC | 目标 | 通过标准 | 回写位置 |
| :--- | :--- | :--- | :--- |
| **PoC-1** | LLVM 18+ Pass 可行性 | 样例函数完成一次 CFF 式改写，可编译可运行、单测通过 | `poc-plan.md §6`、`ADR-001` |
| **PoC-2** | Ghidra Headless 自动化 | 批量反编译成功率 ≥ 95%，文本可喂 LLM | `poc-plan.md §6`、`ADR-006` |
| **PoC-3** | DEAP 策略进化原型 | 完成一轮 初始化→评估→交叉变异→选择 | `poc-plan.md §6` |
| **PoC-4** | 白盒查找表编码 | AES 加解密自洽、无明文密钥常量、性能可接受 | `poc-plan.md §6`、`ADR-003` |

**完成 PoC 后 → 过 M1：**
1. 更新 `poc-plan.md §6 结论汇总表`（通过 / 调整 / 失败 + 证据）；
2. 回写受影响的 ADR 状态（尤其 ADR-003 由「待验证」→「已接受 / 已调整」）；
3. 将 `HLD.md` 文档状态由「待 M1 架构评审基线化」改为「已基线」；
4. 更新本文件 §2 里程碑状态为 M1 ✅，并记录新 tag（如 `m1-architecture`）；
5. 进入 S2 详细设计。

> 若某项 PoC 不通过：**先调整技术方案 + 记录 ADR，不要直接进 S2**（项目计划要求「不带风险进入 S2」）。

## 7. 新环境准备清单（Linux）

```bash
# 系统工具链（示例：Debian/Ubuntu）
sudo apt-get update
sudo apt-get install -y build-essential cmake git curl
# LLVM 18+（含 clang / llvm-config）
sudo apt-get install -y llvm-18 llvm-18-dev clang-18 libclang-18-dev
# JDK + Ghidra（PoC-2）：从 https://ghidra-sre.org 下载并设置 GHIDRA_HOME
sudo apt-get install -y default-jdk

# Python 依赖
python3 -m pip install --user deap jsonschema pyyaml   # z3-solver 可选（MBA 等价性验证）

# 自检：4 份 Schema 必须是合法 JSON
python3 - <<'PY'
import json, glob
for f in glob.glob('schemas/*.json'):
    json.load(open(f, encoding='utf-8')); print('OK', f)
PY
```

> 注意：`clang` / `llvm-config` / `cmake` / `rustc` / `java` 在编写本文件的原环境（Windows）中**均不可用**，因此 PoC-1/PoC-2 无法在原环境执行——这是切换到 Linux 环境的原因之一。

## 8. 如何在新会话继续（给新 Agent 的说明）

**建议开场提示词：**

> 请阅读仓库根目录 `README.md` 与 `docs/STATUS.md`，了解 Anti-REA Skill 项目的当前进度；
> 然后按 `docs/design/poc-plan.md` 执行尚未完成的 PoC（PoC-1…4：LLVM Pass / Ghidra Headless / DEAP / 白盒密码），
> 把结论回写到 `poc-plan.md §6` 与 `ADR.md`，完成后帮我过 M1 门禁并开始 S2 详细设计。
> 注意：需求已基线（tag `m0-baseline`），变更须走变更流程；所有跨模块数据须过 `schemas/` 校验。

**接手顺序**：`README.md` → `docs/STATUS.md`（本文）→ `plan/anti-rea-project-plan.md` → `docs/design/HLD.md` → `docs/design/poc-plan.md`。

## 9. 约定与注意事项

- **不要修改已基线需求**：`docs/requirements/SRS.md` v1.2 已基线；如需变更，走 `plan/anti-rea-project-plan.md §10.4` 变更流程并更新 RTM 与变更记录。
- **PoC 不改需求**：PoC 只回写 ADR 与 `poc-plan.md`；若结论要求改需求，则按变更流程处理。
- **数据契约**：跨模块数据必须通过 `schemas/*.schema.json`（Draft 2020-12）校验，fail-fast。
- **行尾**：仓库统一 LF（见 `.gitattributes`），Windows 上检出时会提示 LF→CRLF，属正常。
- **提交规范**：Conventional Commits（`docs: / feat: / fix: / test: / chore:`）。
- **文档版本**：修改文档需同步升版本号并更新其变更记录。

## 10. 文件地图（便于快速定位）

| 想找…… | 路径 |
| :--- | :--- |
| 项目要做什么 / 为什么这样做 | `plan/anti-rea-plan.md` |
| 全生命周期流程、里程碑、出口准则、风险 | `plan/anti-rea-project-plan.md` |
| 需求、验收标准、优先级 | `docs/requirements/SRS.md` |
| 需求追踪关系 | `docs/requirements/rtm.md` |
| 合规 / 许可证 / 使用边界 | `docs/requirements/compliance.md` |
| 架构、组件、部署、仓库骨架 | `docs/design/HLD.md` |
| 模块接口 / MCP / CLI / SPI / 错误码 | `docs/design/interfaces.md` |
| 技术取舍理由 | `docs/design/ADR.md` |
| 下一步：PoC 执行方案 | `docs/design/poc-plan.md` |
| 数据契约 | `schemas/*.schema.json` |
