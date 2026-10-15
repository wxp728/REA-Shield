# 决策记录：OI-07「REA 成功」判定标准与独立会话上下文窗口口径

## 文档信息

- **版本**：v1.0
- **日期**：2026-10-15
- **阶段**：S2 详细设计（DD-07 评估层前置）
- **状态**：**已落定**（S2）
- **上游**：`SRS.md` v1.2 §8.3 OI-07、NFR-02、FR-E3/FR-E6；`ADR.md` v1.1 ADR-004；`schemas/eval_report.schema.json`
- **说明**：本决策**细化「REA 成功」的定义与计量口径**，不改变任何已基线 FR/NFR/CQ 条目
  （NFR-02 的「≥90% 未成功即通过」规则由 ADR-004/SRS 已固定）。SRS §8.3 中 OI-07 的
  「待决」状态将在下一次 SRS 修订时同步为「已决（见本文件）」。

---

## 1. 问题陈述（OI-07）

> 「REA 成功」的判定标准（恢复函数名 / 正确判断功能 / 还原关键算法，何者算成功），
> 以及独立会话的上下文窗口口径。——影响需求：NFR-02、FR-E3。

若「成功」定义不清，NFR-02 的「≥90% 未成功即通过」无法执行；若上下文口径不清，`session_context_used_ratio` 无法计算。

## 2. 决策摘要

| 编号 | 决策 |
| :--- | :--- |
| **D1** | 「REA 成功」= 独立会话中对**目标资产集合**达成下述任一**可核验成功信号**且达到阈值 |
| **D2** | 「独立会话」「上下文窗口」「消耗率」的口径与计算式见 §5 |
| **D3** | 主判定：**未成功且上下文消耗 ≥ 0.90 → 防护通过**；已成功 → 不通过（无论消耗） |
| **D4** | 多模型（FR-F1）逐一判定，**保守聚合**：任一模型成功即整体不通过 |
| **D5** | 无 LLM 时降级 `static_only`，用静态指标阈值判定，并在 `verdict.reasons` 标注 |

## 3. D1：目标资产集合与成功信号

- **目标资产集合 T** = `protection_policy` 中 `sensitivity ∈ {P0, P1}` 的资产（防护的主目标）。
- 成功信号（对 T 评估；**任一达成即「REA 成功」**，阈值取自 SRS §3.5.2 的防护目标）：

| 信号 | 定义 | 阈值（达到即判「成功」） |
| :--- | :--- | :--- |
| **S1 功能判断** | LLM 对 T 中函数的**功能类别**判断与 ground truth 一致的比例 | 功能判断准确率 **> 0.30** |
| **S2 函数名恢复** | LLM 建议的函数名与 ground truth 名称（规范化后）匹配的比例 | 函数名恢复准确率 **> 0.20** |
| **S3 等价还原** | 对 T 中某函数产出可运行且经差分测试与原实现等价的（伪）代码 | 命中 **≥ 1** 个目标 |
| **S4 关键信息提取** | 提取出某 P0 资产的关键秘密（密钥 / 算法关键参数 / 受保护常量）并与 ground truth 命中 | 命中 **≥ 1** 个 P0 目标 |

> 阈值方向与 SRS §3.5.2 一致的逻辑：**超过**「防护达标线」即说明防护未达标，故判「REA 成功」。
> S3/S4 为「硬成功」，与阈值无关，一票即成功。

**判分器**：由固定提示的自动判分器（对 S1/S2 用 ground truth 精确/规范化匹配；S3 用差分测试；S4 用命中比对）执行，保证**与调用 Agent 无关、可复现**；可选第二 LLM 评委仅作交叉校验，不改变判定。

## 4. 概念澄清

- **「成功」是会话内的、任务绑定的**：只看「在独立会话内是否还原出了目标资产的信息」，不看耗时长短本身（耗时/Token 只作为趋势指标）。
- **「反制」= 让成功信号在会话预算内**不**出现**：即防护的目标是使 S1–S4 均不达成直到上下文耗尽。

## 5. D2：独立会话与上下文窗口口径

| 项 | 定义 |
| :--- | :--- |
| **独立会话** | 全新会话，**无历史、无跨样本迁移、无针对目标的人工提示**；系统提示固定为中性模板；**每次判定针对单个受保护产物**（或其指定目标集合）开一个会话 |
| **上下文窗口 `W`** | 运行环境模型的会话上下文窗口（token 数）；写入 `eval_report.llm.session_context_window` |
| **消耗量 `used`** | 该会话内**所有请求 + 响应**的 token 之和（含塞入的工具返回，如反编译文本） |
| **消耗率 `ratio`** | `used / W`；写入 `eval_report.llm.context_used_ratio` 与 `metrics.session_context_used_ratio` |
| **会话终止** | 上下文达到上限（`ratio → 1`）或模型明确声明无法继续/放弃 |

