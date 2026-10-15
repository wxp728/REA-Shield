# 项目状态与交接（Handoff）

> **新会话请从这里开始。** 本文件描述 Anti-REA Skill 项目的当前进度、已完成的交付物、已决 / 待决事项，以及**下一步该做什么**。

## 0. 快照

| 项 | 值 |
| :--- | :--- |
| 日期 | 2026-10-16 |
| 分支 | `master` |
| 基线 tag | `m0-baseline`（M0 需求基线）、`m1-architecture`（M1 架构基线）、`m2-design`（M2 设计基线）、`m3-r1`（M3 R1）、`m4-r2`（M4 R2）、`m5-frozen`（M5 R3） |
| 远端 | `git@gitee.com:wxp728/anti-rea.git` |
| 最近提交 | 见 `git log -1`（本文件随该提交一并推送） |
| 工作区 | 干净（无未提交改动） |

## 1. 一句话现状

**S4 系统集成与验证（M6 质量门）已完成：** 依 `plan §6.1` 验证类型矩阵实现并实测通过——
**差分 fuzz 10⁵ 随机输入零差异**（NFR-03）、**性能开销落在 NFR-01 预算内**、
**对抗效果内置判定通过且独立工具（objdump/Ghidra）交叉验证不矛盾**、
**同输入同种子产物逐位一致**（NFR-04/08）、**异常输入受控 + 超时受控 + 大工程可扩展**（NFR-07）、
**兼容性矩阵**（linux-x86_64 五组合实测 + aarch64/riscv64/wasm32/windows-gnu IR 层探针）、
**安全自检 SBOM**（NFR-09/CQ-01）。报告见 `docs/release/`（STR / 性能基线 / 对抗评估 /
兼容性矩阵 / 文档验证 / SBOM / 缺陷清单）。**S3（R1/R2/R3）与 S4 全部完成，CI 全绿。**
下一步：按 `plan §7` 进入 **S5（Beta 试点）**。

> **未量化项**（留待 S5）：NFR-02 的 **Token 消耗倍数 ≥ 100x** 与**外部第三方红队**结论
> 需真实 LLM 会话（CQ-05 出站控制 + 多模型）；无 LLM 时评估降级 `static_only`（OI-07 §D5），
> 以可复现的**静态代理指标 + 独立工具交叉验证**作为替代门禁。

## 2. 里程碑状态（对照 `plan/anti-rea-project-plan.md` §1.2）

