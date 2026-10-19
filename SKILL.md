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
  Works in phases: read-only survey → transformation proposal for user review →
  user picks a mode (one-shot build, or transforming the target project's build
  architecture and standing up an anti-REA build environment) → flexible
  execution. The skill provides information and methodology; it does not
  automatically modify the target project's build system. It installs minimally
  by default and fetches optional, language/platform-specific components on
  demand -- third-party tools are never bundled, only their sources and usage
  are recorded.
  For Java / Android (no LLVM IR transforms) it provides a selectable anti-REA
  option menu — server-side logic, bytecode obfuscation, packing, bytecode
  virtualization, offloading to native (JNI/JNA/FFM), GraalVM native-image,
  runtime hardening, key management — with principles, trade-offs, impacts and
  tool sources, plus a decompiler-based verification methodology; the user
  chooses the combination.
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
- 你想让 Agent **分阶段**带你看方案再动手：先只读勘察 + 出改造方案给你审查，
  再按你选的模式（一次性构建 / 改造目标工程的构建架构并搭起防 REA 构建环境）执行。
- 目标语言为纯 Rust / Java / .NET / JS/TS 时，v1.0 **不支持** IR 层变换
  （见「限制」）；但 **Java / Android 有专门的替代方案菜单**（服务端化、字节码混淆、
  加壳、字节码虚拟化、下沉 native、GraalVM native-image、运行期对抗、密钥管理）——
  见「Java / Android 项目」一节与 [`docs/java-anti-rea.md`](docs/java-anti-rea.md)。

## 工作流：先方案、后改造 / Phased workflow

> **本技能不自动修改目标工程的构建体系，也不会替你把改造跑完。**
> 各项目的构建工具、依赖与 CI 千差万别，本技能提供的是**信息 + 方法论 + 命令**，
> 由 AI/Agent 按下述阶段与用户协作落地。**每阶段结束先产出可审查的东西给用户，
> 得到确认后再进入下一阶段。**

| 阶段 | 动手与否 | 产出（交用户审查） |
| :--- | :--- | :--- |
| **P0 勘察**（survey） | **只读** | 环境自检 + 资产清单 + **构建画像**（目标工程怎么构建，见下） |
| **P1 方案**（proposal） | **只读** | 一份改造方案文档（模板见下），**等用户批准** |
| **P2 选模式**（decide） | 用户决策 | 用户在模式 A / B / C 中选定，并提出修改要求 |
| **P3 执行**（execute） | 按所选模式 | 按方案逐步执行；**改构建文件必须先给用户看 diff** |
| **P4 验证交付**（verify） | 产物 | `verify` / `attack_sim` / `report` + 回退说明 |

### P0 · 勘察（只读，不改任何文件）

1. 本技能工具链自检：`anti-rea doctor`（按分级分组：缺什么、**何时需要**、怎么修）。
   P0 **只装 T0**（`requirements.txt`）——LLVM/镜像/Ghidra 等留到 P2 用户选定模式后再装。
2. 资产扫描：`anti-rea scan <project> [-o out]`（范围收窄见「Scoping」节）。
3. **构建画像**——读取目标工程（Makefile / configure / CMakeLists / build.rs /
   package.json / CI 配置 …），回答以下问题并记入方案：
   - 构建入口与构建工具是什么（autoconf+make / CMake / Meson / Cargo / node-gyp /
     Bazel / 自研脚本）？
   - 编译器怎么被指定（`CC=` 变量、toolchain 文件、硬编码 gcc/clang）？
   - 产物形态（可执行 / `.so` / 静态库 / Python 扩展 / 安装包）与平台？
   - 工程自身依赖（头文件、第三方库、交叉编译）有哪些、如何安装？
   - 有没有多变体构建（PIC/非 PIC、`_srv`/`_shlib` 对象）与 CI 流水线？
   - 目标工程**自身**有哪些功能测试（用于加固后回归）？

### P1 · 改造方案（plan / proposal 模式，**先给用户审查**）

> 注意与工具区分：此处的「方案」是 **Agent 起草、给用户审查的工程改造方案文档**，
> 不是 CLI 的 `anti-rea plan` 子命令（后者只把资产清单变成 `protection_policy.yaml`
> 策略文件，是方案里「策略」一节的输入）。

