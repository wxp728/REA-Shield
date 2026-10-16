# 故障排查（Troubleshooting）

先跑一次自检，90% 的问题它会直接指出：

```sh
anti-rea doctor            # 缺什么、怎么修，逐条列出
anti-rea doctor --json     # 机器可读（CI/脚本用）
```

## 按错误码

| 错误码 | 含义 | 处理 |
| :--- | :--- | :--- |
| `E_INVALID_INPUT` | 入参非法（路径不存在、Schema 字段缺失） | 按提示修正入参，检查 `-o` 目录可写 |
| `E_SCHEMA_VIOLATION` | 数据不符合 `schemas/` | 指出字段；不要手改产物 JSON，用对应子命令重新生成 |
| `E_REFUSED` | 拒绝执行（所有权不明 / 疑似恶意） | 确认代码归你所有；确需覆盖加 `--allow-unknown-owner`（慎用） |
| `E_UNSUPPORTED_PLATFORM` | 平台/语言不支持 | 见 `docs/release/compatibility-matrix.md`；Windows 用 Docker/WSL |
| `E_BUDGET_EXCEEDED` | 无法在性能预算内达成目标强度 | 放宽 `plan --max-overhead`，或降低策略强度 |
| `E_BUILD_FAILED` | 目标工程构建失败 / 未找到 clang | 见下方「找不到 clang」 |
| `E_TRANSFORM_FAILED` | 变换失败 / 未找到插件 | 见下方「找不到插件」 |
| `E_VERIFY_FAILED` | 功能或性能验证失败 | 见下方「verify 失败」 |
| `E_PLUGIN_INCOMPATIBLE` | 插件版本/参数不兼容 | 插件与宿主 LLVM 版本需匹配，重建插件 |
| `E_LLM_UNAVAILABLE` | LLM 会话不可用 | 正常：`attack_sim` 会降级 `static_only`；或配置 LLM 环境变量 |

## 常见现象与修复

### 1. `E_BUILD_FAILED: 未找到 clang`

`protect` 需要 LLVM/clang ≥ 18。

```sh
# 查看 doctor 探测结果
anti-rea doctor

# 指定 LLVM 前缀（推荐）
export ANTI_REA_LLVM=/usr/lib/llvm-18
# 或单独指定可执行文件
export ANTI_REA_CLANG=/usr/lib/llvm-18/bin/clang
# 或把 LLVM bin 加入 PATH
export PATH=/usr/lib/llvm-18/bin:$PATH
```

> 路径**不再写死**：按「环境变量 > PATH > 常见目录」自动探测。

### 2. `E_TRANSFORM_FAILED: 未找到变换插件`

引擎插件尚未构建：

```sh
make build
# 等价：cmake -S engine -B engine/build -DLLVM_DIR=$(llvm-config --cmakedir) && cmake --build engine/build -j
```

自定义位置可用 `ANTI_REA_PLUGIN=/path/to/anti_rea_passes.so` 覆盖。

### 3. Windows 上 `protect` 失败

v1.0 的变换引擎是 **Linux 共享库插件**（`.so`），Windows 原生无法加载。
请用 **Docker**（`docker run ... anti-rea:1.0.0 ...`）或 **WSL**。
`scan`/`plan` 在 Windows 上可用的前提是 Python 依赖齐全。

### 4. `ModuleNotFoundError: jsonschema` / `yaml` / `deap`

依赖未安装：

```sh
pip install -r requirements.txt
```

### 5. `verify` 判定失败

```sh
cat build/run/verification_report.json      # 看 functional_pass / overhead
```

- 功能不一致：多为变换与特定语言构造交互问题；减小策略集合
  （`ANTI_REA_STRATEGIES`）或换 seed 复现定位。
- 开销超预算：见 `E_BUDGET_EXCEEDED`。

### 6. `attack_sim` 报 `E_LLM_UNAVAILABLE`

正常。无真实 LLM 会话时会自动降级到 `static_only`（静态代理指标）。
如需真实评估，配置 `ANTI_REA_LLM_CMD` 或
`ANTI_REA_LLM_ENDPOINT/MODEL/KEY`，并加 `--allow-llm`。

### 7. 平台/语言不符预期

`scan` 的 `project.target_platform` 现按**主机探测**（可被
`options.target_platform` 覆盖），不再写死。语言支持范围见 FAQ——
SRS 的「识别语言」≠「可变换语言」。

### 8. `libtinfo.so.5: no version information available`

某些工具链的无害告警，可忽略或
`... 2>&1 | grep -v libtinfo`。

### 9. 多编译单元工程：`undefined reference` / 变体编译失败

工程由多个 `.c/.cpp` 组成时：

- **`protect` 报 `undefined reference to <导出函数>`**：`rename` 改掉了别处仍按原名引用的
  外部链接符号。`protect` 检测到多源会自动降级（`ANTI_REA_RENAME_EXTERNAL=0`，只改
  static）；若你手工传了 `ANTI_REA_RENAME_EXTERNAL=1`，请去掉。
- **`verify` 报编译对抗变体失败**：变体是 `sources[0]` 的副本，含相对 `#include "../..."`
  的源文件在副本挪位后会断链；生成器已自动把这类相对 include 绝对化。若仍失败，检查
  include 是否指向**源文件目录之外且不存在**的路径（这种无法自动定位，需改用 `-I` 或
  绝对路径）。

## CI / 脚本

```sh
bash ci/ci.sh                         # 完整门禁（含 doctor/构建/测试/S4/S5/打包自检）
PY=/path/to/python3.11 bash ci/ci.sh  # 指定解释器
LLVM=/usr/lib/llvm-18 bash ci/ci.sh   # 指定 LLVM
```

仍未解决？提 Issue（`.github/ISSUE_TEMPLATE/bug_report.md`），附上
`anti-rea doctor --json` 的输出与复现命令。
