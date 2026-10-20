[English](README.md) | **简体中文**

# REA-Shield

> **哪里有矛，哪里就有盾——REA 是矛，本技能就是盾。**
>
> 也许这一天会很快到来：AI 能以极低成本开发任何软件，REA 和这个“盾”都将失去意义。但在那一天到来之前，我们始终相信并坚守一点：
>
> **作弊是不对的。**
>
> 目标：将 REA 的成本推高到高于或接近正向开发。
>
> **目前**本技能**仅在 Linux x86_64** 上提供端到端防护；其变换引擎基于 **LLVM IR**，可面向 ARM64 / Windows x64 / WASM 等目标构建（IR 级支持，端到端实测目前仅 Linux x86_64）；其它平台 / OS 会在后续版本持续增加。
>
> **支持的语言**：变换引擎是经 `clang -fpass-plugin` 加载的 LLVM pass，因此防护覆盖 **C / C++**（一等支持）以及 **Rust 的 C/FFI 部分**和 **Python C 扩展**。**Java / Android 不做 IR 变换**——改为提供**可选的反 REA 选项菜单**（J0–J8：核心逻辑上服务端、字节码混淆、加壳、字节码虚拟化、下沉 native（JNI/JNA/FFM）、GraalVM native-image、运行期对抗、密钥管理），每种附原理/优缺点/影响与获取源，**由用户选择**；见 [`docs/java-anti-rea.md`](docs/java-anti-rea.md)。**.NET / Unity 不做 IL 变换**——同样提供 **D0–D8** 菜单（含 NativeAOT 与 IL2CPP）；见 [`docs/dotnet-anti-rea.md`](docs/dotnet-anti-rea.md)。**JavaScript / TypeScript 不做源码级变换**——提供 **JS0–JS8** 菜单（打包/混淆、JS 虚拟化、WebAssembly、native 插件、分发形态加固、运行期对抗、密钥）；见 [`docs/js-anti-rea.md`](docs/js-anti-rea.md)。
>
> **反逆向技术**：控制流平坦化（CFF）、非线性 MBA、不透明谓词、函数边界扰动、数据流噪声、标识符重命名、字符串加密、代码虚拟化、白盒密码、对抗性诱导、MTD 多变体；**代价**：运行时开销（P2 ≤ 5% / P1 ≤ 15% / P0 ≤ 40%，可配置）、体积与构建时间增长、依赖较重的 LLVM 18 工具链、部分平台 / 语言尚未端到端覆盖。
>
> 本项目由 Opencode + DeepSeek V4.1 Flash Free 辅助完成。

## 实战验证（真实工程 REA 红队实测）

以下为**真实生产代码**（非玩具样例）上的端到端验证结果，已匿名化：

| 维度 | 实测内容 |
| :--- | :--- |
| 被测程序 | 约 **10 万行 C 代码**（C99）的业务模块——含 SQL 语句处理器、加解密调度器、密钥/列元数据缓存、硬件密码设备适配器、COPY 协议流式加密等敏感逻辑 |
| 平台 / 形态 | **Linux x86_64**，产物为**共享库 `.so`**（soname + 版本脚本导出收敛），被真实客户端程序动态加载 |
| 保护范围 | 8 个模块 / **59 个编译单元**，经编译器包装器做**构建注入**（用工程自身 Makefile；目标工程源码零改动，树外构建） |
| 测试方法 | baseline 与 protected 用**同一 `clang -O2`**（唯一差异是变换插件）；功能验证 = 对运行中的真实服务器执行查询；REA 攻击由**独立全新上下文的 LLM 红队会话**模拟（固定中性提示 + 二进制证据 + 固定判分器），并用 **Ghidra** 反编译交叉验证 |

防护效果（baseline → protected）：

