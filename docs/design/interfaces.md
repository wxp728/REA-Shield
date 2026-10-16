# REA-Shield 接口契约（Interface Contracts）

## 文档信息

- **文档版本**：v1.1（2026-10-15 经 M1 架构门禁基线化）
- **创建日期**：2026-10-15
- **阶段**：S1 概要设计（任务 HD-03 模块接口、HD-04 MCP API）
- **上游依据**：`HLD.md` v1.1、`docs/requirements/SRS.md` v1.2
- **状态**：**已基线**（M1 架构门禁通过）

---

## 1. 通用约定

### 1.1 数据流与命名

- 契约名统一为 `<组件>.<方法>`，如 `scanner.scan`、`engine.protect`；
- 所有跨模块数据**必须**符合 `schemas/` 中的 Schema；边界处 fail-fast 校验；
- 每个 run 由 `run_id` 唯一标识，贯穿全部产物与日志。

### 1.2 错误模型

所有方法在失败时返回统一错误对象（而非抛裸异常跨模块传播）：

```json
{ "code": "E_SCHEMA_VIOLATION", "message": "...", "asset": "src/crypto/key.cpp", "stage": "protect" }
```

错误码表见 §6。

### 1.3 幂等与确定性

- 给定相同输入 + 相同 `seed`，输出必须逐位一致（NFR-04）；
- `scan` / `verify` / `attack_sim` 视为只读幂等；`protect` 在相同 seed 下也须确定性。

---

## 2. 模块接口契约

### 2.1 输入分析层

| 项 | 内容 |
| :--- | :--- |
| 方法 | `scanner.scan(root: str, options: ScanOptions) -> AssetManifest \| Error` |
| 输入 | `root`（工程路径）；`options`：`{ include?, exclude?, assets_override?, allow_unknown_owner?: bool }` |
| 输出 | `asset_manifest.json`（Schema：asset_manifest） |
| 错误 | `E_INVALID_INPUT`、`E_REFUSED`（所有权不明 / 疑似恶意）、`E_UNSUPPORTED_PLATFORM` |
| 前置 | `root` 可读；所有权可判定（否则触发 E_REFUSED） |
| 后置 | 开源资产 `skip_transform=true`（FR-A4）；分级带证据（FR-A3） |

### 2.2 策略决策层

| 项 | 内容 |
| :--- | :--- |
| 方法 | `strategy.plan(manifest: AssetManifest, budget: PerformanceBudget) -> ProtectionPolicy \| Error` |
| 输入 | `asset_manifest`；`budget`：`{ max_overhead, target_overhead }` |
| 输出 | `protection_policy.yaml`（Schema：protection_policy） |
| 错误 | `E_SCHEMA_VIOLATION`、`E_BUDGET_EXCEEDED`（无法在预算内达成） |
| 前置 | manifest 已通过 Schema 校验 |
| 后置 | 每个资产都有策略或显式标注「不保护」；冲突 / 缺口有告警（FR-B5） |

### 2.3 变换执行层

| 项 | 内容 |
| :--- | :--- |
| 方法 | `engine.protect(input: IRorBinary, policy: ProtectionPolicy, seed: int) -> Artifacts \| Error` |
| 输入 | 中间产物（IR / bitcode / 产物文件）；`protection_policy`；`seed` |
| 输出 | 保护产物 + 变换日志（每个资产应用的变换与参数） |
| 错误 | `E_TRANSFORM_FAILED`、`E_PLUGIN_INCOMPATIBLE`、`E_BUILD_FAILED` |
| 前置 | policy 已校验；仅处理非 `skip_transform` 资产 |
| 后置 | 语义等价（可触发 `verify` 钩子，FR-C12）；产物可复现 |

### 2.4 评估验证层

| 项 | 内容 |
| :--- | :--- |
| 方法 A | `evaluate.verify(artifacts: Artifacts, test_cmd: str) -> VerificationReport \| Error` |
| 方法 B | `evaluate.attack_sim(artifacts: Artifacts, config: AttackConfig) -> EvalReport \| Error` |
| 输入 | 保护产物；`test_cmd`；`AttackConfig`：`{ ghidra?, llm?, session?, budget? }` |
| 输出 | `verification_report` / `eval_report`（对应 Schema） |
| 错误 | `E_VERIFY_FAILED`、`E_LLM_UNAVAILABLE` |
| 前置 | 产物存在；LLM 由运行环境提供（不绑定供应商） |
| 后置 | 指标齐全并落时序库（FR-E6）；判定口径：独立会话上下文消耗 ≥ 90% 未成功 → pass |

### 2.5 对抗策略引擎

| 项 | 内容 |
| :--- | :--- |
| 方法 | `evolve.evolve(feedback: EvalReport[]) -> StrategyUpdate \| Error` |
| 输入 | 历史评估报告（可含多模型结果） |
| 输出 | 更新后的策略模板 / `strategy_kb` 条目 |
| 错误 | `E_LLM_UNAVAILABLE`、`E_SCHEMA_VIOLATION` |
| 前置 | 有历史评估数据 |
| 后置 | 进化后防护得分不劣化，否则回退（FR-F3） |

### 2.6 报告与产物管理

| 项 | 内容 |
| :--- | :--- |
| 方法 | `report.render(run_id: str, format: "json"\|"md"\|"html") -> ReportFiles \| Error` |
| 输入 | `run_id`；目标格式 |
| 输出 | 报告文件 + 统一产物目录 + 可复现元数据 |
| 错误 | `E_INVALID_INPUT` |

