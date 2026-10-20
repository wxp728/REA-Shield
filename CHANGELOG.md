# 变更记录（Changelog）

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### 分析（Rust IR 级加固可行性 spike）

- **新增 [`docs/analysis/rust-ir-spike.md`](docs/analysis/rust-ir-spike.md)**：实测 rustc 与引擎的
  LLVM 版本兼容性——stable `1.99.0`（LLVM 23.1.1）与 `1.82.0`（LLVM 19.1.1）的文本 IR/bitcode
  **均无法被 LLVM 18.1.8 读取**；`1.78.0`/`1.81.0`（LLVM 18）可跑通，CFF/MBA/不透明谓词功能等价，
  热循环 2000 万次 126.8 ms → 597.8 ms（4.7×），`.text` 642 B → 1612 B，`rename` 有效。
- **关键限制**：rustc 的 LLVM 命令行不注册 `-load-pass-plugin`（`-C llvm-args` 无效）、
  `-Z llvm-plugins` 仅 nightly；cargo 无对象替换/注入钩子，接管链接或 `no_std` 代价高；
  **字符串加密对 Rust 字面量不生效**（rustc 发成 `<{ [N x i8] }>` 结构包装，pass 只匹配
  `ConstantDataArray`；同一场景 C 代码正常清除）。
- **结论**：**不把 Rust 纯代码 IR 级支持纳入 v1.x**；维持“Rust 仅 C/FFI 源”的支持矩阵，
  敏感核心建议放 C/FFI（模式 B）。若需覆盖 Rust，优先做**菜单级 R0–R8**（文档+测试，不改引擎）。
  `SKILL.md` 限制一节与 `docs/STATUS.md` 文件地图已同步。

### 新增（技能改进 · .NET / Unity 反 REA 选项目录）

- **新增 [`docs/dotnet-anti-rea.md`](docs/dotnet-anti-rea.md)**：C# / F# / VB.NET（含 Unity、MAUI、Blazor、
  桌面/CLI/服务）的**反 REA 选项目录 D0–D8**——核心逻辑上服务端 / 裁剪+名称混淆 / 字符串与常数加密+
  控制流混淆 / 程序集加密+`AssemblyResolve` 加壳 / IL 虚拟化 / 下沉 native（P/Invoke、C++/CLI、函数指针）/
  NativeAOT 与 Mono AOT / 运行期对抗 / 密钥与水印。每种附**原理 / 效果 / 优点 / 缺点 / 影响 / 获取源与用法**，
  另附**组合阶梯**、**验证方法论**（ILSpy/ilspycmd、dnSpyEx、dotPeek、de4dot、ildasm、Il2CppDumper）、
  与 P0–P4 工作流的接线、许可与合规边界。明确两条易被误解的口径：**ReadyToRun 不算防护**（IL 仍在）、
  **单层混淆易被 de4dot 类工具还原**。
- **Unity / IL2CPP 特别路径**：说明 Mono 构建与普通 .NET 同风险；IL2CPP 虽去掉 IL，但
  `global-metadata.dat` 可被 Il2CppDumper 恢复；**IL2CPP 生成的 C++ 可经本技能构建注入按源文件/符号收窄加固**
  （实验性，需先在你的 Unity 版本上试点）。
- **机器可读清单**：新增 [`docs/dotnet-anti-rea-options.yaml`](docs/dotnet-anti-rea-options.yaml)
  （`options` / `combinations` / `unity` / `verification`），供 Agent 在 P1 方案里直接筛候选。
- **接线**：`skill.json` 新增 `dotnet_anti_rea`（`ir_transforms: false`、选项、Unity 说明、验证工具）与
  `guides`/`supported.languages.dotnet_note`；`SKILL.md` 新增「.NET / Unity 项目」一节并同步 P1/P4、
  T4、See also；`README(.zh-CN)`、`docs/STATUS.md`、`.agents/skills/anti-rea/SKILL.md` 同步；
  `tools/release.py` 的最小技能包与必查文件纳入两份新文档；**新增 `tests/test_dotnet_options.py`**
  （选项目录自洽性 + Unity 路径 + 文档口径 + 接线）。
- **勘查增强**：扫描器识别 `.fs`/`.vb`（`dotnet`）与 `.csproj`/`.sln`/`.fsproj`/`.vbproj` 构建标记
  （`core/scanner/scanner.py`，`build_system` 归入既有 `msbuild`），.NET 项目在 P0 即可得到正确语言/构建画像。
- **零成本复用说明**：`SKILL.md` 与 `docs/build-injection.md` 补充 **Android NDK 的 `.so` 直接走模式 B**、
  **Unity IL2CPP 生成的 C++ 回流本引擎**；`docs/java-anti-rea.md` 注明 **Kotlin / Scala 同属 JVM 菜单**。