| 信号 | 结果 |
| :--- | :--- |
| 符号表（`.symtab`）本地符号 | 2,412 → **0**（strip 生效，内部命名不可恢复） |
| 工程特征字符串 | 4,295 → **87**（**-98%**） |
| 整库指令数 | 22.8 万 → 123 万（**5.4×**；热点函数最高 **13.2×**） |
| Ghidra 反编译核心加解密编排函数 | baseline 输出 **778 行可读伪代码** → protected **反编译失败**（平坦化 + 不透明谓词 + 虚拟化叠加） |
| 独立 LLM 红队 · 函数名恢复 | **0.00**（会话可见符号数为 0）；只能从残余公共 API 名猜测功能**类别** |
| 功能回归 | **无**——对真实服务器输出逐字节一致 |

**结论**：源码级泄漏（命名 / 控制流 / 内嵌常量）被阻断；恢复成本从 baseline 的约半天抬高到专家数天起步。唯一残留的静态线索是**公共 API 导出名**——那是库的对外契约，不能也不应隐藏。与本项目定位一致：**抬高成本、而非"不可破"**。完整记录：[`docs/release/s7-field-report.md`](docs/release/s7-field-report.md)。

> 红队会话与开发上下文完全隔离（CQ-05 出站控制）。运行期动态调试不在静态混淆的防护边界内——这是所有混淆工具的共同边界，如实说明。

## 快速入口（使用者 / 上层 Agent）

> 只想**用**它、不想读全部开发文档的，从这里开始：

| 我想…… | 看这里 |
| :--- | :--- |
| 让 AI / Agent 学会用这个技能 | **[`SKILL.md`](SKILL.md)** + [`skill.json`](skill.json)（机器可读清单） |
| 安装、构建、环境变量、Docker | [`docs/INSTALL.md`](docs/INSTALL.md) |
| 最小安装、按需获取组件（分级） | [`docs/PROVISIONING.md`](docs/PROVISIONING.md) |
| 把 MCP Server 接进我的客户端 | [`docs/mcp-clients.md`](docs/mcp-clients.md) |
| 跑一个端到端示例 | [`examples/quickstart/`](examples/quickstart/) |
| 加固 **Java / Android** 项目（选项目录 J0–J8） | [`docs/java-anti-rea.md`](docs/java-anti-rea.md) |
| 加固 **.NET / Unity** 项目（选项目录 D0–D8） | [`docs/dotnet-anti-rea.md`](docs/dotnet-anti-rea.md) |
| 加固 **JavaScript / TypeScript** 项目（选项目录 JS0–JS8） | [`docs/js-anti-rea.md`](docs/js-anti-rea.md) |
| 出问题了 | [`docs/FAQ.md`](docs/FAQ.md)、[`docs/troubleshooting.md`](docs/troubleshooting.md) |

```bash
pip install -r requirements.txt   # 最小（T0）：jsonschema + PyYAML；按需：requirements-optional.txt
anti-rea doctor                   # 环境自检（按分级分组：缺什么、何时需要、怎么修）
make build                        # 构建 LLVM 变换插件（T1，仅 protect 需要）
docker build -t anti-rea:1.0.0 .  # 或：用钉死的容器镜像（较重路径），免手工装 LLVM18
```

## 仓库现状

本仓库处于**编码实现阶段**（S3 迭代 R1/R2/R3 全部完成，M4/M5 已批准）。

| 阶段 | 状态 |
| :--- | :--- |
| S0 立项与需求分析 | ✅ 完成（M0 需求基线已批准，tag `m0-baseline`） |
| S1 概要设计 | ✅ 完成（设计交付物 + **4 项 PoC 全部通过**，tag `m1-architecture`） |
| S2 详细设计 | ✅ 完成（DD-01…DD-10 + 构建集成，tag `m2-design`） |
| S3 编码实现 · R1 | ✅ 完成（脚手架 + CFF/MBA/谓词 + Scanner/Strategy + 端到端流水线，tag `m3-r1`） |
| S3 编码实现 · R2 | ✅ 完成（虚拟化/白盒/对抗诱导/函数扰动/噪声/SPI/构建集成，tag `m4-r2`） |
| S3 编码实现 · R3 | ✅ 完成（评估验证/自适应进化/MCP Server/报告产物，tag `m5-frozen`） |
| S4 系统集成与验证 | ✅ 完成（差分 fuzz 10⁵ / 性能 / 对抗（内置+独立）/ 可复现 / 稳健 / 兼容 / SBOM；报告 `docs/release/`） |
| S5 Beta 试点 | ✅ 完成（3 试点 C/C++/Python-ext 独立闭环；改进/合规/发布清单/安装指南） |
| S6 正式发布 v1.0 | ✅ 完成（v1.0.0：技能入口/自检/容器/MCP 配置/示例/发布打包；tag `v1.0.0`） |
| S7 持续改进 · 第一轮 | ✅ 完成（约 10 万行 C 的真实 `.so` 工程实战红队——源码级泄漏被阻断；NFR-02 Token 倍数子项废弃，见 `docs/release/s7-field-report.md`） |

