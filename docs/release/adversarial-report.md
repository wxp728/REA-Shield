# 对抗评估报告（Adversarial Evaluation）

> 由 `tools/run_s4.py` 生成（NFR-02 / FR-E3）。判定口径见 `decisions/OI-07-*.md`。

## 内置评估（attack_sim, static_only）

```json
{
  "name_recovery_accuracy": 0.0,
  "function_judgement_accuracy": 0.0,
  "vuln_discovery_rate": 0.0,
  "bin_similarity": 0.4027
}
```

判定：**True**

理由：
- 静态代理指标（无 LLM；见 dd-07 §5）
- 未执行 LLM 会话判定（static_only）

## 独立工具交叉验证

- 工具：objdump（Ghidra 运行：False）
- 泄漏目标名：[]
- 泄漏明文串：['%08x %d']
- 独立结论：通过
- 与内置结论：不矛盾

> **限制**：无 LLM 时 `token_ratio` 不可测（`static_only` 降级）；Token 消耗倍数 ≥ 100x 与外部第三方红队结论留待 S5（CQ-05 出站控制）。
