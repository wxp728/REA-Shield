# .NET / Unity 反 REA 选项目录（供用户选择）

> **状态**：使用指南（**非**需求基线；不修改 `SRS.md`）。
> **定位**：本技能对 .NET **不做 IL 层变换**（ADR-006）。对 C# / F# / VB.NET（含 Unity、MAUI、
> Blazor、桌面/CLI/服务）项目，本技能提供的是**一张选项菜单 + 每种的原理 / 优点 / 缺点 / 影响
> + 获取源与用法要点**，由 Agent 按 `SKILL.md` 的分阶段工作流在 **P1 方案**里呈现给用户，
> **用户选定后再落地**。
> **边界**：第三方工具与商用加固产品**不由本技能分发**——这里只记录获取途径与使用要点；
> 许可、试用与合规由用户自行确认。目标仍是"**抬高成本**"，不追求"不可破"。

## 0. 为什么 .NET 需要单独一张菜单

| 事实 | 含义 |
| :--- | :--- |
| CIL 是**带元数据的栈式字节码**：程序集/类型/方法/字段名、字符串（`#US` 堆）、类型签名、行号、自定义特性 | 反编译器（ILSpy / dnSpyEx / dotPeek）能**近乎还原可编译的 C# 源码** |
| 攻击链极短：`复制 DLL → ilspycmd -p → 得到工程`；LLM 对 C# 的熟悉度很高 | **未加固的 DLL 基本等同交付源码**——比 C/C++ 更"一眼见底" |
| REA（6.5.0）的 provider 含 **MSIX/AppX**（.NET 的主要分发形态之一） | .NET 目标**在其射程内**（见 [`analysis/rea-threat-analysis.md`](analysis/rea-threat-analysis.md) §2） |
| 根本约束：**CLR 必须加载并执行元数据**；反射/序列化/DI/XAML 依赖名字 | 改名与加密都要保留运行期必需的元数据；所有手段都只是抬高还原成本 |
| 公开的去混淆器（如 **de4dot** 及其分支）能还原**部分**商业混淆产物 | **单层混淆很脆弱**——必须"组合 + 下沉 native 或 AOT"，不能只买一个壳 |
| .NET 的"换赛道"出口比 Java 多：**NativeAOT / ReadyToRun / Mono AOT / Unity IL2CPP** | 高价值场景应尽早评估"整体 AOT 或 IL2CPP → 再按 native 加固" |

因此 .NET 侧的正确做法同样是**按价值分层选组合**：下面 D0–D8 按"攻击方要多付出什么"从高到低排列。

## 1. 选项总览

| ID | 手段 | 攻击方要多做的 | 效果量级 | 主要代价 | 产物可移植性 | 本技能是否带工具 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **D0** | 核心逻辑上服务端 | 逆到底也只能拿到协议调用 | 最高（可做到"无产出"） | 需联网、延迟、服务端成本 | 不变（客户端变薄） | 否（架构实践） |
| **D1** | 裁剪 + 名称混淆 | 重建符号语义，靠数据流猜名字 | 低（基线，小时级） | keep 规则维护、mapping 管理 | 不变 | 否（开源/商用工具，见 §2） |
| **D2** | 字符串/常数加密 + 控制流混淆 | 换反编译器、跑动态跟踪、手工还原 CFG | 中（小时～天级） | 商用许可、启动/调试体验下降 | 不变 | 否（商用/自研） |
| **D3** | 程序集加密/打包 + `AssemblyResolve` 加壳 | 必须**运行期 dump** 才能继续 | 中高 | 启动开销、杀软误报、加载兼容性 | 不变 | 否（商用/自研壳） |
| **D4** | IL 虚拟化（VMP 类） | 逆解释器、重建自定义 ISA | **IL 层单点最高** | 工具稀缺、性能降数十倍 | 不变 | 否（商用/自研） |
| **D5** | 下沉 native（P/Invoke / C++/CLI / 函数指针） | 回到 native 逆向（可用本技能加固） | 高 | 逐平台产物、跨语言调试、封送开销 | **丧失**（每平台一份） | **是**（本技能加固 native 侧） |
| **D6** | NativeAOT / Mono AOT（整体 AOT） | 逆原生二进制，且失去 IL/元数据锚点 | 高（一次到位） | 闭世界限制、构建慢、逐平台 | **丧失** | **是**（对本技能能力面友好） |
| **D7** | 运行期对抗（反调试/防篡改/完整性） | 动态 dump 与自动化批量攻击变贵 | 辅助（与 D3/D4 协同） | 误杀风险、杀软/签名冲突 | 不变 | 否（商用/自研） |
| **D8** | 密钥与信任根 + 水印 | 拿不到可用密钥；泄露可溯源 | 辅助 | 服务端/硬件依赖 | 不变 | 否 |

