# FAQ（常见问题）

## 这个项目到底是什么？是"skill"吗？

是。REA-Shield 是一套 **AI Agent 可调用的代码加固工具链**：
- 技能入口：[`../SKILL.md`](../SKILL.md)、机器可读清单 [`../skill.json`](../skill.json)；
- 命令行：`anti-rea`（scan/plan/protect/verify/report/attack_sim/…）；
- MCP Server：`anti-rea-mcp`（stdio JSON-RPC，7 个工具），供上层 Agent 调用。

它不是一个「贴进 prompt 就能用」的纯提示词包，而是**要安装、构建、接线**的软件——
但已经把「上手成本」压到：`pip install -r requirements.txt` → `anti-rea doctor`
→ `make build`（或用 Docker 一步到位）。

## 会不会去攻击/破解别人的软件？

不会。本工具链只对你**拥有或有权修改**的代码施加**加固**（间接反制），
不包含任何针对 REA 工具的破坏能力。扫描器默认跳过开放源码组件，
所有权不明时拒绝执行（`E_REFUSED`）。

## 支持哪些语言？

- **可施加 IR 层变换**：C、C++；Rust 仅 C/FFI 源（经 Cargo 集成）；
  Python 仅 C 扩展（经 setup.py 集成）。
- **可扫描、但不做 IR 变换**：纯 Rust、Java、.NET/C#、JS/TS、纯 Python、Go、Dart。
- **产物级菜单**：WASM（`.wasm` 是编译目标，不是源语言）。

不做 IR 变换的语言/产物，本技能提供**可选的选项目录**（由用户在 P1 方案里选组合）：

| 语言 / 产物 | 菜单 | 人读指南 | 机器可读清单 |
| :--- | :--- | :--- | :--- |
| Java / Android | J0–J8 | [`java-anti-rea.md`](java-anti-rea.md) | [`java-anti-rea-options.yaml`](java-anti-rea-options.yaml) |
| .NET / Unity | D0–D8 | [`dotnet-anti-rea.md`](dotnet-anti-rea.md) | [`dotnet-anti-rea-options.yaml`](dotnet-anti-rea-options.yaml) |
| JavaScript / TypeScript | JS0–JS8 | [`js-anti-rea.md`](js-anti-rea.md) | [`js-anti-rea-options.yaml`](js-anti-rea-options.yaml) |
| Go | G0–G8 | [`go-anti-rea.md`](go-anti-rea.md) | [`go-anti-rea-options.yaml`](go-anti-rea-options.yaml) |
| 纯 Python | PY0–PY8 | [`python-anti-rea.md`](python-anti-rea.md) | [`python-anti-rea-options.yaml`](python-anti-rea-options.yaml) |
| Dart / Flutter | DA0–DA8 | [`dart-anti-rea.md`](dart-anti-rea.md) | [`dart-anti-rea-options.yaml`](dart-anti-rea-options.yaml) |
| WebAssembly 产物 | W0–W8 | [`wasm-anti-rea.md`](wasm-anti-rea.md) | [`wasm-anti-rea-options.yaml`](wasm-anti-rea-options.yaml) |

原因：变换引擎是 LLVM Pass，只处理 **LLVM IR**；Java 字节码、.NET CIL、JS 源码、
Go/Dart 的原生编译都不经过本插件的 LLVM IR（ADR-001）。SRS 中的语言清单是
「扫描/识别范围」，不等于「变换范围」；引擎级新增语言属 SRS 范围外，须用户确认。

## Java / Android 项目怎么办？有防逆向手段吗？

有，而且不止一种——只是**不在字节码层做 LLVM 变换**。Java/Android 项目请见
[`docs/java-anti-rea.md`](java-anti-rea.md) 的**选项目录**（机器可读：
[`docs/java-anti-rea-options.yaml`](java-anti-rea-options.yaml)）：J0 核心逻辑上服务端、
J1 精简+名称混淆（ProGuard/R8/yGuard）、J2 字符串/常数加密+控制流混淆、J3 类加密+自定义
ClassLoader 加壳、J4 字节码虚拟化（VMP 类）、J5 下沉 native（JNI/JNA/Panama FFM，可再用
本技能加固）、J6 GraalVM native-image、J7 运行期对抗、J8 密钥与信任根+水印。每种都给了
**原理、优点、缺点、影响（性能/体积/构建/可移植性/兼容性）与工具获取源**，由你按场景与
预算**选择组合**（第三方工具与商用加固产品**不由本技能分发**，只记录获取源与用法）。

验证提醒：本技能 `verify`/`attack_sim` 面向 **LLVM 原生产物**，**不适用于 Java 字节码**——
Java 侧用反编译器（jadx / CFR / Vineflower）按该文档 §4 的方法论执行；下沉到 native 的部分
回流本技能常规链路。

## .NET / JS / Go / 纯 Python / Dart / WASM 怎么办？

同样有菜单，工作流与 Java 一致：P0 勘察 → P1 把候选组合、代价与验证方法写进方案 →
用户选定 → 再落地。对应文档见上表；几个最容易踩的坑先列在这里：

- **.NET / Unity**：CIL 元数据近乎源码；`.NET` 的 NativeAOT、Unity 的 IL2CPP 会把 C++ 产物
  回流本引擎（D0–D8，见 [`dotnet-anti-rea.md`](dotnet-anti-rea.md)）。
