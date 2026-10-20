# Rust 纯代码的 IR 级加固：可行性 spike 报告

> **状态**：实验报告（**非**需求基线；不修改 `SRS.md`）。
> **目的**：验证“把本引擎的 LLVM Pass 直接用在 rustc 产出的 IR 上”是否可行、代价多大，
> 为“Rust 是否需要引擎级支持”提供证据。**结论不作为功能承诺**。
> **定位**：现有支持矩阵不变——Rust 仅 **C/FFI 源** 可用；本文评估的是“Rust 纯代码”。

## 0. 结论（TL;DR）

1. **IR 版本必须与引擎的 LLVM 主版本一致**。本机 stable `rustc 1.99.0` 使用 **LLVM 23.1.1**，
   而引擎为 **LLVM 18.1.8**：文本 IR 与 bitcode **都无法被读取**（见 §2 表 1）。
2. **固定到 LLVM 18 的 rustc（1.78–1.81）可以跑通**：CFF / MBA / 不透明谓词正常施加，
   功能等价，符号重命名有效（表 2）。但 **1.82 起升级到 LLVM 19**，窗口很窄。
3. **“能跑通”不等于“可交付”**：cargo 没有“替换对象 / 注入插件”的稳定钩子；要接管链接
   （std / panic / allocator）或改用 `no_std` 静态库，工程改造与维护成本高（§3）。
4. **字符串加密对 Rust 字面量暂不生效**：rustc 把字面量发成 `{ [N x i8] }` 结构包装的全局，
   现有 pass 只处理 `ConstantDataArray` 初始化器；C 代码同样场景可正常清除（表 2）。
   修复属于**引擎改动**（ADR-006 范围外），须用户确认后才能做。
5. **建议**：继续把 **C/FFI 边界**作为 Rust 项目的唯一“支持”路径；若需要更强的 Rust 侧保护，
   下一步做**菜单级** Rust 选项（类似 Java/.NET），而不是引擎级 IR 支持。

## 1. 实验设置

| 项 | 值 |
| :--- | :--- |
| 引擎 | 本仓库 `engine/build/anti_rea_passes.so`（LLVM 18.1.8） |
| 工具链 | clang / opt 18.1.8（`<toolchain>/bin`） |
| Rust（stable） | `1.99.0` → **LLVM 23.1.1**（默认） |
| Rust（对照） | `1.78.0` → LLVM 18.1.2；`1.81.0` → LLVM 18.1.7；`1.82.0` → LLVM 19.1.1 |
| 样本 | `cdylib`：`rust_license_check`（字面量比较 + 分支 + 常数）、`rust_mix`（热循环）、`rust_banner`（返回字面量） |
| 方法 | `rustc --emit=llvm-ir` / `--emit=llvm-bc` → `opt` / `clang -fpass-plugin` → 运行、符号、`strings`、尺寸、耗时 |

> 版本边界说明：Rust 的 LLVM 版本随 release 升级，**不能用“最新 stable”假设兼容**。
> 本报告只记录实测到的 1.78 / 1.81 / 1.82 / 1.99 四个点。

## 2. 结果

### 表 1 · 版本兼容性（同一份 Rust 源码）

| rustc | LLVM | 文本 IR → `opt`/`clang` 18 | bitcode → `opt` 18 | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| 1.99.0 | 23.1.1 | ❌ 解析失败：`expected type`（`ptr nofree` 等新语法） | ❌ `Invalid attribute group entry (Producer: LLVM23.1.1 ... Reader: LLVM 18.1.8)` | 不可用 |
| 1.82.0 | 19.1.1 | — | ❌ 同上（Producer: LLVM19.1.1） | 不可用 |
| 1.81.0 | 18.1.7 | ✅ 解析/编译成功 | ✅ | **可用** |
| 1.78.0 | 18.1.2 | ✅ 解析/编译成功 | ✅ | **可用** |

另测两条“绕过版本”的路径，均不可行：

- `rustc -C llvm-args=-load-pass-plugin=<plugin>`：rustc 的 LLVM 命令行**未注册**该选项，
  报 `Unknown command line argument`。插件必须在 `opt`/`clang` 的 PassPlugin 机制下加载。
- `rustc -Z llvm-plugins=<plugin>`：**仅 nightly** 接受（stable 直接报错）；且插件仍需按 rustc
  自带 LLVM 的版本重新构建（LLVM C++ API 无稳定 ABI）。

### 表 2 · 变换效果（rustc 1.81.0，LLVM 18.1.7）

策略：`ANTI_REA_WHITELIST=rust_license_check,rust_mix`、`ANTI_REA_STRATEGIES=cff,mba,opaque`、
`ANTI_REA_SEED=7`；基线为同一份 IR 不带插件编译。

| 指标 | 基线 | 加固后 | 观察 |
| :--- | ---: | ---: | :--- |
| `.text`（对象） | 642 B | 1612 B | 2.5×（CFF/MBA 展开） |
| 热循环 2000 万次调用 | 126.8 ms | 597.8 ms | **4.7×**（P0 级强度作用于热路径的代价） |
| 功能等价 | `lic=0 bad=1 banner=REA-SHIELD-RUST-SPIKE acc=09bb02b9` | 完全一致 | 变换未改变语义 |
| 符号重命名（`rename`） | `T rust_license_check` / `T rust_mix` | `T sub_0d03c45a...` / `T sub_ba1fe...` | 有效 |
| 字符串加密（Rust 字面量） | `strings` 命中 1 | 仍命中 1 | **未生效**（见下） |
| 字符串加密（同场景 C 代码） | 命中 1 | 命中 0 | 生效（对照） |