> **接手请先读 [`docs/STATUS.md`](docs/STATUS.md)**（项目状态与交接说明），再按其中的「下一步」继续。
> **使用者请先读 [`SKILL.md`](SKILL.md)**（技能入口）与 [`docs/INSTALL.md`](docs/INSTALL.md)。

## 目录结构

```text
REA-Shield/
├── SKILL.md                  # ★ 技能入口（AI/使用者从这里开始）
├── skill.json                # ★ 机器可读的 skill 清单（工具/环境/平台）
├── README.md / README.zh-CN.md  # 项目总览（英/中）
├── LICENSE                   # MIT
├── CHANGELOG.md              # 版本变更记录
├── Dockerfile                # 钉死的容器镜像（LLVM18 + Python3.11 + 插件）
├── .agents/skills/anti-rea/  # 技能清单落点（指向根 SKILL.md）
├── examples/quickstart/      # 端到端可运行示例
├── plan/                     # 方案与项目计划
│   ├── anti-rea-plan.md              # 原始技术方案（能力模块导向）
│   └── anti-rea-project-plan.md      # 全生命周期项目计划（阶段/里程碑/出口准则）
├── docs/
│   ├── STATUS.md             # ★ 项目状态与交接（新会话入口）
│   ├── INSTALL.md            # 安装/构建/环境变量/Docker
│   ├── mcp-clients.md        # MCP 客户端配置（可直接粘贴）
│   ├── FAQ.md、troubleshooting.md    # 常见问题与排障
│   ├── requirements/         # S0 交付物
│   │   ├── SRS.md                    # 需求规格（47 FR + 11 NFR + 5 CQ）
│   │   ├── use-cases.md              # 用例文档
│   │   ├── rtm.md                    # 需求追踪矩阵
│   │   └── compliance.md             # 合规与边界需求
│   └── design/               # S1/S2 交付物
│       ├── HLD.md                    # 概要设计说明书（S1）
│       ├── interfaces.md             # 接口契约（模块/MCP/CLI/SPI/错误码）
│       ├── ADR.md                    # 架构决策记录（ADR-001…007）
│       ├── poc-plan.md              # 技术选型 PoC 方案（PoC-1…4）
│       └── ddd/                      # S2 详细设计
│           ├── README.md                    # 索引 / 任务追踪 / M2 出口映射
│           ├── e2e-scenario.md              # 端到端 Agent 调用场景（主线）
│           ├── dd-01-scanner.md … dd-08-adaptive.md  # 各模块详细设计
│           ├── dd-09-test-plan.md           # 测试计划（覆盖全部需求）
│           ├── dd-build-integration.md      # 构建集成与产物管理
│           ├── dd-10-review.md              # 详细设计评审（M2 门）
│           └── decisions/                   # OI-05 / OI-07 决策记录
├── schemas/                  # 数据契约（JSON Schema, Draft 2020-12）
│   ├── asset_manifest.schema.json
│   ├── protection_policy.schema.json
│   ├── verification_report.schema.json
│   ├── eval_report.schema.json
│   └── benchmark.schema.json
├── engine/                   # S3 变换引擎（LLVM Pass 插件）
│   ├── CMakeLists.txt
│   ├── README.md
│   └── passes/anti_rea_passes.cpp    # CFF / MBA / 不透明谓词 / 白名单 / 虚拟化 / 锚点移除
├── core/                     # S3 编排核心（Python）
│   ├── scanner/              #   输入分析层（Scanner v0.1）
│   ├── strategy/             #   策略决策层（Strategy Engine v0.1）
│   ├── evaluate/             #   评估验证层（差分验证 + 攻击模拟 + 指标/时间序列/回归）
│   ├── adaptive/             #   自适应策略引擎（DEAP 进化 + 弱点调整 + 知识库）
│   ├── mcp/                  #   MCP Server（stdio JSON-RPC 2.0，7 工具）
│   ├── verify/               #   S4 系统验证（差分 fuzz/性能/独立交叉/可复现/稳健/兼容）
│   ├── transform.py          #   变换执行（调用 engine 插件）
│   ├── toolchain.py          #   工具链探测与 doctor 自检（去硬编码路径）
│   ├── platform_info.py      #   平台/目标环境探测
│   ├── report.py             #   报告与产物管理（统一目录/元数据/变更对比）
│   ├── common.py             #   Schema 校验 / run_id / IO
│   └── cli.py                #   CLI 入口（doctor/scan/plan/protect/verify/report/attack_sim/regress/diff/evolve）
├── tools/                    # S4/S5/S6 工具（run_s4.py / run_s5.py / sbom.py / release.py / ghidra_functions.py）
├── pilots/                   # S5 Beta 试点工程（crypto-lib / protocol-svc / python-ext）
├── docs/release/             # S4/S5/S6 验证与发布产物（STR/性能/对抗/兼容/SBOM/试点/发布说明）
├── policies/                 # 策略模板库 + 匹配规则
├── integrations/             # 构建集成（CMake/Cargo/npm/Python/MCP，R2+）
├── plugins/                  # 变换插件 SPI（R2+）
├── benchmarks/               # 攻击模拟基准题库（R3）
├── tests/                    # 单测 / 集成测试 + 样例
├── ci/ci.sh                  # CI 门禁
├── Makefile                  # build / test / e2e / ci
└── poc/                      # S1 技术选型 PoC（可执行代码与证据）
    ├── poc1-llvm-pass/       #   LLVM Pass：控制流平坦化（CFF）
    ├── poc2-ghidra-headless/ #   Ghidra Headless（PyGhidra）批量反编译
    ├── poc3-deap/            #   DEAP 策略进化原型
    ├── poc4-wbc/             #   白盒查找表编码（AES）
    └── setup_env.sh          #   环境安装记录脚本
```

