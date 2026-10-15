# S5 Beta 试点报告（Pilot Report）

> 由 `tools/run_s5.py` 生成（`plan §7`）。试点覆盖不同语言 / 构建系统 / 敏感度。

## 1. 试点总览

| 试点 | 语言 | 构建系统 | 敏感度 | 资产 | 功能保持 | 对抗判定 | 独立闭环 |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- | :--- |
| crypto-lib | C | CMake | P0 | 3 | 通过 | 通过 | 是 |
| protocol-svc | C++ | Make | P1 | 3 | 通过 | 通过 | 是 |
| python-ext | Python C 扩展 | setuptools build_ext | P2 | - | 通过 | 通过 | 是 |

## 2. 逐试点详情

### crypto-lib（C / CMake / P0）

- 产物目录：`build/s5/crypto-lib/anti-rea`
- 策略：`["cff", "func_split", "mba", "noise", "opaque", "rename", "string_encrypt", "virtualize"]`
- 白名单：`["secret_key_schedule", "verify_license"]`
- 功能保持：通过；对抗判定：通过
- 对抗指标：`{"name_recovery_accuracy": 0.0, "function_judgement_accuracy": 0.0, "vuln_discovery_rate": 0.0, "bin_similarity": 0.4007}`
- 用时：0.66s

### protocol-svc（C++ / Make / P1）

- 产物目录：`build/s5/protocol-svc/anti-rea`
- 策略：`["cff", "func_split", "mba", "noise", "opaque", "rename", "string_encrypt", "virtualize"]`
- 白名单：`["derive_frame", "secret_decode_frame"]`
- 功能保持：通过；对抗判定：通过
- 对抗指标：`{"name_recovery_accuracy": 0.0, "function_judgement_accuracy": 0.0, "vuln_discovery_rate": 0.0, "bin_similarity": 0.3988}`
- 用时：0.58s

### python-ext（Python C 扩展 / setuptools build_ext / P2）

- 产物目录：`build/s5/python-ext/anti-rea`
- 策略：`["cff", "func_split", "mba", "noise", "opaque", "rename", "string_encrypt", "virtualize"]`
- 白名单：`["secret_key_schedule"]`
- 功能保持：通过；对抗判定：通过
- 对抗指标：`{"name_recovery_accuracy": 0.0, "function_judgement_accuracy": 0.0, "vuln_discovery_rate": 0.0, "bin_similarity": 0.4061}`
- 扩展调用：protected=6123 / baseline=6123（可导入：True）
- 用时：1.08s

## 3. 结论与改进行动

- 三个试点**均按文档独立完成保护闭环**：`是`
- 功能保持全通过：`True`；对抗判定全通过：`True`

改进行动（见 `docs/release/improvements.md`）：
- I-01 将「独立工具交叉验证」纳入试点验收（已在 S4 落地）；
- I-02 交叉编译仅到 IR 层，链接层目标支持待补交叉 sysroot（S5→后续）；
- I-03 无 LLM 时以 `static_only` 代理指标验收，Token 倍数在配置 LLM 后补测。