> **ReadyToRun 不算防护**：R2R 只是"预编译 + IL 仍在"，反编译器照样能读——它属于**性能/启动**
> 优化，不要当作 D6。只有 **NativeAOT / Mono 全 AOT / IL2CPP** 才真正去掉 IL。

## 2. 选项详解

### D0 · 核心逻辑上服务端

- **原理**：把授权、密钥运算、核心算法放到服务端 API（REST/gRPC/自定义协议），客户端只保留调用与展示。
- **优点**：唯一能让"逆到底也没有产出"的路径；不受 CLR/元数据约束；密钥不进客户端。
- **缺点**：需联网、有延迟与服务端容量成本；离线软件、嵌入式、无网/内网隔离环境**不可用**。
- **影响**：架构改造量最大（往往重写模块边界）；可用性/SLA 成为新的失败点；客户端协议仍可被观察与重放。
- **获取源**：无工具，工程实践。客户端可再用 D1/D2/D5 保护签名校验与协议逻辑。
- **适用判据**：产品本来就要联网、核心价值可服务化（订阅制、在线激活、云端推理）。

### D1 · 裁剪 + 名称混淆（基线，必做）

- **原理**：`PublishTrimmed` 删除未被引用的代码；把命名空间/类型/方法/字段/参数重命名为无意义短名；
  发布不带 PDB；开启确定性构建。
- **效果**：攻击方失去"名字即文档"的锚点（`LicenseValidator.CheckActivation`、`DecryptLicenseBlob`
  这类语义泄漏消失），必须靠数据流/调用图重建语义；**反编译本身仍然成功**。
- **优点**：开源/低成本；顺带减小体积；**任何 .NET 项目都该先做**。
- **缺点**：单层 D1 对 REA 通常只是"失去名字"——字符串、常量、控制流完好；有经验的攻击方**小时级**即可读通。
- **影响**：需维护 keep 规则（反射、序列化、DI、XAML 绑定、EF、Json.NET/System.Text.Json、
  P/Invoke 入口、COM、插件发现、Unity 的 `link.xml`）；栈跟踪要靠 mapping 还原，线上排障变难；
  trimming 与反射天然冲突（用 `DynamicDependency` / `RequiresUnreferencedCode` / `rd.xml` 显式声明）。
- **工具与获取源**：

  | 工具 | 许可 | 获取源 | 用法要点 |
  | :--- | :--- | :--- | :--- |
  | **Obfuscar** | MIT | `https://github.com/obfuscar/obfuscar` | 轻量、XML 规则；`obfuscar.console.exe obfuscar.xml`；先跑通回归与 mapping 归档 |
  | **ConfuserEx**（社区维护分支） | MIT | `https://github.com/mkaring/ConfuserEx` | 模块化保护（rename/constants/ctrl flow/anti-debug/packer）；规则按程序集/类型粒度配置 |
  | **Dotfuscator**（Community / Pro） | 商用（CE 免费但功能受限） | `https://www.preemptive.com/products/dotfuscator/` | 与 MSBuild/CI 集成；重命名 + 字符串加密 + 防篡改（Pro） |
  | **Eazfuscator.NET** | 商用 | `https://www.gapotchenko.com/eazfuscator.net` | 与 MSBuild 集成好；重命名、字符串加密、常量、资源、防篡改 |
  | **.NET Reactor** | 商用 | `https://www.eziriz.com/dotnet_reactor.htm` | NecroBit / 虚拟化 / 加壳 / 反调试（见 D3/D4/D7） |