把 P0 结果整理为一份方案文档（建议放 `out/PROPOSAL.md`，Agent 起草、用户改），
**至少**包含：

1. **目标与范围**：保护哪些模块/目录；白名单与导出契约（哪些公共 API 名必然保留）。
2. **构建画像**：P0 第 3 步的结论。
3. **依赖与环境安装清单**：按分级（[`docs/PROVISIONING.md`](docs/PROVISIONING.md)）分三档列出并**说明触发条件**：
   - **现在就装（T0）**：`pip install -r requirements.txt`；
   - **选定模式后再装（T1）**：LLVM 18、cmake、binutils、`make build`（模式 A/B 要 protect 时才需要）；
   - **用到才装（T2/T3）**：按目标语言（rustc/cargo、node/npm、JDK 用工程自带）、是否要独立验证
     （Ghidra）、是否跑 `evolve`（`requirements-optional.txt`）、是否走红队会话（LLM 端点）；
     可用 Docker 镜像替代宿主安装（属较重路径）。

   目标工程侧（工程自己的依赖怎么装）另列；**未选到的组件标注"延后安装"**，不要在 P1 就预装。
4. **推荐模式与理由**：模式 A / B / C（见 P2），预估代价（体积、构建时间、运行开销）。
5. **分步骤执行计划**：每步一条命令或一处脚本改动点，标注改哪个文件。
6. **语言特定的可选手段**（目标为 Java / Android 时**必填**）：从
   [`docs/java-anti-rea.md`](docs/java-anti-rea.md)（机器可读：
   [`docs/java-anti-rea-options.yaml`](docs/java-anti-rea-options.yaml)）的 J0–J8 里
   挑 1–3 个候选组合，逐一摘要**原理 / 优点 / 缺点 / 影响（性能、体积、构建、可移植性、
   兼容性）与获取源**，并给"按场景推荐"的取舍——**由用户勾选**；其中 J5/J6 的 native 部分
   可回归本技能的常规加固链路。
7. **验证与回退**：baseline 对照怎么留、`verify`/`attack_sim` 怎么跑、如何还原
   （构建注入不改源码；确需改构建文件的，保留原文件副本或 VCS 分支）；Java 字节码侧
   按 `docs/java-anti-rea.md` §4 的反编译方法论执行（本技能 `verify`/`attack_sim`
   不适用于 Java 字节码）。

> 方案必须**停下等用户批准**；用户可能改范围、换模式、加要求——按其修订后再进入 P3。

### P2 · 用户选择执行模式（用户决策点）

| 模式 | 适用 | 改目标工程的构建体系？ | 产物 | 典型路径 |
| :--- | :--- | :--- | :--- | :--- |
| **A · 一次性构建** | 快速验证效果、小而自包含的目标、试点 | **否** | `out/` 下独立 baseline/protected 产物 | `scan → plan → protect → verify` |
| **B · 改造构建架构 + 防 REA 构建环境** | 真实工程长期交付（`.so`、安装包、进 CI） | **是**（构建脚本/环境/CI） | 工程**原生形态**的真实产物（如 `.so`） | `scan → plan → buildenv → 注入原有构建 → verify` |
| **C · 先 A 后 B**（推荐给大型工程） | 先低成本验收策略与开销，再落地架构改造 | A 否 → B 是 | 先对照产物、后真实产物 | A 路径 + B 路径顺序执行 |

选择时给用户摆清楚：A 的局限（`protect` 只产出独立可执行文件，产不出 `.so`/多文件
真实产物）、B 的成本（要动构建脚本、装依赖、可能改 CI）、C 的顺序建议。

### P3 · 执行（按用户所选模式；Agent 灵活适配，**不套死模板**）

