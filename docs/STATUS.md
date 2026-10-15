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

**S2 详细设计交付物已完成（DD-01…DD-10 + 构建集成补充设计 + OI-05/OI-07 落定），评审建议通过 M2（待人工技术负责人批准）。** 尚未开始编码，下一步进入 S3。

## 2. 里程碑状态（对照 `plan/anti-rea-project-plan.md` §1.2）

| 里程碑 | 状态 | 说明 |
| :--- | :--- | :--- |
| **M0 需求基线** | ✅ 已通过 | tag `m0-baseline`；47 FR + 11 NFR + 5 CQ 已基线 |
| **M1 架构基线** | ✅ 已通过 | HLD / 接口 / ADR / Schema 已产出；**PoC-1…4 全部通过**；tag `m1-architecture` |
| **M2 设计基线** | 🟡 待批准 | S2 交付物完成（`docs/design/ddd/`）；评审建议通过（`dd-10-review.md`），待人工批准后打 tag `m2-design` |
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
| S2 | 详细设计索引（任务追踪 / M2 出口映射） | `docs/design/ddd/README.md` | v1.0 |
| S2 | **端到端场景**：AI 经 MCP 调用 skill（集成主线） | `docs/design/ddd/e2e-scenario.md` | v1.0 |
| S2 | 详细设计 DD-01…DD-09 + 构建集成补充 | `docs/design/ddd/dd-*.md` | v1.0 |
| S2 | 详细设计评审记录（M2 门） | `docs/design/ddd/dd-10-review.md` | v1.0 |
| S2 | 决策：OI-07（REA 成功判定）/ OI-05（MTD 变体与签名） | `docs/design/ddd/decisions/*` | v1.0 |
| S2 | 测试计划 + RTM 设计锚点回填 | `docs/design/ddd/dd-09-test-plan.md`、`docs/requirements/rtm.md` v1.3 | — |

## 4. 已决决策（**不要重新讨论**）

| 编号 | 决策 | 落点 |
| :--- | :--- | :--- |
| OI-01 | 产物目标平台含 Windows x64 = Must；工具自身原生 Windows = Should（优先 Linux/WSL2） | SRS NFR-05、ADR-007 |
| OI-02 | 白盒密码 v1.0 走**自研查找表编码**；Chow 留作增强；由 PoC-4 复核 | SRS §8.2、ADR-003（**PoC-4 通过**） |
| OI-03 | 评估 LLM **不绑定供应商**，用运行环境 LLM；判定 = 独立会话**上下文消耗 ≥ 90% 仍未成功 REA 即通过**；同时保留 Token 倍数指标 | SRS NFR-02/FR-E3/FR-F1、ADR-004 |
| OI-07 | 「REA 成功」定义（S1 功能判断 >0.30 / S2 函数名恢复 >0.20 / S3 等价还原 / S4 关键信息提取，任一即成功）；独立会话**上下文 ≤90% 未出现成功信号即通过**；无 LLM 降级 `static_only` | `docs/design/ddd/decisions/OI-07-rea-success-criteria.md`（S2 落定，未改需求） |
| OI-05 | MTD `variant_count`：Schema 上限 64、缺省 8、建议 ≤16；制品以**签名 release bundle**（哈希清单 + 分离签名 + SBOM）分发；签名私钥不入库 | `docs/design/ddd/decisions/OI-05-mtd-signing.md`（S2 落定，未改需求） |

架构侧另见 `docs/design/ADR.md`（ADR-001…007，均已回写 PoC 结论）。

## 5. 待决问题（后续阶段处理，当前不阻塞）

| 编号 | 问题 | 处置阶段 |
| :--- | :--- | :--- |
| OI-04 | 出口管制目标市场清单与加密强度分级 | S5 |
| ~~OI-05~~ | ~~MTD 变体上限与制品签名 / 分发方式~~ | ✅ **已决（S2）** → 见 `docs/design/ddd/decisions/OI-05-mtd-signing.md` |
| OI-06 | 是否引入 RISC-V 后端 | 后续版本 |
| ~~OI-07~~ | ~~「REA 成功」的判定标准 + 独立会话上下文窗口口径~~ | ✅ **已决（S2）** → 见 `docs/design/ddd/decisions/OI-07-rea-success-criteria.md` |

## 6. 当前阶段：S2 详细设计（交付完成，待 M2 批准）

M1 已通过（4 项 PoC 结论见 `poc-plan.md §6`、`ADR.md`）。S2 交付物落在 **`docs/design/ddd/`**，已全部产出：

- ✅ `README.md`（索引/任务追踪）、`e2e-scenario.md`（端到端主线）；
- ✅ 各模块详细设计：`dd-01-scanner.md`、`dd-02-strategy.md`、`dd-03-llvm-transforms.md`、`dd-04-virtualization.md`、`dd-05-adversarial.md`、`dd-06-wbc.md`、`dd-07-evaluation.md`、`dd-08-adaptive.md`、`dd-build-integration.md`（FR-D*/G* 补充）；
- ✅ `dd-09-test-plan.md`（覆盖 47 FR + 11 NFR + 5 CQ，RTM v1.3 已回填设计锚点）；
- ✅ 决策：`decisions/OI-07-rea-success-criteria.md`、`decisions/OI-05-mtd-signing.md`；
- ✅ `dd-10-review.md`：**评审结论 = 满足 M2 出口准则，建议通过（待人工技术负责人批准）**。

**M2 出口准则核对**：每模块设计「换人可实现」（✅）；关键算法有伪代码+复杂度+正确性论证（✅ 12 项）；测试计划覆盖 100% FR（✅ 47/47）；评审无阻塞问题（✅）。

> **下一步**：人工批准 M2 后打 tag `m2-design`，进入 **S3 编码实现（R1 基础骨架与基础变换，M3）**。S3 前置行动项见 `dd-10-review.md §7`（基准题库、检测器选型、参数标定）。

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
> M1 架构门禁已通过（4 项 PoC），S2 详细设计交付物已完成（见 `docs/design/ddd/`），
> 评审建议通过 M2（见 `docs/design/ddd/dd-10-review.md`）。请确认/批准 M2 后打 tag `m2-design`，
> 再按 `plan/anti-rea-project-plan.md §5` 进入 **S3 编码实现（R1）**。
> 注意：需求已基线（tag `m0-baseline`），变更须走变更流程；所有跨模块数据须过 `schemas/` 校验。

**接手顺序**：`README.md` → `docs/STATUS.md`（本文）→ `docs/design/ddd/README.md`（S2 索引）→ `docs/design/ddd/dd-10-review.md` → `plan/anti-rea-project-plan.md`（§5 S3）。

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
| S2 详细设计索引 / 任务追踪 | `docs/design/ddd/README.md` |
| 端到端 Agent 调用场景（S2 主线） | `docs/design/ddd/e2e-scenario.md` |
| 各模块详细设计（DD-01…DD-09 + 构建集成） | `docs/design/ddd/dd-*.md` |
| 详细设计评审（M2 门） | `docs/design/ddd/dd-10-review.md` |
| 「REA 成功」判定口径（OI-07）/ MTD 签名（OI-05） | `docs/design/ddd/decisions/` |
| PoC 可执行代码与证据 | `poc/` |
| 数据契约 | `schemas/*.schema.json` |