- **适用判据**：所有 .NET 项目的第一步；先跑通"混淆后功能回归 + mapping 落库"。
- **注意**：**强名称签名（strong-name）不是保护**——它只保证程序集身份与完整性，不隐藏任何信息；
  Authenticode/代码签名同理（身份与信任，不是保密）。

### D2 · 字符串/常数加密 + 控制流混淆

- **原理**：字面量与整数/浮点常量在运行期解密；分支/循环改写为无源码对应结构（不透明谓词、平坦化、
  代理调用），部分类型/方法可加密。
- **效果**：REA 赖以闭合的 `strings`/常量锚点失效；反编译产物出现非法 `goto`、缺块或直接失败——
  攻击方从"读源码"退化到"读 IL + 动态观察"。
- **优点**：不动架构、可按程序集/类型/方法粒度启用；对"LLM 读反编译文本"这条最省力的攻击路径打击最明显。
- **缺点**：**公开去混淆器（de4dot 及其分支）能自动还原部分常见混淆模式**——单靠 D2 往往撑不过
  一次工具运行；反编译失败 ≠ 不可解（攻击方可换反编译器、用 dnSpy 调试、或 hook 解密函数）。
- **影响**：模块初始化解密带来启动开销；JIT 后运行开销通常可控但需 A/B；调试与异常栈可读性下降；
  反射、序列化、XAML、`nameof`、资源名、ILMerge/ILRepack 与单文件发布需工具支持。
- **获取源**：ConfuserEx 的 `constants` / `ctrl flow` 模块（开源）；商用 .NET Reactor、Agile.NET、
  Babel Obfuscator、Eazfuscator（字符串/常量/流混淆）。
- **适用判据**：只对 P0/P1 资产（授权、算法、协议、密钥派生）启用重混淆，P2 保持轻量，避免全局开销。

### D3 · 程序集加密/打包 + `AssemblyResolve`（加壳）

- **原理**：发布物里的程序集/资源被加密，运行期由 native stub 或托管 Loader 解密到内存，
  通过 `Assembly.Load(byte[])` / `AssemblyResolve` / 自定义 `AssemblyLoadContext` 加载；
  静态只看到 stub 与密文。
- **效果**：静态分析**没有可读 IL**，攻击方必须运行期 dump（内存 dump、hook `Assembly.Load`、
  dump 工具、调试器附加）。
- **优点**：静态防护强度显著高于 D1/D2，可叠加在 D2 之上；对"直接 ilspycmd"这类低成本攻击有效。
- **缺点**：只抬高**静态**闭合成本——必须配合 D7 才真正难打；杀软对 packer 敏感（误报）；与
  NativeAOT/单文件/R2R、插件热加载、`Assembly.Location` 依赖、依赖注入扫描可能冲突。
- **影响**：启动开销（解密 + 校验）；排障困难（堆栈/模块信息失真）；需保留"无壳降级"路径；
  签名/公证（Windows/macOS）与加壳的先后顺序需实测。
- **获取源**：.NET Reactor（NecroBit）、Themida/WinLicense（.NET 支持）、Eazfuscator、
  Agile.NET，或自研（自定义 `AssemblyLoadContext` + 加密资源 + 完整性校验）。
- **适用判据**：有明确"防静态抄源码"诉求，且产品能接受启动开销、杀软误报与兼容性约束。

### D4 · IL 虚拟化（VMP 类，IL 层单点最高）

- **原理**：把敏感方法编译成**自定义指令集**（虚拟寄存器/栈 + 随机化 opcode 映射）并内嵌解释器，
  CLR 只执行解释器；原方法体不再以标准 IL 存在。
- **效果**：攻击方必须逆解释器、重建自定义 ISA 与映射，才能恢复语义——**把"读源码"变成"写反编译器"**，
  是对抗自动化 REA 最有效的手段之一。
