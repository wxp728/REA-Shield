# Dart / Flutter 反 REA 选项目录（供用户选择）

> **状态**：使用指南（**非**需求基线；不修改 `SRS.md`）。
> **定位**：本技能对 Dart **不做 IR 层变换**（Flutter 用 Dart AOT，不经过 LLVM；ADR-001）。
> 对 Flutter 应用、Dart CLI/服务，本文提供**一张选项菜单 + 每种的原理 / 优点 / 缺点 / 影响 +
> 获取源与用法要点**，由 Agent 按 `SKILL.md` 的分阶段工作流在 **P1 方案**里呈现给用户，
> **用户选定后再落地**。
> **边界**：第三方工具与商用产品**不由本技能分发**；目标仍是“**抬高成本**”。

## 0. 为什么 Dart / Flutter 需要单独一张菜单

| 事实 | 含义 |
| :--- | :--- |
| Flutter **release** 把 Dart AOT 编译进 `libapp.so`（Android）或 App 主二进制（iOS） | 不是字节码，但仍保留**快照元数据、对象池、字符串常量** |
| **debug/profile** 产物包含 `kernel_blob.bin`（Dart kernel）或 snapshot data | **误发 debug 包等于直接发源码**；这是最常见的事故 |
| `--obfuscate` **只重命名 Dart 标识符**，不隐藏字符串/常量/逻辑 | 反编译工具仍能恢复结构；字符串仍可 `strings` |
| `--split-debug-info` 生成**符号映射**，用于还原崩溃栈 | 映射文件**绝不能随包发布**；否则 `--obfuscate` 的效果被抵消 |
| Flutter 逆向工具（如 **blutter**）可针对 `libapp.so` + `libflutter.so` 恢复类/函数名与伪代码 | 未混淆的 release 包**接近可读**；混淆后名字失真但结构仍在 |
| Flutter 引擎（`libflutter.so`）是通用产物，可被替换/重打包（如 reFlutter） | 不要依赖“引擎完整性”作为唯一防线 |
| Dart AOT **不支持 `dart:mirrors`** | 按名反射的风险较低；但 JSON/序列化按字段名查找仍受影响 |
| 根本约束：**AOT 代码必须在设备上可执行**，密钥不能安全地藏在客户端 | 纯客户端方案只能抬高成本；高价值逻辑应服务端化或下沉 native |

因此 Dart/Flutter 侧的正确做法是：**先把构建基线做对**（release + 混淆 + 不发符号），
再按价值选择**native 下沉**或**服务端化**。下面 DA0–DA8 按“攻击方要多付出什么”排列。

> **零成本复用**：Flutter 的 **`dart:ffi`** 原生库、Android host 的 Java/Kotlin、iOS 的
> Objective-C/Swift、以及 C/C++/Rust 编译出的 **WASM**，都可以回到本技能的 native 链路。
> 把核心算法/授权放到这些位置，比在 Dart 层堆混淆更划算。

## 1. 选项总览

