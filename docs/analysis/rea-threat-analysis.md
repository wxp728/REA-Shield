# REA 威胁分析（REA-Shield 针对性设计输入）

> 状态：分析文档（**非**需求基线）。不修改 `SRS.md`；如需据此新增/调整需求，走 `plan §10.4` 变更流程。
> 边界：仅为**防御性**分析——用于把 REA-Shield 的加固产物做得更有针对性。本文不含任何针对 REA 的攻击手段，
> 也不改变 REA-Shield 既定的"间接反制"定位（只产出加固产物，不攻击 REA 工具本身）。

## 1. 分析对象与方法

| 项 | 值 |
| :--- | :--- |
| 项目 | **REA — "Reverse Engineer Anything"** |
| 仓库 | `https://github.com/morluto/rea` |
| 版本 / 提交 | `6.5.0` / `40f73f62bc3acf8b444dbafba1b8ed0aef6dd641` |
| 许可 | MIT（开源，本地运行） |
| 形态 | MCP Server + CLI（TypeScript），本地编排外部分析引擎 |
| 分析方式 | 克隆到 `../rea-reference` 后**静态阅读**（skill、docs、`src/` 契约层）；未运行其对任何目标的实际分析 |

## 2. REA 能力概览

REA 本身**不实现**反编译/反汇编，而是把"分析引擎"统一编排成面向 AI Agent 的 MCP 工具：

- **静态引擎 provider**：Ghidra（临时 DB，PyGhidra）、IDA（只读，不保存/不关闭 GUI DB）、Hopper、
  Kuna（缓存 whole-program 导出）、JEB、Rizin、Cutter、GNU objdump、pwntools（`inspect_binary_layout`）。
- **运行期观测**：Frida、GDB（持久 MCP 会话，仅 Linux）、浏览器（Playwright/CDP）、Electron、Fiddler/`saz`。
- **包/构件层**：apktool（APK）、MSIX/AppX/IPA/DMG/ASAR/JS 树、WASM（WABT）、EVM 字节码、Go/Rust 元数据、
  SQLite、PE 资源、firmware（Binwalk/Unblob）、pcap/qlog（TShark）、sigrok 信号。
- **典型工作流**（`SKILL.md`）：`Route the target` → `Work summary-first` →
  `open_binary` / `analyze_function` / pseudocode / function·string 搜索 / xrefs → **recreate**（重建为自有技术栈）。

> 关键点：REA 面向的"目标"默认是**已发布的二进制/包**（shipped artifact），其证据链要求"shipped-artifact 权威"。

## 3. REA 的证据/权威模型 —— 对我们最有利的一点

REA 强制区分：

- `confidence`：`observed`（直接观测） / `derived`（推导） / `inferred`（推断）；
- `authority`：`shipped-artifact` / `controlled-replay` / `historical-reference` / `external-service` / `analyst-inference`。

并**fail-closed**：未决即 `unknown`；`fail`/`unknown` **永不**聚合为 `pass`。其"重建就绪度"（reconstruction
readiness）本质是**证据闭合流程**：必须关闭"义务账本（obligation ledgers）"、能定位版本间主分歧，才可判定就绪。

**推论**：只要我们让静态证据**无法闭合到 `observed`**，REA 就只能停在 `inferred/unknown`，判据即"未成功"。
这与我们既有的 OI-07 判据（`pass = 未成功 AND session_context_used_ratio ≥ 0.90`）方向一致。

## 4. REA 的能力缺口 —— 我们的主攻面

| REA 现状 | 对我们意味着 |
| :--- | :--- |
| **没有专门的抗混淆/脱壳/反虚拟化能力**。全仓仅一处相关表述：`JavaScriptArtifactAnalysis.ts:341` "Static paths and relationships may remain unresolved when expressions are dynamic or **obfuscated**." | 混淆直接被 REA 归入 **unresolved unknown**，而非"可解难题"。CFF/MBA/VM/噪声直接抬高其闭合成本。 |
| 静态 provider 只读（Ghidra 临时 DB、IDA 只读） | 静态变换效果**稳定保留**在产物里，不会被其"回写修复"。 |
| 运行期观测（Frida/GDB/浏览器）需**目标可执行且可控** | 静态加固到一定程度后，REA 的唯一突破口是 `controlled-replay`；这是 R3+ 的对抗面（须走 SRS 变更）。 |
| 强依赖 **字符串与符号名**作为"锚点"（skill 明示 strings/symbol names） | **移除锚点**是性价比最高的针对性手段（见 §5-A）。 |
| 支持 **跨版本对比**（localize primary divergence） | 版本间结构不稳定（MTD）可直接让"分歧定位"退化为乱码/unknown。 |
| 重建后需对原程序做**差分验证**（原始 x86 用例 / 字节级函数匹配） | 功能保持前提下 REA 最终**可能有能力**重建行为；我们只抬高成本，不追求不可破（与威胁模型一致）。 |

## 5. 针对性对策（按性价比排序）

