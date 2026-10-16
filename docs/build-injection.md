# 构建注入（Build Injection）——保护真实工程产物

> 适用：目标不是「单文件可执行程序」，而是由构建系统（autoconf / Makefile / PGXS /
> CMake …）产出的**共享库 `.so`、静态库或大型可执行文件**，且需要**逐编译单元**施加
> 变换。对应 FR-D2…D7；引擎侧见 `docs/design/ddd/dd-build-integration.md`。

## 为什么需要它

`anti-rea protect` 与各语言集成（`integrations/`）都是**把你的源文件编译成一份独立
可执行文件**再验证。这对「自包含小程序」够用，但**产不出真实工程的多文件产物**（例如
PostgreSQL 扩展 `.so`，需要 PG 头文件、OpenSSL/GMSSL 等外部链接）。

真实工程的正确做法是：**不替换构建系统**，而是把「clang + 变换插件」**注入**到原有构建
里——编译每个 `.c` 时挂插件，链接步骤保持原样。这样产出的就是真正的 `.so`/可执行文件。

## 三步用法

```sh
# 0) 先扫描 + 生成策略（可收窄范围，见下）
anti-rea scan  /path/to/project -o out                 # 可加 --include/--exclude
anti-rea plan  out/asset_manifest.json -o out          # 可加 --only-path/--only-func

# 1) 生成构建注入环境（含白名单/策略/种子/插件路径）
anti-rea buildenv out/protection_policy.yaml \
    --root /path/to/project --protect-all -o out/scope.env

# 2) source 环境，并把 CC 指向包装器，然后照常构建
source out/scope.env
export CC=$PWD/integrations/cc-wrapper/anti-rea-cc
./configure ...            # 例如 PostgreSQL: ./configure --prefix=... --with-openssl ...
make -j"$(nproc)"
```

包装器 `integrations/cc-wrapper/anti-rea-cc` 的行为：

- 编译步骤（含 `-c` 或 `-S`）：转发给真实编译器并追加 `-fpass-plugin=$ANTI_REA_PLUGIN`；
- 预处理（`-E`）与**链接步骤**：原样透传；
- `ANTI_REA_REAL_CC` 指定真实编译器（默认 `clang`）；`ANTI_REA_DISABLE=1` 关闭注入
  （用于对插件敏感的 configure 探测）。

## 范围收窄（只保护自有代码）

```sh
# 只扫描/保护某个子树
anti-rea scan /path/to/project --include src/common/crypto_algorithm -o out
# 只保护路径/函数匹配的资产（免手改 YAML）
anti-rea plan out/asset_manifest.json --only-path 'src/common/crypto_*/*' \
    --only-func '^crypto_' -o out
# 整文件保护：白名单取 scope 内**文件全部函数**（含内部辅助函数）
anti-rea buildenv out/protection_policy.yaml --root /path/to/project --protect-all -o out/scope.env
```

> **整文件保护（`--protect-all`）** 建议与「已收窄的 scope」搭配：先把范围限定到自有
> 敏感模块，再整文件保护，避免把整个工程（含第三方/上游代码）都纳入变换。

## 导出收敛（隐藏内部符号名）

真实工程多 TU 构建下**外部符号名会保留**（改名会与他 TU 断链），看符号表即知「这是什么库」。
两步收敛：

```sh
# 1) 由公共头文件生成链接版本脚本（只导出公共 API，其余本地化）
anti-rea exportmap src/include/yourmodule -o out/exports.map

# 2) buildenv 带上版本脚本 + strip（链接后去本地符号）
anti-rea buildenv out/protection_policy.yaml --root . --protect-all \
    --exports out/exports.map --strip -o out/scope.env
source out/scope.env && export CC=$PWD/integrations/cc-wrapper/anti-rea-cc
make -j"$(nproc)"
```

- 版本脚本让**非 API 符号**（含引擎注入的 `anti_rea_vm_run`、函数拆分产物）从 `.dynsym`
  消失——不再提示「有虚拟化保护」；