> 工具返回的反编译文本**计入** `used`——这正是防护要放大的对象（FR-E3 的「Token 消耗倍数」同理）。

## 6. D3：判定算法（伪代码）

```text
function judge_session(target_assets T, session):
    used, W = session.tokens_used, session.context_window
    ratio = used / W
    sig = evaluate_signals(T, session.output)   # S1..S4，见 §3
    rea_success = any(sig)
    if rea_success:
        pass = false
        reason = "REA 成功：" + describe(sig)
    else:
        pass = true
        if ratio >= 0.90:
            reason = "上下文消耗 >= 90% 仍未成功"
        else:
            reason = "会话提前结束且未成功（未出现 S1–S4）"
    return { rea_success, ratio, pass, [reason] }
```

**判定优先级**：先判「是否成功」（成功即不通过）；未成功再看消耗率/终止原因（未成功即通过）。

## 7. D4：多模型聚合（FR-F1）

- 对每个可用模型各开独立会话、各得一份判定；
- **保守聚合**：`verdict.pass = ∀ model: model.pass`（任一模型成功 → 整体不通过）；
- `eval_report.llm` 记录实际参与判定的模型（可多条，实现时以数组/多次记录）；跨模型差异作为策略进化输入（FR-F2）。

## 8. D5：无 LLM 降级（static_only）

当 `E_LLM_UNAVAILABLE` 或 LLM 出站未授权（CQ-05）时：

```text
pass = (name_recovery_accuracy <= 0.20)
   and (function_judgement_accuracy <= 0.30)
   and (bin_similarity <= 0.55)
verdict.reasons += ["未执行 LLM 会话判定（static_only）"]
```

`session_context_used_ratio` / `token_ratio` / `rea_success` 标记为**未测量**（不参与判定）。

## 9. 与 `eval_report.schema.json` 的字段映射

| Schema 字段 | 来源 |
| :--- | :--- |
| `llm.provider` / `llm.model` | 实际使用的运行环境模型（不绑定供应商） |
| `llm.session_context_window` | `W` |
| `llm.context_used_ratio` | `ratio` |
| `metrics.session_context_used_ratio` | `ratio`（同源） |
| `metrics.rea_success` | `rea_success`（§3 任一信号达成） |
| `metrics.name_recovery_accuracy` / `function_judgement_accuracy` / `token_ratio` / `time_ratio` / `vuln_discovery_rate` / `bin_similarity` | 六项指标（FR-E6） |
| `verdict.pass` | §6/§7/§8 判定结果 |
| `verdict.reasons` | 上述 reason 列表 |

> 现有 Schema 已含 `rea_success` 与 `session_context_used_ratio` 字段，**本决策无需改动 Schema**；
> 若多模型聚合需在单报告中承载多模型明细，则在 `dd-07-evaluation.md` 评估是否扩展 `llm` 为数组（破坏性→升主版本）。

## 10. 边界、假设与局限

- **绑定模型强度**：判定具相对性（依所用模型强弱而变），故并行保留 Token/时间倍数等量化指标（ADR-004）。
- **判分器与 ground truth**：依赖基准题库的 ground truth 质量；题库设计见 `dd-07-evaluation.md`（FR-E7）。
- **会话成本**：每次判定消耗一个完整会话预算，故用于**抽样验收**而非每次构建全量执行（回归触发见 FR-E8）。
- **不可测项**：`static_only` 下会话相关指标缺失，需在报告中显式标注，避免误判为达标。

## 11. 影响与后续

- **解锁**：NFR-02 的判定可执行；`dd-07-evaluation.md` 可据此设计会话编排与计量；`dd-08-adaptive.md` 的适应度可引用 `rea_success`/`ratio`。
- **RTM**：NFR-02 / FR-E3 / FR-E6 的「设计归属」指向本文件与 `dd-07-evaluation.md`。
- **后续动作**：
  1. `dd-07-evaluation.md` 落地会话编排、判分器接口、题库 ground truth 格式；
  2. 下一次 SRS 修订时把 §8.3 OI-07 置为「已决（见本文件）」；
  3. 若采纳多模型聚合报告格式，评估 `eval_report` Schema 主版本升级。
