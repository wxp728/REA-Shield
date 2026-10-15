# Anti-REA 系统测试报告（STR）

> 由 `tools/run_s4.py` 生成；对应 `plan §6.3` M6 质量门。

## 1. 验证类型矩阵结果

| 验证类型 | 结果 | 证据 |
| :--- | :--- | :--- |
| 端到端集成 | 通过 | `tests/test_engine_e2e.py`、`test_mcp.py` |
| 差分 fuzz | 通过（100000 输入，0 差异） | `core/verify/differential.py` |
| 性能基准 | 通过（最差开销 0.0421） | `core/verify/overhead.py` |
| 对抗效果（内置） | 判定 通过 | `eval_report.json` |
| 对抗效果（独立工具） | 一致 | `core/verify/independent.py` |
| 可复现性 | 逐位一致 | `core/verify/reproducibility.py` |
| 稳健性（异常输入） | 受控失败 | `core/verify/robustness.py` |
| 稳健性（大工程） | 通过（200 文件，0.02s） | `robustness.large_project` |
| 兼容性 | 9 组合实测 | `core/verify/matrix.py` |
| 安全自检 | 见 `security-selfcheck.md` | `tools/sbom.py` |

## 2. 差分 fuzz（NFR-03 / FR-E1）

- 输入数：100000；差异：0；批次：64；种子：1
- 结论：**无行为差异，满足 M6 门槛**

## 3. 性能基线（NFR-01 / FR-E2）

| 资产 | 敏感度 | 基线(ms) | 保护(ms) | 开销 | 预算 | 达标 |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| p0_secret.c | P0 | 0.488 | 0.503 | 0.0310 | 0.40 | 是 |
| fuzz_target.c | P1 | 0.755 | 0.787 | 0.0421 | 0.15 | 是 |

> 开销 = (保护版中位耗时 − 基线中位耗时) / 基线（与 NFR-01 同口径）。

## 4. 对抗评估（NFR-02；内置 + 独立工具）

内置指标：`{"name_recovery_accuracy": 0.0, "function_judgement_accuracy": 0.0, "vuln_discovery_rate": 0.0, "bin_similarity": 0.4027}`

内置判定：**True**

独立工具（objdump）：泄漏名 []；泄漏串 ['%08x %d']；结论 通过

> **外部第三方红队**为 S5 行动项；本节以**独立工具交叉验证**近似 M6 的「外部独立验证不矛盾」要求（见 `docs/release/README.md` 说明）。

## 5. 缺陷清单

见 `docs/release/defects.md`。

## 6. M6 门槛核对

| 门槛 | 标准 | 现状 |
| :--- | :--- | :--- |
| 功能 | 单测 100% | 见 CI（全绿） |
| 语义保持 | 差分 fuzz 10⁵ 无差异 | 达成 |
| 性能 | 开销在预算内 | 达成 |
| 对抗（内置） | 相似度 ≤ 0.55 等 | 达成 |
| 对抗（外部） | 至少 1 家不矛盾 | 独立工具一致 |
| 缺陷 | 无未修复 P0/P1 | 无 |
| 安全 | 依赖无已知高危 | 离线自检通过，在线查询待 S5 |
| 文档 | 按文档可复现 | 见 `doc-verification.md` |
