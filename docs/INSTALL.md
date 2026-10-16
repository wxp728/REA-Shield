# 安装与升级指南（Install & Upgrade）

> 面向 **Linux x86_64**（v1.0 已实测平台）。其他平台见
> `docs/release/compatibility-matrix.md`。

## 0. 最快路径：容器（推荐给新用户）

不想手工拼装 LLVM18 + 插件？用仓库根目录的钉死镜像，开箱即用：

```sh
git clone https://gitee.com/wxp728/REA-Shield.git   # 或 GitHub 镜像：https://github.com/wxp728/REA-Shield
cd anti-rea
docker build -t anti-rea:1.0.0 .

# 直接跑 CLI（宿主目录挂进 /work）
docker run --rm -v "$PWD:/work" anti-rea:1.0.0 doctor
docker run --rm -v "$PWD:/work" anti-rea:1.0.0 scan /work/tests/samples -o /work/out

# 以 MCP stdio 服务器方式运行（供上层 Agent 调用）
docker run --rm -i anti-rea:1.0.0 mcp
```

镜像内固定 Python 3.11 + LLVM/clang 18 + 已构建的变换插件，`doctor` 在构建期
即自检通过。**Windows 用户建议用 Docker 或 WSL**（变换引擎是 Linux 共享库插件）。

## 1. 依赖

| 组件 | 版本 | 用途 | 是否必需 |
| :--- | :--- | :--- | :--- |
| Python | ≥ 3.11 | 编排核心 / 评估 | 必需 |
| Python 包 | `jsonschema`、`PyYAML`、`deap` | Schema 校验 / 配置 / 遗传进化 | 必需 |
| LLVM/clang | 18.x | 变换引擎宿主 + 编译 | 必需③ |
| CMake | ≥ 3.16 | 构建引擎 | 必需③ |
| binutils | `nm`/`objdump`/`strings` | 静态特征 / 独立验证 | 必需③ |
| Node.js / npm | ≥ 18 | npm 集成 | 可选 |
| rustc / cargo | ≥ 1.75 | Cargo 集成（C/FFI 源） | 可选 |
| JDK + Ghidra | 21 + 12.x | 可选独立验证（PyGhidra） | 可选 |

③ `scan`/`plan` 只需要 Python + Python 包；LLVM/CMake/binutils 是
`protect`/`verify` 的依赖。缺什么、怎么修，`anti-rea doctor` 会直接告诉你。

## 2. 安装（源码）

```sh
git clone https://gitee.com/wxp728/REA-Shield.git   # 或 git@gitee.com:wxp728/REA-Shield.git
# GitHub 镜像：git clone git@github.com:wxp728/REA-Shield.git
cd REA-Shield

# 依赖
pip install -r requirements.txt      # 等价：pip install jsonschema PyYAML deap

# 构建变换引擎（LLVM Pass 插件）——路径**自动探测**，不必写死
make build                           # 等价于 cmake -S engine -B engine/build \
                                     #          -DLLVM_DIR=$(llvm-config --cmakedir) && cmake --build engine/build -j

# 环境自检（缺件会给出明确指引）
anti-rea doctor                      # 或：python -m core.cli doctor
```

### LLVM 定位（不再写死路径）

工具链定位优先级：**环境变量 > PATH > 常见安装目录**。若 clang 不在 PATH：

```sh
export ANTI_REA_LLVM=/usr/lib/llvm-18          # LLVM 安装前缀（其下有 bin/）
# 或 make/ci 时：make build LLVM=/usr/lib/llvm-18
# 或单独指定可执行文件：
export ANTI_REA_CLANG=/usr/lib/llvm-18/bin/clang
```

`anti-rea doctor --llvm /usr/lib/llvm-18` 可临时指定前缀做自检。

### 常用环境变量

