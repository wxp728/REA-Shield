# REA-Shield Skill v1.0.0 发布说明（Release Notes）

- **版本**：1.0.0
- **日期**：2026-10-16
- **标签**：`v1.0.0`
- **主产物**：`anti-rea-1.0.0-bundle.tar.gz`（全仓自包含，离线可构建）
- **次产物**：`anti_rea-1.0.0-py3-none-any.whl`、`anti_rea-1.0.0.tar.gz`（sdist）
- **完整性**：`MANIFEST.sha256`（`sha256sum -c` 校验）；签名流程见 `dist/SIGNING.md`

## 一句话

一个 AI Agent 可调用的**代码反逆向加固工具链**：对**你自有**的 C/C++（及 Rust C/FFI 源、
Python C 扩展）代码施加多层级 LLVM 变换，把自动化逆向（REA 类工具）的成本推高到
高于收益。目标是「不值得逆向」，不是「不可逆向」。

## 亮点（本次发布重点：可用性）

| 关注点 | 交付 |
| :--- | :--- |
| 外部 Agent/人能否获取并上手 | 根 `SKILL.md` + 机器可读 `skill.json` + `.agents/skills/anti-rea/SKILL.md` |
| 环境门槛高、报错模糊 | `anti-rea doctor` 自检，缺件**快速失败并给出修复指引** |
| 路径写死、换机就崩 | `core/toolchain.py` 自动探测（环境变量 > PATH > 常见目录）；Makefile/CI 同步 |
| 手工装 LLVM18 太累 | 根 `Dockerfile`：`docker run` 即跑通闭环（含 MCP） |
| 平台误判 | `core/platform_info.py`：`target_platform` 按主机探测，可覆盖 |
| Agent 接入无范例 | `docs/mcp-clients.md`（Claude Desktop/Cursor/通用 stdio 可直接粘贴） |
| 无示例 | `examples/quickstart/`（scan→plan→protect→verify→attack_sim→report 全流程） |

## 能力范围

- **变换**：CFF、MBA、不透明谓词、字符串加密（锚点移除）、代码虚拟化、
  函数拆分/噪声、模块级去锚点；进程内 C++ SPI 支持外部插件。
- **接口**：CLI（10 子命令）+ MCP Server（7 工具）+ 构建集成（CMake/Cargo/npm/Python）。
- **质量**：S4 系统验证（差分 fuzz 10⁵ 零差异、性能预算内、对抗（内置+独立）、
  可复现、跨目标 IR 探针、SBOM）；S5 三个 Beta 试点独立闭环。

## 兼容性

| 维度 | 支持 |
| :--- | :--- |
| 平台 | **完整实测**：linux-x86_64；其他平台 protect 需 Docker/WSL |
| 语言（IR 变换） | C、C++；Rust（仅 C/FFI 源）、Python（仅 C 扩展） |
| 语言（仅扫描） | 纯 Rust、Java、.NET/C#、JS/TS、纯 Python |
| LLVM | 18.x | 
| Python | ≥ 3.11 |

详见 `compatibility-matrix.md`。

## 已知限制 / 顺延项

1. **NFR-02：Token 倍数 ≥ 100×** —— ~~顺延至 S7~~ → **S7 已处置：废弃**。
   两轮真实工程实测（小型驱动 / 十万行级 `.so`）恒 ≈1.0；评估认定该指标在固定单轮提示
   协议下不可测且与防护效果解耦，不再作为验收门禁（`docs/release/s7-field-report.md` §5）。
2. **外部第三方红队** —— ~~顺延至 S7~~ → **S7 已闭环** ✅：真实工程（10 万行 C / 59 TU /
   Linux x86_64 `.so`）全范围构建注入 + 独立 LLM 会话红队 + Ghidra 交叉验证，
   源码级泄漏被阻断（`docs/release/s7-field-report.md`）。
3. 非 Linux 平台 `protect` 需容器/WSL。
4. 纯 Rust/Java/.NET/JS 无 IR 层防护（ADR-001，架构决策，非缺陷）。

> 上述第 1、2 项的 S7 处置详情见 `docs/release/s7-field-report.md`；本版本其余范围以
> **可复现的静态代理指标 + 独立核验**替代，并在 `docs/release/` 中如实标注。

## 升级说明

首次发布，无破坏性变更。后续版本遵循语义化版本；数据契约（`schemas/`）向后兼容。

## 使用入口

- 技能入口：[`../../SKILL.md`](../../SKILL.md)
- 安装/构建/Docker：[`../INSTALL.md`](../INSTALL.md)
- MCP 配置：[`../mcp-clients.md`](../mcp-clients.md)
- 端到端示例：[`../../examples/quickstart/`](../../examples/quickstart/)

## 校验与签名

```bash
cd dist && sha256sum -c MANIFEST.sha256
```

维护者签名与公钥发布流程见 `dist/SIGNING.md`；**签名私钥不入库**（OI-05）。