- **优点**：单点成本抬升在 IL 层最大；与 D2/D3 叠加后形成完整纵深。
- **缺点**：实现门槛高、独立工具稀缺（多为商用加固或自研）；与 async/iterator、泛型、反射、
  异常处理、调试的兼容性复杂；部分工具对 .NET 新版本支持滞后。
- **影响**：被虚拟化方法运行开销可达**几十倍至两个数量级**（解释执行）——只适合极少数关键方法；
  体积增大；异常栈与调试信息失真；可能阻断 ReadyToRun/AOT 或需要专门适配。
- **获取源**：.NET Reactor（虚拟化）、Agile.NET、Babel Obfuscator、VMProtect（.NET 支持）、
  Themida，或自研（自定义 VM + IL 重写）。
- **适用判据**：只挑 2–5 个最敏感方法；必须做性能 A/B，并留运行期回退开关。

### D5 · 下沉 native（P/Invoke / C++/CLI / 函数指针）

- **原理**：把敏感核心用 C/C++ 实现成原生库，托管侧只做调用；原生二进制回到 **LLVM 战场**——
  正是本技能的主战场（可挂 CFF/MBA/字符串加密/虚拟化/白盒密码）。

  | 接口 | 机制 | 单次调用开销 | 适用 | 备注 |
  | :--- | :--- | :--- | :--- | :--- |
  | **P/Invoke**（`DllImport` / 源生成 `LibraryImport`） | CLR 内置封送 | 低（绝对开销小） | 绝大多数场景 | `LibraryImport` 源生成器可避免运行期封送代码；注意字符串/数组/结构体封送 |
  | **C++/CLI** | 混合模式程序集 | 最低（同进程、可直接调 C++ 对象） | Windows-only 的桌面/服务 | 仅 Windows + MSVC；与 .NET Core/5+ 支持受限 |
  | **函数指针**（`NativeLibrary.Load` + `Marshal.GetDelegateForFunctionPointer`） | 手动绑定 | 低 | 跨平台、需要动态加载 | 需自行管理库生命周期与 ABI；AOT/裁剪下要显式保留 |
  | **COM / WinRT** | 进程内/跨进程组件 | 中～高 | Windows 集成 | 部署与注册成本高，现代 .NET 上逐步弃用 |

- **优点**：防护强度直接跳到 native 量级；计算密集段常**更快**；核心逻辑既不上服务端也不裸露在 IL 里；
  与 D6 可叠加（NativeAOT + native 库）。
- **缺点**：**可移植性在"产物"层丧失**——每个平台/架构各编一份；跨语言边界调试困难；封送开销与
  内存/句柄管理易错；native 层崩溃会直接杀掉进程；AOT/裁剪下需显式保留互操作元数据。
- **影响**：构建矩阵增加（win-x64/x86、linux-x64/arm64、macos-x64/arm64）；包体增大；签名/公证
  需覆盖新增原生库；不允许加载原生库的沙箱/托管环境不可用。
- **获取源**：P/Invoke（.NET 内置）；`LibraryImport` 源生成器（.NET 7+）；`NativeLibrary`
  （`https://learn.microsoft.com/dotnet/api/system.runtime.interopservices.nativelibrary`）。
- **用法要点**：设计**批量化边界**（一次调用做完一段工作，绝不让热循环跨边界）；native 侧用本技能做
  IR 变换 + 导出收敛，并沿用 [`build-injection.md`](build-injection.md) 的构建注入。

### D6 · NativeAOT / Mono AOT（整体 AOT）

- **原理**：构建期把整个应用 AOT 编译为原生可执行文件，IL 与元数据不再作为可执行内容存在。
- **效果**：REA 从"反编译 .NET"退回"逆原生二进制"，同时**失去 CIL 的符号/常量锚点**——成本量级上升，
  且可用本技能继续加固（D5 的 native 部分同样受益）。
- **优点**：一次到位（整应用换赛道）；启动快、内存占用低、可做无运行时分发；对 CLI/桌面/服务都适用。
- **缺点**：**闭世界分析**——反射、`Reflection.Emit`、动态加载、部分序列化/DI 需源生成器或
  `DynamicDependency`/`rd.xml` 显式声明；**逐 RID 产物**；构建时间明显变长；调试与诊断手段受限；
  并非所有库/框架都兼容。