### 新增（技能改进 · JS / TS 反 REA 选项目录）

- **新增 [`docs/js-anti-rea.md`](docs/js-anti-rea.md)**：浏览器 / Node / Electron / React Native / Tauri 的
  **反 REA 选项目录 JS0–JS8**——服务端化 / 打包+压缩+改名+不发 source map / 字符串与控制流混淆 /
  JS 字节码虚拟化 / 核心编译为 WebAssembly / 下沉 native（N-API、Electron 原生模块、TurboModule/JSI、
  Tauri）/ 分发形态加固（ASAR 完整性、Electron fuses、SEA、pkg、Hermes）/ 运行期对抗 / 密钥与水印。
  每种附**原理 / 效果 / 优点 / 缺点 / 影响 / 获取源与用法**，另附运行时画像、组合阶梯、
  验证方法论（js-beautify、webcrack、de4js、REstringer、wasm2wat、asar、hbctool）、
  与 P0–P4 的接线、许可与合规边界。
- **口径固定**：**压缩/混淆 ≠ 加密**；**ASAR 不是加密**；**Hermes / V8 字节码不是不可逆**；
  **生产环境绝不外发 source map**；单层 JS 混淆可被 webcrack/de4js 类工具还原。
- **机器可读清单**：新增 [`docs/js-anti-rea-options.yaml`](docs/js-anti-rea-options.yaml)
  （`options` / `combinations` / `runtimes` / `verification`）。
- **接线**：`skill.json` 新增 `js_anti_rea`（`ir_transforms: false`、选项、运行时、验证工具）与
  `guides`/`supported.languages.js_note`；`SKILL.md` 新增「JavaScript / TypeScript 项目」一节并同步
  P1/P4、T4、See also；`README(.zh-CN)`、`docs/STATUS.md`、`.agents/skills/anti-rea/SKILL.md` 同步；
  `tools/release.py` 的最小技能包与必查文件纳入两份新文档；**新增 `tests/test_js_options.py`**。

### 新增（技能改进 · Go 反 REA 选项目录）

- **新增 [`docs/go-anti-rea.md`](docs/go-anti-rea.md)**：**G0–G8**——服务端化 / 构建基线
  （`-trimpath -s -w`、去 buildinfo）/ 符号与路径混淆（garble）/ 字符串与控制流 /
  下沉 native（cgo、C 核心、`-buildmode=c-shared`）/ TinyGo 与 WASM（实验性）/ 分发形态
  （UPX、容器）/ 运行期对抗 / 密钥与水印。每种附原理/优缺点/影响/获取源，另附组合阶梯、
  验证方法论（`go tool nm`、`go version -m`、**GoReSym**、redress、Ghidra）、P0–P4 接线、许可边界。
- **口径固定**：**`-s -w` 不是保护**（`pclntab` 仍在，GoReSym 可恢复函数名/路径）；
  cgo 下沉 native 是 Go 最推荐的换赛道方式；UPX 可 `upx -d` 还原。
- **机器可读清单**：新增 [`docs/go-anti-rea-options.yaml`](docs/go-anti-rea-options.yaml)。
- **勘察增强**：扫描器识别 `.go`（`go`）与 `go.mod`（`build_system=go`）；schema 语言/构建枚举同步
  增加 `go`（并为后续 Dart 预留 `dart`/`pub`）。
- **接线**：`skill.json.go_anti_rea` / `guides` / `supported.languages.go_note`；`SKILL.md` 新增
  「Go 项目」一节并同步 P1/P4、T4、See also；`README(.zh-CN)`、`STATUS`、`.agents`、`release.py` 同步；
  **新增 `tests/test_go_options.py`** 与扫描器回归。

### 新增（技能改进 · 纯 Python 反 REA 选项目录）

- **新增 [`docs/python-anti-rea.md`](docs/python-anti-rea.md)**：**PY0–PY8**——服务端化 /
  分发基线（不带源码、`-OO`）/ 字节码加密与加壳（PyArmor 等）/ 源码级字符串与控制流 /
  编译为 C 扩展（Cython、mypyc、Nuitka）/ 下沉 native（ctypes/cffi/pybind11）/ 打包可执行
  （PyInstaller/PEX）/ 运行期对抗 / 密钥与水印。
- **口径固定**：`.pyc` **可反编译**、打包工具**可解包**、商用壳**有 unpacker**；
  纯 Python 静态防护**天花板很低**，优先 PY0（服务端）或 PY5（native 下沉）。
  Python **C 扩展**仍走既有 native 链路，能力不变。
- **机器可读清单**：新增 [`docs/python-anti-rea-options.yaml`](docs/python-anti-rea-options.yaml)
  （含 pycdc/decompyle3/pylingual/pyinstxtractor-ng 验证方法论）。
