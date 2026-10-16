# 变更记录（Changelog）

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### 变更（S7 首轮 · 条件项补测）

- **实战红队验证闭环**：对某真实生产 C 工程（约 10 万行 / 59 编译单元 / Linux x86_64 `.so`，
  经构建注入全范围保护）完成独立 LLM 会话红队 + Ghidra 交叉验证——内部符号 0 残留、
  特征字符串 -98%、整库指令 5.4×、核心函数反编译失败、函数名恢复 0.00，**源码级泄漏被阻断**；
  记录见 `docs/release/s7-field-report.md`，README 增「实战验证」小节（匿名化）。
- **NFR-02「Token 倍数 ≥ 100x」子项废弃**：两轮实测恒 ≈1.0，评估认定该指标在固定单轮提示
  协议下不可测且与防护效果解耦，不再作为验收门禁（保留「上下文消耗 ≥90% 未成功即通过」
  会话判定子项）；`docs/requirements/rtm.md` / `docs/STATUS.md` / `docs/release/RELEASE-1.0.0.md`
  已同步标注（SRS 条目内容未改，需求已基线）。

## [1.0.0] — 2026-10-16

首个正式版本。REA-Shield Skill 是一个 AI Agent 可调用的**代码反逆向加固工具链**，
对用户自有代码施加多层级 LLVM 变换，抬高自动化逆向（REA）的成本。

### 新增（能力）

- **变换引擎（LLVM Pass 插件）**：控制流平坦化（CFF）、混合布尔算术（MBA）、
  不透明谓词、字符串加密（锚点移除）、代码虚拟化、函数拆分/噪声、
  模块级去锚点（`rename`/`string-encrypt`）；运行期 LCG 密钥流。
- **进程内 C++ SPI**：外部变换插件可插拔（FR-C11），宿主导出 LLVM 符号。
- **CLI**：`scan` / `plan` / `protect` / `verify` / `report` /
  `attack_sim` / `regress` / `diff` / `evolve`（`core.cli`）。
- **MCP Server**：`anti-rea-mcp`，stdio JSON-RPC 2.0，7 个工具（FR-D6）。
- **评估与自适应**：攻击模拟（static/dynamic/crossver）、指标时间序列、回归检测、
  DEAP 策略遗传进化与知识库（FR-E/F）。
- **系统验证（S4）**：差分 fuzz 10⁵ 零差异、性能预算、对抗评估（内置 + 独立
  objdump/Ghidra）、可复现、稳健、跨目标 IR 探针、SBOM。
- **Beta 试点（S5）**：C / C++ / Python-C-ext 三个独立闭环试点。
- **构建集成**：CMake / Cargo / npm / Python（不含引擎，统一调用驱动）。

### 新增（可用性，本次发布重点）

- **技能入口**：根 [`SKILL.md`](SKILL.md) + 机器可读 [`skill.json`](skill.json) +
  `.agents/skills/anti-rea/SKILL.md`（对标 REA 的 skill 清单，便于外部 Agent 自举）。
- **`anti-rea doctor`**：环境自检，缺件时**快速失败并给出明确修复指引**；
  支持 `--json` 与 `--llvm <前缀>`。
- **去除硬编码路径**：新增 `core/toolchain.py`，按「环境变量 > PATH > 常见目录」
  自动探测 clang/opt/llvm-config/插件/cmake；`Makefile`、`ci/ci.sh`、
  `INSTALL.md` 同步更新。
- **容器镜像**：根 `Dockerfile`（钉死 Python 3.11 + LLVM/clang 18 + 预构建插件），
  `docker run` 即可跑通闭环；`mcp` 子命令切到 MCP 服务器。
- **平台探测修正**：`core/platform_info.py`，`scan` 的 `target_platform`
  由写死改为按主机探测（可显式覆盖）。
- **MCP 客户端配置**：[`docs/mcp-clients.md`](docs/mcp-clients.md)，
  Claude Desktop / Cursor / 通用 stdio 可直接粘贴。
- **示例与文档**：`examples/quickstart/`（端到端可运行）、
  `docs/FAQ.md`、`docs/troubleshooting.md`、英文 `README.md` / 中文 `README.zh-CN.md`、`LICENSE`、`CHANGELOG.md`。
- **依赖修正**：`requirements.txt` / `pyproject.toml` 补 `deap`、补
  `core.verify` 包与元数据（classifiers/urls/license）。
- **发布打包**：`tools/release.py`（wheel + sdist + 全仓自包含 bundle +
  `MANIFEST.sha256` + `SIGNING.md`，含 `--check`/`--verify`）。

### 已知限制

- **平台**：完整实测仅 Linux x86_64；其他平台 `protect` 需 Docker/WSL。
- **语言**：IR 变换覆盖 C/C++（Rust 仅 C/FFI 源，Python 仅 C 扩展）；
  纯 Rust / Java / .NET / JS/TS 仅可扫描（ADR-006）。
- **NFR-02 Token 倍数 ≥ 100×** 与 **外部第三方红队** 两项验收需真实 LLM 会话，
  v1.0 未在离线环境实测，**顺延至 S7**（见 `docs/release/RELEASE-1.0.0.md`）。
- 威胁模型为「抬高成本」，非「不可逆向」。

### 安全

- 仅加固用户自有代码；开放源码默认跳过；所有权不明拒绝执行。
- 签名私钥**不入库**（OI-05）；发布产物由维护者离线签名。

## 里程碑标签

`m0-baseline` · `m1-architecture` · `m2-design` · `m3-r1` · `m4-r2` ·
`m5-frozen` · `m6-verified` · `m7-pilot` · `v1.0.0`
