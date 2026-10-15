# 项目状态与交接（Handoff）

> **新会话请从这里开始。** 本文件描述 Anti-REA Skill 项目的当前进度、已完成的交付物、已决 / 待决事项，以及**下一步该做什么**。

## 0. 快照

| 项 | 值 |
| :--- | :--- |
| 日期 | 2026-10-15 |
| 分支 | `master` |
| 基线 tag | `m0-baseline`（M0 需求基线）、`m1-architecture`（M1 架构基线） |
| 远端 | `git@gitee.com:wxp728/anti-rea.git` |
| 最近提交 | 见 `git log -1`（本文件随该提交一并推送） |
| 工作区 | 干净（无未提交改动） |

## 1. 一句话现状

**规划与设计已到 S1，并通过 M1 架构门禁（4 项 PoC 全部通过）；尚未开始编码。** 下一步是进入 **S2 详细设计**。

## 2. 里程碑状态（对照 `plan/anti-rea-project-plan.md` §1.2）

| 里程碑 | 状态 | 说明 |
| :--- | :--- | :--- |
| **M0 需求基线** | ✅ 已通过 | tag `m0-baseline`；47 FR + 11 NFR + 5 CQ 已基线 |
| **M1 架构基线** | ✅ 已通过 | HLD / 接口 / ADR / Schema 已产出；**PoC-1…4 全部通过**；tag `m1-architecture` |
| **M2 设计基线** | ⬜ 未开始 | 下一步：S2 详细设计（DD-01…DD-10） |
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
| S1 | 概要设计说明书 | `docs/design/HLD.md` | v1.1（已基线） |
| S1 | 接口契约 | `docs/design/interfaces.md` | v1.1（已基线） |
| S1 | 架构决策记录 | `docs/design/ADR.md` | v1.1（PoC 已验证） |
| S1 | PoC 方案与结论 | `docs/design/poc-plan.md` | v1.1（含 §6 结论） |
| S1 | 数据契约 Schema ×4 | `schemas/*.schema.json` | — |
| S1 | **PoC 可执行代码与证据** | `poc/poc1-llvm-pass/`、`poc/poc2-ghidra-headless/`、`poc/poc3-deap/`、`poc/poc4-wbc/` | — |
| S1 | 环境安装记录脚本 | `poc/setup_env.sh` | — |

## 4. 已决决策（**不要重新讨论**）

| 编号 | 决策 | 落点 |
| :--- | :--- | :--- |
| OI-01 | 产物目标平台含 Windows x64 = Must；工具自身原生 Windows = Should（优先 Linux/WSL2） | SRS NFR-05、ADR-007 |
| OI-02 | 白盒密码 v1.0 走**自研查找表编码**；Chow 留作增强；由 PoC-4 复核 | SRS §8.2、ADR-003（**PoC-4 通过**） |
| OI-03 | 评估 LLM **不绑定供应商**，用运行环境 LLM；判定 = 独立会话**上下文消耗 ≥ 90% 仍未成功 REA 即通过**；同时保留 Token 倍数指标 | SRS NFR-02/FR-E3/FR-F1、ADR-004 |

架构侧另见 `docs/design/ADR.md`（ADR-001…007，均已回写 PoC 结论）。

## 5. 待决问题（后续阶段处理，当前不阻塞）

| 编号 | 问题 | 处置阶段 |
| :--- | :--- | :--- |
| OI-04 | 出口管制目标市场清单与加密强度分级 | S5 |
| OI-05 | MTD 变体上限与制品签名 / 分发方式 | S2 |
| OI-06 | 是否引入 RISC-V 后端 | 后续版本 |
| OI-07 | 「REA 成功」的判定标准 + 独立会话上下文窗口口径 | **S2 详细设计**（重要：NFR-02 判定依赖它） |

## 6. 下一步：进入 S2 详细设计（M1 后的第一要务）

M1 已通过（4 项 PoC 结论见 `poc-plan.md §6`、`ADR.md`）。按 `plan/anti-rea-project-plan.md §4` 开展 S2：

| 任务 | 内容 | 必须回答的设计点（节选） |
| :--- | :--- | :--- |
| DD-01 | 资产扫描详细设计 | 语言检测；三类扫描规则与权重；误报控制；敏感度打分公式 |
| DD-02 | 策略引擎详细设计 | 策略 DSL；匹配规则；预算约束下的优化算法与开销预测模型 |
| DD-03 | LLVM 变换详细设计 | Pass 管线顺序；CFF 块提取/调度构造/状态重排；MBA 恒等式库；不透明谓词；等价性验证（SMT/差分） |
| DD-04 | 虚拟化引擎详细设计 | 自定义 ISA 规范；字节码编译；解释器与反调试陷阱；覆盖率控制 |
| DD-05 | 对抗诱导详细设计 | 语料库；相似度度量；变异算子；适应度 |
| DD-06 | 白盒密码详细设计 | 查找表编码；密钥生命周期；威胁模型边界 |
| DD-07 | 评估层详细设计 | 攻击模拟编排；六项指标口径；基准题库 ground truth |
| DD-08 | 自适应引擎详细设计 | 策略基因编码；进化参数；适应度；多 LLM 探测协议 |
| DD-09 | 测试计划 | 各类测试用例设计，逐条回溯 FR |
| DD-10 | 详细设计评审 | 可编码性 + 测试计划覆盖评审 |

