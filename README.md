# Anti-REA Skill

> 一个 AI Agent 可调用的**代码工程反逆向加固技能**：对源码 / 二进制施加多层级防护变换，把 AI 驱动逆向工具（REA 类）的**逆向成本推高到高于逆向收益**——目标不是「不可逆向」，而是「不值得逆向」。

## 仓库现状

本仓库当前处于**规划与设计阶段**（尚未开始编码）。

| 阶段 | 状态 |
| :--- | :--- |
| S0 立项与需求分析 | ✅ 完成（M0 需求基线已批准，tag `m0-baseline`） |
| S1 概要设计 | ✅ 完成（设计交付物 + **4 项 PoC 全部通过**，M1 架构门禁通过，tag `m1-architecture`） |
| S2 详细设计 | ✅ 完成（DD-01…DD-10 + 构建集成；评审建议通过 **M2**，待人工批准 tag `m2-design`） |
| S3 及以后 | ⬜ 未开始 |

> **接手请先读 [`docs/STATUS.md`](docs/STATUS.md)**（项目状态与交接说明），再按其中的「下一步」继续。

## 目录结构

```text
anti-rea/
├── plan/                     # 方案与项目计划
│   ├── anti-rea-plan.md              # 原始技术方案（能力模块导向）
│   └── anti-rea-project-plan.md      # 全生命周期项目计划（阶段/里程碑/出口准则）
├── docs/
│   ├── STATUS.md             # ★ 项目状态与交接（新会话入口）
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
│   └── eval_report.schema.json
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
| 了解这个项目要做什么 | `plan/anti-rea-plan.md` |
| 了解开发流程与里程碑 | `plan/anti-rea-project-plan.md` |
| 知道当前进度 / 如何接手 | `docs/STATUS.md` |
| 查需求与验收标准 | `docs/requirements/SRS.md` |
| 查架构与接口 | `docs/design/HLD.md`、`docs/design/interfaces.md` |
| 查技术取舍理由 | `docs/design/ADR.md` |
| 看 PoC 方案与结论 | `docs/design/poc-plan.md`、`poc/` |
| 看详细设计 / 端到端场景 | `docs/design/ddd/README.md`、`docs/design/ddd/e2e-scenario.md` |
| 继续做去风险验证 | `docs/design/poc-plan.md` |

## 约定

- 需求编号：`FR-<层><序号>` / `NFR-<序号>` / `CQ-<序号>`；优先级 MoSCoW。
- 所有跨模块数据必须通过 `schemas/` 校验（fail-fast）。
- 行尾统一 LF（见 `.gitattributes`）。
- 文档变更需记录版本与变更历史。