- **影响**：CI 变慢；发布矩阵 ×N；行为差异需完整回归；体积/启动的收益需实测。
- **获取源**：`dotnet publish -c Release -r <rid> -p:PublishAot=true`（.NET 7+；
  `https://learn.microsoft.com/dotnet/core/deploying/native-aot/`）；Mono 全 AOT 见 iOS/Android/
  主机平台文档。**许可**：.NET 运行时与 NativeAOT 为 MIT。
- **用法要点**：先 `PublishTrimmed=true` + 源生成器改造，再开 AOT；AOT 前后各跑一遍完整回归；
  若同时用 D1/D2，**先混淆再 AOT**并验证 AOT 后仍可运行。

### D7 · 运行期对抗（反调试 / 防篡改 / 完整性）

- **原理**：检测调试器/托管调试器/Profiler、校验自身哈希与签名、检测模块注入与内存补丁、检测
  虚拟化/沙箱；异常时降级或拒绝继续。
- **效果**：抬高"动态 dump、单步跟踪、脚本化批量攻击"的成本——**尤其与 D3/D4 配合**（它们迫使攻击方转动态）。
- **优点**：与静态混淆正交、可叠加；把便宜的分析变成要花人力的分析。
- **缺点**：不阻止静态分析；误报会伤合法用户、调试与无障碍工具；检测逻辑本身可被 patch；
  杀软/EDR 可能把行为判为可疑；与代码签名/公证、商店审核可能冲突。
- **影响**：启动/运行检测开销（通常可控）；平台适配成本；需设计**被检测后的救济通道**（合规与支持成本）。
- **获取源**：商用加固（.NET Reactor、Eazfuscator、Agile.NET、Dotfuscator Pro 的防篡改/调试检测），
  或自研（`Debugger.IsAttached`、`IsDebuggerPresent`、`NtQueryInformationProcess`、哈希自校验）。
- **用法要点**：检测失败**降级而非崩溃**，避免误杀灾难；留取证日志；不把检测当作唯一防线。

### D8 · 密钥与信任根 + 水印

- **原理**：密钥不进客户端（服务端签发 / HSM / KMS / 平台安全存储）；水印用于**溯源**而非防护。
- **平台能力**：Windows **DPAPI**（用户/机器绑定，注意漫游与多用户）、Apple **Keychain/Secure Enclave**、
  Android **Keystore/StrongBox**、服务端 **HSM/KMS**；许可服务可做在线激活与吊销。
- **优点**：即使代码被逆，拿不到可用密钥 → 攻击产出不可直接用；水印为维权留证。
- **缺点**：需要服务端或硬件能力；离线场景受限；DPAPI 绑定用户/机器，迁移与多端体验需设计；
  白盒密码在 .NET 侧同样不是银弹。
- **影响**：架构与运维改动；硬件依赖（TEE/TPM 可用性因设备而异）；合规（密钥托管、数据驻留）。
- **获取源**：平台 API（DPAPI/Keychain/Keystore）；服务端 HSM/KMS；商用加固多自带水印。
- **适用判据**：只要还发密钥到客户端，前面的混淆都可能是"给锁配了把公开的钥匙"。

## 3. Unity / IL2CPP 特别路径

| 构建形态 | 攻击面 | 建议 |
| :--- | :--- | :--- |
| **Mono（`Assembly-CSharp.dll`）** | 与普通 .NET 相同：dnSpy/ILSpy 直接还原 | D1（+D2）基线；托管裁剪 + `link.xml`；关键逻辑可下沉 native（D5） |
| **IL2CPP（C# → C++ → 原生）** | 原生二进制 + `global-metadata.dat`；**Il2CppDumper** 可恢复类型/方法名 | **IL2CPP 本身就是"换赛道"**；再对生成的 C++ 用本技能加固（见下）+ 元数据/名称处理 + D7/D8 |
| **WebGL / 小游戏** | IL2CPP/WASM 产物可下载；前端逆向门槛低 | 服务端化（D0）优先；WASM 层只能抬门槛 |