**M2 出口准则**：每模块设计「换人可实现」；关键算法有伪代码+复杂度+正确性论证；测试计划覆盖 100% FR（RTM「测试」列填实）；评审无阻塞问题。

> 具体化 **OI-07**（REA 成功判定 + 上下文窗口口径）是本阶段关键前置，NFR-02 判定依赖它。

## 7. 新环境准备（**已完成，记录实测**）

本项目 PoC 环境已在 **RHEL 系 Linux（x86_64）** 上搭建完成：

| 组件 | 实测版本 | 安装位置 | 说明 |
| :--- | :--- | :--- | :--- |
| LLVM / clang / opt | 18.1.8 | `/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04` | 官方预编译；发行版源仅 LLVM 10，不满足 |
| JDK | Temurin 21.0.12.1+1 | `/opt/anti-rea-toolchain/jdk-21.0.12.1+1` | 供 Ghidra |
| Ghidra | 12.1.4 PUBLIC | `/opt/anti-rea-toolchain/ghidra_12.1.4_PUBLIC` | **12 起无内置 Jython，须用 PyGhidra** |
| PyGhidra | 3.1.0 | `/opt/anti-rea-toolchain/python3.11` | 随 Ghidra 分发离线安装 |
| Python | 3.11.9 | `/opt/anti-rea-toolchain/python3.11` | 源码编译（源仅 3.7） |
| DEAP | 1.4.4 | 同上 site-packages | 策略进化 |
| GCC | 7.3.0（系统） | `/usr/bin` | 样例二进制 / PoC-4 |
| jsonschema / pyyaml / numpy | 4.26 / 6.0 / 2.4 | 同上 | 数据契约校验 |

一键/逐步复现见 `poc/setup_env.sh`。使用前将 LLVM `bin` 加入 `PATH`，并设置
`GHIDRA_INSTALL_DIR` / `JAVA_HOME`（`poc/poc2-ghidra-headless/run.sh` 会自动探测）。

> 原环境（Windows）缺 clang/llvm-config/cmake/rustc/java，故无法执行 PoC-1/PoC-2——这是切换到 Linux 的原因。

## 8. 如何在新会话继续（给新 Agent 的说明）

**建议开场提示词：**

> 请阅读仓库根目录 `README.md` 与 `docs/STATUS.md`，了解 Anti-REA Skill 项目的当前进度；
> M1 架构门禁已通过（4 项 PoC 全部通过，见 `docs/design/poc-plan.md §6` 与 `docs/design/ADR.md`）。
> 请按 `plan/anti-rea-project-plan.md §4` 开始 **S2 详细设计**（DD-01…DD-10），
> 首先细化 **OI-07**（REA 成功判定标准 + 独立会话上下文窗口口径），并产出 DDD 与覆盖全部 FR 的测试计划，最终过 M2 门禁。
> 注意：需求已基线（tag `m0-baseline`），变更须走变更流程；所有跨模块数据须过 `schemas/` 校验。

**接手顺序**：`README.md` → `docs/STATUS.md`（本文）→ `plan/anti-rea-project-plan.md`（§4 S2）→ `docs/design/HLD.md` → `docs/design/interfaces.md`。

## 9. 约定与注意事项

- **不要修改已基线需求**：`docs/requirements/SRS.md` v1.2 已基线；如需变更，走 `plan/anti-rea-project-plan.md §10.4` 变更流程并更新 RTM 与变更记录。
- **数据契约**：跨模块数据必须通过 `schemas/*.schema.json`（Draft 2020-12）校验，fail-fast。
- **行尾**：仓库统一 LF（见 `.gitattributes`），Windows 上检出时会提示 LF→CRLF，属正常。
- **提交规范**：Conventional Commits（`docs: / feat: / fix: / test: / chore:`）。
- **文档版本**：修改文档需同步升版本号并更新其变更记录。
- **PoC 代码**：位于 `poc/`，构建产物已由 `.gitignore` 排除。

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
| PoC 方案与结论 | `docs/design/poc-plan.md` |
| PoC 可执行代码与证据 | `poc/` |
| 数据契约 | `schemas/*.schema.json` |