| ID | 手段 | 攻击方要多做的 | 效果量级 | 主要代价 | 产物可移植性 | 本技能是否带工具 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DA0** | 核心逻辑上服务端 | 逆到底也只能拿到协议调用 | 最高（可做到\"无产出\"） | 需联网、延迟、服务端成本 | 不变（客户端变薄） | 否（架构实践） |
| **DA1** | 构建基线（release AOT + `--obfuscate --split-debug-info`） | 失去可读符号与调试信息 | 低～中（**必做**） | 崩溃栈需私有映射；构建流程改造 | 不变 | 否（Flutter 工具链） |
| **DA2** | 字符串/常量处理（Dart 层代码生成） | 失去明文锚点 | 低～中 | 自研生成器；可读性/性能 | 不变 | 否（自研） |
| **DA3** | 控制流/自定义虚拟机（Dart 层，高风险） | 重建语义成本高 | 中（工具少、风险高） | 自研维护、性能、稳定性 | 不变 | 否（自研） |
| **DA4** | 下沉 native（`dart:ffi` / platform channel / 原生插件） | 回到 native 逆向（可用本技能加固） | 高 | FFI/channel 开销、逐平台产物、调试 | **丧失**（每平台一份） | **是**（加固 native 侧） |
| **DA5** | Web 目标（dart2js / dart2wasm） | 换一套工具链（按 JS/WASM 处理） | 中 | Web 运行时/体积/兼容性 | 部分 | 仅 WASM/JS 源侧 |
| **DA6** | 平台完整性（Play Integrity / App Attest / root·越狱检测） | 伪造环境/绕过证明 | 辅助（服务端联动才有效） | 平台依赖、误杀、运维 | 不变 | 否 |
| **DA7** | 运行期对抗（Dart 侧反调试/完整性） | 动态分析变贵 | 辅助（较弱） | 易被 patch、误杀 | 不变 | 否 |
| **DA8** | 密钥与信任根 + 水印 | 拿不到可用密钥 | 辅助 | 服务端/硬件依赖 | 不变 | 否 |

> **最重要的一句话**：**不要发 debug/profile 包**。Flutter debug 产物里的 `kernel_blob.bin`
> 就是 Dart kernel，拿到它基本等于拿到源码；这比任何混淆都关键。

## 2. 选项详解

### DA0 · 核心逻辑上服务端

- **原理**：授权、密钥运算、核心算法、风控放服务端 API，客户端只保留调用与展示。
- **优点**：唯一能让\"逆到底也没有产出\"的路径；密钥不进客户端；不受 Dart 快照可读性约束。
- **缺点**：需联网、有延迟与服务端成本；离线 App、内网环境不可用。
- **影响**：架构改造量最大；可用性/SLA 成为新的失败点；协议仍可被观察与重放。
- **获取源**：无工具，工程实践。客户端可再用 DA1/DA4 保护签名校验与协议逻辑。
- **适用判据**：产品本就要联网、核心价值可服务化。

### DA1 · 构建基线（release AOT + `--obfuscate --split-debug-info`）

- **原理**：只发 release（Android/iOS/desktop）AOT 产物；构建时启用
  `flutter build <target> --obfuscate --split-debug-info=<私有目录>`；
  确保 `kernel_blob.bin`、`vm_snapshot_data`、`isolate_snapshot_data` 等调试产物**不在发布包**；
  Android host 开启 R8/资源压缩；Web 不发 source map。
- **效果**：Dart 标识符不可读、无调试信息；**字符串常量仍在对象池**，逻辑结构仍可被工具恢复。
- **优点**：官方支持、成本低；是所有 Flutter 项目的发布底线。
- **缺点**：单层不是保护；`--obfuscate` 不做字符串加密；符号映射丢失会导致崩溃栈不可读；
  某些插件/序列化依赖名字时需要验证。
- **影响**：CI 增加符号归档（私有）；崩溃分析流程要接入 `--split-debug-info` 产物；
  包体略变；`--obfuscate` 与部分代码生成/反射式框架需回归。
- **获取源**：Flutter 官方（`https://docs.flutter.dev/deployment/obfuscate`）。
- **适用判据**：**所有 Flutter 项目**；先做 DA1，再谈其它。

### DA2 · 字符串/常量处理（Dart 层代码生成）

- **原理**：在生成 Dart 代码时拆分/编码字符串、延迟拼接、把常量转为计算值；
  可用 build_runner 生成器或自研 AST 工具（`analyzer` 包）。
- **效果**：`strings` 与关键字检索失效；静态阅读变难。
- **优点**：无需引入运行时；可按模块/资源粒度启用；与 DA1 叠加。
- **缺点**：Dart 生态缺少成熟的开源字符串/控制流混淆器；自研需维护 analyzer/生成器；
  AOT 常量折叠可能把拼接重新折叠（需动态屏障）；对性能与可读性有影响。
