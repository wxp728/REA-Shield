# JavaScript / TypeScript 反 REA 选项目录（供用户选择）

> **状态**：使用指南（**非**需求基线；不修改 `SRS.md`）。
> **定位**：本技能对 JS/TS **不做源码级混淆**（不是 LLVM IR 语言）。对浏览器、Node.js、
> Electron、React Native 等项目，本技能提供的是**一张选项菜单 + 每种的原理 / 优点 / 缺点 /
> 影响 + 获取源与用法要点**，由 Agent 按 `SKILL.md` 的分阶段工作流在 **P1 方案**里呈现给用户，
> **用户选定后再落地**。
> **边界**：第三方工具与商用产品**不由本技能分发**——这里只记录获取途径与使用要点；
> 许可、试用与合规由用户自行确认。目标仍是"**抬高成本**"，不追求"不可破"。

## 0. 为什么 JS/TS 需要单独一张菜单

| 事实 | 含义 |
| :--- | :--- |
| REA（6.5.0）的 provider 含 **ASAR / JS 树**与浏览器（Playwright/CDP） | Electron / Web 目标**在其射程内**（见 [`analysis/rea-threat-analysis.md`](analysis/rea-threat-analysis.md) §2） |
| 交付物就是**可读的 JS 源码**（打包/压缩只是改名与去空白） | `prettier`/`js-beautify` 一次即可恢复结构；source map 若外发则**直接还原原始工程** |
| 攻击链极短：下载 `app.asar`/bundle → 解包 → 美化 → 读源码；LLM 对 JS/TS 的熟悉度极高 | **未加固的前端基本等同交付源码**——比 Java/.NET 更直接 |
| 根本约束：**运行时必须能执行这段 JS** | 所有手段都只是抬高还原成本；Web 端天花板低于 native/WASM |
| 生态现实：`node_modules` 巨大、动态 `require`/`import()`、`eval`/`new Function` 常见 | 混淆/裁剪易破坏运行；**keep 规则与回归成本**高于编译型语言 |
| 有两条真实"换赛道"出口：**WebAssembly**（C/C++/Rust → WASM）与**原生插件/原生外壳** | 与 Java 的 GraalVM、.NET 的 NativeAOT 同理：把核心下沉，再按 native 方法加固 |

因此 JS/TS 侧的正确做法同样是**按价值分层选组合**：下面 JS0–JS8 按"攻击方要多付出什么"从高到低排列。

> **零成本复用（无需新增引擎能力）**：
>
> - **Node 原生插件（`.node`，N-API）/ Electron 原生模块**本身就是 C/C++ → 直接走
>   [`build-injection.md`](build-injection.md) 的模式 B。
> - **由 C/C++/Rust（C/FFI）编译出的 WASM**可走本引擎的 IR 流水线（LLVM 的 wasm 后端；
>   端到端实测目前仅 Linux x86_64，其它目标需自行验证），见 JS4。
> - **Tauri** 的 Rust 核心、**React Native** 的原生模块同理：核心逻辑放 native，JS 只做 UI。

## 1. 选项总览

| ID | 手段 | 攻击方要多做的 | 效果量级 | 主要代价 | 产物可移植性 | 本技能是否带工具 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **JS0** | 核心逻辑上服务端 | 逆到底也只能拿到协议调用 | 最高（可做到"无产出"） | 需联网、延迟、服务端成本 | 不变（客户端变薄） | 否（架构实践） |
| **JS1** | 打包 + 压缩 + 名称混淆 + **不发 source map** | 美化后重建命名与模块边界 | 低（基线，分钟级） | 构建配置、调试体验下降 | 不变 | 否（开源工具） |
| **JS2** | 字符串/常量加密 + 控制流混淆 | 换反混淆器、动态跟踪、手工还原 CFG | 中（小时～天级） | 性能/体积/兼容性；商用许可 | 不变 | 否（开源/商用） |
| **JS3** | JS 字节码虚拟化（自定义 VM / 字节码） | 逆解释器、重建 ISA | **JS 层单点最高** | 工具稀缺、性能降数十倍 | 不变 | 否（商用/自研） |
| **JS4** | 核心编译为 **WebAssembly** | 逆 WASM（wat/反编译），失去 JS 语义 | 高（换赛道） | 需要重写核心；WASM 仍可反编译 | **部分**（需 wasm 运行时） | **是**（对 C/C++/Rust→WASM 的 IR 侧） |
| **JS5** | 下沉 **native**（N-API 插件 / 原生模块 / 原生外壳） | 回到 native 逆向（可用本技能加固） | 高 | 逐平台产物、构建矩阵、跨语言调试 | **丧失**（每平台一份） | **是**（本技能加固 native 侧） |
| **JS6** | 分发形态加固（ASAR 完整性 / Electron fuses / SEA / pkg / Hermes） | 解包与改包变难，但仍需读代码 | 中（主要抬"改包/注入"成本） | 平台耦合、签名/公证、升级成本 | 不变 | 否（平台工具） |
| **JS7** | 运行期对抗（反调试/反篡改/完整性/环境） | 动态调试与自动化批量分析变贵 | 辅助（与 JS2/JS3/JS6 协同） | 误杀、CSP/商店审核冲突 | 不变 | 否（商用/自研） |
| **JS8** | 密钥与信任根 + 水印 | 拿不到可用密钥；泄露可溯源 | 辅助 | 服务端/硬件依赖 | 不变 | 否 |

