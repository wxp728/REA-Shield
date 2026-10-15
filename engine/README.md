# Anti-REA Transform Engine（LLVM Pass 插件）

对 LLVM IR 施加**代码工程反逆向加固**变换，供 `core` 保护流水线经 `clang -fpass-plugin` 调用。

设计文档：`docs/design/ddd/dd-03-llvm-transforms.md`、`docs/design/ddd/dd-04-virtualization.md`

## 提供的 pass

| pass | 说明 | 需求 |
| :--- | :--- | :--- |
| `cff-flatten` | 控制流平坦化（switch 派发 + seed 状态置换） | FR-C1 |
| `mba` | 非线性 MBA（加法/异或恒等式） | FR-C2 |
| `opaque-predicates` | 不透明谓词（恒真守卫，抗折叠） | FR-C3 |
| `vm-virtualize` | 代码虚拟化（整型叶子函数 → 自定义 ISA 字节码） | FR-C7/C8 |
| `anti-rea` | 按 `ANTI_REA_STRATEGIES` 组合施加 | FR-C1/C2/C3/C7 |

## 白名单（选择性变换，FR-C6）

经**环境变量**配置（`clang -fpass-plugin` 下 `cl::opt` 注册晚于命令行解析，故不用 `-mllvm`）：

| 变量 | 含义 | 缺省 |
| :--- | :--- | :--- |
| `ANTI_REA_WHITELIST` | IR 变换白名单（逗号分隔函数名）；`*` 表示全部；**空则不变换任何函数** | 空 |
| `ANTI_REA_VMP_WHITELIST` | 虚拟化白名单；命中者只做 VM（不走 IR 变换） | 空 |
| `ANTI_REA_STRATEGIES` | `cff,mba,opaque,virtualize` 子集 | `cff,mba,opaque` |
| `ANTI_REA_SEED` | 随机种子（可复现，NFR-04/08） | `0` |
| `ANTI_REA_MAX_BLOCKS` | CFF 最大基本块数，超过则跳过 | `256` |

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

## 构建

```sh
LLVM=/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04
cmake -S engine -B engine/build -DLLVM_DIR=$LLVM/lib/cmake/llvm -DCMAKE_BUILD_TYPE=Release
cmake --build engine/build -j
# 产物：engine/build/anti_rea_passes.so 与 engine/build/vm_interp.bc
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