---

## 3. MCP 工具契约（HD-04）

- **传输**：JSON-RPC over stdio；每个工具暴露 JSON Schema 供 Agent 发现；
- **通用返回**：成功返回结果对象；失败返回 §1.2 错误对象。

| 工具 | 入参（摘要） | 出参 | 关联 FR |
| :--- | :--- | :--- | :--- |
| `anti_rea.scan` | `path`, `options?` | `asset_manifest` | FR-A* |
| `anti_rea.plan` | `manifest`, `budget` | `protection_policy` | FR-B* |
| `anti_rea.protect` | `policy`, `build_cmd?`, `seed?` | `artifacts` + 变换日志 | FR-C* |
| `anti_rea.verify` | `artifacts`, `test_cmd?` | `verification_report` | FR-E1/E2 |
| `anti_rea.attack_sim` | `artifacts`, `config?` | `eval_report` | FR-E3…E6 |
| `anti_rea.report` | `run_id`, `format` | 报告文件 | FR-E7、FR-G* |
| `anti_rea.evolve` | `feedback` | 更新后的策略 / 知识库条目 | FR-F* |

**约定**：`anti_rea.protect` 在验证失败时按 policy 的 `abort_on_failure` 决定是否返回错误；`anti_rea.attack_sim` 需显式开启外部 LLM 出站（CQ-05）。

---

## 4. CLI 契约

| 命令 | 参数 | 输出 | 退出码 |
| :--- | :--- | :--- | :--- |
| `anti-rea scan <path>` | `--include/--exclude`、`--override <assets.yaml>`、`--json` | `asset_manifest.json` | 0 / 1 / 3 |
| `anti-rea plan <manifest>` | `--budget <yaml/json>`、`--seed` | `protection_policy.yaml` | 0 / 1 |
| `anti-rea protect <policy>` | `--build-cmd`、`--seed`、`--out` | 保护产物 + 变换日志 | 0 / 1 / 2 |
| `anti-rea verify <artifacts>` | `--test-cmd`、`--json` | `verification_report.json` | 0 / 2 |
| `anti-rea report <run_id>` | `--format json\|md\|html`、`--out` | 报告文件 | 0 / 1 |

**退出码约定**：`0` 成功；`1` 一般错误；`2` 验证失败；`3` 拒绝执行（所有权 / 疑似恶意）。
所有子命令支持 `--help`；关键路径支持 `--json` 结构化输出。

---

## 5. 插件 SPI 契约（C++）

```cpp
// engine/spi/transform_plugin.h
static constexpr int SPI_VERSION = 1;

struct TransformCapabilities {
  std::string name;                 // 与 policy.strategies[] 名称一致
  std::vector<std::string> applies_to;  // {"ir","binary"}
  bool supports_coverage = false;
  std::string params_schema;        // 参数 JSON Schema
  double predicted_overhead = 0.0;  // 开销估计（供预算预测器）
};

class TransformPlugin {
public:
  virtual ~TransformPlugin() = default;
  virtual TransformCapabilities capabilities() const = 0;
  virtual bool validate(const Config& cfg, std::string& err) const = 0;
  virtual Result apply(Module& m, const Config& cfg, uint64_t seed) = 0;
  virtual Result verify(const Module& m, std::string& err) const = 0;
};

// 插件导出入口
extern "C" TransformPlugin* register_plugin();
```

**约定**：宿主校验 `SPI_VERSION` 与 `params_schema`；策略中出现未知插件名 → 策略校验失败（fail-fast）。

---

## 6. 错误码表

| 错误码 | 含义 | 典型处置 |
| :--- | :--- | :--- |
| `E_INVALID_INPUT` | 入参非法 | 返回并提示修正 |
| `E_SCHEMA_VIOLATION` | 数据不符合 Schema | 中止，指出字段 |
| `E_REFUSED` | 拒绝执行（所有权不明 / 疑似恶意） | 中止并生成拒绝报告（FR-A6 / CQ-03） |
| `E_UNSUPPORTED_PLATFORM` | 平台 / 语言不支持 | 提示可用范围（NFR-05） |
| `E_BUDGET_EXCEEDED` | 无法在预算内达成目标强度 | 告警并给出降级选项（FR-B3） |
| `E_BUILD_FAILED` | 目标工程构建失败 | 中止（FR-D7） |
| `E_TRANSFORM_FAILED` | 变换失败 / 破坏语义 | 回滚或中止（FR-C12） |
| `E_VERIFY_FAILED` | 功能 / 性能验证失败 | 退出码 2，定位到资产（NFR-11） |
| `E_PLUGIN_INCOMPATIBLE` | 插件版本 / 参数不兼容 | 拒绝加载该插件 |
| `E_LLM_UNAVAILABLE` | 评估 LLM 不可用 | 提示离线或换用可用模型（FR-E3） |

---

## 7. 版本与兼容策略

- **Schema 版本**：每个数据契约带 `schema_version`（`^[0-9]+\.[0-9]+$`）；破坏性变更升主版本；
- **SPI 版本**：`SPI_VERSION` 整数，破坏性变更 +1，宿主拒绝低版本插件；
- **MCP 工具**：工具新增不破坏既有调用；参数变更遵循 JSON Schema 向后兼容；
- **CLI**：子命令与选项新增向后兼容；移除 / 重命名视为破坏性变更。