## 快速导航

| 我想…… | 看这里 |
| :--- | :--- |
| **把技能交给一个不懂本项目的 AI/人** | **[`SKILL.md`](SKILL.md)** + [`docs/INSTALL.md`](docs/INSTALL.md) + [`docs/mcp-clients.md`](docs/mcp-clients.md) |
| 了解这个项目要做什么 | `plan/anti-rea-plan.md` |
| 了解开发流程与里程碑 | `plan/anti-rea-project-plan.md` |
| 知道当前进度 / 如何接手 | `docs/STATUS.md` |
| 查需求与验收标准 | `docs/requirements/SRS.md` |
| 查架构与接口 | `docs/design/HLD.md`、`docs/design/interfaces.md` |
| 查技术取舍理由 | `docs/design/ADR.md` |
| 看 PoC 方案与结论 | `docs/design/poc-plan.md`、`poc/` |
| 看详细设计 / 端到端场景 | `docs/design/ddd/README.md`、`docs/design/ddd/e2e-scenario.md` |
| 构建与运行（R1） | `engine/README.md`、`Makefile`（`make build/test/e2e/ci`） |
| 继续做去风险验证 | `docs/design/poc-plan.md` |

## 约定

- 需求编号：`FR-<层><序号>` / `NFR-<序号>` / `CQ-<序号>`；优先级 MoSCoW。
- 所有跨模块数据必须通过 `schemas/` 校验（fail-fast）。
- 行尾统一 LF（见 `.gitattributes`）。
- 文档变更需记录版本与变更历史。