| 里程碑 | 状态 | 说明 |
| :--- | :--- | :--- |
| **M0 需求基线** | ✅ 已通过 | tag `m0-baseline`；47 FR + 11 NFR + 5 CQ 已基线 |
| **M1 架构基线** | ✅ 已通过 | HLD / 接口 / ADR / Schema 已产出；**PoC-1…4 全部通过**；tag `m1-architecture` |
| **M2 设计基线** | ✅ 已通过 | tag `m2-design`；S2 交付物完成（`docs/design/ddd/`），评审见 `dd-10-review.md` |
| **M3 编码 R1** | ✅ 已通过 | 脚手架 + Scanner/Strategy MVP + CFF/MBA/谓词 + 端到端流水线；tag `m3-r1` |
| **M4 编码 R2** | ✅ 已通过 | 虚拟化/白盒/对抗/函数扰动/数据流噪声/SPI/构建集成；tag `m4-r2` |
| **M5 编码 R3** | ✅ 已完成 | 评估/进化/MCP/产物管理；`make ci` 全绿；tag `m5-frozen` |
| **M6 验证 S4** | ✅ 已完成 | 差分 fuzz/性能/对抗/可复现/稳健/兼容/安全/文档验证全绿；报告 `docs/release/` |
| M7 试点 S5 | ⬜ 未开始 | 真实工程灰度试用 + 发布准备 |
| M8 发布 S6 | ⬜ 未开始 | v1.0 制品发布与支持渠道 |

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
| S3·R1 | LLVM 变换插件（CFF/MBA/谓词 + 白名单） | `engine/`（`passes/anti_rea_passes.cpp`） | v0.1 |
| S3·R1 | Python 核心：Scanner/Strategy/Transform/Evaluate + CLI | `core/` | v0.1 |
| S3·R1 | 策略模板库与匹配规则（YAML） | `policies/strategy_templates.yaml`、`policies/match_rules.yaml` | v1 |
| S3·R1 | 单元/集成测试 + 端到端样例 | `tests/`（`test_scanner.py`、`test_strategy.py`、`test_engine_e2e.py`、`samples/hello.c`） | — |
| S3·R1 | 构建与 CI（CMake/Makefile/ci.sh/pre-commit） | `engine/CMakeLists.txt`、`Makefile`、`ci/ci.sh`、`.pre-commit-config.yaml` | — |
| S3·R2 | 代码虚拟化引擎（VM ISA + 解释器 + lowering） | `engine/vm/vm_isa.h`、`engine/vm/vm_interp.c`、`engine/passes/anti_rea_passes.cpp`（`applyVM`） | v0.1 |
| S3·R2 | 白盒密码（AES-128 查找表编码 + 自检 + 无明文密钥校验） | `core/wbc/wbc.py` | v0.1 |
| S3·R2 | 对抗诱导生成器（功能保持变体） | `core/adversarial/generator.py` | v0.1 |
| S3·R2 | 函数边界扰动（FR-C4）+ 数据流噪声（FR-C5） | `engine/passes/anti_rea_passes.cpp`（`applyFuncSplit`/`applyNoise`） | v0.1 |
| S3·R2 | 变换插件 SPI（FR-C11）+ 示例插件 | `engine/spi/transform_plugin.h`、`plugins/example-transform/` | v1 |
| S3·R2 | 构建集成插件（CMake/npm/Python 已测；Cargo 待 rust） | `integrations/`（`anti-rea` 驱动 + 四类插件 + 样例） | v0.1 |
| S3·R2 | Scanner 轻量数据流分级（FR-A4 增强） | `core/scanner/scanner.py`（`secret_schedule` → P0） | — |
| S3·R3 | 评估验证层：攻击模拟（静态/动态/跨版本）+ 六项指标 + 时间序列 + 判定 | `core/evaluate/{attack_sim,metrics,static_features,llm,timeseries,regression}.py` | v0.1 |
| S3·R3 | 攻击模拟基准题库 + Schema | `schemas/benchmark.schema.json`、`benchmarks/*.yaml` | v1 |
| S3·R3 | 自适应策略引擎：遗传进化 + 弱点调整 + 策略知识库迁移 | `core/adaptive/{engine,genome,weakness,knowledge}.py` | v0.1 |
| S3·R3 | MCP Server（stdio JSON-RPC 2.0，7 工具） | `core/mcp/server.py`（+ `anti-rea-mcp` 脚本） | v0.1 |
| S3·R3 | 报告与产物管理：统一目录 + 可复现元数据 + 变更对比 | `core/report.py`、CLI `report/diff/attack_sim/regress/evolve` | v0.1 |
| S3·R3 | R3 自动化用例 | `tests/{test_evaluation,test_adaptive,test_mcp}.py` | — |
| S4 | 验证工具集：差分 fuzz/性能/独立交叉/可复现/稳健/兼容 | `core/verify/{differential,overhead,independent,reproducibility,robustness,matrix}.py` | v0.1 |
| S4 | S4 运行器 + SBOM/安全自检 | `tools/run_s4.py`、`tools/sbom.py`、`tools/ghidra_functions.py` | v0.1 |
| S4 | S4 报告与数据（STR/性能/对抗/兼容/文档验证/SBOM/缺陷） | `docs/release/*` | v1.0 |
| S4 | S4 自动化用例 | `tests/test_verify_s4.py` | — |
| S2+ | REA 对手分析（针对性设计输入，非需求） | `docs/analysis/rea-threat-analysis.md` | v0.1 |

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

## 6. 当前阶段：S3 编码实现 · 迭代 R1（完成，待 M3 批准）

**M2 已通过**（tag `m2-design`）。R1 交付物（对照 `plan §5.2`）：

| 任务 | 交付物 | 证据 |
| :--- | :--- | :--- |
| 项目脚手架 + CI | 可构建骨架 + `ci/ci.sh` | `make build` / `bash ci/ci.sh` 全绿 |
| 资产扫描 MVP | Scanner v0.1（`core/scanner/`） | 对 `tests/samples` 产出合规 `asset_manifest.json`（FR-A1/A2/A3/A5/A6） |
| 策略引擎 MVP | Strategy Engine v0.1（`core/strategy/` + `policies/`） | 产出合规 `protection_policy.yaml`（FR-B1/B2/B6） |
| LLVM CFF + MBA + 谓词 | Transform Engine v0.1（`engine/`） | 三种变换生效且功能保持（FR-C1/C2/C3） |
| 选择性变换 | 白名单（函数级） | 名单外函数零变换（FR-C6） |
| 最小端到端流水线 | `core/cli.py` | `scan→plan→protect→verify` 一条命令跑通 |

**运行方式**：

```sh
make build        # 构建 engine/build/anti_rea_passes.so
make test         # 单元 + 集成测试（7 用例）
make e2e          # scan → plan → protect → verify
make ci           # 完整 CI 门禁
```