> **三个常见误解**：
> 1. **压缩/混淆 ≠ 加密**：变量改名不改变控制流与字符串，美化后仍可读。
> 2. **ASAR 不是加密**：`asar extract` 即可解开；它只是打包格式（完整性校验才有一点防护意义）。
> 3. **Hermes / V8 字节码（`bytenode`）不是不可逆**：仍有反汇编/反编译工具，且强绑定运行时版本；
>    只能算"提高一点门槛"，不能替代 JS2/JS4/JS5。

## 2. 选项详解

### JS0 · 核心逻辑上服务端

- **原理**：授权、密钥运算、核心算法、风控规则放到服务端 API（REST/GraphQL/WebSocket/自定义协议），
  客户端只保留调用与展示。
- **优点**：唯一能让"逆到底也没有产出"的路径；密钥不进客户端；不受 JS 可读性约束。
- **缺点**：需联网、有延迟与服务端容量成本；离线 Web/桌面、内网隔离环境不可用。
- **影响**：架构改造量最大；可用性/SLA 成为新的失败点；协议仍可被观察、重放与自动化调用
  （需配合鉴权、配额、设备证明）。
- **获取源**：无工具，工程实践。客户端可再用 JS1/JS2 保护签名校验与协议逻辑。
- **适用判据**：产品本来就要联网、核心价值可服务化（订阅、在线激活、云端推理、风控）。

### JS1 · 打包 + 压缩 + 名称混淆 + 不发 source map（基线，必做）

- **原理**：用 bundler 打包（webpack / Rollup / esbuild / Vite），压缩并 mangle 局部标识符
  （terser / esbuild），**生产环境不发布 `.map`**，关闭 `devtool`/`sourceMappingURL`。
- **效果**：攻击方失去"原始文件名、目录结构、语义化变量名、原始注释"；**控制流与字符串仍然完整**，
  美化后可读。
- **优点**：零/低成本；顺带减小体积、加快加载；**任何 JS 项目都该先做**。
- **缺点**：单层对 REA 通常只是"多花几分钟"；mangle 对导出名/反射式访问/字符串引用无效。
- **影响**：线上排障需要**私有** source map（只上传到错误监控，不随产物分发）；动态 `import()`、
  `require` 变量、装饰器/依赖注入、框架约定名需保留规则。
- **工具与获取源**：

  | 工具 | 许可 | 获取源 | 用法要点 |
  | :--- | :--- | :--- | :--- |
  | **esbuild** | MIT | `https://esbuild.github.io/` | `--minify --sourcemap=external`（仅内部留存）；构建快 |
  | **terser** | BSD-2-Clause | `https://github.com/terser/terser` | `mangle` + `compress`；注意保留导出名 |
  | **webpack / Rollup / Vite** | MIT | 各自官网 | 生产配置 `devtool: false`；检查插件是否偷偷发 map |
  | **source-map 审计** | — | 自建脚本 | 产物中禁止出现 `//# sourceMappingURL=` 与 `.map` 文件 |

- **适用判据**：所有 JS/TS 项目的第一步；把"source map 不外发"写进发布检查单。