**IL2CPP → 本技能（实验性，需要用户工程配合）**：

1. Unity 生成 IL2CPP 工程（`Library/Il2cppBuildCache` / 导出的 C++ 工程），其中是**可读的 C++**；
2. 用本技能的构建注入（模式 B）把 `clang + 变换插件` 挂到该工程的编译命令上，**按源文件/符号收窄范围**
   （只保护核心逻辑，避免整包变换导致构建时间与体积失控）；
3. 按 native 方法论验证（功能回归 + `verify` / `attack_sim` + 体积/耗时对比）；
4. **代价**：Unity 版本耦合、构建时间显著增加、崩溃栈可读性下降；升级 Unity/IL2CPP 需重跑验证。
   > 该路径不属于"官方支持"，属**方法论 + 构建注入**；是否可行须在你的 Unity 版本上先做小范围试点。

**其他 Unity 手段**：Beebyte Obfuscator（Asset Store，商用）、代码裁剪 + 资源加密、`global-metadata.dat`
混淆/加密（工具与兼容性需实测）、D7 运行期检测。注意 IL2CPP 下反射受限，混淆/裁剪规则要同步调整。

## 4. 组合阶梯（按场景推荐）

| 场景 | 建议组合 | 说明 |
| :--- | :--- | :--- |
| 内部工具、低价值 | **D1** | 基线，顺带减小体积 |
| 商用小工具、本就要联网 | **D0 + D1** | 关键逻辑上服务端，客户端做基线混淆 |
| 商用离线桌面 / CLI | **D1 + D2 + D5** | 名字/常量/控制流 + 核心下沉 native；可评估 D6 替代 |
| 高价值离线产品 | **D6 + D5 + D7 + D8** | NativeAOT 整体换赛道 + 核心再加固 + 运行期对抗 + 密钥不落客户端 |
| Unity（Mono） | **D1 + D2 + D5** | 托管层基线，核心下沉 native |
| Unity（IL2CPP） | **IL2CPP + 本技能加固生成的 C++ + D7** | IL2CPP 先去 IL，再按 native 加固；实验性路径先试点 |
| 预算充足、需最强 | **D0 或 D6 + D4 + D7 + D8** | 多层叠加，且密钥不落客户端 |

> 选择原则：**先明确"逆到底会得到什么"**。如果答案是"一个 HTTP 调用"，D0 就够；如果必须离线交付
> 完整客户端，就往 D1→D2→D5/D6→D4 逐级叠加，并始终配 D8。

## 5. 验证方法论（自证防护有效）

**攻击方视角工具**（自行获取；REA 亦使用其中的 MSIX/AppX 解包能力）：

| 工具 | 许可 | 获取源 | 用途 |
| :--- | :--- | :--- | :--- |
| **ILSpy / ilspycmd** | MIT | `https://github.com/icsharpcode/ILSpy` | 程序集 → C# 工程；`ilspycmd -p -o out Assembly.dll` 可批量 |
| **dnSpyEx** | GPLv3 | `https://github.com/dnSpyEx/dnSpy` | 反编译 + 调试 + 内存查看（动态分析主力） |
| **dotPeek** | 免费（JetBrains） | `https://www.jetbrains.com/decompiler/` | 备选反编译器（交叉验证） |
| **de4dot**（及分支） | GPLv3 | `https://github.com/de4dot/de4dot` | **去混淆**：检验 D1/D2 是否只是"纸糊" |
| **ildasm / monodis** | 随 SDK / Mono | .NET SDK、Mono | IL 级核对（反编译器失败时的交叉验证） |
| **Il2CppDumper** | MIT | `https://github.com/Perfare/Il2CppDumper` | IL2CPP：从二进制 + `global-metadata.dat` 恢复类型/方法名 |
| **objdump / nm / strings** | 系统 binutils | 系统包 | NativeAOT / IL2CPP / D5 原生产物的静态核验 |

**流程**：