- **影响**：构建期增加代码生成；调试/日志可读性下降；需回归热重载与代码生成链。
- **获取源**：自研（`package:analyzer`、`build_runner`）；商用 Flutter 加固产品较少。
- **适用判据**：只对少量关键字符串/接口路径/协议字段；必须做性能与功能回归。

### DA3 · 控制流/自定义虚拟机（Dart 层，高风险）

- **原理**：把关键函数改写为状态机/解释器循环，或把字节码/指令表放进 Dart 数据，
  运行期解释；目标是打掉调用图与可读控制流。
- **效果**：静态阅读与自动反编译成本显著上升。
- **优点**：不依赖第三方壳；可按函数粒度。
- **缺点**：**性能损失大**；Dart AOT 的内联/优化可能干扰；实现与维护成本高；
  仍可被动态跟踪还原；容易引入稳定性问题。
- **影响**：需要专门的代码生成/验证流程；热路径可能不可用；调试困难。
- **获取源**：自研；参考通用控制流平坦化/VM 保护思路，但**没有**成熟的 Dart 开源实现。
- **适用判据**：仅用于极小范围的高价值函数，且能接受性能与维护成本。

### DA4 · 下沉 native（`dart:ffi` / platform channel / 原生插件）

- **原理**：核心用 C/C++/Rust 实现为共享库，Dart 通过 `dart:ffi` 调用；
  或通过 platform channel / 原生插件调用 Android/iOS 原生代码；C/C++ 侧用本技能做 IR 变换。
- **效果**：核心不再以 Dart 形式存在，回到 native 战场，可用本技能全套手段。
- **优点**：防护强度最高；性能好（FFI 批量调用）；可复用到 Android/iOS/desktop。
- **缺点**：FFI 调用有固定开销（热循环内逐次调用会明显变慢）；platform channel 是异步且更重；
  每平台/架构各编一份；跨语言调试困难；native 崩溃会杀掉 App。
- **影响**：构建矩阵（Android ABI × iOS arch × desktop）与 CI 变重；需要设计**批量化边界**；
  发布物包含原生库，签名/公证/上架审核要覆盖。
- **获取源**：`dart:ffi`（`https://dart.dev/guides/libraries/c-interop`）、Flutter platform channels、
  `ffigen`；C 侧用本技能。
- **适用判据**：加密/授权/协议/算法核心；**Flutter 项目最推荐的换赛道方式**。

### DA5 · Web 目标（dart2js / dart2wasm）

- **原理**：Flutter Web / Dart Web 把代码编译为 JS（dart2js）或 WASM（dart2wasm/WasmGC）。
- **效果**：产物形态改变，按 **JS 菜单（JS0–JS8）** 或 **WASM 菜单（W0–W8）** 处理。
- **优点**：可复用 Web 侧的分发/完整性手段；WASM 有一定结构隐藏效果。
- **缺点**：**JS/WASM 都可反编译**；Flutter Web 体积大、性能与平台能力受限；
  `dart2wasm` 的浏览器/运行时兼容性需验证。
- **影响**：需要维护 Web 构建链；source map/调试符号绝不能发布；性能回归。
- **获取源**：`dart compile js`、`dart compile wasm`、`flutter build web`。
- **适用判据**：产品本就有 Web 形态；否则不要把桌面/移动逻辑迁到 Web 只为“加固”。

### DA6 · 平台完整性（Play Integrity / App Attest / root·越狱检测）

- **原理**：Android 用 Play Integrity API，iOS 用 App Attest/DeviceCheck，把“运行环境可信”
  的证明交给服务端校验；辅以 root/越狱/模拟器/hook 框架检测。
- **效果**：提高批量伪造/改包/自动化的成本；**必须服务端联动**才有意义。
- **优点**：平台官方能力、可审计；与 DA0 天然配合。
- **缺点**：依赖 Google/Apple 服务与网络；存在误杀（定制 ROM、企业设备、CI）；
  检测可被绕过；隐私与合规需评估。