- **模式 A**：即「Quickstart」四步。
- **模式 B**：核心是**构建注入**——不替换目标工程的构建系统，而是把
  「clang + 变换插件」挂进其原有构建（编译挂插件、链接透传），并把这套做法
  **固化成目标工程可复用的构建环境**（如工程内脚本 / Makefile 目标 / CI job）：

  ```sh
  anti-rea buildenv out/protection_policy.yaml --root <project> --protect-all -o out/scope.env
  source out/scope.env
  export CC=<repo>/integrations/cc-wrapper/anti-rea-cc
  <目标工程照常构建>          # ./configure && make / cmake --build / cargo build ...
  ```

  **常见构建体系的注入点（方法论参考，按工程实际灵活裁剪）**：

  | 构建体系 | 注入方式 |
  | :--- | :--- |
  | autoconf + Make | `CC=包装器` 传给 `./configure` 与 `make`；configure 探测可用 `ANTI_REA_DISABLE=1` |
  | 纯 Makefile | `make CC=包装器`，或 Makefile 中 `CC ?=` 允许外部覆盖 |
  | CMake | `-DCMAKE_C_COMPILER=<包装器>` 或 toolchain 文件里设 `CMAKE_C_COMPILER` |
  | Meson | native file 的 `c/cpp` compiler 字段，或 `-Dc_args` 仅传插件参数 |
  | Cargo（Rust C/FFI） | 经 `cc` crate 的 `CC` 环境变量注入（仅 C/FFI 源受保护） |
  | node-gyp / npm | `CC` 环境变量（仅 C 扩展部分受保护） |
  | Bazel | 自定义 C++ toolchain 或 `--action_env=CC=包装器` |
  | 自研脚本 / 硬编码编译器 | 改脚本把编译命令指到包装器，或加 PATH shim；**改动先给用户看** |

  **执行纪律**：改任何构建文件/CI 前，把 diff 贴给用户过目；只加不删（保留原构建
  路径可随时回退）；工程依赖安装按 P1 清单执行，装不上的项如实回报用户而不是跳过。

### P4 · 验证与交付

`anti-rea verify`（功能保持 + 开销）→ `anti-rea attack_sim`（`--allow-llm` 走真实
LLM 红队会话）→ `anti-rea report`；附回退说明与后续再构建的操作方式
（模式 B：如何一条命令再产出受保护产物）。


## 前置条件 / Prerequisites

**分级（默认最小安装，其余按需）**——不必然用到的组件**先不下载**：

| 分级 | 什么时候才需要 | 组成 |
| :--- | :--- | :--- |
| **T0 核心（必装）** | 始终（`scan` / `plan` / `doctor` / `report` 只需这些） | Python >= 3.11 + `jsonschema` + `PyYAML`（`requirements.txt`） |
| **T1 原生变换** | 选定模式 A/B 且要 `protect` / `verify` / `attack_sim` | LLVM/clang >= 18、CMake >= 3.16、binutils、`make build` |
| **T2 语言与平台** | 按目标语言 / 构建体系 / 宿主平台 | rustc+cargo（Rust C/FFI）、node+npm（JS/TS 仅扫描）、JDK（Java 勘察用工程自带）、容器运行时 |
| **T3 可选增强** | 只在用到该功能时 | Ghidra+PyGhidra（独立验证）、`deap`（`evolve`，`requirements-optional.txt`）、LLM 端点（红队会话） |
| **T4 永不下发** | — | Java/Android 第三方加固工具/产品（只记录获取源，见 `docs/java-anti-rea.md`） |

> **本技能不打包、不预装、不代下载任何第三方工具**；第三方组件一律只记录**获取源与用法**。
> 完整策略、体量量级与最小部署集见 [`docs/PROVISIONING.md`](docs/PROVISIONING.md)。

```bash
pip install -r requirements.txt     # T0 最小：够跑 scan/plan/doctor/report
anti-rea doctor                     # 按分级分组：缺什么、何时需要、怎么装一目了然
anti-rea doctor --tier T0           # 只看最小集；--tier T1 只看原生变换所需
```

`doctor` 检查 Python、`jsonschema`/`PyYAML`/`deap`、clang/opt、引擎插件、cmake、
binutils、平台，并在缺件时给出明确指引。**T0 缺件会快速失败，而不是到 protect 才报
一个模糊错误**；T1/T2/T3 缺件只提示"选到该功能时再装"，**不阻塞** scan/plan。