1. 加固产物 → 用 **2–3 个反编译器**（ILSpy / dnSpyEx / dotPeek）交叉验证，再跑一次 **de4dot**；
2. 统计可量化指标：**命名可读率**、**字符串明文比例**、**反编译失败/异常率**、**去混淆后恢复率**；
3. 尝试重建可编译工程并**计时**（工时是最终成本指标）；
4. 记录"逆到底得到了什么"（能拿到可用算法/密钥 = 防护不够）；
5. D5/D6/IL2CPP 的**原生产物**改用 native 方法论：`strings`/`nm`/`objdump` + 本技能 `verify` / `attack_sim`。

> **明确**：本技能的 `verify` / `attack_sim` 面向 **LLVM 原生产物**，**不适用于 CIL 托管程序集**。
> .NET 托管侧按本节方法论执行（**本技能提供方法论与口径，不代跑**）；D5/D6/IL2CPP 产出的原生部分
> 照常使用本技能链路。

## 6. 与分阶段工作流的接线（`SKILL.md`）

| 阶段 | .NET 项目怎么做 |
| :--- | :--- |
| **P0 勘察** | `anti-rea scan` 可识别 `dotnet` 语言与 `.csproj`/`.sln` 构建标记；构建画像补充：TargetFramework、发布形态（framework-dependent / self-contained / single-file / trimmed / R2R / NativeAOT）、是否 Unity/IL2CPP、是否 Blazor/MAUI/WPF、反射/序列化/DI 依赖、代码签名/公证、目标平台矩阵、是否允许联网（决定 D0） |
| **P1 方案** | 从 §1 表里选 1–3 个候选组合，把每种候选的**原理 / 优点 / 缺点 / 影响**摘要 + §4 的场景匹配 + **依赖获取方式**写进 `PROPOSAL.md`，**交用户选择**；与 native 侧（D5/D6）一并给出代价预算 |
| **P2 决策** | 用户可逐项取舍（例如"只做 D1 基线""D0+D5""D6+D7"），也可要求先做小范围试点 |
| **P3 执行** | 多为**构建/发布流程改造**（MSBuild 属性、混淆器 task、native 模块、NativeAOT 配置、IL2CPP 构建注入）；按模式 B 的纪律：**改构建文件先给用户看 diff，只加不删** |
| **P4 验证** | 按 §5 方法论执行托管侧验证；D5/D6/IL2CPP 的 native 部分用本技能常规链路 |

## 7. 边界、许可与合规

- **不分发**：本技能不打包、不代下载上述第三方工具与商用产品，只**记录获取源与用法**；商业许可与
  试用条款由用户与厂商确认。
- **许可影响**：混淆/加壳可能影响**开源许可义务**（例如 LGPL 组件的"可替换"要求、再分发条款）与
  第三方 SDK 的条款；NativeAOT/IL2CPP 的产物分发也需遵守各自许可，落地前须自查。
- **不要破坏可诊断性**：去 PDB/改名会显著降低线上排障能力，必须保留 mapping 归档与符号服务器策略。
- **合规**：防篡改/反调试不得用于规避用户合法调试、无障碍或安全研究；部分平台商店对加壳/动态加载有限制。
- **不改基线**：本文是"给用户的选项"，不是需求；涉及需求变更走 `plan/anti-rea-project-plan.md` §10.4 流程。
- **口径一致**：与 native / Java 侧同一立场——**抬高成本，不承诺不可破**；不针对 REA 工具本身做任何攻击。

## 8. 参考

- REA 威胁分析：`docs/analysis/rea-threat-analysis.md`（REA 的 provider，含 MSIX/AppX）
- 语言/变换范围决策：`docs/design/ADR.md`（ADR-006）
- native 侧构建注入与加固：`docs/build-injection.md`、`SKILL.md`（工作流模式 B）
- NativeAOT：`https://learn.microsoft.com/dotnet/core/deploying/native-aot/`
- ReadyToRun：`https://learn.microsoft.com/dotnet/core/deploying/ready-to-run`
- 裁剪：`https://learn.microsoft.com/dotnet/core/deploying/trimming/trim-self-contained`
- IL2CPP：`https://docs.unity3d.com/Manual/IL2CPP.html`
- Java 侧同类菜单（对照）：`docs/java-anti-rea.md`