- **影响**：服务端要接验证链；失败策略（降级/拒绝）要设计；测试矩阵变大。
- **获取源**：Play Integrity API、App Attest/DeviceCheck 官方文档；root/越狱检测可自研或用商用 SDK。
- **适用判据**：有服务端、能接受平台依赖的商用 App。

### DA7 · 运行期对抗（Dart 侧反调试/完整性）

- **原理**：检测调试器/附加、校验关键资源/自身哈希、检测 hook/重打包；异常时降级或退出。
- **效果**：抬高动态分析成本（与 DA1/DA4 协同）。
- **优点**：与静态手段正交；实现成本相对低。
- **缺点**：Dart 侧能做的检测有限，**很容易被 patch**；Flutter 引擎可被替换；
  误报伤合法用户/CI；对静态阅读无效。
- **影响**：启动/运行开销；需要误杀救济；测试与灰度复杂。
- **获取源**：自研 + 平台原生检测（放 Android/iOS 侧更可靠）；商用加固 SDK。
- **适用判据**：只作为辅助层；高价值逻辑应已在 DA4 或服务端。

### DA8 · 密钥与信任根 + 水印

- **原理**：密钥不进客户端（服务端签发/KMS/HSM）；需要本地保存时用 Android Keystore /
  iOS Keychain（配合 Secure Enclave/StrongBox 能力）；水印用于溯源。
- **效果**：代码被逆也拿不到可用密钥；泄露可追踪。
- **优点**：让攻击产出不可直接用；平台密钥存储有硬件-backed 选项。
- **缺点**：需服务端/硬件；离线场景受限；客户端最终要使用明文密钥时仍有内存抓取风险。
- **影响**：密钥生命周期与轮换；合规成本；生物识别/设备解锁策略。
- **获取源**：Android Keystore、iOS Keychain/Secure Enclave、云 KMS/HSM、商用许可证服务。
- **适用判据**：只要还发密钥到客户端，就应优先处理。

## 3. 组合阶梯（按场景推荐）

| 场景 | 建议组合 | 说明 |
| :--- | :--- | :--- |
| 所有 Flutter 项目 | **DA1** | release + `--obfuscate --split-debug-info`；不发 debug 包/符号 |
| 商用 App（有服务端） | **DA1 + DA6 + DA8** | 平台完整性 + 密钥不落客户端 |
| 高价值离线 App | **DA1 + DA4 + DA7 + DA8** | 核心下沉 native（本技能加固）+ 运行期对抗 |
| 含关键字符串/协议 | **DA1 + DA2（+DA3 小范围）** | 先做字符串，控制流只用于极小范围 |
| Flutter Web / 多端 | **DA1 + DA5** | Web 侧按 JS/WASM 菜单处理 |

> 选择原则：**先消除\"误发 debug 包\"和\"发符号文件\"**；这两件事的收益远大于任何 Dart 层混淆。
> 然后优先 **DA4（native 下沉）** 或 **DA0（服务端）**，Dart 层混淆只作补充。

## 4. 验证方法论（自证防护有效）

**攻击方视角工具**（自行获取）：

| 工具 | 许可 | 获取源 | 用途 |
| :--- | :--- | :--- | :--- |
| **blutter** | 见仓库 | `https://github.com/worawit/blutter` | 从 `libapp.so` + `libflutter.so` 恢复 Dart 类/函数与伪代码 |
| **reFlutter** | 见仓库 | `https://github.com/Impact-I/reFlutter` | 重打包 Flutter 引擎做流量/运行分析（检验引擎可替换性） |
| **unzip / apktool** | Apache-2.0 | 系统/官方 | 检查 APK 内是否残留 `kernel_blob.bin`、符号、调试资源 |
| **strings / nm / objdump** | binutils | 系统包 | `libapp.so` 字符串/符号线索 |
| **Ghidra / IDA** | Apache-2.0 / 商用 | 官方 | 原生库反编译（DA4） |
| **jadx / apktool** | Apache-2.0 | 官方 | Android host（Java/Kotlin）检查 |