LLVM 位置无需写死：通过 `ANTI_REA_LLVM=<前缀>` 或把工具放进 `PATH` 即可；
`doctor` 也接受 `--llvm <前缀>`。

## 安装与按需获取 / Provisioning（不打包第三方）

**纪律（Agent 自查）**：

1. **先最小、后按需**：P0 只装 T0 + 跑 `scan`；**在用户选定模式之前**不装 LLVM、不拉镜像、不下载 Ghidra。
2. **只读需要的那一篇文档**：`SKILL.md` + 与当前语言/模式相关的**一篇**（`docs/build-injection.md`
   或 `docs/java-anti-rea.md`）；不要把 `docs/` 全量读进上下文（省 token 也是省部署代价）。
3. **把"要装什么"写进 P1 方案**：按「现在就装（T0）/ 选定模式后再装（T1）/ 用到才装（T2/T3）」
   三档列出，附触发条件；T4 只给获取源。
4. **安装动作先经用户确认**：装系统包、拉镜像、下载第三方工具前说明体量与影响；工具许可与
   凭据由用户自管。
5. **装不上如实回报**，不要悄悄换组件或假装成功。

**只把技能装到别的项目**（不带开发/审计材料：`tests/`、`ci/`、`poc/`、`pilots/`、`benchmarks/`、设计文档）：

```bash
python tools/release.py --skill dist     # → dist/anti-rea-skill-<version>.tar.gz（附 SKILL-FILES.txt）
```

## 快速开始 / Quickstart (CLI)

> 以下即工作流 **模式 A（一次性构建）** 的最短路径；对应「先方案、后改造」的
> P0/P3——正式改造前仍建议先走 P1 出方案给用户审查。

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
| `buildenv` | 输出构建注入环境变量（真实构建 CC 包装器用） | `policy`, `root`, `protect_all` |
| `exportmap` | 由公共头文件生成链接版本脚本（导出收敛） | `path`, `out` |
| `verify` | 差分验证功能保持 | `artifacts` |
| `attack_sim` | 攻击模拟，产出 `eval_report.json`（`--allow-llm` 走真实 LLM 会话判定，见 [`docs/INSTALL.md`](docs/INSTALL.md)） | `artifacts`, `mode`, `allow_llm` |
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

## 收窄范围 / Scoping（只保护自有代码）

默认会保护扫描到的全部敏感资产。真实工程往往只想保护**自有敏感模块**，可用：

```sh
anti-rea scan /path/to/project --include src/common/crypto_algorithm --exclude contrib -o out
anti-rea plan out/asset_manifest.json --only-path 'src/common/crypto_*/*' --only-func '^crypto_' -o out
```

- `scan --include/--exclude`：限定扫描子路径；
- `plan --only-path`（路径 glob）/ `--only-func`（符号正则）：范围外的资产**被丢弃**，
  不进策略、不进白名单（免手改 YAML）；
- `protect --protect-all`：**整文件保护**——白名单取 scope 内文件**全部函数**（含
  `sm4_key_expand` 这类名字不含关键词的内部辅助函数），推荐与已收窄的 scope 搭配。

## 保护真实工程产物（`.so`/大型构建）——工作流模式 B

`protect` 只产出**独立可执行文件**，产不出 PG 扩展 `.so` 这类真实产物。此时用**构建注入**（工作流模式 B）：
把「clang + 变换插件」挂进原有构建（编译挂插件、链接透传），产出真正的 `.so`：
**不替换**目标工程的构建系统，也不替用户把改造跑完——按工作流 P1 先把注入点、
依赖安装与改动 diff 方案交给用户，再据其选择执行并固化为可复用的构建环境：

```sh
anti-rea buildenv out/protection_policy.yaml --root /path/to/project --protect-all -o out/scope.env
source out/scope.env
export CC=$PWD/integrations/cc-wrapper/anti-rea-cc
./configure ... && make -j"$(nproc)"
```

详见 [`docs/build-injection.md`](docs/build-injection.md)。

## Java / Android 项目——无 IR 变换，提供**选项菜单**

