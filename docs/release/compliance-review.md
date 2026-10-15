# 合规审查结论（Compliance Review）

> 依据：`docs/requirements/compliance.md`（CQ-01…CQ-05）。S5 出口要求「合规审查通过」。

## CQ 逐条结论

| 编号 | 内容 | 结论 | 证据 / 说明 |
| :--- | :--- | :--- | :--- |
| CQ-01 | 许可证合规：仅处理用户自有代码；不采集/不引入受限代码 | ✅ 通过 | 扫描器**所有权闸门** `_ownership_ok`（要求资产祖先含 `.git`/`LICENSE`）；工具自身依赖许可证齐全（`docs/release/sbom.json`）；自带基准/样例均为 MIT |
| CQ-02 | 审计留痕：拒绝执行/加密强度/LLM 出站等行为记录 | ✅ 通过 | 统一产物目录 `metadata.json`/`transform.log`/`verification_report.json`/`eval_report.json`；`run_id` 贯穿（FR-G1/G2） |
| CQ-03 | 边界：目标非恶意软件；拒绝未知所有权目标 | ✅ 通过 | `scan` 对未知所有权目标拒绝（`E_*`）；`test_scanner.test_refuse_unknown_owner` |
| CQ-04 | 安全软件兼容：产物不应大规模触发 EDR 误报 | 🟡 部分 | 兼容性矩阵已覆盖平台/构建系统；**EDR 真机误报测试**需 S5 试点环境，列为观察项 |
| CQ-05 | LLM 出站控制：外部 LLM 调用需可控、可关闭 | ✅ 通过（开关就绪） | LLM 会话为可选（`ANTI_REA_LLM_CMD`/`ENDPOINT`）；无配置时降级 `static_only`，**不发起任何出站**；真实出站与成本计量待配置后执行 |

## 结论

除 **CQ-04（EDR 真机误报）** 与 **CQ-05 的「真实出站计量」** 属环境/配置相关观察项外，
其余合规边界**全部通过**。本工具仅面向**用户自己拥有**的代码，不涉及第三方软件的再分发。