**流程**：

1. 解包发布物，确认**没有** `kernel_blob.bin`、`vm_snapshot_data`、`isolate_snapshot_data`、
   `*.symbols`、source map、调试配置；
2. 对 `libapp.so` 跑 `strings`/`nm`，再用 **blutter** 恢复类/函数/伪代码，统计**可读率**；
3. 对比 `--obfuscate` 前后：名字是否失真、字符串是否仍明文、结构是否仍可重建；
4. 用 reFlutter 检验引擎替换/重打包难度（说明“引擎完整性”不能当唯一防线）；
5. DA4 的 native 部分改用 `strings`/`nm`/`objdump` + 本技能 `verify` / `attack_sim`；
6. 记录\"逆到底得到了什么\"（可用算法/密钥 = 防护不够）。

> **明确**：本技能 `verify` / `attack_sim` 面向 **LLVM 原生产物**，**不适用于 Dart AOT 快照**。
> Dart 侧按本节方法论执行；DA4 的 native 部分照常使用本技能链路。

## 5. 与分阶段工作流的接线（`SKILL.md`）

| 阶段 | Dart / Flutter 项目怎么做 |
| :--- | :--- |
| **P0 勘察** | `anti-rea scan` 可识别 `dart` 语言与 `pubspec.yaml`（pub）；**函数级资产面向 C 系**，Dart 的敏感模块需人工补充。画像：是否 Flutter、目标平台（Android/iOS/desktop/web）、是否联网（DA0）、是否有服务端（DA6）、是否可改构建（DA1/DA4）、价值等级 |
| **P1 方案** | 从 §1 选 1–3 个组合，把原理/优缺点/影响 + §3 场景匹配 + 获取方式写进 `PROPOSAL.md`，**交用户选择** |
| **P2 决策** | 用户可逐项取舍（如\"只做 DA1\"、\"DA1+DA4\"），也可先试点 |
| **P3 执行** | 多为构建/发布链改造（release、obfuscate、符号归档、FFI 插件、R8）；改构建文件先给 diff，只加不删 |
| **P4 验证** | 按 §4 执行 Dart 侧验证；DA4 的 native 部分用本技能常规链路 |

## 6. 边界、许可与合规

- **不分发**：不打包、不代下载 blutter/reFlutter/apktool 等，只记录获取源与用法。
- **符号文件**：`--split-debug-info` 产物是**私有资产**，只进内部符号服务器；泄露即抵消 DA1。
- **动态代码下发**：iOS 与 Google Play 对动态下发可执行代码有严格限制；**不要把“热更新壳”
  当加固方案**，合规风险高于收益。
- **引擎替换**：Flutter 引擎是通用产物，重打包/替换是已知风险；完整性校验要与服务端联动。
- **不改基线**：本文是\"给用户的选项\"，不是需求；需求变更走 `plan/anti-rea-project-plan.md` §10.4。
- **口径一致**：**抬高成本，不承诺不可破**。

## 7. 参考

- REA 威胁分析：`docs/analysis/rea-threat-analysis.md`
- IR 变换范围决策：`docs/design/ADR.md`（ADR-001）
- native 侧构建注入：`docs/build-injection.md`、`SKILL.md`（模式 B）
- Flutter 混淆官方文档：`https://docs.flutter.dev/deployment/obfuscate`
- Dart FFI：`https://dart.dev/guides/libraries/c-interop`
- 其它语言菜单（对照）：`docs/java-anti-rea.md`、`docs/dotnet-anti-rea.md`、`docs/js-anti-rea.md`、
  `docs/go-anti-rea.md`、`docs/python-anti-rea.md`
