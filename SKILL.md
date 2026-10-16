---
name: anti-rea
description: >-
  Harden your own source code against reverse-engineering agents (REA) with an
  LLVM-based code-protection toolchain. Use when you want to raise the cost of
  automated reverse engineering / decompilation for C/C++ (and Rust C/FFI or
  Python C-extension) code that you own: scan assets, plan a protection policy,
  apply obfuscation transforms (control-flow flattening, MBA, opaque predicates,
  string encryption, virtualization, noise), verify functional equivalence, and
  simulate an attack to measure effectiveness. Callable from the CLI or over MCP.
license: MIT
version: 1.0.0
entrypoints:
  cli: "anti-rea"
  mcp: "anti-rea-mcp"
  doctor: "anti-rea doctor"
---

# REA-Shield

> 仓库：**REA-Shield**（REA 是矛，本技能就是盾）— Gitee `https://gitee.com/wxp728/REA-Shield` ｜ GitHub 镜像 `https://github.com/wxp728/REA-Shield`

> 把**你自己的**代码加固到「自动反逆向（REA）成本显著升高」的工具链。
> 只加固你拥有或有权修改的代码；本项目**不**攻击、不削弱任何 REA 工具。

这是一个 AI Agent 可直接调用的 **skill**：既有命令行 (`anti-rea`)，也有
MCP Server (`anti-rea-mcp`)，让上层 Agent 用工具调用而不是手工拼命令来完成加固。

## 何时使用 / When to use

- 你有一个**自己拥有**的 C/C++ 项目（或 Rust 的 C/FFI 源、Python C 扩展），
  希望提高自动化逆向/反编译的成本。
- 你想让 Agent 自动完成：扫描敏感资产 → 生成加固策略 → 施加变换 → 验证功能
  保持 → 攻击模拟评估 → 出报告。
- 目标语言为纯 Rust / Java / .NET / JS/TS 时，v1.0 **不支持** IR 层变换
  （见「限制」）。

## 前置条件 / Prerequisites

- Linux x86_64（v1.0 实测唯一完整支持平台）。
- Python >= 3.11，LLVM/clang >= 18，CMake >= 3.16，binutils (nm/objdump/strings)。
- 安装依赖并自检：

```bash
pip install -r requirements.txt
anti-rea doctor          # 打印环境自检；缺什么、怎么修一目了然
```

`doctor` 会检查 Python、jsonschema/PyYAML/deap、clang/opt、引擎插件、cmake、
binutils、平台，并在缺件时给出明确指引。**环境不满足时它会快速失败，而不是
到 protect 才报一个模糊错误。**

LLVM 位置无需写死：通过 `ANTI_REA_LLVM=<前缀>` 或把工具放进 `PATH` 即可；
`doctor` 也接受 `--llvm <前缀>`。

## 快速开始 / Quickstart (CLI)

```bash
# 0) 自检
anti-rea doctor

# 1) 扫描自己的项目，产出资产清单
anti-rea scan /path/to/your/project -o out

# 2) 生成加固策略（按敏感度分级、受性能预算约束）
anti-rea plan out/asset_manifest.json -o out

# 3) 施加变换（需已构建引擎插件：make build）
anti-rea protect out/protection_policy.yaml --root /path/to/your/project \
    --source /path/to/your/project/src/main.c -o out

# 4) 功能保持验证 + 攻击模拟 + 报告
anti-rea verify out
anti-rea attack_sim out --mode all
anti-rea report out
```

产物：`out/` 下的 `asset_manifest.json`、`protection_policy.yaml`、
`artifacts/`（baseline/protected 可执行文件、变换日志）、`verification_report.json`、
`eval_report.json`、保护报告。

## 作为 MCP Server 使用（推荐给 Agent）

```bash
anti-rea-mcp        # stdio JSON-RPC，暴露 7 个工具
```

工具：`scan` / `plan` / `protect` / `verify` / `attack_sim` / `report` / `evolve`。

面向常见客户端的**可直接粘贴配置**见 [`docs/mcp-clients.md`](docs/mcp-clients.md)。

## 工具速查 / Tools

| 工具 | 作用 | 关键输入 |
|------|------|----------|
| `scan` | 扫描工程，产出 `asset_manifest.json` | `path` |
| `plan` | 生成策略 `protection_policy.yaml` | `manifest`, `budget` |
| `protect` | 施加变换，产出保护产物 | `policy`, `root`, `sources` |
| `verify` | 差分验证功能保持 | `artifacts` |
| `attack_sim` | 攻击模拟，产出 `eval_report.json` | `artifacts`, `mode` |
| `report` | 生成人读保护报告 | `run` |
| `evolve` | 策略遗传进化（DEAP） | `manifest` |

## 多编译单元工程 / Multi-TU projects

`protect` 通过 `clang -fpass-plugin` 施加变换，Pass **逐编译单元（TU）** 运行。当工程由多个
`.c/.cpp` 组成（`--source a.c --source b.c ...`）时：

- **标识符重命名会自动降级**：外部链接函数可能被其它 TU 按原名引用，改名会导致
  `undefined reference`。故 `protect` 检测到多源时自动设 `ANTI_REA_RENAME_EXTERNAL=0`
  ——只改名 static/内部函数，公共符号名保留（REA 仍能在符号表看到导出名）。单文件工程/
  整程序编译默认全量改名（`ANTI_REA_RENAME_EXTERNAL=1`）。
- **`verify` 的对抗诱导变体**会与全部源文件一起链接（`metadata.json` 记录 `sources`）；
  变体是 `sources[0]` 的副本，源文件里的**相对 `#include "../..."` 会被自动改写为绝对
  路径**，避免副本挪到 `out_dir` 后断链。
- **口径提示**：`baseline` 用 `clang -O0`、`protected` 用 `clang -O1`，两者的体积/符号差异
  含优化因素，不全是混淆所致；需严格对比时请自行对齐优化级别。

## 安全边界 / Safety & Limits (v1.0)

- **只加固你拥有的代码**。开放源码组件默认跳过（`allow_unknown_owner` 可覆盖）。
- 目标是**抬高成本**，不是「不可破解」。任何加固都可被有决心的分析者攻破。
- 变换引擎基于 LLVM Pass：支持 C/C++；Rust 仅 C/FFI 源、Python 仅 C 扩展。
  纯 Rust / Java / .NET / JS/TS 无 IR 层防护（ADR-006）。
- 默认平台 Linux x86_64；其他平台可运行 scan/plan，protect 需自行验证。
- 详细兼容性与实测结论见 `docs/release/`、`docs/INSTALL.md`。

## 进一步阅读 / See also

- `docs/INSTALL.md` — 安装、构建、环境变量、Docker。
- `docs/mcp-clients.md` — MCP 客户端配置（Claude Desktop / Cursor / 通用 stdio）。
- `examples/quickstart/` — 端到端可运行示例。
- `docs/FAQ.md`、`docs/troubleshooting.md` — 常见问题与故障排查。
- `skill.json` — 机器可读的 skill 清单。
- `README.md` / `README.zh-CN.md` — 项目总览（英 / 中）。