### JS2 · 字符串/常量加密 + 控制流混淆

- **原理**：字符串移入加密数组并在运行期解密；常量编码；控制流平坦化 / 不透明谓词 / 死代码注入；
  自防护（self-defending）与调试保护。
- **效果**：`strings`/关键字检索失效；美化后出现大量调度器与间接调用；攻击方需动态跟踪或写反混淆脚本。
- **优点**：不动架构、可按文件/模块/函数粒度启用；对"LLM 读美化后代码"这条最省力路径打击明显。
- **缺点**：**开源反混淆器（webcrack、de4js、REstringer 等）能自动还原部分模式**；单层往往撑不过
  一次工具运行；反混淆失败 ≠ 不可解（可换工具、动态 hook、DevTools 断点）。
- **影响**：体积与启动时间上升；JIT 优化可能受影响（热路径需 A/B）；`eval`/`new Function` 方案与
  **CSP** 冲突；与 SSR、动态 `import()`、框架反射、测试工具可能冲突；错误栈可读性下降。
- **获取源**：
  - 开源：`javascript-obfuscator`（BSD-2-Clause，`https://github.com/javascript-obfuscator/javascript-obfuscator`）——
    字符串数组/RC4、控制流平坦化、死代码、self-defending、debug protection、domain lock；
  - 商用：**Jscrambler**（`https://jscrambler.com/`）、**Protect** 等（策略与许可由用户确认）。
- **适用判据**：只对 P0/P1 资产（授权、算法、协议、密钥派生）启用重混淆；UI/路由/埋点保持轻量。
- **注意**：`self-defending`/`debug protection` 与部分浏览器扩展、无障碍工具、CSP 有冲突，需回归。

### JS3 · JS 字节码虚拟化（自定义 VM / 字节码）

- **原理**：把敏感函数编译为**自定义指令集**并内嵌解释器；运行时只执行解释器，原函数不再以标准 JS 存在。
- **效果**：攻击方必须逆解释器、重建 ISA 与 opcode 映射，才能恢复语义——把"读源码"变成"写反编译器"。
- **优点**：JS 层单点成本最高；与 JS2/JS6 叠加形成纵深。
- **缺点**：工具稀缺（多为商用或自研）；与 `async`/生成器、闭包、原型链、`this` 绑定的兼容性复杂；
  性能开销大；调试与错误栈失真。
- **影响**：只适合极少数关键函数（解释执行可慢**数十倍**）；体积增大；可能阻断 tree-shaking；
  需为每个运行时（浏览器/Node）验证。
- **获取源**：Jscrambler 的代码虚拟化、商用 JS 保护产品，或自研（字节码 + 解释器 + 映射随机化）。
- **适用判据**：2–5 个最敏感函数；必须做性能 A/B 并保留降级开关。

### JS4 · 核心编译为 WebAssembly

- **原理**：用 C/C++/Rust（C/FFI）/AssemblyScript 重写核心，编译为 `.wasm`，JS 只做加载与调用；
  WASM 是二进制字节码，不含 JS 源码结构。
- **效果**：REA 从"读 JS"变为"读 WASM 字节码/反编译"；WASM 可继续用 `wasm-opt` 优化，
  **C/C++/Rust 源可再经本引擎做 IR 变换**（LLVM wasm 后端）。
- **优点**：真正的"换赛道"；性能通常优于 JS（计算密集场景）；跨浏览器/Node 可移植；
  与 JS2 相比**没有 CSP/eval 冲突**。
- **缺点**：核心需重写（或维护双实现）；WASM **不是不可反编译**（`wasm2wat`、`wasm-decompile`、
  Ghidra/JEB 等）；与 JS 的边界（字符串/对象/异常/GC）需要胶水代码；调试体验差。
- **影响**：构建链增加（clang/rustc + wasm 目标）；包体与加载策略（流式编译、缓存）；
  某些平台/商店对动态 WASM 编译有限制；**端到端实测**目前仅 Linux x86_64（IR 级支持其它目标）。
- **获取源**：LLVM/clang（`--target=wasm32`）、Rust `wasm32-unknown-unknown`、Emscripten、
  AssemblyScript（`https://www.assemblyscript.org/`）、Binaryen（`wasm-opt`）。