**R1 出口准则核对**：对简单 C 工程（`tests/samples/hello.c`）施加 CFF+MBA 后功能测试通过 ✅；`asset_manifest` / `protection_policy` 均过 Schema ✅；端到端一条命令跑通 ✅。

> **M3 已通过**（tag `m3-r1`）。

### 6.1 迭代 R2（核心防护能力，完成、待 M4 批准）

对照 `plan §5.3`：

| 任务 | 交付物 | 证据 |
| :--- | :--- | :--- |
| 代码虚拟化引擎 | VMP Engine v0.1（`engine/vm/`） | `test_vm_virtualization_pipeline`：虚拟化后功能与基线一致（FR-C7/C8） |
| 白盒密码模块 | White-Box Crypto v0.1（`core/wbc/`） | `test_wbc.py`：加解密自洽、密钥不以明文常量驻留（FR-C10） |
| 对抗性诱导生成器 | Adversarial Generator v0.1（`core/adversarial/`） | `test_adversarial.py`：变体功能保持（FR-C9） |
| 函数扰动 + 数据流噪声 | 补充变换 Pass（FR-C4/C5） | `test_func_split_and_noise`：语义不变 + IR 指标变化 |
| 构建集成插件 | CMake/Cargo/npm/Python（`integrations/`） | `test_integrations.py`：CMake/npm/Python 实测通过，Cargo 因无 rust 跳过（FR-D1…D5） |
| 变换插件 SPI | `engine/spi/` + 示例插件 | `test_spi.py`：示例变换免改核心引擎；版本不兼容拒载（FR-C11） |
| 锚点移除（字符串加密 + 标识符重命名） | `string-encrypt` / `ident-rename` 模块级 Pass | `test_anchor_removal`：明文串/符号消失且功能保持（dd-03 §7） |

**R2 出口准则核对**：对 P0 资产产出「虚拟化 + 白盒 + 对抗诱导」组合防护产物，功能测试通过 ✅
（`test_r2_combo_protection`）；插件 SPI 与构建集成样例工程均产出保护产物 ✅。

**运行方式**：`make build` / `make test` / `make e2e` / `make ci`（见 Makefile）。

**针对性设计输入**：`docs/analysis/rea-threat-analysis.md` 分析了对标 AI 逆向工具 REA
（`github.com/morluto/rea` v6.5.0）的能力缺口——REA **无脱混淆能力**且证据模型 fail-closed，
故优先补「锚点移除」（字符串加密 / 标识符重命名）——**已实现**。

> **下一步**：按 `plan §5.4` 进入 **R3**（评估/进化/MCP Server），或先做 M4 门评审。

> **M4 已通过**（tag `m4-r2`）。

### 6.2 迭代 R3（评估 / 进化 / MCP / 产物管理，已完成）

对照 `plan §5.4`：

| 任务 | 交付物 | 证据 |
| :--- | :--- | :--- |
| 评估框架 v0.1 | `core/evaluate/`（静态特征 + 六项指标 + 时间序列） | `test_evaluation.py`：指标计算、`static_only` 判定、基线产物判不通过（FR-E1/E2/E6） |
| 攻击模拟 | `attack_sim`（静态 / 动态 / 跨版本）+ 基准题库 | 端到端 `eval_report` 过 Schema；`mode=all` 时无工具/无上一版本自动降级（FR-E3/E4/E5） |
| 保护报告 | `core/report.py`（json / md / html 一致） | `test_report_three_formats_and_diff`（FR-E7） |
| 回归检测 | `core/evaluate/regression.py` + CLI `regress` | 首跑无历史不退化；`compare` 检测指标退化与未达标（FR-E8） |
| 自适应引擎 v0.1 | `core/adaptive/`（DEAP 进化 + 弱点调整 + 知识库） | `test_adaptive.py`：进化不劣化、同 seed 确定、弱点一键调整、迁移推荐（FR-F1…F4） |
| MCP Server | `core/mcp/server.py`（7 工具）+ `anti-rea-mcp` | `test_mcp.py`：协议 + Agent 全流程 `scan→…→evolve`（FR-D6） |
| 报告与产物 | 统一目录 / 可复现元数据 / 变更对比 | `test_evaluation.py`：目录定位、指纹/策略哈希、`diff`（FR-G1…G3） |

**R3 出口准则核对（`plan §5.4`）**：全部 FR 实现且有自动化用例 ✅；`strings` 无关的静态攻击模拟 ✅
（仅依赖 `nm`/`strings` 无关的结构特征 + ground truth）；**Token 消耗倍数 ≥ 100x** ⏳
需真实 LLM 会话（CQ-05），当前以 `static_only` 可复现代理指标替代——见 `docs/requirements/rtm.md §1.2`。