- **接线**：`skill.json.python_anti_rea` / `guides` / `supported.languages.python_note`；
  `SKILL.md` 新增「纯 Python 项目」一节并同步 P1/P4、T4、See also；`README(.zh-CN)`、`STATUS`、
  `.agents`、`release.py` 同步；**新增 `tests/test_python_options.py`**。

### 变更（文档 / PoC 去本地化）

- 清掉入库文件中残留的本机绝对路径（`/opt/<toolchain>`、`/home/<user>` 等），**不改变任何验证结论**：
  `docs/STATUS.md` §7 安装位置改占位符；`docs/design/ddd/dd-09-test-plan.md` 工具链前缀占位化；
  `docs/release/doc-verification.md` 命令改 `python3.11` / `<out>` 占位（并修 `tools/run_s4.py`：
  生成该文档时自动替换解释器与输出目录，避免下次再写入本机路径）；
  `examples/quickstart/run.sh`、`pilots/python-ext/README.md` 改用 PATH 中的 Python；
  `poc/poc2-ghidra-headless/run.sh` 的 Ghidra/JDK/Python 改**通用探测**（环境变量 > 常见位置，
  含 `/opt/*/ghidra_*`、`$HOME/.local/...`）；`poc/setup_env.sh` 默认前缀改为
  `$HOME/.local/anti-rea-toolchain`（免 sudo，可用 `PREFIX=` 覆盖）。
- 复核：`git grep` 已无本机绝对路径（工具链安装前缀、用户主目录等）；单测 135 例、
  `ci/ci.sh` 8/8 全绿。

### 变更（技能改进 · 分级安装 / 按需获取，不打包第三方）

- **新增 [`docs/PROVISIONING.md`](docs/PROVISIONING.md)**：安装与按需获取策略——**本技能只交付自己的源码**，
  第三方工具/商用产品**不打包、不预装、不代下载**，只记录获取源与用法。定义 **T0 核心（必装，最小）/
  T1 原生变换 / T2 语言与平台 / T3 可选增强 / T4 永不下发** 五档及**触发条件**，附"安装会下载什么"对照表、
  **最小部署集**（哪些文件不必下发）、Agent 侧纪律（省 token）、与 P0–P4 工作流的接线、卸载回退，以及
  **C/C++（原生）侧审查结论**（原生侧从不打包第三方；插件由本仓库源码本地编译；仅 `Dockerfile` 在镜像
  构建期联网取 Debian 包，属可选容器路径）。
- **依赖拆分（降部署代价）**：`requirements.txt` 收敛为**核心**（`jsonschema` + `PyYAML`）；
  新增 [`requirements-optional.txt`](requirements-optional.txt) 承载**按需**依赖 `deap`（会连带 numpy，
  仅 `anti-rea evolve` 需要）——`deap` 从硬依赖改为**可选 extra**（`pyproject.toml` 增 `evolve` extra，
  代码里本就惰性导入）；`Makefile` 增 `install-extras` 目标；`Dockerfile` 增 `ARG WITH_EXTRAS`（默认不装）。
- **`anti-rea doctor` 分级化**：每项自检带 `tier` / `when`（何时需要），报告中 **T0 在前、按需项分组显示
  并解释"何时需要 / 怎么装"**；新增 `--tier T0|T1|T2|T3` 只看某一档；新增自检项 `rust-cargo`、`node-npm`、
  `container-runtime`、`ghidra`、`llm-egress`（均为按需、不阻塞）。缺 T1/T2/T3 **不影响** `scan`/`plan`。
- **最小技能包**：`python tools/release.py --skill <dir>` 产出 `anti-rea-skill-<ver>.tar.gz` +
  `SKILL-FILES.txt`（只含运行与接线所需文件；`tests/`、`ci/`、`poc/`、`pilots/`、`benchmarks/`、
  设计/审计文档不下发）。`tools/release.py` 自检必查文件增 `requirements-optional.txt`、`docs/PROVISIONING.md`。
- **接线**：`SKILL.md`（前置条件改为分级表 + 新增「安装与按需获取」一节，P0/P1 按档说明"现在就装/选定
  模式后再装/用到才装"、See also、frontmatter description）、`skill.json`（新增 `provisioning`（tiers /
  deferral_rules / commands）与 `deploy`（minimal / add_for_protect / optional / dev_only_not_shipped /
  bundle_cmd））、`docs/INSTALL.md`（重构为 §0 分级安装策略 + 依赖表增"分级"列 + T1 按需说明 + 卸载回退）、
  `docs/FAQ.md`（新增「安装这个 skill 会下载什么？可以只装一部分吗？」）、`README.md` / `README.zh-CN.md`、
  `docs/STATUS.md`、`.agents/skills/anti-rea/SKILL.md`。