- **适用判据**：核心是计算/算法/协议，且能接受重写与胶水成本；**优先把"最值钱的一小块"下沉**。

### JS5 · 下沉 native（N-API 插件 / 原生模块 / 原生外壳）

- **原理**：核心用 C/C++（或 Rust C/FFI）实现为原生库，JS 通过 N-API（Node-API）、Electron 原生模块、
  React Native TurboModule/JSI、Tauri command 调用；原生侧回到 LLVM 战场，可用本技能加固。
- **效果**：JS 里只剩调用桩；核心不再以 JS/WASM 形式存在；可结合 D5/J5 的 native 方法论。
- **优点**：防护强度最高（与 WASM 相比没有可反编译的字节码）；性能好；可利用平台安全能力
  （Keychain/Keystore/DPAPI）。
- **缺点**：**逐平台/架构各编一份**（win/mac/linux × x64/arm64，移动端 ABI 更多）；跨语言调试困难；
  native 崩溃直接杀掉进程；分发与签名/公证复杂；Electron 的 ABI 与 Node 版本需匹配。
- **影响**：构建矩阵与 CI 显著变重；安装包增大；需要为每个目标平台准备 CI runner；
  Web 端不可用（只能走 JS4/WASM）。
- **获取源**：Node-API（`https://nodejs.org/api/n-api.html`）、`node-addon-api`、
  Electron 原生模块文档、React Native JSI、Tauri（Rust）。
- **适用判据**：桌面/移动/服务端 Node，且能接受多平台构建；**与 JS4 二选一或组合**（Web 用 WASM，
  桌面用 native）。

### JS6 · 分发形态加固（ASAR 完整性 / Electron fuses / SEA / pkg / Hermes）

- **原理**：在"打包/分发"层加约束——Electron 开启 **ASAR 完整性校验**与 **fuses**（禁用
  `ELECTRON_RUN_AS_NODE`、`--inspect`、`NODE_OPTIONS`，强制只从 ASAR 加载）；Node 用 **SEA**
  （Single Executable Application）或 `pkg`；React Native 用 **Hermes** 字节码；配合代码签名/公证。
- **效果**：抬高"解包、改包、注入、带调试器启动"的成本；**不隐藏代码本身**（解包后仍要读）。
- **优点**：平台原生、与现有发布流程兼容；对"改一改再分发"的盗版/外挂有明显作用；
  与 JS2/JS7 协同好。
- **缺点**：不是保密手段；ASAR 可被 `asar extract`；SEA/pkg 只是打包（可提取）；Hermes 字节码
  可反汇编/反编译且绑定版本；fuses 一旦开启会影响合法调试与部分工具。
- **影响**：签名/公证流程必须覆盖所有原生产物；自动更新与差分升级需重新设计；
  某些 fuses 与 CI/测试环境冲突（需保留开发构建）。
- **获取源**：`@electron/fuses`（`https://github.com/electron/fuses`）、Electron ASAR 完整性文档、
  Node SEA（`https://nodejs.org/api/single-executable-applications.html`）、`pkg`、
  Hermes（`https://hermesengine.dev/`）、`asar`（`https://github.com/electron/asar`）。
- **适用判据**：Electron/Node/RN 桌面与移动分发；**先做完整性/签名，再谈混淆**。

### JS7 · 运行期对抗（反调试 / 反篡改 / 完整性 / 环境）

- **原理**：检测 DevTools/调试器、检测代码/资源被修改（哈希、SRI、ASAR 完整性）、检测注入与
  自动化环境（headless/Playwright/CDP 特征）、异常时降级或拒绝继续。
- **效果**：抬高"动态调试、内存/网络抓取、脚本化批量分析"的成本——与 JS2/JS3/JS6 配合最关键。
- **优点**：与静态混淆正交、可叠加；让便宜分析变成要花人力的分析。
- **缺点**：不阻止静态阅读；误报会伤合法用户/无障碍/测试；检测逻辑本身可被 patch；
  与 CSP、浏览器扩展、商店审核可能冲突；Web 端**无法真正隐藏**检测逻辑。
- **影响**：启动/运行开销（通常可控）；平台适配成本；需设计**误杀救济通道**与遥测。
- **获取源**：商用保护产品（Jscrambler 等）、平台完整性能力（ASAR integrity、SRI、CSP）、
  自研（`debugger` 计时、`Function.prototype.toString` 校验、环境指纹）。
