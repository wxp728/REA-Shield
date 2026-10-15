# Anti-REA Transform Engine（LLVM Pass 插件）

对 LLVM IR 施加**代码工程反逆向加固**变换，供 `core` 保护流水线经 `clang -fpass-plugin` 调用。

设计文档：`docs/design/ddd/dd-03-llvm-transforms.md`

## 提供的 pass

| pass | 说明 | 需求 |
| :--- | :--- | :--- |
| `cff-flatten` | 控制流平坦化（switch 派发 + seed 状态置换） | FR-C1 |
| `mba` | 非线性 MBA（加法/异或恒等式） | FR-C2 |
| `opaque-predicates` | 不透明谓词（恒真守卫，抗折叠） | FR-C3 |
| `anti-rea` | 按 `ANTI_REA_STRATEGIES` 组合施加 | FR-C1/C2/C3 |

## 白名单（选择性变换，FR-C6）

经**环境变量**配置（`clang -fpass-plugin` 下 `cl::opt` 注册晚于命令行解析，故不用 `-mllvm`）：

| 变量 | 含义 | 缺省 |
| :--- | :--- | :--- |
| `ANTI_REA_WHITELIST` | 逗号分隔的函数名；`*` 表示全部；**空则不变换任何函数** | 空 |
| `ANTI_REA_STRATEGIES` | `cff,mba,opaque` 子集 | `cff,mba,opaque` |
| `ANTI_REA_SEED` | 随机种子（可复现，NFR-04/08） | `0` |
| `ANTI_REA_MAX_BLOCKS` | CFF 最大基本块数，超过则跳过 | `256` |

> 白名单外的代码**零变换**（字节级不变）。

## 构建

```sh
LLVM=/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04
cmake -S engine -B engine/build -DLLVM_DIR=$LLVM/lib/cmake/llvm -DCMAKE_BUILD_TYPE=Release
cmake --build engine/build -j
# 产物：engine/build/anti_rea_passes.so
```

## 用法

```sh
# 经 clang 插件路径（推荐，变换在优化流水线末端执行）
ANTI_REA_WHITELIST=secret_mix ANTI_REA_STRATEGIES=cff,mba,opaque ANTI_REA_SEED=42 \
  clang -O1 -fpass-plugin=$PWD/engine/build/anti_rea_passes.so hello.c -o hello.prot

# 经 opt 路径（便于检查 IR）
ANTI_REA_WHITELIST='*' opt -load-pass-plugin=engine/build/anti_rea_passes.so \
  -passes='reg2mem,anti-rea' hello.ll -S -o hello.prot.ll
```

## 关键约束（PoC-1 结论）

- CFF 前必须 `reg2mem`（消除跨块 SSA 支配依赖）；插件在 `OptimizerLast` 扩展点自动挂 `reg2mem`；
- 变换须在优化流水线末端执行，否则被 `SimplifyCFG` 还原；
- 含 `invoke/callbr/indirectbr/switch/EH` 端子的函数在 v1.0 **跳过**（记录且不中止）。
