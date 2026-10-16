# REA-Shield Transform Engine（LLVM Pass 插件）

对 LLVM IR 施加**代码工程反逆向加固**变换，供 `core` 保护流水线经 `clang -fpass-plugin` 调用。

设计文档：`docs/design/ddd/dd-03-llvm-transforms.md`、`docs/design/ddd/dd-04-virtualization.md`

## 提供的 pass

| pass | 说明 | 需求 |
| :--- | :--- | :--- |
| `cff-flatten` | 控制流平坦化（switch 派发 + seed 状态置换） | FR-C1 |
| `mba` | 非线性 MBA（加法/异或恒等式） | FR-C2 |
| `opaque-predicates` | 不透明谓词（恒真守卫，抗折叠） | FR-C3 |
| `vm-virtualize` | 代码虚拟化（整型叶子函数 → 自定义 ISA 字节码） | FR-C7/C8 |
| `func-split` | 函数边界扰动（CodeExtractor 外提基本块为新函数） | FR-C4 |
| `data-flow-noise` | 数据流噪声（`(v+k)-k` 无副作用冗余运算） | FR-C5 |
| `external-transforms` | 外部 SPI 插件宿主（加载 `ANTI_REA_EXTRA_PLUGINS`） | FR-C11 |
| `string-encrypt` | 字符串加密（异或编码 + 运行期解码桩；模块级） | dd-03 §7 |
| `ident-rename` | 标识符重命名（白名单函数改不透明符号；模块级） | dd-03 §7 |
| `anti-rea` | 按 `ANTI_REA_STRATEGIES` 组合施加 | FR-C1…C5/C7 |

## 插件 SPI（FR-C11 / ADR-005）

第三方变换以共享库提供 `anti_rea_spi_version()` + `anti_rea_register_plugin()`（契约见
`engine/spi/transform_plugin.h`）；宿主校验 `SPI_VERSION`，不匹配即拒载（`E_PLUGIN_INCOMPATIBLE`）。
示例见 `plugins/example-transform/`（构建为 `engine/build/libanti_rea_example_plugin.so`）。

## 白名单（选择性变换，FR-C6）

经**环境变量**配置（`clang -fpass-plugin` 下 `cl::opt` 注册晚于命令行解析，故不用 `-mllvm`）：

| 变量 | 含义 | 缺省 |
| :--- | :--- | :--- |
| `ANTI_REA_WHITELIST` | IR 变换白名单（逗号分隔函数名）；`*` 表示全部；**空则不变换任何函数** | 空 |
| `ANTI_REA_VMP_WHITELIST` | 虚拟化白名单；命中者只做 VM（不走 IR 变换） | 空 |
| `ANTI_REA_STRATEGIES` | `cff,mba,opaque,virtualize,func_split,noise,string_encrypt,rename` 子集 | `cff,mba,opaque` |
| `ANTI_REA_SEED` | 随机种子（可复现，NFR-04/08） | `0` |
| `ANTI_REA_MAX_BLOCKS` | CFF 最大基本块数，超过则跳过 | `256` |
| `ANTI_REA_NOISE_RATIO` | 数据流噪声密度（0…1） | `1.0` |
| `ANTI_REA_EXTRA_PLUGINS` | 外部 SPI 插件 `.so` 路径（逗号分隔） | 空 |

> 白名单外的代码**零变换**（字节级不变）。

## 代码虚拟化（FR-C7/C8）

`vm-virtualize` 将**整型叶子函数** lower 为自定义栈/寄存器机器字节码，并把函数体替换为对
解释器 `anti_rea_vm_run` 的调用。解释器以 C 编写，编译为 LLVM bitcode（`engine/build/vm_interp.bc`），
与目标一起链接。

- **ISA**：256 个 64 位寄存器 + 变长字节码；opcode 映射按 `seed` 每实例随机化
  （共享定义：`engine/vm/vm_isa.h`）。
- **v0.1 边界**：仅整型（i1…i64）；支持算术/位运算/移位/比较/`select`/分支/`switch`/返回；
  暂不支持浮点、聚合、指针运算、全局内存与函数调用——不支持者**自动跳过并回退 IR 变换**，不中止构建。
- **不变量**：i32 值在寄存器中按 32 位符号扩展；i32 无符号比较暂不支持（回退）。

## 锚点移除：字符串加密 + 标识符重命名（dd-03 §7）

针对 AI 逆向工具（REA 类）依赖的"明文串 + 符号名"锚点（见 `docs/analysis/rea-threat-analysis.md`）：

- **`string_encrypt`**（模块级，流水线最先执行）：对**仅被白名单函数使用**的本转换义字节串常量做
  逐字节异或编码（密钥流由 `seed` + 全局名派生），并在每个使用函数入口插入运行期解码桩
  （`alloca` + 逐字节 `load/xor/store`），使用处改为指向解码缓冲区。
- **`rename`**（模块级，流水线最后执行）：把白名单内的定义函数改名为不透明符号 `sub_<hash>`（保留 `main`）。

> **v0.1 限制**：异或密钥流以编译期常量形式随解码指令出现，且不剥离调试信息；目标是**移除
> `strings`/符号级线索、抬高 REA 的静态闭合成本**，而非密码学强度。更强方案（查表/多态解码、
> 调试信息剥离）见 `docs/design/ddd/dd-03-llvm-transforms.md §7/§13`，列为后续增强。

## 构建

```sh
LLVM=/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04
cmake -S engine -B engine/build -DLLVM_DIR=$LLVM/lib/cmake/llvm -DCMAKE_BUILD_TYPE=Release
cmake --build engine/build -j
# 产物：engine/build/anti_rea_passes.so、engine/build/vm_interp.bc、
#       engine/build/libanti_rea_example_plugin.so（SPI 示例）
```

## 用法

```sh
# 经 clang 插件路径（推荐，变换在优化流水线末端执行）
ANTI_REA_WHITELIST=secret_mix ANTI_REA_STRATEGIES=cff,mba,opaque ANTI_REA_SEED=42 \
  clang -O1 -fpass-plugin=$PWD/engine/build/anti_rea_passes.so hello.c -o hello.prot

# 代码虚拟化（需链接解释器 bitcode）
ANTI_REA_VMP_WHITELIST=secret_schedule ANTI_REA_STRATEGIES=virtualize ANTI_REA_SEED=42 \
  clang -O1 -fpass-plugin=$PWD/engine/build/anti_rea_passes.so \
        p0_secret.c engine/build/vm_interp.bc -o p0.prot

# 经 opt 路径（便于检查 IR）
ANTI_REA_SEED=42 opt -load-pass-plugin=engine/build/anti_rea_passes.so \
  -passes='reg2mem,anti-rea' hello.ll -S -o hello.prot.ll
```

## 关键约束（PoC-1 结论）

- CFF/VM 前必须 `reg2mem`（消除跨块 SSA 支配依赖）；插件在 `OptimizerLast` 扩展点自动挂 `reg2mem`；
- 变换须在优化流水线末端执行，否则被 `SimplifyCFG` 还原；
- 含 `invoke/callbr/indirectbr/switch/EH` 端子的函数在 CFF 中 **跳过**（记录且不中止）；VM 对不支持函数同样回退。
- 在 `-O1` 下 `*2` 常被优化为 `shl`、`if` 常被优化为 `select`——VM 已支持 `shl/shr/ashr` 与无分支 `select`。