- **JS / TS**：压缩/改名不是保护；**source map 不得随包发布**；核心可下沉 WASM/native
  （JS0–JS8，见 [`js-anti-rea.md`](js-anti-rea.md)）。
- **Go**：`-s -w` 后 `pclntab` 仍可恢复函数名/路径；优先 garble + cgo 下沉
  （G0–G8，见 [`go-anti-rea.md`](go-anti-rea.md)）。
- **纯 Python**：`.pyc` 可反编译，打包也可解包；优先上服务端或 C 扩展/native
  （PY0–PY8，见 [`python-anti-rea.md`](python-anti-rea.md)）。
- **Dart / Flutter**：不要发 debug/profile 包（`kernel_blob.bin` 就是 kernel），不要发
  `--split-debug-info` 符号；`--obfuscate` 只改名（DA0–DA8，见
  [`dart-anti-rea.md`](dart-anti-rea.md)）。
- **WASM**：不能对宿主保密；`strip` 只是基线，W2/W4 的 wasm32 IR 变换仍是**实验性**，
  W5 宿主 native 下沉通常更划算（W0–W8，见 [`wasm-anti-rea.md`](wasm-anti-rea.md)）。

## 支持哪些平台？

v1.0 **完整实测**：Linux x86_64。`scan`/`plan` 在任何能跑 Python 的平台都可用；
`protect`/`verify` 需要已构建的 LLVM 插件，其他平台（含 Windows）请用
Docker 或 WSL。见 `docs/release/compatibility-matrix.md`。

## 为什么 `protect` 说找不到 clang？

因为 `protect` 需要 LLVM/clang。先跑 `anti-rea doctor` 看缺什么。修复方式：

```sh
export ANTI_REA_LLVM=/usr/lib/llvm-18     # 指向你的 LLVM 前缀
# 或把 LLVM 的 bin 加进 PATH
```

工具链路径**已不再写死**，按「环境变量 > PATH > 常见目录」自动探测。

## 安装这个 skill 会下载什么？可以只装一部分吗？

可以，而且**默认就是最小安装**——本技能**只交付自己的源码**，第三方工具一律不分发，
只记录获取源与用法。按需分档（详见 [`PROVISIONING.md`](PROVISIONING.md)）：

- **T0 核心（必装，最小）**：`pip install -r requirements.txt`（只装 `jsonschema` + `PyYAML`，
  数 MB），够跑 `scan`/`plan`/`doctor`/`report`；
- **T1 原生变换**：要 `protect`/`verify`/`attack_sim` 时，自行安装 LLVM/clang 18、CMake、
  binutils，再 `make build`（本技能不分发这些系统组件）；
- **T2 语言与平台**：按目标语言/构建体系选装（rustc+cargo、node+npm、JDK/Android SDK 用工程自带、
  Go 工具链、Dart/Flutter SDK、wasm32 目标与 wabt、容器）；
- **T3 可选增强**：只在用到时（Ghidra+PyGhidra 独立验证、`deap`→`pip install -r
  requirements-optional.txt`、LLM 红队端点）；
- **T4 永不下发**：Java/.NET/JS/Go/纯 Python/Dart/WASM 的第三方加固、混淆、反编译与验证工具/
  商用产品（各菜单只记录获取源与用法）。

只看最小集：`anti-rea doctor --tier T0`。**只把技能装到别的项目**（不带测试/开发材料）：
`python tools/release.py --skill dist`。缺 T1/T2/T3 **不阻塞** `scan`/`plan`。

## 需要联网/LLM 吗？

核心闭环**不需要**。`attack_sim` 在没有真实 LLM 会话时自动降级为
`static_only`（静态代理指标）。接入真实 LLM 会话是可选能力，通过
`ANTI_REA_LLM_CMD`（外部命令）或 `ANTI_REA_LLM_ENDPOINT` 等环境变量配置，
且必须显式 `--allow-llm` 才出站。

## 加固后是不是就"不可逆向"了？

不是，也不追求这个。威胁模型是「把逆向成本抬高到高于收益」。任何加固都可被
有决心、有资源的分析者攻克。请把它当作**提高门槛**的手段，而非绝对保护。

## 会拖慢程序吗？

会，但受**性能预算**约束（NFR-01）：P0 增量开销 ≤ 0.40、P1 ≤ 0.15、
P2/P3 ≤ 0.05（相对基线）。`verify` 会实测并判定是否超预算。

## 产物在哪 / 怎么判断"加固成功"？

`protect` 产出到 `-o` 指定目录：`artifacts/baseline`（未加固）、
`artifacts/protected`（加固后）、`artifacts/transform.log`、`protection_policy.yaml`。
`verify` 判断功能是否保持 + 开销是否达标；`attack_sim` 给出逆向成功率等评估。

## Wheel 安装后报找不到 schemas/policies？

wheel 是次要件。数据契约与策略模板随仓库分发，wheel 安装后请设置
`ANTI_REA_ROOT` 指向含 `schemas/`、`policies/` 的目录，或直接用**全仓自包含包**
`anti-rea-<ver>-bundle.tar.gz`（主产物）。

## 还有问题？

见 [`troubleshooting.md`](troubleshooting.md)（按错误码/现象排障），
或在仓库提 Issue（`.github/ISSUE_TEMPLATE/`）。