**字符串为何漏掉**：rustc 把 `b"REA-SHIELD-RUST-SPIKE"` 发成
`@alloc_... = private unnamed_addr constant <{ [21 x i8] }> <{ [21 x i8] c"..." }>`，
即**结构包装**的常量；`applyStringEncrypt` 只对 `GlobalVariable` 初始化器直接做
`dyn_cast<ConstantDataArray>`，因此跳过。C 侧的字面量是裸 `[N x i8]`，所以正常命中。

> 这不是“配置问题”，而是 pass 的匹配范围问题。修复它需要动引擎（新语言支持属 SRS 范围外，
> 须用户确认），且还要处理 Rust 的 slice 描述符（`{ ptr, i64 }`）引用同一全局的情况。

### 表 3 · 集成路径评估

| 路径 | 做法 | 可行性 | 成本 / 风险 | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| **A. 固定 rustc** | 钉死 1.78–1.81（LLVM 18），`--emit=llvm-ir` → clang+插件 | 实验可跑通 | 1.82 起即失效；1.81 已停止安全更新（2024-09）；cargo 无对象替换钩子，需接管链接或 `no_std` | 不建议作为产品能力 |
| **B. 按 rustc 重编插件 + nightly** | 用 rustc 自带 LLVM（23）重建插件，`-Z llvm-plugins` | 理论可行 | 每个 Rust 版本重编；nightly-only；LLVM C++ ABI 不稳定；CI 矩阵爆炸 | 不投入 |
| **C. C/FFI 边界（现状）** | 敏感核心写 C（或 `extern "C"` + 独立 C TU），按模式 B 注入；Rust 只做调用 | **已验证可用**（既有 libpq 等实战结论） | 需要模块边界设计；跨语言调试/封送成本 | **推荐，维持现状** |
| **D. 源码级菜单** | 类似 Java/.NET：服务端化、strip、字符串/控制流（宏或手写）、LTO/`panic=abort`、native 下沉、完整性、密钥、水印 | 文档级可行 | 1–2 天文档 + 测试；不改变引擎 | 若要覆盖 Rust，**优先做这个** |

## 3. 为什么“跑通”不等于“可交付”

1. **没有构建钩子**：`cargo` / `rustc` 不提供“编译后、链接前替换对象”的稳定接口。可选做法
   （接管最终链接、替换 rlib 内对象、`no_std` 静态库）都会侵入工程，且随工具链升级易碎。
2. **版本窗口极窄**：LLVM 主版本一旦变化，IR 完全不兼容；Rust 每 6 周一个 release，
   固定旧版本意味着**放弃安全修复**。对交付产品不可接受。
3. **插件 ABI 绑定 LLVM**：引擎用 C++ LLVM API，必须与 rustc 的 LLVM **同版本、同构建选项**；
   rustc 静态链接 LLVM，运行期注入不可行（`-C llvm-args` 不注册插件加载项）。
4. **锚点移除不完整**：即使跑通，Rust 字面量/元数据形态与 C 不同，需要逐项适配
   （字符串、符号、调试信息）；适配成本持续存在。
5. **SRS 边界**：引擎级新增语言支持属于 SRS 范围外；本 spike 不改变任何需求与承诺。

## 4. 建议

1. **保持支持矩阵不变**：Rust 只声明 **C/FFI 源**；README / `SKILL.md` 已如此表述，无需改动。
2. **把“敏感核心放 C/FFI”写成 Rust 项目的首选路径**（模式 B 构建注入），并在 P1 方案里
   明确边界设计（批量化调用、导出收敛、跨语言验证）。
3. 如果用户希望 Rust 侧也有“菜单”：新增 **R0–R8**（服务端化 / strip+符号 / 字符串与控制流 /
   LTO 与 `panic=abort` / native 下沉 / 完整性 / 密钥 / 水印），**纯文档 + 测试**，
   不改引擎；这是覆盖 Rust 的最低成本方式。
4. **重评条件**（满足任一再看 IR 路径）：上游出现稳定的“加载 LLVM Pass”稳定接口；
   或 rustc 提供官方的对象/IR 注入钩子；或团队接受固定旧 rustc 并自担安全更新。

## 5. 复现步骤（匿名化）

```sh
# 1) 版本对齐检查（必须与引擎 LLVM 主版本一致）
rustc -vV | grep 'LLVM version'

# 2) 产出 IR（示例：1.81.0，LLVM 18）
rustc +1.81.0 --crate-type cdylib -C opt-level=2 --emit=llvm-ir -o out/libspike.ll src/lib.rs

# 3) 经引擎插件编译（等价于模式 B 的单 TU 注入）
ANTI_REA_WHITELIST='rust_license_check,rust_mix' \
ANTI_REA_STRATEGIES='cff,mba,opaque' ANTI_REA_SEED=7 \
  <toolchain>/bin/clang -O2 -fpass-plugin=<plugin> -c out/libspike.ll -o out/spike.o

# 4) 对照与验证：size / nm / strings / 运行同一驱动，比较输出与耗时
```

> 注：步骤 3 只适用于“已经拿到 `.ll` 且版本匹配”的场景；实际 cargo 工程仍需解决 §3.1 的
> 链接/对象替换问题——这也是本报告不建议把它做成产品能力的原因。

## 6. 参考

- LLVM Bitcode 兼容性（不同版本不保证可读）：`https://llvm.org/docs/BitCodeFormat.html`
- `rustc` 的 LLVM 版本：`rustc -vV`（每个 release 可能升级）
- 语言/变换范围决策：`docs/design/ADR.md`（ADR-006）
- 构建注入：`docs/build-injection.md`
- Java / .NET 的菜单级先例：`docs/java-anti-rea.md`、`docs/dotnet-anti-rea.md`