- **新增测试** [`tests/test_provisioning.py`](tests/test_provisioning.py)（20 例）：tiers/deploy 结构与自洽、
  核心依赖不含 `deap`、`doctor` 分级与 `--tier` 过滤、最小技能包不含开发材料、文档接线。
- **顺带修正（与"不提交本地环境信息"一致）**：工具链兜底搜索路径由写死的本机目录改为通用通配
  （`core/toolchain.py`、`Makefile`、`ci/ci.sh`、`integrations/anti-rea`、`core/verify/independent.py`
  的 Ghidra 定位），**行为不变**、换机更稳。

### 变更（技能改进 · Java / Android 反 REA 选项目录）

- **新增 [`docs/java-anti-rea.md`](docs/java-anti-rea.md)**：Java / Android 的**反 REA 选项目录**
  （J0–J8，按"攻击方要多付出什么"排序）——核心逻辑上服务端 / 精简+名称混淆（ProGuard、R8、
  yGuard）/ 字符串与常数加密+控制流混淆（Zelix KlassMaster、Allatori、DashO，或 ASM/ByteBuddy 自研）/
  类加密+自定义 ClassLoader 加壳 / 字节码虚拟化（VMP 类）/ 下沉 native（JNI、JNA、Panama FFM）/
  GraalVM native-image / 运行期对抗 / 密钥与信任根+水印。每项给出**原理、优点、缺点、影响
  （性能、体积、构建、可移植性、兼容性）、获取源与用法要点**，并附**按场景的组合阶梯**与
  **反编译器验证方法论**（jadx / CFR / Vineflower / Procyon / javap / apktool）。
- **机器可读清单**：新增 [`docs/java-anti-rea-options.yaml`](docs/java-anti-rea-options.yaml)
  （options / combinations / verification），供 Agent 在 P1 方案里组装"菜单"。
- **接线**：`SKILL.md` 何时使用、P1 方案（第 6 条：语言特定可选手段）、新增「Java / Android 项目
  ——无 IR 变换，提供选项菜单」一节、安全边界与 See also；`skill.json` 增 `java_anti_rea` 与 `guides`；
  `.agents/skills/anti-rea/SKILL.md`、`README.md` / `README.zh-CN.md`、`docs/FAQ.md` 同步；
  `docs/analysis/rea-threat-analysis.md` §2 增 Java/Android（REA 的 JEB/apktool provider）交叉引用。
- **边界**：第三方工具与商用加固产品**不由本技能分发**，只记录获取源与用法；Java 字节码的
  `verify`/`attack_sim` **不适用**（本技能提供方法论，不代跑），下沉 native 的部分仍走本技能常规链路。

### 变更（S7 首轮 · 条件项补测）

- **实战红队验证闭环**：对某真实生产 C 工程（约 10 万行 / 59 编译单元 / Linux x86_64 `.so`，
  经构建注入全范围保护）完成独立 LLM 会话红队 + Ghidra 交叉验证——内部符号 0 残留、
  特征字符串 -98%、整库指令 5.4×、核心函数反编译失败、函数名恢复 0.00，**源码级泄漏被阻断**；
  记录见 `docs/release/s7-field-report.md`，README 增「实战验证」小节（匿名化）。
- **NFR-02「Token 倍数 ≥ 100x」子项废弃**：两轮实测恒 ≈1.0，评估认定该指标在固定单轮提示
  协议下不可测且与防护效果解耦，不再作为验收门禁（保留「上下文消耗 ≥90% 未成功即通过」
  会话判定子项）；`docs/requirements/rtm.md` / `docs/STATUS.md` / `docs/release/RELEASE-1.0.0.md`
  已同步标注（SRS 条目内容未改，需求已基线）。

### 变更（技能改进 · 分阶段改造工作流）

- **SKILL.md 新增「工作流：先方案、后改造」**：P0 勘察（只读，含目标工程**构建画像**）
  → P1 改造方案（模板化产出 `out/PROPOSAL.md`，**交用户审查**）→ P2 用户选执行模式
  （**A 一次性构建 / B 改造构建架构 + 防 REA 构建环境 / C 先 A 后 B**）→ P3 执行
  （模式 B 含各构建体系注入点方法论：autoconf/Make/CMake/Meson/Cargo/node-gyp/Bazel/
  自研脚本；改构建文件先给用户看 diff）→ P4 验证交付。
- **定位声明**：技能只提供信息 + 方法论 + 命令，**不自动修改目标工程构建体系**、
  不替用户把改造跑完；依赖安装清单（技能侧 + 工程侧）纳入 P1 方案。
- `skill.json` 增 `workflow`（phases/modes/principle）与模式 B 的 quickstart 提示；
  `.agents/skills/anti-rea/SKILL.md` TL;DR 同步；`docs/build-injection.md` 顶部
  加工作流指引（模式 B 动手前先 P0–P2）。

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