- **适用判据**：与 JS2/JS3/JS6 叠加；不把检测当唯一防线。

### JS8 · 密钥与信任根 + 水印

- **原理**：密钥不进客户端（服务端签发 / KMS / HSM / 平台安全存储）；水印用于**溯源**而非防护。
- **平台能力**：Electron `safeStorage`（Windows DPAPI / macOS Keychain / Linux secret service）、
  iOS Keychain、Android Keystore、服务端 KMS/HSM。
- **优点**：即使代码被读，拿不到可用密钥 → 攻击产出不可直接用；水印为维权留证。
- **缺点**：需服务端或硬件能力；离线场景受限；Web 端没有可信存储（只能靠服务端）；
  白盒密码在 JS/WASM 侧同样不是银弹。
- **影响**：架构与运维改动；密钥轮换与吊销；合规（密钥托管、数据驻留）。
- **获取源**：Electron `safeStorage`、平台 Keychain/Keystore、云 KMS/HSM；商用保护产品多自带水印。
- **适用判据**：只要还发密钥到客户端，前面的混淆都可能是"给锁配了把公开的钥匙"。

## 3. 组合阶梯（按场景推荐）

| 场景 | 建议组合 | 说明 |
| :--- | :--- | :--- |
| 内部工具 / 低价值 Web | **JS1** | 基线：压缩 + 不发 source map |
| 商用 Web 前端、核心在服务端 | **JS0 + JS1** | 关键逻辑上服务端；前端只做基线 |
| 商用 Web、必须离线算一部分 | **JS1 + JS2 + JS4** | 字符串/控制流混淆 + 核心下沉 WASM |
| Node CLI / 服务端工具 | **JS1 + JS2 + JS6（SEA/pkg）** | 分发形态 + 混淆；高价值再上 JS5 |
| Electron 桌面 | **JS1 + JS2 + JS6（fuses/ASAR 完整性/签名）+ JS7 + JS8** | 先完整性，再混淆；密钥不进渲染进程 |
| React Native / 移动 | **JS1 + JS2 + JS6（Hermes）+ JS5 + JS8** | Hermes 只算门槛；核心下沉原生模块 |
| 预算充足、需最强 | **JS0 或 JS5 + JS3 + JS7 + JS8** | 多层叠加，密钥不落客户端 |

> 选择原则：**先明确"逆到底会得到什么"**。如果答案是"一个 HTTP 调用"，JS0 就够；如果必须离线交付
> 完整客户端，就往 JS1 → JS2 → JS4/JS5 → JS3 逐级叠加，并始终配 JS8。

## 4. 验证方法论（自证防护有效）

**攻击方视角工具**（自行获取）：

| 工具 | 许可 | 获取源 | 用途 |
| :--- | :--- | :--- | :--- |
| **js-beautify / prettier** | MIT | `https://github.com/beautifier/js-beautify`、`https://prettier.io/` | 美化，检验"可读性" |
| **webcrack** | MIT | `https://github.com/j4k0xb/webcrack` | 反混淆（webpack/obfuscator.io 常见模式） |
| **de4js** | MIT | `https://github.com/lelinhtinh/de4js` | 在线/本地反混淆（字符串数组、eval 包装） |
| **REstringer** | MIT | `https://github.com/HumanSecurity/REstringer` | 反混淆与静态还原 |
| **DevTools / Node inspector** | 随浏览器/Node | 内置 | 动态调试、断点、网络/内存观察 |
| **wasm2wat / wasm-decompile** | Apache-2.0 | `https://github.com/WebAssembly/wabt`、`https://github.com/WebAssembly/binaryen` | WASM 反汇编/反编译 |
| **Ghidra / JEB** | Apache-2.0 / 商用 | 各自官网 | WASM/native 深入分析（按许可自行获取） |
| **asar** | MIT | `https://github.com/electron/asar` | 解包 Electron 应用 |
| **hbctool / hermes-dec** | MIT | `https://github.com/bongtrop/hbctool` 等 | Hermes 字节码反汇编/反编译 |

**流程**：

