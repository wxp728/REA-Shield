# Anti-REA Skill 详细设计（DDD）

## 文档信息

- **文档版本**：v1.0
- **创建日期**：2026-10-15
- **阶段**：S2 详细设计（任务 DD-01…DD-10）
- **上游依据**：`HLD.md` v1.1（M1 基线）、`interfaces.md` v1.1、`ADR.md` v1.1、`docs/requirements/SRS.md` v1.2（M0 基线）
- **状态**：进行中
- **目标**：把每个模块设计到「换一个执行者也能照着实现」的算法级，并产出与设计同步、覆盖全部 FR 的测试计划（M2 设计基线）。

---

## 1. 交付物索引

| 文件 | 内容 | 对应任务 | 状态 |
| :--- | :--- | :--- | :--- |
| `e2e-scenario.md` | **主线**：AI Agent 经 MCP 调用 skill 的端到端场景（集成视图） | DD-10 交叉 / 全局 | ✅ 初稿 |
| `decisions/OI-07-rea-success-criteria.md` | 待决问题 OI-07 落定：「REA 成功」判定 + 独立会话上下文窗口口径 | DD-07 | ✅ 初稿 |
| `dd-01-scanner.md` | 资产扫描详细设计 | DD-01 | ✅ 初稿 |
| `dd-02-strategy.md` | 策略引擎详细设计 | DD-02 | ✅ 初稿 |
| `dd-03-llvm-transforms.md` | LLVM 变换详细设计 | DD-03 | ✅ 初稿 |
| `dd-04-virtualization.md` | 虚拟化引擎与 ISA 规范 | DD-04 | ✅ 初稿 |
| `dd-05-adversarial.md` | 对抗诱导详细设计 | DD-05 | ⬜ 待产出 |
| `dd-06-wbc.md` | 白盒密码详细设计 | DD-06 | ⬜ 待产出 |
| `dd-07-evaluation.md` | 评估层详细设计 | DD-07 | ⬜ 待产出 |
| `dd-08-adaptive.md` | 自适应引擎详细设计 | DD-08 | ⬜ 待产出 |
| `dd-09-test-plan.md` | 测试计划（覆盖全部 FR） | DD-09 | ⬜ 待产出 |
| `dd-10-review.md` | 详细设计评审记录 | DD-10 | ⬜ 待产出 |

## 2. 编写顺序与依赖

```text
e2e-scenario（集成主线，先行）
   └─ OI-07（判定口径，DD-07 前置）
        ├─ dd-01 scanner ─┐
        ├─ dd-02 strategy ┤
        ├─ dd-03 llvm     ├─ 各模块详细设计（相互以 interfaces.md 契约为边界）
        ├─ dd-04 vm       │
        ├─ dd-05 adv      │
        ├─ dd-06 wbc      │
        └─ dd-07 eval ────┘
             └─ dd-08 adaptive（依赖 eval 的反馈）
   └─ dd-09 test-plan（随各模块同步编写，最后收口）
        └─ dd-10 review
```

**原则**：`e2e-scenario.md` 是贯穿性「验收主线」，各模块详细设计必须能支撑它跑通；任一处设计若与场景冲突，以「可执行、可验证」为准。

## 3. M2 出口准则映射（对照 `plan/anti-rea-project-plan.md §4.2`）

| 出口准则 | 落点 | 状态 |
| :--- | :--- | :--- |
| 每模块设计达「换人可实现」 | 各 `dd-*.md` 的算法伪代码 + 数据结构 + 接口落点 | ⬜ |
| 关键算法有伪代码 + 复杂度 + 正确性论证思路 | 各 `dd-*.md` 对应小节 | ⬜ |
| 测试计划覆盖 100% FR（RTM「测试」列填实） | `dd-09-test-plan.md` + 更新 `docs/requirements/rtm.md` | ⬜ |
| 详细设计评审通过，无阻塞未决问题 | `dd-10-review.md` | ⬜ |

## 4. 与 S3 的衔接

S2 全部产出后：更新 `docs/STATUS.md`（M2 ✅，打 tag `m2-design`）→ 进入 S3 编码迭代（R1 基础骨架与基础变换）。