### A. 移除 REA 的锚点 —— **最高优先**
- **字符串加密**（`string_encryption`）：常量串异或/查表编码 + 运行期解码桩；并含**常数编码**，把算法
  指纹立即数（SM4 FK / SM3 IV 等 `#define` 常量）收进运行期解码的常量池——REA 的 `strings` 搜索、字节
  特征扫描、IOC 定位、"feature 识别"高度依赖明文串与明文常量；加密后这些查询命中率骤降。
- **标识符重命名**（`identifier_renaming`）：符号级重命名 + 调试信息剥离。破坏 `analyze_function` 的语义命名、
  caller/callee 推理与"human-readable 命名"依赖。
- 现状：两者已在 `dd-03 §7` 设计、并在策略枚举 `strategy_templates.yaml` 中出现，**已于 R2 实现**
  （`string-encrypt` / `ident-rename` 模块级 Pass；示例见 `engine/README.md`、测试 `test_anchor_removal`）。
  v0.1 以"移除 `strings`/符号线索"为目标（异或编码 + 运行期解码桩 + 符号改不透明名），
  更强方案（查表/多态解码、调试信息剥离）列为后续增强。
- 落地建议：R2 收尾或 R3 首个任务；作为 LLVM Pass（字符串加密需插入 decode 桩，注意与 CFF/VM 的顺序，
  参考 `dd-03 §6`：重命名 → 字符串加密 → 其余变换）。

### B. 提高静态闭合成本 —— **已实现，继续参数化**
- `control_flow_flattening` / `mixed_boolean_arithmetic` / `non_linear_mba` / `opaque_predicates`：降低
  pseudocode 可读性与 REA 的 value-flow 推理置信度（`inferred` 而非 `observed`）。
- `code_virtualization`（FR-C7/C8）：把函数体送入自定义 ISA，pseudocode 退化为"解释器调度"，REA 需先**识别
  VM 并还原 ISA**（其无此能力）→ 直接落到 unknown。
- `function_boundary_perturbation`（FR-C4）：改变反编译器的函数识别数，破坏 `analyze_function` 的函数清单与 xref 图。
- `data_flow_noise`（FR-C5）：注入无副作用冗余数据运算，稀释 REA 的数据流推断。

### C. 破坏跨版本对比 —— **已具备（MTD/adversarial）**
- `adversarial_inducement`（FR-C9）+ 变体生成（OI-05：`variant_count` schema 上限 64 / 默认 8 / 建议 ≤16）：
  每次发布结构不同，REA 的 "compare-authority-candidate" 阶段难以稳定定位分歧 → 退化为 unknown。
- 建议：在 R3 的成本模型（DD-07/GA）中，把"变体间结构差异度"作为**可度量指标**显式纳入。

### D. 白盒密码（FR-C10）—— 保护密钥而非行为
- 对 P0 密钥材料，WBC 使"从产物中直接提取密钥常量"失败（`check_no_key_constant` 已自测）。REA 即便还原
  算法，也拿不到可用密钥 → `analyst-inference` 而非 `shipped-artifact`。

### E. 运行期对抗（反调试/反追踪）—— **R3+ / 需 SRS 变更**
- 若威胁模型扩展到"REA 用 Frida/GDB 动态观测"，则需 anti-debug / 反注入能力。
- 现状：不在 SRS 基线，且属较激进行为；**必须先走 `plan §10.4` 变更**再实现。建议作为 R3 议题登记，而非本期硬塞。

## 6. 结论与建议动作

1. **主攻方向确定为"移除锚点"**：`string_encryption` 与 `identifier_renaming` 已于 R2 实现（见 §5-A 现状），
   直接针对 REA 的结构性短板（无脱混淆能力）。下一步可在成本模型（DD-07）中量化其对 REA 静态闭合的影响。
2. **既有变换不需改动，只需在成本模型里显式建模 REA 的 fail-closed 语义**（把"证据无法闭合"计为我们的成功信号）。
3. **跨版本（MTD）与白盒是差异化壁垒**，继续保留并度量。
4. **反运行期对抗**作为独立议题，经变更流程后再启动。
5. 建议将本分析在 `docs/STATUS.md` 与 DD-07（成本模型）中引用；RTM 不因本文变动（非需求）。

## 7. 参考

- REA skill：`rea-reference/.agents/skills/reverse-engineer-anything/SKILL.md`（+ `references/*.md`）
- REA 文档：`docs/reconstruction-readiness.md`、`docs/reconstruction-obligation-ledgers.md`、
  `docs/reconstruction-coverage.md`、`docs/reverse-engineering-tools.md`、`docs/ghidra-provider.md`、`docs/kuna-provider.md`
- REA 证据/权威：`src/evaluation/KnownAnswerEvaluation.ts`、`src/contracts/*`
- 本地对照实现：`docs/design/ddd/dd-03-llvm-transforms.md`（§6/§7）、`dd-04-virtualization.md`、`dd-06-wbc.md`、
  `dd-05-adversarial.md`、`policies/strategy_templates.yaml`