本技能对 Java **不做 IR 层变换**（字节码不经过 LLVM；ADR-006），但**不是没有手段**：
Java 侧的正确做法是按价值**分层选组合**。完整说明（原理 / 优点 / 缺点 / 影响 / 获取源 / 用法 /
验证方法论）见 [`docs/java-anti-rea.md`](docs/java-anti-rea.md)，机器可读清单见
[`docs/java-anti-rea-options.yaml`](docs/java-anti-rea-options.yaml)。九个选项（按"攻击方要多付出什么"排序）：

| ID | 手段 | 一句话 |
| :--- | :--- | :--- |
| J0 | 核心逻辑上服务端 | 唯一"逆到底也无产出"的路径；需联网 |
| J1 | 精简 + 名称混淆（ProGuard / R8 / yGuard） | 必做基线；单层对 REA 约小时级可读通 |
| J2 | 字符串/常数加密 + 控制流混淆（商用/自研） | 打掉 strings/常量锚点，逼攻击方转动态 |
| J3 | 类加密 + 自定义 ClassLoader（加壳） | 静态无字节码，必须运行期 dump |
| J4 | 字节码虚拟化（VMP 类） | Java 层单点成本最高；性能代价数十倍 |
| J5 | 下沉 native（JNI / JNA / Panama FFM） | 回到本技能主战场；产物可移植性丧失 |
| J6 | GraalVM native-image（整体 AOT） | 一次到位换赛道；闭世界配置 + 逐平台 |
| J7 | 运行期对抗（反调试/完整性/环境） | 与 J3/J4 协同，抬高动态 dump 成本 |
| J8 | 密钥与信任根 + 水印 | 密钥不落客户端；水印用于溯源 |

**用法**：这些手段**由用户选择**——Agent 在 **P1 方案**里按项目画像（是否联网、是否 Android、
能否改构建、价值等级）给出该文档 §1「选项总览」与 §3「组合阶梯」中的候选组合与取舍，
用户勾选后再按 **P3（模式 B 纪律：改构建文件先给 diff）** 落地。工具与商用产品
**不由本技能分发**，只记录**获取源与用法**。
Java 字节码的验证用反编译器（jadx / CFR / Vineflower）按该文档 §4 方法论执行；下沉到 native
的部分回流本技能 `verify` / `attack_sim`。

## 安全边界 / Safety & Limits (v1.0)

- **只加固你拥有的代码**。开放源码组件默认跳过（`allow_unknown_owner` 可覆盖）。
- 目标是**抬高成本**，不是「不可破解」。任何加固都可被有决心的分析者攻破。
- 变换引擎基于 LLVM Pass：支持 C/C++；Rust 仅 C/FFI 源、Python 仅 C 扩展。
  纯 Rust / Java / .NET / JS/TS 无 IR 层防护（ADR-006）；Java / Android 改用
  「选项菜单 + 方法论」（见上节与 `docs/java-anti-rea.md`）。
- 默认平台 Linux x86_64；其他平台可运行 scan/plan，protect 需自行验证。
- **不越权改造**：本技能只提供信息与方法论；对目标工程构建体系的任何修改
  （构建脚本、CI、环境）都须先经工作流 P1 出方案、用户审查后再动，且只改用户批准的项。
- 详细兼容性与实测结论见 `docs/release/`、`docs/INSTALL.md`。

## 进一步阅读 / See also

- `docs/INSTALL.md` — 安装、构建、环境变量、Docker。
- `docs/PROVISIONING.md` — **分级安装与按需获取**（装什么/何时装/不装什么、最小部署集、卸载）。
- `docs/java-anti-rea.md` — **Java / Android 反 REA 选项目录**（J0–J8 原理/优缺点/影响/获取源/验证方法论）。
- `docs/mcp-clients.md` — MCP 客户端配置（Claude Desktop / Cursor / 通用 stdio）。
- `examples/quickstart/` — 端到端可运行示例。
- `docs/FAQ.md`、`docs/troubleshooting.md` — 常见问题与故障排查。
- `skill.json` — 机器可读的 skill 清单。
- `README.md` / `README.zh-CN.md` — 项目总览（英 / 中）。