| 变量 | 作用 |
| :--- | :--- |
| `ANTI_REA_LLVM` / `ANTI_REA_LLVM_BIN` | LLVM 前缀 / bin 目录 |
| `ANTI_REA_CLANG` / `ANTI_REA_OPT` | 显式指定可执行文件 |
| `ANTI_REA_PLUGIN` / `ANTI_REA_VM_BC` | 插件 / VM 解释器路径 |
| `ANTI_REA_WHITELIST` / `ANTI_REA_STRATEGIES` / `ANTI_REA_SEED` | 变换白名单 / 策略 / 随机种子 |
| `ANTI_REA_RENAME_EXTERNAL` | 是否重命名**外部链接**函数（默认 `1`）。多编译单元工程改名会断链，`protect` 多源时自动置 `0`；单文件/整程序可保持 `1`。 |
| `ANTI_REA_CONST_ENCODE` | `string_encryption` 下是否启用**常数编码**（默认 `1`）：把可疑整型立即数（SM4 FK / SM3 IV 等）收进本函数常量池、用运行期解码取值。设 `0` 关闭。 |
| `ANTI_REA_STRIP` | 链接后是否 `strip --strip-unneeded`（默认 `0`）。由 `buildenv --strip` 置 `1`；隐藏产物的本地符号名。 |
| `ANTI_REA_VERSION_SCRIPT` | 链接期 `-Wl,--version-script` 的版本脚本路径（导出收敛）。由 `buildenv --exports` 写入 `scope.env`。 |
| `ANTI_REA_GHIDRA=1` + `GHIDRA_INSTALL_DIR` | 启用 Ghidra 独立验证 |
| `ANTI_REA_LLM_CMD` / `ANTI_REA_LLM_ENDPOINT` 等 | 接入真实 LLM 会话（攻击模拟） |
| `ANTI_REA_ROOT` | wheel 安装场景下指向含 `schemas/`、`policies/` 的目录 |

### LLM 会话判定（FR-E3，可选）

`attack_sim --allow-llm` 会经 `core.evaluate.llm` 开**独立会话**，对 baseline / protected 各做一次
同协议逆向，产出 `token_ratio` / `time_ratio` / `name_recovery_accuracy` / `function_judgement_accuracy`
等（判定口径见 `docs/design/ddd/decisions/OI-07-rea-success-criteria.md`）。两种出站方式二选一：

- **本地命令钩子** `ANTI_REA_LLM_CMD`：stdin 收提示词、stdout 回 `{"output":...,"tokens_used":...}`。
  本机 OpenCode 可直接用：`export ANTI_REA_LLM_CMD="$PWD/tools/opencode_llm_hook.sh"`。
- **OpenAI 兼容 HTTP**：`ANTI_REA_LLM_ENDPOINT`（`/chat/completions`）+ `ANTI_REA_LLM_MODEL`
  （+ 可选 `ANTI_REA_LLM_KEY`）。

未配置时自动降级 `static_only`（OI-07 §D5）。会话窗口经 `ANTI_REA_LLM_WINDOW` 指定（默认 128000）。

## 3. 快速上手（保护闭环）

```sh
anti-rea scan       <你的工程> -o build/run
anti-rea plan       build/run/asset_manifest.json -o build/run
anti-rea protect    build/run/protection_policy.yaml \
                    --root <你的工程> --source <敏感源文件> -o build/run
anti-rea verify     build/run
anti-rea attack_sim build/run --mode all
anti-rea report     build/run --format all
```

端到端可运行示例见 [`../examples/quickstart/`](../examples/quickstart/)：

```sh
bash examples/quickstart/run.sh
```

- `attack_sim` 无 LLM 时自动降级 `static_only`（以静态代理指标判定）。
- `report` 产出 `report.json/md/html`；`diff` 对比两次运行（FR-G3）。

## 4. 构建系统集成

```sh
# CMake：在 CMakeLists 内 include 并挂 POST_BUILD
include(integrations/cmake/AntiRea.cmake)

# npm：scripts.postbuild 调 integrations/npm/anti-rea-protect.js
# Python：setup.py 用 integrations/python/anti_rea_build_ext.py 作为 build_ext
# Cargo：build.rs 调 integrations/cargo
```

统一原则：**集成不内嵌引擎**，均调用驱动 `integrations/anti-rea`（`scan→plan→protect→verify`）；
验证失败时 `--abort-on-failure` 以非零退出中止构建（FR-D7）。

## 5. MCP Server（供 AI Agent 调用）

```sh
anti-rea-mcp            # 或 python -m core.mcp
```

stdio JSON-RPC 2.0，暴露 7 个工具：`anti_rea.scan/plan/protect/verify/attack_sim/report/evolve`。
面向常见客户端的**可直接粘贴配置**见 [`mcp-clients.md`](mcp-clients.md)。

## 6. 升级

```sh
git fetch --tags && git checkout v1.0.0
make build                             # 引擎需随版本重建
anti-rea --version                     # 确认版本
```

> 数据契约（`schemas/`）向后兼容；跨大版本升级请阅读 [`CHANGELOG.md`](../CHANGELOG.md)
> 的「破坏性变更」小节。

## 7. 卸载

源码安装：删除目录即可（Python 包为可编辑/就地使用，不污染环境）。
容器安装：`docker rmi anti-rea:1.0.0`。