- `ANTI_REA_STRIP=1` 在链接后 `strip --strip-unneeded`，去掉 `.symtab`（本地符号）；
- 效果（真实加密库实测）：`.symtab` 本地符号 201 → **0**，算法相关字符串 132 → **64**，
  `anti_rea_vm_run` 不再导出；**公共 API 名仍可见**（这是库的对外契约，无法也不应隐藏）。

> 前提：该 `.so` 的内部符号不被**其他** `.so`/可执行文件按名引用；否则它们不能被本地化。
> 若模块被拆成多个共享库互相引用，请把跨库接口一并列入 `exportmap`。

## 常数编码（隐藏算法立即数）

算法指纹常写成 `#define` 立即数而非数据表（如 SM4 FK `0xa3b1bac6`、SM3 IV `0x7380166f`），
数据表加密覆盖不到。`string_encryption` 策略下新增**常数编码**：把白名单函数里**可疑的整型立即数**
逐函数收进一个本地常量池，使用点改为从「运行期解码的缓冲」取值，池本身再由整型常数表加密。

- 开关：`ANTI_REA_CONST_ENCODE`（默认 `1`，设 `0` 关闭）；
- 纳入范围：白名单函数里**所有指令**的整型常量操作数（`add/sub/xor/…` 的立即数、`store`/`ret` 的常量等）；
  仅取位宽 32–64 bit 且值 ≥ `0x10000`，跳过 `2^k-1` 掩码；跳过「操作数必须为常量」的指令
  （`phi`/`gep`/`switch`/`extractvalue`/`insertvalue`/`alloca`/`call` 等）；
- 逐函数建池：解码桩只为**本函数实际用到**的常量付出代价，避免跨函数放大体积；单池上限 256 元素；
- 效果（真实加密库实测）：SM4 FK、SM3 IV 的明文出现次数 **1 → 0**；语义逐字节不变。

> 注意：常量索引的 `getelementptr` 会被 LLVM 折叠成 `ConstantExpr`。改写时必须**按相同索引在解码
> 缓冲上重建 `GEP`**，不能整体替换为缓冲指针（否则丢索引、恒读元素 0）。回归见
> `tests/test_const_encode.py`。

## 注意事项

- **外部符号名默认保留**：真实构建多编译单元，改名外部链接函数会导致他 TU 按原名引用
  而断链，故 `buildenv` 默认输出 `ANTI_REA_RENAME_EXTERNAL=0`。若产物仍需隐藏导出名，
  在**链接后**用 `strip`（可执行）或版本脚本 / `-fvisibility=hidden`（`.so`）收敛导出集。
- **只保护自有代码**：开源/第三方代码默认跳过（CQ-01）。用 `--include`/`--only-*` 收窄。
- **性能预算**：`code_virtualization` 在热点路径开销显著（解释器逐次调用）；用
  `--only-func` / `--only-path` 把虚拟化限制在高价值小函数集合。
- **可复现**：`ANTI_REA_SEED` 由 `buildenv` 写入 `scope.env`；同种子 + 同源码 → 同产物
  （NFR-04/08）。
- **验证**：`anti-rea verify` 的差分验证面向独立可执行文件；对长驻服务/`.so` 请改用工程
  自带的回归测试（如 PostgreSQL 的 `make check`）。
- **点名构建目标**：有些工程（如 PostgreSQL 的 `src/common`）在子目录里直接 `make` 是空动作
  （默认目标由 `Makefile.global` 的 `all:` 处理）。此时须显式点名目标，例如
  `make -C src/common all CC=$PWD/integrations/cc-wrapper/anti-rea-cc`，否则不会重编、也看不出注入。
- **优化档会影响常量形态**：`-O2` 下 clang 会把连续常量存储 SLP 向量化成 `<N x i32>` 常量；
  常数编码（`ANTI_REA_CONST_ENCODE`）已覆盖整型常量与常量向量两种操作数，但**不要**只在
  `-O1` 上验指纹——高优化档能看到额外的常量形态。