1. 按分发形态取产物（Web bundle / ASAR / SEA / `.node` / `.wasm` / Hermes `.hbc`）；
2. **先查 source map**：产物中是否残留 `sourceMappingURL`、`.map`、内联 base64 map；
3. 用美化器 + 至少一个反混淆器（webcrack / de4js / REstringer）交叉验证；
4. 统计指标：**命名可读率**、**字符串明文比例**、**反混淆恢复率**、**反编译/断点闭合时间**；
5. 尝试重建可运行工程并**计时**（工时是最终成本指标）；
6. 记录"逆到底得到了什么"（能拿到可用算法/密钥 = 防护不够）；
7. WASM / native 插件等原生产物改用 native 方法论：`strings`/`nm`/`objdump` + 本技能
   `verify` / `attack_sim`。

> **明确**：本技能的 `verify` / `attack_sim` 面向 **LLVM 原生产物**，**不适用于 JS/TS 源码与
> Hermes/V8 字节码**。JS 侧按本节方法论执行；JS4/JS5 产出的 WASM/native 部分照常使用本技能链路。

## 5. 与分阶段工作流的接线（`SKILL.md`）

| 阶段 | JS/TS 项目怎么做 |
| :--- | :--- |
| **P0 勘察** | `anti-rea scan` 可识别 `javascript`/`typescript` 语言与 `package.json`（npm）构建标记；构建画像补充：运行时（浏览器/Node/Electron/RN/Tauri）、bundler、**source map 策略**、分发形态（ASAR/SEA/pkg/Hermes）、是否联网（决定 JS0）、原生模块、CSP、签名/公证、目标平台矩阵 |
| **P1 方案** | 从 §1 表里选 1–3 个候选组合，把**原理 / 优点 / 缺点 / 影响**摘要 + §3 场景匹配 + **依赖获取方式**写进 `PROPOSAL.md`，**交用户选择**；JS4/JS5 与 native 侧一并给出代价预算 |
| **P2 决策** | 用户可逐项取舍（如"只做 JS1"、"JS1+JS6"、"JS2+JS4"），也可要求先做小范围试点 |
| **P3 执行** | 多为**构建/发布流程改造**（bundler 配置、混淆插件、Electron fuses/完整性、SEA/Hermes、native 模块）；按模式 B 的纪律：**改构建文件先给用户看 diff，只加不删** |
| **P4 验证** | 按 §4 方法论执行 JS 侧验证；JS4/JS5 的 WASM/native 部分用本技能常规链路 |

## 6. 边界、许可与合规

- **不分发**：本技能不打包、不代下载上述第三方工具与商用产品，只**记录获取源与用法**；
  商业许可与试用条款由用户与厂商确认。
- **source map 是最大的泄漏源**：生产产物**一律不外发** `.map`；错误监控用的私有 map 要有访问控制。
- **CSP 冲突**：`eval`/`new Function`/内联脚本型混淆会破坏严格 CSP；优先选择不依赖动态求值的方案
  （JS4/JS5 或纯静态变换）。
- **商店与平台规则**：Chrome Web Store、Apple App Store、Microsoft Store 对混淆/动态代码/加壳
  有各自政策；Electron fuses 与自动更新、无障碍工具可能冲突，需逐项确认。
- **许可影响**：混淆可能影响开源许可义务（如 LGPL 的"可替换"要求）与第三方 SDK 条款；落地前自查。
- **不要破坏可诊断性**：保留**私有** source map 与错误监控的符号化能力。
- **不改基线**：本文是"给用户的选项"，不是需求；涉及需求变更走 `plan/anti-rea-project-plan.md` §10.4 流程。
- **口径一致**：**抬高成本，不承诺不可破**；不针对 REA 工具本身做任何攻击。

## 7. 参考

- REA 威胁分析：`docs/analysis/rea-threat-analysis.md`（含 ASAR/JS 树 provider）
- IR 变换范围决策：`docs/design/ADR.md`（ADR-001）
- native 侧构建注入与加固：`docs/build-injection.md`、`SKILL.md`（工作流模式 B）
- Electron 安全清单：`https://www.electronjs.org/docs/latest/tutorial/security`
- Electron fuses：`https://github.com/electron/fuses`
- Node SEA：`https://nodejs.org/api/single-executable-applications.html`
- WebAssembly：`https://webassembly.org/`
- Java / .NET 同类菜单（对照）：`docs/java-anti-rea.md`、`docs/dotnet-anti-rea.md`