**运行方式**：`make build` / `make test` / `make e2e` / `make ci`。
攻击模拟与报告（示例）：

```sh
python -m core.cli attack_sim build/run --benchmark benchmarks/bench-crypto-001.yaml --db build/metrics.db
python -m core.cli regress    build/run --benchmark benchmarks/bench-crypto-001.yaml --db build/metrics.db
python -m core.cli report     build/run --format all
python -m core.cli diff       build/run.A build/run.B
python -m core.cli evolve     build/run/asset_manifest.json -o build/evolved --kb build/kb.json
python -m core.mcp            # 或 anti-rea-mcp（stdio MCP Server）
```

> **下一步**：按 `plan §6` 进入 **S4（M6 验证）**。

### 6.3 阶段 S4：系统集成与验证（M6 质量门，已完成）

对照 `plan §6.1` 验证类型矩阵，运行器 `python tools/run_s4.py`（完整 `--n 100000`）：

| 验证类型 | 结果 | 证据 / 实现 |
| :--- | :--- | :--- |
| 端到端集成 | 通过 | `tests/test_engine_e2e.py`、`test_mcp.py` |
| 回归测试（功能保持） | 通过 | `verify()` 差分 + WBC 自洽 + 对抗变体等价 |
| **差分 fuzz** | **10⁵ 输入零差异** | `core/verify/differential.py`（批式投喂 + 定位） |
| 性能基准 | 最差开销 0.042 ≤ 预算 | `core/verify/overhead.py`（NFR-01：P0≤40%/P1≤15%/P2≤5%） |
| 对抗效果（内置） | 判定通过（相似度 0.40 ≤ 0.55） | `attack_sim` + `eval_report.json` |
| 对抗效果（独立） | objdump/Ghidra 交叉验证**不矛盾** | `core/verify/independent.py`、`tools/ghidra_functions.py` |
| 兼容性 | linux-x86_64 五组合 + 4 目标 IR 探针 | `core/verify/matrix.py` |
| 稳健性 | 异常输入受控 / 超时受控 / 大工程可扩展 | `core/verify/robustness.py` |
| 可复现性 | 同输入同种子**产物逐位一致** | `core/verify/reproducibility.py` |
| 安全自检 | SBOM 齐全、无未授权组件 | `tools/sbom.py`、`docs/release/sbom.json` |
| 文档验证 | 6 条文档命令全部通过 | `tools/run_s4.py::doc_verification` |

**M6 出口准则核对**：功能全绿、差分 fuzz 10⁵ 无差异、性能在预算内、对抗内置达标且独立验证不矛盾、
无未修复 P0/P1、SBOM 完整、文档可复现 —— 除「Token 消耗倍数 ≥ 100x」「外部第三方红队」两项
（需真实 LLM，CQ-05）外**全部达成**；报告见 `docs/release/`。

> **下一步**：按 `plan §7` 进入 **S5（Beta 试点）**。

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
> M0–M6 均已通过（tag `m0-baseline` / `m1-architecture` / `m2-design` / `m3-r1` / `m4-r2` / `m5-frozen`），
> **S3（R1/R2/R3）与 S4（系统验证，M6）已完成**（`make ci` 全绿；S4 报告见 `docs/release/`）。
> 请按 `plan/anti-rea-project-plan.md §7` 进入 **S5（Beta 试点）**。
> 注意：需求已基线（tag `m0-baseline`），变更须走变更流程；所有跨模块数据须过 `schemas/` 校验；
> NFR-02 的 Token 倍数 ≥ 100x 与外部第三方红队结论需真实 LLM（CQ-05），列为 S5 行动项。

**接手顺序**：`README.md` → `docs/STATUS.md`（本文）→ `plan/anti-rea-project-plan.md`（§5 S3）→ `engine/README.md` → `core/cli.py`。

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
| LLVM 变换插件（CFF/MBA/谓词/虚拟化/扰动/噪声 + 白名单） | `engine/passes/anti_rea_passes.cpp`、`engine/vm/`、`engine/README.md` |
| 变换插件 SPI 契约 + 示例插件 | `engine/spi/transform_plugin.h`、`plugins/` |
| 构建集成（CMake/Cargo/npm/Python） | `integrations/` |
| REA 对手分析（针对性设计输入） | `docs/analysis/rea-threat-analysis.md` |
| Python 核心（Scanner/Strategy/Transform/Evaluate） | `core/` |
| CLI 入口 | `core/cli.py` |
| 策略模板库 / 匹配规则 | `policies/` |
| 构建 / CI / 测试 | `Makefile`、`ci/ci.sh`、`tests/` |
| PoC 可执行代码与证据 | `poc/` |
| 数据契约 | `schemas/*.schema.json` |
